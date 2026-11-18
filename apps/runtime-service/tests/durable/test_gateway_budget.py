"""Real PostgreSQL governance tests; never connect to the primary environment."""

import asyncio
import copy
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import psycopg
import pytest
from langchain_core.messages import AIMessage
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb
from support import BindableFakeMessagesChatModel

from runtime_service.db import upgrade
from runtime_service.db.repositories import usage
from runtime_service.gateway_budget import ledger
from runtime_service.gateway_budget.contracts import PolicySnapshot
from runtime_service.gateway_budget.service import GatewayBudgetExceededError
from runtime_service.observability.usage import empty_tokens, with_runtime_usage

TEST_BATCH = uuid4().hex[:12]
TEST_TENANT_PREFIX = f"budget-test-{TEST_BATCH}-"


@pytest.fixture
def db(monkeypatch):
    dsn = os.getenv("GATEWAY_BUDGET_TEST_DSN")
    if not dsn:
        pytest.skip("GATEWAY_BUDGET_TEST_DSN must be a dedicated Worktree database")
    database = conninfo_to_dict(dsn)["dbname"]
    assert database.startswith("wt_") and database.endswith("_runtime")
    monkeypatch.setenv("DATABASE_URI", dsn)
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_TOKEN_BUDGET_ENABLED", "false")
    upgrade(dsn)
    yield True
    with usage._connection() as conn:
        conn.execute(
            "DELETE FROM runs WHERE metadata->>'budget_test_batch'=%s", (TEST_BATCH,)
        )
        for table in (
            "runtime_budget_outbox",
            "runtime_budget_call_leases",
            "runtime_budget_contributions",
            "runtime_budget_windows",
            "runtime_budget_tenants",
            "runtime_usage_calls",
            "runtime_usage_runs",
            "runtime_usage_run_slots",
            "runtime_usage_projection_dirty",
        ):
            conn.execute(
                f"DELETE FROM {table} WHERE tenant_id LIKE %s",
                (TEST_TENANT_PREFIX + "%",),
            )


def identity():
    return dict(
        tenant_id=TEST_TENANT_PREFIX + uuid4().hex[:12],
        project_id=str(uuid4()),
        thread_id=str(uuid4()),
        run_id=str(uuid4()),
        graph_id="reference_agent",
    )


def policy(project=None, *, at=None, action="REJECT", amount="1.000000000000"):
    at = at or datetime.now(UTC)
    return {
        "id": str(uuid4()),
        "version": 1,
        "definition_version": 1,
        "scope": "PROJECT" if project else "GLOBAL",
        "project_id": project,
        "budget_amount": amount,
        "budget_unit": "USD",
        "duration": {"unit": "DAYS", "value": 1},
        "action": action,
        "created_at": at.isoformat(),
        "definition_started_at": at.isoformat(),
        "updated_at": at.isoformat(),
        "deleted_at": None,
    }


def snapshot(ident, policies):
    return PolicySnapshot.model_validate(
        {"tenant_id": ident["tenant_id"], "revision": 1, "policies": policies}
    ).model_dump(mode="json")


def call(amount=None, *, at=None):
    at = at or datetime.now(UTC)
    return {
        "model_call_id": str(uuid4()),
        "parent_call_id": None,
        "model_id": None,
        "provider": "openai",
        "model_name": "test",
        "scope": "primary",
        "purpose": "agent",
        "namespace": [],
        "pricing_snapshot": {
            "currency": "USD",
            "basis": "per_million_tokens",
            "source": "configured_catalog",
            "version": str(uuid4()),
            "updated_at": at.isoformat(),
            "input": "600000",
            "output": "0",
            "cache_read": "0",
            "cache_write": "0",
            "cache_write_5m": "0",
            "cache_write_1h": "0",
        },
        "started_at": at.isoformat(),
        "ended_at": at.isoformat() if amount is not None else None,
        "outcome": "completed" if amount is not None else "started",
        "tokens": empty_tokens(0),
        "token_details": {},
        "quality": "reported" if amount is not None else "missing",
        "usage_source": "usage_metadata",
        "estimated_cost_usd": amount,
        "cost_reason": None,
    }


