"""Reuse the established isolated stack; completion adds real PostgreSQL and two Workers."""

import importlib.util
import json
import os
import time
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from starlette.requests import Request

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_COMPLETION_WORKER") != "1",
        reason="isolated completion integration opt-in",
    ),
]


async def verify_completion_extensions(
    app, client, project, ids, dsn, tmp_path, harness
):
    from platform_api.core.context.models import (
        PlatformRequestContext,
        ProjectContext,
        RequestContext,
        TenantContext,
    )
    from platform_api.modules.identity.actors import load_user_actor
    from platform_api.modules.runtime_gateway.presentation.http import (
        get_runtime_gateway_service,
    )
    from platform_api.modules.scheduled_tasks.service import ScheduledTasksService

    response = await client.post(
        "/api/langgraph/threads", json={"metadata": {"graph_id": "reference_agent"}}
    )
    response.raise_for_status()
    thread_id = response.json()["thread_id"]
    app.state.settings.runtime_completion_enabled = False
    try:
        response = await client.post(
            "/api/scheduled-tasks",
            json={
                "title": "Legacy completion migration",
                "prompt": "exhausted",
                "agent_key": "reference_agent",
                "cron": "0 0 1 1 *",
                "thread_mode": "reuse",
                "thread_id": thread_id,
                "context": {"model_id": ids[0]},
            },
        )
        response.raise_for_status()
        task_id = response.json()["id"]
    finally:
        app.state.settings.runtime_completion_enabled = True
    async with await psycopg.AsyncConnection.connect(dsn) as connection:
        metadata = (
            await (
                await connection.execute(
                    "SELECT metadata FROM crons WHERE cron_id=%s", (task_id,)
                )
            ).fetchone()
        )[0]
    actor = load_user_actor(
        session_factory=app.state.db_session_factory,
        user_id=metadata["scheduled_owner"],
        project_id=project,
    )
    context = PlatformRequestContext(
        RequestContext(
            str(uuid4()), str(uuid4()), "POST", "/internal/backfill", time.monotonic()
        ),
        TenantContext(metadata["scheduled_tenant"]),
        ProjectContext(project),
        actor,
    )
    request = Request(
        {
            "type": "http",
            "headers": [],
            "app": app,
            "state": {"platform_context": context},
        }
    )
    service = ScheduledTasksService(
        get_runtime_gateway_service(request, actor),
        tenant_id=context.tenant.tenant_id,
        secret=app.state.settings.runtime_delegation_secret,
    )
    spec = importlib.util.spec_from_file_location(
        "live_backfill",
        Path(__file__).resolve().parents[3]
        / "platform-api/scripts/backfill_run_completion_origins.py",
    )
    backfill = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backfill)
    manifest = tmp_path / "private-backfill.json"
    report = await backfill.backfill(service, actor=actor, project_id=project)
    assert {"task_id": task_id, "action": "backfill"} in report
    assert not manifest.exists()
    for _ in range(2):
        report = await backfill.backfill(
            service,
            actor=actor,
            project_id=project,
            action="apply",
            manifest_path=manifest,
        )
        assert {"task_id": task_id, "action": "applied"} in report
    assert manifest.stat().st_mode & 0o777 == 0o600
    origin = json.loads(manifest.read_text())["entries"][task_id]["origin_ref"]
    async with await psycopg.AsyncConnection.connect(dsn) as connection:
        await connection.execute(
            "UPDATE crons SET next_run_date=now()-interval '1 second' WHERE cron_id=%s",
            (task_id,),
        )
    item = await harness.wait_scheduled_run(client, task_id)
    assert item["status"] == "error" and item["thread_id"] == thread_id
    await harness.verify_completion(client, thread_id, item["run_id"], "error")
    await backfill.backfill(
        service,
        actor=actor,
        project_id=project,
        action="revert",
        manifest_path=manifest,
    )
    async with await psycopg.AsyncConnection.connect(dsn) as connection:
        row = (
            await (
                await connection.execute(
                    "SELECT payload FROM crons WHERE cron_id=%s", (task_id,)
                )
            ).fetchone()
        )[0]
        assert not row["__graphharbor_runtime_context"]["auth_user"].get(
            "callback_context"
        )
        await connection.execute(
            "UPDATE crons SET next_run_date=now()-interval '1 second' WHERE cron_id=%s",
            (task_id,),
        )
    async with harness.asyncio.timeout(40):
        while True:
            response = await client.get(f"/api/scheduled-tasks/{task_id}/runs")
            response.raise_for_status()
            reverted = next(
                (
                    value
                    for value in response.json()["items"]
                    if value["run_id"] != item["run_id"] and value["status"] == "error"
                ),
                None,
            )
            if reverted:
                break
            await harness.asyncio.sleep(0.1)
    response = await client.get(
        f"/api/langgraph/threads/{thread_id}/runs/{reverted['run_id']}/completion"
    )
    response.raise_for_status()
    assert response.json()["availability"] == "unsupported"
    response = await client.post(f"/api/scheduled-tasks/{task_id}/pause")
    response.raise_for_status()
    response = await client.delete(f"/api/langgraph/threads/{thread_id}")
    response.raise_for_status()
    response = await client.get(
        f"/api/langgraph/threads/{thread_id}/runs/{item['run_id']}/completion"
    )
    assert response.status_code in {403, 404}
    (tmp_path / "backfill-evidence.json").write_text(
        json.dumps(
            {
                "task_id": task_id,
                "thread_mode": "reuse",
                "origin_ref": origin,
                "dry_run": "no mutation",
                "repeat_apply": "same origin",
                "managed_run": item["run_id"],
                "reverted_run": reverted["run_id"],
                "reverted_availability": "unsupported",
                "thread_delete": response.status_code,
            },
            indent=2,
        )
    )


def test_isolated_completion_platform_runtime_worker(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "completion_worker_harness",
        Path(__file__).with_name("test_model_resilience_worker.py"),
    )
    harness = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(harness)

    async def extensions(*args):
        await verify_completion_extensions(*args, harness)

    harness.verify_completion_extensions = extensions
    harness.test_isolated_platform_worker_preserves_attempt_budget_and_error_stream(
        monkeypatch, tmp_path
    )
