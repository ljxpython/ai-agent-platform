import asyncio
import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import httpx
from fastapi import FastAPI

from runtime_service.http import diagnostics
from runtime_service.observability import execution_evidence as module


def test_execution_receipt_is_server_scoped_and_insert_only(monkeypatch):
    run, thread, attempt = (str(uuid4()) for _ in range(3))
    facts = NS(
        principal=NS(tenant_id="tenant", project_id="project"),
        context_hash="context",
        scope=NS(operation="run-create", thread_id=thread, assistant_id="agent"),
    )
    connection = MagicMock()
    monkeypatch.setattr(
        module,
        "runtime_config_snapshot",
        lambda resolved: {"config_hash": resolved.config_hash},
    )
    connection.__enter__().execute().fetchone.return_value = {
        "metadata": {"evaluation_attempt_id": attempt}
    }
    connection.reset_mock()
    monkeypatch.setattr(module, "connect", lambda connection=connection: connection)
    config = {
        "configurable": {"thread_id": thread},
        "metadata": {
            "run_id": run,
            "evaluation_attempt_id": attempt,
            "platform_build": {"package_sha256": "api"},
        },
    }
    module.record_execution(config, NS(config_hash="effective"), facts, "agent")
    connection.__enter__.assert_not_called()
    monkeypatch.setenv("RUNTIME_EVALUATION_EVIDENCE_ENABLED", "1")
    module.record_execution(config, NS(config_hash="effective"), facts, "agent")
    sql, params = connection.__enter__().execute.call_args.args
    assert "ON CONFLICT DO NOTHING" in sql
    assert params[:6] == ("tenant", "project", thread, run, "agent", attempt)
    assert json.loads(params[6])["runtime"] == module.STARTUP_MANIFEST
    assert params[-2:] == ("context", "effective")
    connection.reset_mock()
    config["configurable"]["thread_id"] = str(uuid4())
    module.record_execution(config, NS(config_hash="effective"), facts, "agent")
    connection.__enter__.assert_not_called()


def test_receipt_route_checks_scope_and_current_acl(monkeypatch):
    thread, run = str(uuid4()), str(uuid4())
    scope = {
        "operation": "diagnostics-read",
        "thread_id": thread,
        "assistant_id": "agent",
        "tenant_id": "t",
        "project_id": "p",
    }
    facts = {
        "runtime_scope": scope,
        "runtime_principal": {"tenant_id": "t", "project_id": "p"},
    }
    monkeypatch.setattr(diagnostics, "authenticate", AsyncMock(return_value=facts))
    acl = AsyncMock()
    monkeypatch.setattr(diagnostics, "authorize_thread_targets", acl)
    read = MagicMock(
        return_value={"run_id": run, "thread_id": thread, "graph_id": "agent"}
    )
    monkeypatch.setattr(module, "read_execution", read)
    app = FastAPI()
    app.include_router(diagnostics.router)

    async def check():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            url = f"/internal/threads/{thread}/runs/{run}/execution-evidence"
            response = await client.get(url)
            assert (
                response.status_code == 200
                and response.headers["cache-control"] == "no-store"
            )
            read.assert_called_once_with("t", "p", thread, run)
            for field, value in [
                ("operation", "run-create"),
                ("thread_id", str(uuid4())),
                ("project_id", "other"),
            ]:
                original = scope[field]
                scope[field] = value
                read.reset_mock()
                assert (await client.get(url)).status_code == 403
                read.assert_not_called()
                scope[field] = original
            read.return_value = None
            assert (await client.get(url)).status_code == 404

    asyncio.run(check())
    assert acl.await_count == 2


def test_source_snapshot_is_hidden_after_capture_replaced_or_revoked(monkeypatch):
    from datetime import UTC, datetime, timedelta

    expiry = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    for capture in [
        None,
        {"id": "new-capture", "expires_at": expiry},
        {"id": "old-capture", "expires_at": expiry},
    ]:
        row = {
            "run_id": "run",
            "thread_id": "thread",
            "attempt_id": "attempt",
            "recorded_at": "now",
            "manifest": {
                "environment": {
                    "capture_id": "old-capture",
                    "expires_at": expiry,
                    "initial_files": {"a.txt": "data"},
                }
            },
        }
        connection = MagicMock()
        connection.__enter__().execute().fetchone.side_effect = [
            row,
            {"metadata": {"evaluation_material_capture": capture}},
        ]
        monkeypatch.setattr(module, "connect", lambda connection=connection: connection)
        observed = module.read_execution("tenant", "project", "thread", "run")
        assert ("environment" in observed["manifest"]) == bool(
            capture and capture["id"] == "old-capture"
        )