def priced_model(responses):
    pricing = {
        "currency": "USD",
        "basis": "per_million_tokens",
        "source": "configured_catalog",
        "version": str(uuid4()),
        "updated_at": datetime.now(UTC).isoformat(),
        "input": "600000",
        "output": "0",
        "cache_read": "0",
        "cache_write": "0",
        "cache_write_5m": "0",
        "cache_write_1h": "0",
    }
    return BindableFakeMessagesChatModel(
        responses=responses,
        metadata={
            "runtime_usage_model": {
                "model_id": str(uuid4()),
                "provider": "openai",
                "protocol": "openai",
                "pricing": pricing,
            }
        },
    )


def answer(content="ok", **changes):
    return AIMessage(
        content=content,
        usage_metadata={
            "input_tokens": 1,
            "output_tokens": 0,
            "total_tokens": 1,
            "input_token_details": {"cache_read": 0},
        },
        **changes,
    )


def bind(model, ident):
    return with_runtime_usage(
        model,
        {"metadata": {"run_id": ident["run_id"], "thread_id": ident["thread_id"]}},
        graph_id=ident["graph_id"],
        trusted_metadata=ident,
    )


def test_long_agent_stops_before_next_call(monkeypatch, db):
    from langchain.agents import create_agent
    from langchain_core.tools import tool

    ident = identity()
    snap = snapshot(ident, [policy()])
    monkeypatch.setenv("RUNTIME_GATEWAY_BUDGET_ENABLED", "true")
    monkeypatch.setattr(
        "runtime_service.gateway_budget.service.post", lambda *args: snap
    )

    @tool
    def ping() -> str:
        """A bounded synthetic tool."""
        return "pong"

    primary = priced_model(
        [
            answer(tool_calls=[{"name": "ping", "args": {}, "id": str(uuid4())}]),
            answer(tool_calls=[{"name": "ping", "args": {}, "id": str(uuid4())}]),
            answer("unreachable"),
        ]
    )
    graph = bind(
        create_agent(
            primary,
            tools=[ping],
        ),
        ident,
    )
    with pytest.raises(GatewayBudgetExceededError):
        asyncio.run(graph.ainvoke({"messages": [{"role": "user", "content": "ping"}]}))
    with usage._connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM runtime_usage_calls WHERE tenant_id=%s",
                (ident["tenant_id"],),
            ).fetchone()["n"]
            == 2
        )
    assert primary.i == 2
    from runtime_service.observability.usage_query import query_run_usage

    result = asyncio.run(query_run_usage(ident))
    assert result["gateway_budget_stop_code"] == "runtime.gateway_budget.exhausted"


def test_resilience_does_not_retry_or_fallback_budget_error():
    from langchain.agents.middleware import ModelRequest

    from runtime_service.middlewares.model_resilience import ModelResilienceMiddleware
    from runtime_service.runtime.contracts import ModelResiliencePolicy

    primary, backup = priced_model([answer()]), priced_model([answer()])
    middleware = ModelResilienceMiddleware(
        ModelResiliencePolicy(enabled=True, fallback_model_id=str(uuid4())),
        backup,
        primary_model_id=str(uuid4()),
    )
    calls = []

    async def guarded(candidate):
        calls.append(candidate.model)
        raise GatewayBudgetExceededError()

    with pytest.raises(GatewayBudgetExceededError):
        asyncio.run(
            middleware.awrap_model_call(
                ModelRequest(model=primary, messages=[]), guarded
            )
        )
    assert len(calls) == 1
    assert (
        calls[0].metadata["runtime_usage_model"]["model_id"]
        == primary.metadata["runtime_usage_model"]["model_id"]
    )


