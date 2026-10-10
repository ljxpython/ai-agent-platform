"""Measure approved callback/feed load against a disposable 100k-event PostgreSQL store."""

import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event, insert, text

from platform_api.core.errors import register_exception_handlers
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    RunCompletionEventRecord as Event,
)
from platform_api.modules.runtime_gateway.presentation.completion_http import router
from tests import test_run_completion as contract

fixture = contract.fixture
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_COMPLETION_CAPACITY") != "1", reason="disposable capacity opt-in"
)


def percentiles(values):
    ordered = sorted(values)
    return {
        name: round(ordered[min(int(len(ordered) * ratio), len(ordered) - 1)] * 1000, 3)
        for name, ratio in (("p50_ms", 0.50), ("p95_ms", 0.95), ("p99_ms", 0.99))
    }


def test_http_completion_and_feed_100k_events(fixture, tmp_path):
    assert os.getenv("RUN_COMPLETION_PG_TEST") == "1", (
        "PostgreSQL isolation is required"
    )
    now = datetime.now(UTC)
    recipients = [fixture.user] + [str(uuid4()) for _ in range(9)]
    with fixture.factory.begin() as session:
        for offset in range(0, 100000, 1000):
            session.execute(
                insert(Event),
                [
                    {
                        "event_id": uuid4(),
                        "runtime_id": "default",
                        "origin_ref": str(uuid4()),
                        "run_id": str(uuid4()),
                        "thread_id": fixture.thread,
                        "project_id": fixture.project,
                        "status": "error",
                        "reason": "business_error",
                        "reason_code": "runtime_execution_failed",
                        "agent_key": "probe",
                        "recipient_user_id": recipients[index % 10],
                        "suppressed": False,
                        "detail_expires_at": now + timedelta(days=30),
                        "dedup_expires_at": now + timedelta(days=90),
                        "sequence": index + 1,
                        "occurred_at": now - timedelta(seconds=index),
                        "body_digest": hashlib.sha256(str(index).encode()).hexdigest(),
                        "payload": {},
                        "accepted_at": now - timedelta(seconds=index),
                    }
                    for index in range(offset, offset + 1000)
                ],
            )
        session.execute(text("ANALYZE"))
        plan = (
            session.execute(
                text(
                    "EXPLAIN SELECT event_id FROM run_completion_events WHERE project_id=:project AND recipient_user_id=:actor ORDER BY accepted_at DESC,event_id DESC LIMIT 50"
                ),
                {"project": fixture.project, "actor": fixture.user},
            )
            .scalars()
            .all()
        )
    assert any("ix_run_completion_feed" in line for line in plan), plan
    feed_plan = []

    @event.listens_for(fixture.factory.kw["bind"], "before_cursor_execute")
    def query_plan(conn, cursor, statement, parameters, context, executemany):
        if (
            not feed_plan
            and statement.startswith("SELECT")
            and "LEFT OUTER JOIN run_completion_receipts" in statement
        ):
            with cursor.connection.cursor() as probe:
                probe.execute("EXPLAIN " + statement, parameters)
                feed_plan.extend(row[0] for row in probe.fetchall())

    app = FastAPI()
    app.state.settings = fixture.settings
    app.state.db_session_factory = fixture.factory
    register_exception_handlers(app)
    app.include_router(router)
    app.dependency_overrides[get_actor_context] = lambda: fixture.actor

    @app.middleware("http")
    async def context(request, call_next):
        request.state.platform_context = SimpleNamespace(
            project=SimpleNamespace(project_id=fixture.project),
            request=SimpleNamespace(request_id="capacity"),
            actor=fixture.actor,
        )
        return await call_next(request)

    samples = {"callback": [], "feed": []}
    with TestClient(app) as client, ThreadPoolExecutor(max_workers=8) as pool:

        def request(kind, value=None):
            started = time.perf_counter()
            if kind == "callback":
                terminal, raw = value
                response = client.post(
                    "/api/runtime/internal/run-completion",
                    content=raw,
                    headers=contract.signed(fixture, raw, terminal.event_id),
                )
            else:
                response = client.get("/api/runtime/run-notifications?limit=20")
            elapsed = time.perf_counter() - started
            assert response.status_code == 200, response.text
            assert response.headers["cache-control"] == "private, no-store"
            return kind, elapsed

        pending = []
        started = time.perf_counter()
        for tick in range(120):
            terminal = contract.terminal(fixture)
            pending.append(pool.submit(request, "callback", terminal))
            if tick % 2 == 0:
                pending.append(pool.submit(request, "feed"))
            time.sleep(max(0, started + (tick + 1) / 20 - time.perf_counter()))
        for future in pending:
            kind, elapsed = future.result(timeout=20)
            samples[kind].append(elapsed)
    result = {
        kind: {"requests": len(values), **percentiles(values)}
        for kind, values in samples.items()
    }
    result.update(
        events=100000,
        callback_per_second=20,
        feed_per_second=10,
        query_plan=plan,
        feed_query_plan=feed_plan,
    )
    destination = Path(
        os.getenv("RUN_COMPLETION_CAPACITY_EVIDENCE", str(tmp_path / "capacity.json"))
    )
    destination.write_text(json.dumps(result, indent=2))
    print(json.dumps(result))
    assert all(item["p95_ms"] < 200 for item in (result["callback"], result["feed"])), (
        result
    )
