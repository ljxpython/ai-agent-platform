"""Opt-in real PostgreSQL tests, only with a separately provisioned usage test DB."""

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from uuid import uuid4

import psycopg
import pytest
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from support import BindableFakeMessagesChatModel

from runtime_service.db import upgrade
from runtime_service.db.repositories import usage as repo
from runtime_service.observability.usage import empty_tokens, with_runtime_usage
from runtime_service.observability.usage_query import (
    query_run_usage,
    query_thread_usage,
)


@pytest.fixture
def ledger_dsn(monkeypatch):
    dsn = os.getenv("USAGE_TEST_DSN")
    if not dsn:
        pytest.skip("USAGE_TEST_DSN must refer to an isolated PostgreSQL database")
    monkeypatch.setenv("DATABASE_URI", dsn)
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "true")
    upgrade(dsn)
    upgrade(dsn)
    return dsn


def test_real_ledger_migration_dedup_restart_paging_and_faults(monkeypatch, ledger_dsn):
    dsn = ledger_dsn
    identity = dict(
        tenant_id="usage-test",
        project_id=str(uuid4()),
        thread_id=str(uuid4()),
        run_id=str(uuid4()),
        graph_id="reference_agent",
    )
    repo.begin_collection(identity)
    assert asyncio.run(query_run_usage(identity))["availability"] == "partial"
    repo.finish_collection(identity, False)
    zero = asyncio.run(query_run_usage(identity))
    assert (
        zero["tokens"]["total_tokens"] == 0
        and zero["cost"]["status"] == "not_applicable"
    )
    repo.begin_collection(identity)
    call = dict(
        model_call_id=str(uuid4()),
        parent_call_id=None,
        model_id=None,
        provider="openai",
        model_name="test",
        scope="primary",
        purpose="agent",
        namespace=[],
        pricing_snapshot=None,
        started_at=datetime.now(UTC).isoformat(),
        ended_at=None,
        outcome="started",
        tokens=empty_tokens(),
        token_details={},
        quality="missing",
        usage_source="missing",
        estimated_cost_usd=None,
        cost_reason="incomplete_call",
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: repo.upsert_call(identity, call), range(2)))
    assert (
        asyncio.run(query_run_usage(identity))["coverage"]["observed_call_count"] == 1
    )
    call.update(
        tokens={
            **empty_tokens(0),
            "input_tokens": 1000,
            "output_tokens": 100,
            "total_tokens": 1100,
        },
        ended_at=datetime.now(UTC).isoformat(),
        outcome="completed",
        quality="reported",
        usage_source="usage_metadata",
        estimated_cost_usd="0.002580000000",
        cost_reason=None,
    )
    child = "from runtime_service.db.repositories.usage import upsert_call; import sys,json; x=json.load(sys.stdin); upsert_call(x['identity'],x['call'])"
    with ThreadPoolExecutor(max_workers=2) as pool:
        processes = list(
            pool.map(
                lambda _: subprocess.run(
                    ["rtk", "proxy", sys.executable, "-c", child],
                    input=json.dumps({"identity": identity, "call": call}),
                    text=True,
                    capture_output=True,
                    timeout=60,
                ),
                range(2),
            )
        )
    assert all(p.returncode == 0 for p in processes), [p.stderr for p in processes]
    repo.upsert_call(
        identity,
        {**call, "outcome": "started", "tokens": empty_tokens(), "quality": "missing"},
    )
    second = {
        **call,
        "model_call_id": str(uuid4()),
        "started_at": datetime.now(UTC).isoformat(),
        "tokens": {
            **empty_tokens(0),
            "input_tokens": 500,
            "output_tokens": 50,
            "total_tokens": 550,
        },
        "estimated_cost_usd": "0.001400000000",
    }
    repo.upsert_call(identity, second)
    repo.finish_collection(identity, False)
    first_page = asyncio.run(query_run_usage(identity, limit=1))
    assert (
        first_page["tokens"]["total_tokens"] == 1650
        and first_page["cost"]["estimated_cost_usd"] == "0.003980000000"
    )
    assert not first_page["truncated"] and first_page["calls"]["next_cursor"]
    page = asyncio.run(
        query_run_usage(identity, limit=1, cursor=first_page["calls"]["next_cursor"])
    )
    assert (
        page["tokens"] == first_page["tokens"]
        and page["calls"]["items"][0]["model_call_id"]
        != first_page["calls"]["items"][0]["model_call_id"]
    )
    thread_identity = {k: v for k, v in identity.items() if k != "run_id"}
    thread = asyncio.run(query_thread_usage(thread_identity))
    assert thread["tokens"]["total_tokens"] == 1650
    assert (
        asyncio.run(query_run_usage({**identity, "project_id": "different"}))[
            "unavailable_reason"
        ]
        == "not_recorded"
    )
    assert (
        asyncio.run(query_run_usage({**identity, "thread_id": str(uuid4())}))[
            "unavailable_reason"
        ]
        == "not_recorded"
    )
    with psycopg.connect(dsn) as lock:
        lock.execute(
            "SELECT 1 FROM runtime_usage_runs WHERE tenant_id=%s AND project_id=%s AND run_id=%s FOR UPDATE",
            (identity["tenant_id"], identity["project_id"], identity["run_id"]),
        )
        start = time.monotonic()
        with pytest.raises(psycopg.errors.LockNotAvailable):
            repo.begin_collection(identity)
        assert time.monotonic() - start < 2
    repo.begin_collection(identity)
    repo.finish_collection(identity, True)
    partial = asyncio.run(query_run_usage(identity))
    assert (
        partial["cost"]["status"] == "partial"
        and partial["cost"]["known_cost_usd"] == "0.003980000000"
    )
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "false")
    assert (
        asyncio.run(query_run_usage(identity))["coverage"]["observed_call_count"] == 2
    )
    assert (
        asyncio.run(query_run_usage({**identity, "run_id": str(uuid4())}))[
            "availability"
        ]
        == "disabled"
    )
    monkeypatch.setenv("DATABASE_URI", "postgresql://127.0.0.1:1/missing")
    assert (
        asyncio.run(query_run_usage(identity))["unavailable_reason"]
        == "backend_unavailable"
    )