def test_live_edit_and_settlement_failure_stop_following_reject(monkeypatch, db):
    from runtime_service.gateway_budget.service import GatewayBudgetUnverifiableError

    ident = identity()
    snap = snapshot(ident, [policy(amount="10")])
    monkeypatch.setenv("RUNTIME_GATEWAY_BUDGET_ENABLED", "true")
    monkeypatch.setattr(
        "runtime_service.gateway_budget.service.post", lambda *args: snap
    )
    configured = bind(priced_model([answer()]), ident)
    asyncio.run(configured.ainvoke("hello"))
    snap["revision"] = 2
    snap["policies"][0].update(
        version=2,
        budget_amount="0.500000000000",
        updated_at=datetime.now(UTC).isoformat(),
    )
    with pytest.raises(GatewayBudgetExceededError):
        asyncio.run(configured.ainvoke("must stop after edit"))
    snap["revision"] = 3
    snap["policies"][0].update(
        version=3,
        budget_amount="10.000000000000",
        updated_at=datetime.now(UTC).isoformat(),
    )
    original = usage._upsert_call

    def fail_settlement(conn, identity, call):
        if call["outcome"] != "started":
            raise RuntimeError("synthetic write failure")
        original(conn, identity, call)

    monkeypatch.setattr(usage, "_upsert_call", fail_settlement)
    asyncio.run(configured.ainvoke("ends with uncertain settlement"))
    with pytest.raises(GatewayBudgetUnverifiableError):
        asyncio.run(configured.ainvoke("must not bypass callback failure"))


@pytest.mark.parametrize("action", ["ALERT", "REJECT"])
def test_cannot_dispatch_when_start_cannot_persist(monkeypatch, db, action):
    from runtime_service.gateway_budget.service import GatewayBudgetUnverifiableError

    ident = identity()
    snap = snapshot(ident, [policy(action=action)])
    monkeypatch.setenv("RUNTIME_GATEWAY_BUDGET_ENABLED", "true")
    monkeypatch.setattr(
        "runtime_service.gateway_budget.service.post", lambda *args: snap
    )

    def unavailable(*args):
        raise RuntimeError("synthetic database outage")

    monkeypatch.setattr(ledger, "admit", unavailable)
    model = priced_model([answer(), answer()])
    with pytest.raises(GatewayBudgetUnverifiableError):
        asyncio.run(bind(model, ident).ainvoke("blocked"))
    assert model.i == 0


def test_control_plane_failure_is_not_an_empty_policy_set(monkeypatch, db):
    from runtime_service.gateway_budget.service import GatewayBudgetUnverifiableError

    monkeypatch.setenv("RUNTIME_GATEWAY_BUDGET_ENABLED", "true")

    def failed(*args):
        raise ConnectionError("synthetic control-plane outage")

    monkeypatch.setattr("runtime_service.gateway_budget.service.post", failed)
    model = priced_model([answer(), answer()])
    with pytest.raises(GatewayBudgetUnverifiableError):
        asyncio.run(bind(model, identity()).ainvoke("must not dispatch"))
    assert model.i == 0


def test_history_immutable_after_edit_and_definition_change(db):
    ident = identity()
    old = datetime(2026, 11, 17, 23, 59, tzinfo=UTC)
    now = old + timedelta(minutes=2)
    p = policy(at=old - timedelta(days=2))
    snap = snapshot(ident, [p])
    ledger.synchronize(snap, at=old)
    usage.upsert_call(ident, call("0.600000000000", at=old))
    edited = copy.deepcopy(snap)
    edited["revision"] = 2
    edited["policies"][0].update(
        version=2, budget_amount="10.000000000000", updated_at=now.isoformat()
    )
    ledger.synchronize(edited, at=now)
    with usage._connection() as conn:
        history = conn.execute(
            "SELECT policy FROM runtime_budget_windows WHERE tenant_id=%s ORDER BY window_start",
            (ident["tenant_id"],),
        ).fetchall()
        assert [r["policy"]["budget_amount"] for r in history] == [
            "1.000000000000",
            "10.000000000000",
        ]
    edited["revision"] = 3
    edited["policies"][0].update(
        version=3,
        definition_version=2,
        definition_started_at=now.isoformat(),
        duration={"unit": "WEEKS", "value": 1},
    )
    ledger.synchronize(edited, at=now)
    assert ledger.synchronize(edited, at=now)[0]["known_spend"] == "0.600000000000"


