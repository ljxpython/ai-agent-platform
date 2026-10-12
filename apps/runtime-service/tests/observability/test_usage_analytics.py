import asyncio
import gc
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from unittest.mock import patch

import psycopg
import pytest
from pydantic import ValidationError

from runtime_service.observability.usage import TOKEN_FIELDS
from runtime_service.observability.usage_analytics import (
    AggregateQuery,
    RunsQuery,
    dashboard,
    project_metrics,
    query_aggregate,
)

PROJECT = "10000000-0000-0000-0000-000000000001"
MODEL = "20000000-0000-0000-0000-000000000001"


def query_body(**updates):
    return {
        "version": 1,
        "actor_id": "actor",
        "tenant_id": "analytics-test",
        "project_ids": [PROJECT],
        "request_id": "query-1",
        "from": "2026-10-09T16:00:00Z",
        "to": "2026-10-11T16:00:00Z",
        **updates,
    }


def query(**updates):
    return AggregateQuery.model_validate_json(json.dumps(query_body(**updates)))


def facts(**updates):
    row = {
        "observed_call_count": 2,
        "reported_call_count": 2,
        "missing_usage_call_count": 0,
        "incomplete_call_count": 0,
        "recorded_run_count": 1,
        "open_run_count": 0,
        "degraded": False,
        "priced_call_count": 1,
        "known_cost_usd": "0.001000000000",
        "pricing_versions": [],
    }
    tokens = {
        **dict.fromkeys(TOKEN_FIELDS, 0),
        "input_tokens": 20,
        "output_tokens": 10,
        "total_tokens": 30,
        "cache_read_tokens": 5,
        "reasoning_tokens": 2,
    }
    return {**row, **tokens, **{k + "_count": 2 for k in TOKEN_FIELDS}, **updates}


@pytest.mark.parametrize(
    "changes",
    [
        {"version": True},
        {"project_ids": []},
        {"project_ids": [PROJECT, PROJECT]},
        {"to": "2026-10-09T16:00:00Z"},
        {"to": "2027-01-10T16:00:00Z"},
        {"from": "2026-10-10T00:00:00+08:00"},
        {"granularity": "minute"},
        {"granularity": "hour", "to": "2026-10-20T16:00:00Z"},
        {"group_by": "provider"},
        {"top_n": True},
        {"top_n": "10"},
        {"model_id": MODEL, "model_mapping": "unmapped"},
        {"graph_id": "agent", "project_ids": [PROJECT, MODEL]},
        {"source": "web"},
    ],
)
def test_query_rejects_unsupported_or_unbounded_inputs(changes):
    with pytest.raises(ValidationError):
        query(**changes)


def test_runs_do_not_accept_dashboard_parameters():
    with pytest.raises(ValidationError):
        RunsQuery.model_validate_json(json.dumps(query_body(group_by="model")))


def test_subsets_cost_and_partial_projection():
    result = project_metrics(facts())
    assert result["tokens"]["total_tokens"] == 30
    assert result["tokens"]["input_tokens"] == 20
    assert result["cost"]["estimated_cost_usd"] is None
    assert result["cost"]["known_cost_usd"] == "0.001000000000"
    assert result["average_tokens_per_recorded_run"] == 30
    partial = project_metrics(
        facts(
            reported_call_count=1,
            missing_usage_call_count=1,
            incomplete_call_count=1,
            total_tokens=15,
            total_tokens_count=1,
        )
    )
    assert partial["tokens"]["total_tokens"] is None
    assert partial["known_tokens"]["total_tokens"] == 15
    assert partial["average_tokens_per_recorded_run"] is None


def test_unknown_optional_fields_are_not_zeroed():
    result = project_metrics(facts(cache_read_tokens=None, cache_read_tokens_count=0))
    assert result["tokens"]["cache_read_tokens"] is None
    assert result["known_tokens"]["cache_read_tokens"] is None
    with pytest.raises(ValueError, match="unsafe_usage_total"):
        project_metrics(facts(total_tokens=2**53))
    result = project_metrics(
        facts(priced_call_count=2, known_cost_usd="10000000000000000")
    )
    assert (
        result["cost"]["status"] == "unknown"
        and result["cost"]["known_cost_usd"] is None
    )


def test_buckets_previous_window_and_disabled_history(monkeypatch):
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "false")
    result = dashboard(
        query(),
        {
            "collection": {"manifest_count": 1},
            "summary": facts(),
            "previous": facts(total_tokens=15, input_tokens=10, output_tokens=5),
            "series": [{"bucket": datetime(2026, 10, 9, 16, tzinfo=UTC), **facts()}],
        },
    )
    assert result["availability"] == "available"
    assert result["collection"]["enabled_now"] is False
    assert result["previous_window"]["total_token_change_ratio"] == 1
    assert len(result["series"]) == 2
    assert result["series"][0]["from"] == "2026-10-10T00:00:00+08:00"
    assert result["series"][1]["tokens"]["total_tokens"] == 0
    assert dashboard(query())["availability"] == "disabled"
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "true")
    assert dashboard(query())["unavailable_reason"] == "not_recorded"
    assert dashboard(query())["summary"]["known_tokens"]["total_tokens"] is None


def test_database_fault_is_safe_unavailable():
    with patch(
        "runtime_service.db.repositories.usage_analytics.aggregate_usage",
        side_effect=psycopg.OperationalError("SECRET SQL"),
    ):
        result = asyncio.run(query_aggregate(query()))
    assert result["unavailable_reason"] == "backend_unavailable"
    assert "SECRET" not in json.dumps(result)


def test_cancelled_query_keeps_budget_until_sql_exits_even_after_loop_closes(
    monkeypatch,
):
    from runtime_service.observability import usage_analytics as module

    entered, release, exited = threading.Event(), threading.Event(), threading.Event()
    slots = threading.BoundedSemaphore(1)
    with ThreadPoolExecutor(max_workers=1) as executor:
        monkeypatch.setattr(module, "_executor", executor)
        monkeypatch.setattr(module, "_inflight", slots)

        def execute(query, *, deadline):
            assert deadline > module.time.monotonic()
            entered.set()
            try:
                assert release.wait(2)
                return "ok"
            finally:
                exited.set()

        async def cancel():
            task = asyncio.create_task(module._read(execute, query()))
            assert await asyncio.to_thread(entered.wait, 1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            with pytest.raises(psycopg.OperationalError, match="capacity exhausted"):
                await module._read(execute, query())

        try:
            asyncio.run(cancel())
        finally:
            release.set()
            assert exited.wait(1)
    assert slots.acquire(timeout=1)
    slots.release()


def test_cancelled_query_consumes_late_database_exception(monkeypatch):
    from runtime_service.observability import usage_analytics as module

    entered, release = threading.Event(), threading.Event()
    errors = []
    with ThreadPoolExecutor(max_workers=1) as executor:
        monkeypatch.setattr(module, "_executor", executor)
        monkeypatch.setattr(module, "_inflight", threading.BoundedSemaphore(1))

        def execute(query, *, deadline):
            entered.set()
            assert release.wait(2)
            raise psycopg.OperationalError("late database failure")

        async def cancel():
            loop = asyncio.get_running_loop()
            loop.set_exception_handler(lambda _, context: errors.append(context))
            task = asyncio.create_task(module._read(execute, query()))
            assert await asyncio.to_thread(entered.wait, 1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            release.set()
            await loop.run_in_executor(executor, lambda: None)
            await asyncio.sleep(0)
            del task
            gc.collect()
            await asyncio.sleep(0)

        try:
            asyncio.run(cancel())
        finally:
            release.set()
    assert errors == []