def test_sigkill_placeholder_and_real_database_failure_recovery(
    monkeypatch, ledger_dsn
):
    identity = dict(
        tenant_id="usage-test",
        project_id=str(uuid4()),
        thread_id=str(uuid4()),
        run_id=str(uuid4()),
        graph_id="fault-probe",
    )
    call = dict(
        model_call_id=str(uuid4()),
        parent_call_id=None,
        model_id=None,
        provider="openai",
        model_name="test",
        scope="primary",
        purpose="agent",
        namespace=[],
        pricing_snapshot=None,
        started_at=datetime.now(UTC).isoformat(),
        ended_at=None,
        outcome="started",
        tokens=empty_tokens(),
        token_details={},
        quality="missing",
        usage_source="missing",
        estimated_cost_usd=None,
        cost_reason="incomplete_call",
    )
    child = "from runtime_service.db.repositories.usage import begin_collection,upsert_call; import sys,json,os,signal; x=json.load(sys.stdin); begin_collection(x['identity']); upsert_call(x['identity'],x['call']); os.kill(os.getpid(),signal.SIGKILL)"
    killed = subprocess.run(
        ["rtk", "proxy", sys.executable, "-c", child],
        input=json.dumps({"identity": identity, "call": call}),
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert killed.returncode in {-signal.SIGKILL, 128 + signal.SIGKILL}, killed.stderr
    restarted = asyncio.run(query_run_usage(identity))
    assert restarted["availability"] == "partial" and not restarted["finalized"]
    assert restarted["coverage"]["incomplete_call_count"] == 1
    assert restarted["tokens"]["total_tokens"] is None

    chat = BindableFakeMessagesChatModel(
        responses=[
            AIMessage(
                content="successful",
                usage_metadata={
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "total_tokens": 15,
                },
            )
        ]
    )

    async def node(state):
        monkeypatch.setenv("DATABASE_URI", "postgresql://127.0.0.1:1/missing")
        result = await chat.ainvoke("first")
        monkeypatch.setenv("DATABASE_URI", ledger_dsn)
        await chat.ainvoke("second")
        return {"answer": result.content}

    builder = StateGraph(dict)
    builder.add_node("probe", node)
    builder.add_edge(START, "probe")
    builder.add_edge("probe", END)
    new_identity = {**identity, "run_id": str(uuid4())}
    graph = with_runtime_usage(
        builder.compile(),
        {
            "metadata": {
                "thread_id": identity["thread_id"],
                "run_id": new_identity["run_id"],
            }
        },
        graph_id=identity["graph_id"],
        trusted_metadata=identity,
    )
    assert asyncio.run(graph.ainvoke({}))["answer"] == "successful"
    recovered = asyncio.run(query_run_usage(new_identity))
    assert (
        recovered["availability"] == "partial"
        and recovered["coverage"]["collection_degraded"]
    )
    assert (
        recovered["known_tokens"]["total_tokens"] == 15
        and recovered["tokens"]["total_tokens"] is None
    )
    assert recovered["coverage"]["observed_call_count"] == 1
    with psycopg.connect(ledger_dsn) as conn:
        indexes = conn.execute(
            "SELECT indexname FROM pg_indexes WHERE tablename='runtime_usage_calls'"
        ).fetchall()
        assert {"ix_runtime_usage_calls_page", "ix_runtime_usage_calls_thread"} <= {
            row[0] for row in indexes
        }
        conn.execute("SET LOCAL enable_seqscan=off")
        plan = conn.execute(
            "EXPLAIN SELECT * FROM runtime_usage_calls WHERE tenant_id=%s AND project_id=%s AND run_id=%s ORDER BY started_at, model_call_id LIMIT 50",
            (identity["tenant_id"], identity["project_id"], identity["run_id"]),
        ).fetchall()
        assert "ix_runtime_usage_calls_page" in str(plan)