@pytest.mark.parametrize(
    ("unit", "at", "start", "end"),
    [
        ("DAYS", "2026-12-31T23:59:59+00:00", "2026-12-31", "2027-01-01"),
        ("WEEKS", "2026-11-22T00:00:00+00:00", "2026-11-22", "2026-11-29"),
        ("WEEKS", "2026-11-21T23:59:59+00:00", "2026-11-15", "2026-11-22"),
        ("MONTHS", "2028-02-29T23:59:59+00:00", "2028-02-01", "2028-03-01"),
    ],
)
def test_windows(unit, at, start, end):
    a, b = ledger.window(unit, datetime.fromisoformat(at))
    assert a.date().isoformat() == start and b.date().isoformat() == end


def test_concurrent_precision_two_scopes_dedup(db):
    ident = identity()
    snap = snapshot(
        ident, [policy(amount="10"), policy(ident["project_id"], amount="10")]
    )
    ledger.synchronize(snap)
    calls = [call("0.000000000001") for _ in range(24)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda c: usage.upsert_call(ident, c), calls + calls))
    states = ledger.synchronize(snap)
    assert len(states) == 2
    assert all(s["known_spend"] == "0.000000000024" for s in states)
    assert all(s["accounting_status"] == "complete" for s in states)


def test_tenant_and_project_isolation(db):
    first = identity()
    second = {**identity(), "tenant_id": first["tenant_id"]}
    other = identity()
    policies = [
        policy(amount="10"),
        policy(first["project_id"], amount="0.5"),
        policy(second["project_id"], amount="2"),
    ]
    snap = snapshot(first, policies)
    ledger.synchronize(snap)
    other_snap = snapshot(other, [policy(amount="20")])
    ledger.synchronize(other_snap)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(
            pool.map(
                lambda pair: usage.upsert_call(*pair),
                [
                    (first, call("0.600000000000")),
                    (second, call("0.500000000000")),
                    (other, call("9.000000000000")),
                ],
            )
        )
    states = {s["policy_id"]: s for s in ledger.synchronize(snap)}
    assert [states[p["id"]]["current_spend"] for p in policies] == [
        "1.100000000000",
        "0.600000000000",
        "0.500000000000",
    ]
    assert ledger.admit(first, call(), snap)["code"].endswith("exhausted")
    assert ledger.admit(second, call(), snap) is None
    assert ledger.synchronize(other_snap)[0]["current_spend"] == "9.000000000000"


def test_backfill_partial_improvement_and_price_snapshot(db):
    ident = identity()
    c = call()
    usage.upsert_call(ident, c)
    snap = snapshot(ident, [policy()])
    assert ledger.synchronize(snap)[0]["accounting_status"] == "unverifiable"
    c.update(outcome="failed", quality="partial", estimated_cost_usd=None)
    usage.upsert_call(ident, c)
    c.update(quality="reported", estimated_cost_usd="0.600000000000")
    usage.upsert_call(ident, c)
    usage.upsert_call(ident, {**c, "quality": "missing", "estimated_cost_usd": None})
    assert ledger.synchronize(snap)[0]["current_spend"] == "0.600000000000"
    usage.upsert_call(ident, c)
    assert ledger.synchronize(snap)[0]["current_spend"] == "0.600000000000"


def test_threshold_event_edits_and_delete(db):
    ident = identity()
    p = policy(action="ALERT")
    snap = snapshot(ident, [p])
    ledger.synchronize(snap)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(
            pool.map(
                lambda c: usage.upsert_call(ident, c),
                [call("0.600000000000") for _ in range(3)],
            )
        )
    assert ledger.synchronize(snap)[0]["current_spend"] == "1.800000000000"
    revised = copy.deepcopy(snap)
    revised["revision"], revised["policies"][0]["version"] = 2, 2
    revised["policies"][0]["budget_amount"] = "3.000000000000"
    revised["policies"][0]["action"] = "REJECT"
    assert ledger.synchronize(revised)[0]["is_exceeded"] is False
    usage.upsert_call(ident, call("2.000000000000"))
    with usage._connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM runtime_budget_outbox WHERE tenant_id=%s",
                (ident["tenant_id"],),
            ).fetchone()["n"]
            == 1
        )
    with pytest.raises(ValueError, match="stale"):
        ledger.synchronize(snap)
    revised["revision"] = 3
    revised["policies"][0]["version"] = 3
    revised["policies"][0]["deleted_at"] = datetime.now(UTC).isoformat()
    assert ledger.synchronize(revised) == []


def test_late_call_old_window_and_rebuild(db):
    ident = identity()
    old = datetime(2026, 11, 17, 23, 59, tzinfo=UTC)
    p = policy(at=old - timedelta(days=1), amount="10")
    snap = snapshot(ident, [p])
    ledger.synchronize(snap, at=old)
    later = old + timedelta(minutes=2)
    ledger.synchronize(snap, at=later)
    usage.upsert_call(ident, call("0.600000000000", at=old))
    usage.upsert_call(ident, call("0.500000000000", at=later))
    assert ledger.synchronize(snap, at=old)[0]["known_spend"] == "0.600000000000"
    assert ledger.synchronize(snap, at=later)[0]["known_spend"] == "0.500000000000"
    with usage._connection() as conn:
        ledger.locked(conn, ident["tenant_id"])
        start, _ = ledger.window("DAYS", old)
        ledger.rebuild(conn, (ident["tenant_id"], p["id"], 1, start))
    assert ledger.synchronize(snap, at=old)[0]["known_spend"] == "0.600000000000"


def test_projection_mismatch_repairs_before_reject_decision(db):
    ident = identity()
    snap = snapshot(ident, [policy()])
    ledger.synchronize(snap)
    usage.upsert_call(ident, call("1.100000000000"))
    with usage._connection() as conn:
        conn.execute(
            "UPDATE runtime_budget_windows SET known_spend=0 WHERE tenant_id=%s",
            (ident["tenant_id"],),
        )
    assert ledger.admit(ident, call(), snap)["code"].endswith("exhausted")
    assert ledger.synchronize(snap)[0]["current_spend"] == "1.100000000000"


def test_backfill_persists_known_collection_gap_before_thread_cleanup(db):
    ident = identity()
    with usage._connection() as conn:
        conn.execute(
            "INSERT INTO runs(run_id,thread_id,assistant_id,status,metadata,kwargs) "
            "VALUES(%s,%s,%s,'error',%s,%s)",
            (
                ident["run_id"],
                ident["thread_id"],
                str(uuid4()),
                Jsonb({"budget_test_batch": TEST_BATCH}),
                Jsonb(
                    {
                        "__graphharbor_runtime_context": {
                            "auth_user": {
                                "tenant_id": ident["tenant_id"],
                                "project_id": ident["project_id"],
                            }
                        }
                    }
                ),
            ),
        )
    snap = snapshot(ident, [policy()])
    assert ledger.synchronize(snap)[0]["accounting_status"] == "unverifiable"
    with usage._connection() as conn:
        conn.execute("DELETE FROM runs WHERE run_id=%s", (ident["run_id"],))
    state = ledger.synchronize(snap)[0]
    assert state["current_spend"] is None and state["known_spend"] == "0.000000000000"


def test_admission_inflight_unknown_and_duplicate_dispatch(db):
    ident = identity()
    snap = snapshot(ident, [policy()])
    a, b = call(), call()
    assert ledger.admit(ident, a, snap) is None
    assert ledger.admit(ident, b, snap) is None
    assert ledger.admit(ident, a, snap)["code"].endswith("unverifiable")
    a.update(
        outcome="completed", quality="reported", estimated_cost_usd="0.600000000000"
    )
    b.update(
        outcome="cancelled", quality="reported", estimated_cost_usd="0.500000000000"
    )
    usage.upsert_call(ident, a)
    usage.upsert_call(ident, b)
    assert ledger.admit(ident, call(), snap)["code"].endswith("exhausted")
    assert ledger.synchronize(snap)[0]["known_spend"] == "1.100000000000"
    other = identity()
    other_snap = snapshot(other, [policy()])
    pending = call()
    ledger.admit(other, pending, other_snap)
    with usage._connection() as conn:
        conn.execute(
            "UPDATE runtime_budget_call_leases SET expires_at=now()-interval '1 second' WHERE tenant_id=%s",
            (other["tenant_id"],),
        )
    assert ledger.admit(other, call(), other_snap)["code"].endswith("unverifiable")


@pytest.mark.parametrize(
    "fault", ["usage", "contribution", "window", "event", "second_scope"]
)
def test_transaction_rollback_including_outbox(monkeypatch, db, fault):
    ident = identity()
    snap = snapshot(ident, [policy(), policy(ident["project_id"])])
    ledger.synchronize(snap)

    original = ledger.event
    events = []

    def crash(conn, row):
        original(conn, row)
        events.append(row["policy_id"])
        if len(events) == 2:
            raise RuntimeError("injected after both scopes before commit")

    if fault == "second_scope":
        monkeypatch.setattr(ledger, "event", crash)
    else:
        original_execute = psycopg.Connection.execute
        prefix = {
            "usage": "INSERT INTO runtime_usage_calls",
            "contribution": "INSERT INTO runtime_budget_contributions",
            "window": "UPDATE runtime_budget_windows SET known_spend=known_spend+",
            "event": "INSERT INTO runtime_budget_outbox",
        }[fault]

        def interrupted(conn, statement, *args, **kwargs):
            result = original_execute(conn, statement, *args, **kwargs)
            if isinstance(statement, str) and statement.startswith(prefix):
                raise RuntimeError("synthetic failure after " + fault)
            return result

        monkeypatch.setattr(psycopg.Connection, "execute", interrupted)
    with pytest.raises(RuntimeError):
        usage.upsert_call(ident, call("1.000000000000"))
    with usage._connection() as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM runtime_usage_calls WHERE tenant_id=%s",
                (ident["tenant_id"],),
            ).fetchone()["n"]
            == 0
        )
        assert all(
            row["known_spend"] == Decimal(0)
            for row in conn.execute(
                "SELECT known_spend FROM runtime_budget_windows WHERE tenant_id=%s",
                (ident["tenant_id"],),
            ).fetchall()
        )
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM runtime_budget_outbox WHERE tenant_id=%s",
                (ident["tenant_id"],),
            ).fetchone()["n"]
            == 0
        )


def test_price_snapshot_is_frozen_on_late_usage(db):
    ident = identity()
    snap = snapshot(ident, [policy()])
    c = call()
    usage.upsert_call(ident, c)
    revised = copy.deepcopy(c)
    revised["pricing_snapshot"]["input"] = "900000"
    revised.update(
        outcome="completed",
        quality="reported",
        tokens={**empty_tokens(0), "input_tokens": 1, "total_tokens": 1},
        estimated_cost_usd="0.900000000000",
    )
    usage.upsert_call(ident, revised)
    assert ledger.synchronize(snap)[0]["current_spend"] == "0.600000000000"
    with usage._connection() as conn:
        row = conn.execute(
            "SELECT pricing_snapshot FROM runtime_usage_calls WHERE tenant_id=%s",
            (ident["tenant_id"],),
        ).fetchone()
    assert row["pricing_snapshot"] == c["pricing_snapshot"]


@pytest.mark.parametrize("action", ["ALERT", "REJECT"])
def test_missing_input_price_is_known_before_dispatch(db, action):
    ident = identity()
    c = call()
    c["pricing_snapshot"]["input"] = None
    decision = ledger.admit(ident, c, snapshot(ident, [policy(action=action)]))
    assert (decision is None) is (action == "ALERT")


def test_backfill_waits_for_started_but_later_committed_writer(db):
    ident = identity()
    snap = snapshot(ident, [policy()])
    ready, release = threading.Event(), threading.Event()

    def writer():
        with usage._connection() as conn:
            ledger.locked(conn, ident["tenant_id"])
            usage._begin(conn, ident)
            usage._upsert_call(conn, ident, call("0.600000000000"))
            ready.set()
            assert release.wait(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        pending = pool.submit(writer)
        assert ready.wait(2)
        backfill = pool.submit(ledger.synchronize, snap)
        release.set()
        pending.result()
        assert backfill.result()[0]["current_spend"] == "0.600000000000"


def test_auxiliary_and_nested_calls_keep_dispatch_guard(monkeypatch, db):
    from langgraph.graph import StateGraph

    from runtime_service.observability.usage import usage_only_config

    ident = identity()
    snap = snapshot(ident, [policy()])
    monkeypatch.setenv("RUNTIME_GATEWAY_BUDGET_ENABLED", "true")
    monkeypatch.setattr(
        "runtime_service.gateway_budget.service.post", lambda *args: snap
    )
    model = priced_model([answer(), answer(), answer()])

    async def node(state):
        await model.ainvoke("summary", config=usage_only_config("summarization"))
        await model.ainvoke(
            "nested",
            config={"metadata": {"langgraph_checkpoint_ns": "parent|child:model"}},
        )
        await model.ainvoke(
            "blocked hidden", config=usage_only_config("memory_extraction")
        )
        return state

    builder = StateGraph(dict)
    builder.add_node("work", node)
    builder.set_entry_point("work")
    builder.set_finish_point("work")
    with pytest.raises(GatewayBudgetExceededError):
        asyncio.run(bind(builder.compile(), ident).ainvoke({"value": 1}))
    with usage._connection() as conn:
        rows = conn.execute(
            "SELECT scope,purpose FROM runtime_usage_calls WHERE tenant_id=%s ORDER BY started_at",
            (ident["tenant_id"],),
        ).fetchall()
    assert [(r["scope"], r["purpose"]) for r in rows] == [
        ("auxiliary", "summarization"),
        ("subagent", "agent"),
    ]
    assert model.i == 2


def test_signed_runtime_http_auth_replay_and_expiry(monkeypatch, db):
    import time

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from runtime_service.gateway_budget import transport
    from runtime_service.http.gateway_budgets import router

    secret = "budget-runtime-test-secret-at-least-32"
    monkeypatch.setenv("RUNTIME_GATEWAY_BUDGET_ENABLED", "true")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", secret)
    ident = identity()
    app = FastAPI()
    app.include_router(router)
    path = "/internal/budgets/query"
    payload = {"snapshot": snapshot(ident, [policy()]), "mode": "sync"}
    with TestClient(app) as client:
        assert client.post(path, json=payload).status_code == 403
        raw, headers = transport.encode(secret, path, payload)
        result = client.post(path, content=raw, headers=headers)
        assert result.status_code == 200
        assert result.json()["states"][0]["current_spend"] == "0.000000000000"
        assert client.post(path, content=raw, headers=headers).status_code == 409
        raw, headers = transport.encode(secret, "/another-purpose", payload)
        assert client.post(path, content=raw, headers=headers).status_code == 403
        raw, headers = transport.encode(secret, path, payload)
        assert client.post(path, content=raw + b" ", headers=headers).status_code == 403
        assert (
            client.post(path + "?skip=true", content=raw, headers=headers).status_code
            == 403
        )
        assert client.get(path, headers=headers).status_code == 405
        expired = time.time() - 120
        with monkeypatch.context() as patch:
            patch.setattr(transport.time, "time", lambda: expired)
            raw, headers = transport.encode(secret, path, payload)
        assert client.post(path, content=raw, headers=headers).status_code == 403


def test_mixed_worker_claim_fence_and_rollback_pause(monkeypatch, db):
    from sqlalchemy import create_engine, text

    ident = identity()
    ledger.synchronize(snapshot(ident, []))
    run_id = str(uuid4())
    with usage._connection() as conn:
        conn.execute(
            "INSERT INTO runs(run_id,assistant_id,status,metadata) VALUES(%s,%s,'pending',%s)",
            (run_id, str(uuid4()), Jsonb({"budget_test_batch": TEST_BATCH})),
        )
    # A legacy process has no session capability, even when it shares the queue/database.
    with pytest.raises(psycopg.errors.ObjectNotInPrerequisiteState):
        with usage._connection() as conn:
            conn.execute("UPDATE runs SET status='running' WHERE run_id=%s", (run_id,))
    monkeypatch.setenv("RUNTIME_GATEWAY_BUDGET_ENABLED", "true")
    engine = create_engine(
        os.environ["DATABASE_URI"].replace("postgresql://", "postgresql+psycopg://", 1)
    )
    try:
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE runs SET status='running' WHERE run_id=:id"),
                {"id": run_id},
            )
            conn.execute(
                text("UPDATE runs SET status='error' WHERE run_id=:id"), {"id": run_id}
            )
    finally:
        engine.dispose()
    monkeypatch.setenv("RUNTIME_GATEWAY_BUDGET_ENABLED", "false")
    engine = create_engine(
        os.environ["DATABASE_URI"].replace("postgresql://", "postgresql+psycopg://", 1)
    )
    try:
        with pytest.raises(Exception, match="worker capability required"):
            with engine.begin() as conn:
                conn.execute(
                    text("UPDATE runs SET status='running' WHERE run_id=:id"),
                    {"id": run_id},
                )
        with engine.begin() as conn:
            assert (
                conn.scalar(
                    text("SELECT status FROM runs WHERE run_id=:id"), {"id": run_id}
                )
                == "error"
            )
    finally:
        engine.dispose()


def test_first_activation_requires_drained_execution(db):
    from runtime_service.gateway_budget.worker_guard import activate

    with usage._connection() as conn:
        # Temporary shadows exercise first activation without toggling the live fence.
        conn.execute(
            "CREATE TEMP TABLE runtime_budget_worker_fence(id integer,active boolean)"
        )
        conn.execute("INSERT INTO pg_temp.runtime_budget_worker_fence VALUES(1,false)")
        conn.execute("CREATE TEMP TABLE runs(status text)")
        conn.execute("INSERT INTO pg_temp.runs VALUES('running')")
        with pytest.raises(ValueError, match="drained"):
            activate(conn)
        conn.execute("DELETE FROM pg_temp.runs")
        activate(conn)
        assert (
            conn.execute(
                "SELECT active FROM pg_temp.runtime_budget_worker_fence"
            ).fetchone()["active"]
            is True
        )


@pytest.mark.parametrize("asynchronous", [False, True])
def test_real_langchain_dispatch_guard(monkeypatch, db, asynchronous):
    ident = identity()
    snap = snapshot(ident, [policy()])
    monkeypatch.setenv("RUNTIME_GATEWAY_BUDGET_ENABLED", "true")
    monkeypatch.setattr(
        "runtime_service.gateway_budget.service.post", lambda *args: snap
    )
    pricing = {
        "currency": "USD",
        "basis": "per_million_tokens",
        "source": "configured_catalog",
        "version": str(uuid4()),
        "updated_at": datetime.now(UTC).isoformat(),
        "input": "600000",
        "output": "0",
        "cache_read": "0",
        "cache_write": "0",
        "cache_write_5m": "0",
        "cache_write_1h": "0",
    }
    model = BindableFakeMessagesChatModel(
        responses=[
            AIMessage(
                content="ok",
                usage_metadata={
                    "input_tokens": 1,
                    "output_tokens": 0,
                    "total_tokens": 1,
                    "input_token_details": {"cache_read": 0},
                },
            )
        ],
        metadata={
            "runtime_usage_model": {
                "model_id": str(uuid4()),
                "provider": "openai",
                "protocol": "openai",
                "pricing": pricing,
            }
        },
    )
    configured = with_runtime_usage(
        model,
        {"metadata": {"run_id": ident["run_id"], "thread_id": ident["thread_id"]}},
        graph_id=ident["graph_id"],
        trusted_metadata=ident,
    )

    async def run():
        for _ in range(2):
            if asynchronous:
                await configured.ainvoke("hello")
            else:
                await asyncio.to_thread(configured.invoke, "hello")
        with pytest.raises(GatewayBudgetExceededError):
            if asynchronous:
                await configured.ainvoke("blocked")
            else:
                await asyncio.to_thread(configured.invoke, "blocked")

    asyncio.run(run())
    assert ledger.synchronize(snap)[0]["known_spend"] == "1.200000000000"
