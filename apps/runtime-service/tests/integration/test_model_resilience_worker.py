"""Opt-in isolated Platform/GraphHarbor/SDK integration with synthetic providers.

Run with RUN_MODEL_RESILIENCE_WORKER=1 and both app sources on PYTHONPATH.
Native PostgreSQL and Redis are created on unused ports and stopped in finally.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import socket
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
import pytest
import uvicorn
from cryptography.fernet import Fernet
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_MODEL_RESILIENCE_WORKER") != "1",
        reason="isolated native Worker integration opt-in",
    ),
]
ROOT = Path(__file__).resolve().parents[2]
SECRET = "resilience-isolated-runtime-secret-32-bytes"


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def wait_ready(client, path, process=None):
    async with asyncio.timeout(180):
        while True:
            if process is not None and process.returncode is not None:
                raise AssertionError("isolated service exited; inspect fixture logs")
            try:
                if (await client.get(path)).is_success:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(0.2)


async def start_process(command, *, directory, env, processes, log):
    process = await asyncio.create_subprocess_exec(
        *command, cwd=directory, env=env, stdout=log, stderr=log
    )
    processes.append(process)
    return process


async def stop_processes(processes):
    for process in reversed(processes):
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 15)
            except TimeoutError:
                process.kill()
                await process.wait()


async def wait_database(dsn, process):
    async with asyncio.timeout(30):
        while True:
            assert process.returncode is None, "isolated PostgreSQL exited"
            try:
                async with await psycopg.AsyncConnection.connect(
                    dsn, connect_timeout=1
                ):
                    return
            except psycopg.OperationalError:
                await asyncio.sleep(0.1)


def install_provider(app, calls):
    @app.post("/fixture/v1/chat/completions")
    async def complete(request: Request):
        body = await request.json()
        scenario = next(
            message["content"]
            for message in body["messages"]
            if message["role"] == "user"
        )
        candidate = body["model"]
        calls.setdefault(scenario, []).append(candidate)
        if (
            scenario in {"exhausted", "budget"}
            or (candidate == "primary" and scenario in {"fallback", "tool"})
            or (scenario == "recover" and len(calls[scenario]) <= 2)
        ):
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "message": "private-provider-detail",
                        "type": "server_error",
                        "code": "overloaded",
                    }
                },
                headers={"retry-after": "100"} if scenario == "budget" else None,
            )

        async def stream():
            if scenario in {"slow", "cancel", "queue-blocker"}:
                await asyncio.sleep(12)
            delta = {"role": "assistant", "content": "answer " + candidate}
            tool = scenario == "tool" and not any(
                message["role"] == "tool" for message in body["messages"]
            )
            if tool:
                delta = {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "toolu_once",
                            "type": "function",
                            "function": {
                                "name": "read_reference",
                                "arguments": '{"topic":"fixture"}',
                            },
                        }
                    ],
                }
            if scenario == "empty" and candidate == "primary":
                delta = {"role": "assistant", "content": ""}
            if scenario == "reasoning":
                delta = {
                    "role": "assistant",
                    "content": "",
                    "reasoning_content": "partial thought",
                }
            if scenario == "tool_partial":
                delta = {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": "partial-call",
                            "type": "function",
                            "function": {
                                "name": "read_reference",
                                "arguments": '{"topic":',
                            },
                        }
                    ],
                }
            chunk = {
                "id": "synthetic-" + scenario + "-" + candidate,
                "object": "chat.completion.chunk",
                "model": candidate,
                "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
            }
            yield "data: " + json.dumps(chunk) + "\n\n"
            if scenario in {"partial", "reasoning", "tool_partial"} or (
                scenario == "empty" and candidate == "primary"
            ):
                raise RuntimeError("synthetic connection reset")
            chunk["choices"] = [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "tool_calls" if tool else "stop",
                }
            ]
            yield "data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")


async def prepare_platform(app, client):
    from platform_api.modules.iam.domain import ProjectRole
    from platform_api.modules.identity.repository import SqlAlchemyIdentityRepository
    from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository

    with app.state.db_session_factory.begin() as session:
        projects = SqlAlchemyProjectsRepository(session)
        tenant = projects.get_or_create_default_tenant()
        project = projects.create_project(
            tenant_id=tenant.id, name="Resilience fixture", description="isolated"
        )
        admin = SqlAlchemyIdentityRepository(session).get_user_by_username(
            "resilience-admin"
        )
        projects.upsert_project_member(
            project_id=project.id, user_id=admin.id, role=ProjectRole.ADMIN
        )
        project_id = str(project.id)
    response = await client.post(
        "/api/identity/session",
        json={
            "username": "resilience-admin",
            "password": "Resilience-fixture-only-2026!",
        },
    )
    response.raise_for_status()
    client.headers.update(
        {
            "authorization": "Bearer " + response.json()["tokens"]["access_token"],
            "x-project-id": project_id,
        }
    )
    return project_id


async def create_managed_agent(app, client, project, platform_url):
    from uuid import UUID

    from platform_api.modules.runtime_catalog.infra.sqlalchemy.repository import (
        SqlAlchemyRuntimeCatalogRepository,
    )

    response = await client.post("/api/runtime/graphs/refresh")
    response.raise_for_status()
    ids = []
    for name in ("primary", "backup"):
        response = await client.post(
            "/api/runtime/models",
            json={
                "provider": "openai",
                "display_name": name,
                "model": name,
                "protocol": "openai",
                "base_url": "https://provider.invalid/v1",
                "api_key": "synthetic-key-" + name,
                "scope_type": "project",
                "project_id": project,
            },
        )
        response.raise_for_status()
        ids.append(response.json()["id"])
    # Loopback is fixture-only; production management must keep rejecting it.
    with app.state.db_session_factory.begin() as session:
        for model_id in ids:
            SqlAlchemyRuntimeCatalogRepository(session).update_configured_model(
                UUID(model_id), values={"base_url": platform_url + "/fixture/v1"}
            )
    policy = {
        "enabled": True,
        "fallback_model_id": ids[1],
        "max_attempts": 3,
        "attempt_timeout_seconds": 1,
        "total_timeout_seconds": 5,
    }
    response = await client.post(
        f"/api/projects/{project}/agents",
        json={
            "name": "Resilience fixture",
            "graph_id": "reference_agent",
            "context": {"model_id": ids[0]},
            "model_resilience": policy,
        },
    )
    response.raise_for_status()
    return response.json(), ids


async def run_scenario(client, scenario, model_id, calls, dsn):
    cancel_observation = {}
    response = await client.post(
        "/api/langgraph/threads", json={"metadata": {"graph_id": "reference_agent"}}
    )
    response.raise_for_status()
    thread_id = response.json()["thread_id"]
    path = f"/api/langgraph/threads/{thread_id}"
    response = await client.post(
        path + "/runs",
        json={
            "assistant_id": "reference_agent",
            "context": {"model_id": model_id},
            "input": {"messages": [{"role": "user", "content": scenario}]},
        },
        headers={"Idempotency-Key": str(uuid4())},
    )
    response.raise_for_status()
    run_id = response.json()["run_id"]
    if scenario == "cancel":
        async with asyncio.timeout(60):
            while not calls.get(scenario):
                await asyncio.sleep(0.02)
        cancel_path = path + "/runs/" + run_id + "/cancel"
        response = await client.post(cancel_path, json={"wait": False})
        response.raise_for_status()
        cancel_ack_at = time.monotonic()
        cancel_observation["provider_calls_at_ack"] = list(calls[scenario])
        response = await client.post(cancel_path, json={"wait": True})
        response.raise_for_status()
        cancel_observation["provider_calls_at_stop_confirmation"] = list(
            calls[scenario]
        )
        async with await psycopg.AsyncConnection.connect(dsn) as connection:
            row = await (
                await connection.execute(
                    "SELECT r.lease_owner, e.payload, e.created_at FROM runs r "
                    "JOIN runtime_events e ON e.run_id=r.run_id AND e.terminal=true "
                    "WHERE r.run_id=%s",
                    (run_id,),
                )
            ).fetchone()
        assert (
            row is not None and row[0] is None and row[1]["execution_stopped"] is True
        )
        cancel_observation["terminal_execution_stopped"] = row[1]["execution_stopped"]
        cancel_observation["terminal_committed_at"] = row[2].isoformat()
        cancel_observation["ack_to_lease_release_seconds"] = round(
            time.monotonic() - cancel_ack_at, 3
        )
        await asyncio.sleep(0.1)
    async with asyncio.timeout(30):
        while True:
            run = await client.get(path + "/runs/" + run_id)
            run.raise_for_status()
            if run.json()["status"] not in {"pending", "running"}:
                break
            await asyncio.sleep(0.1)
    events = await client.get(
        path + "/runs/" + run_id + "/stream", params={"cancel_on_disconnect": "false"}
    )
    events.raise_for_status()
    state = await client.get(path + "/state")
    state.raise_for_status()
    run_snapshot = run.json()
    if cancel_observation:
        run_snapshot["_fixture_cancel"] = cancel_observation
    return run_id, run_snapshot, events.text, state.json()


def error_samples(events):
    samples = []
    for line in events.splitlines():
        if line.startswith("data: "):
            event = json.loads(line[6:])
            payload = event.get("params", {}).get("data", {})
            if event.get("method") == "error" or (
                event.get("method") == "lifecycle" and payload.get("status") == "error"
            ):
                samples.append(payload)
    return samples


async def verify_scenarios(client, dsn, calls, ids, agent, tmp_path):
    evidence = []
    scenarios = (
        ("fallback", "success", None, ["primary", "backup"]),
        ("recover", "success", None, ["primary", "backup", "primary"]),
        (
            "exhausted",
            "error",
            "runtime.model.retry_exhausted",
            ["primary", "backup", "primary"],
        ),
        ("partial", "error", "runtime.model.stream_interrupted", ["primary"]),
        ("reasoning", "error", "runtime.model.stream_interrupted", ["primary"]),
        ("tool_partial", "error", "runtime.model.stream_interrupted", ["primary"]),
        (
            "slow",
            "error",
            "runtime.model.retry_exhausted",
            ["primary", "backup", "primary"],
        ),
        (
            "budget",
            "error",
            "runtime.model.retry_budget_exceeded",
            ["primary", "backup"],
        ),
        ("cancel", "interrupted", None, ["primary"]),
        ("empty", "success", None, ["primary", "backup"]),
        ("tool", "success", None, ["primary", "backup", "primary", "backup"]),
    )
    selected = set(
        filter(None, os.getenv("MODEL_RESILIENCE_WORKER_SCENARIOS", "").split(","))
    )
    if selected:
        assert selected <= {scenario[0] for scenario in scenarios}, selected
        scenarios = tuple(scenario for scenario in scenarios if scenario[0] in selected)
    for scenario, status, code, expected in scenarios:
        if scenario == "cancel":
            response = await client.patch(
                "/api/agents/" + agent["id"],
                json={
                    "model_resilience": {
                        **agent["model_resilience"],
                        "attempt_timeout_seconds": 5,
                        "total_timeout_seconds": 10,
                    }
                },
            )
            response.raise_for_status()
        started = time.monotonic()
        run_id, run, events, state = await run_scenario(
            client, scenario, ids[0], calls, dsn
        )
        assert run["status"] == status, (scenario, run, events[-3000:])
        with psycopg.connect(dsn) as connection:
            attempts = connection.execute(
                "SELECT retry_count FROM runs WHERE run_id=%s", (run_id,)
            ).fetchone()[0]
        # GraphHarbor increments retry_count on the first lease acquisition too.
        assert attempts == 1, (scenario, calls)
        assert "private-provider-detail" not in events and "synthetic-key" not in str(
            (run, events, state)
        )
        assert "runtime_model_ref" not in str((run, events, state))
        messages = state["values"].get("messages", [])
        summary = None
        if code:
            assert code in events, (scenario, events[-2000:])
        elif status == "success":
            summary = messages[-1]["response_metadata"]["platform_model_resilience"]
            effective = ids[0] if scenario == "recover" else ids[1]
            assert summary["effective_model_id"] == effective
            assert summary["fallback_used"] == (effective != ids[0])
            assert summary["attempts"] == (3 if scenario == "recover" else 2)
        if scenario == "tool":
            assert sum(message.get("type") == "tool" for message in messages) == 1
            assert (
                sum(
                    call["id"] == "toolu_once"
                    for message in messages
                    for call in message.get("tool_calls", [])
                )
                == 1
            )
        if scenario == "empty":
            assert sum(message.get("type") == "ai" for message in messages) == 1
        if scenario == "cancel":
            (tmp_path / "cancel-evidence.json").write_text(
                json.dumps(
                    {
                        "scenario": scenario,
                        "run_id": run_id,
                        "status": status,
                        "provider_calls": list(calls[scenario]),
                        "duration_seconds": round(time.monotonic() - started, 3),
                        "worker_lease_released": True,
                        "worker_heartbeat_setting": (
                            os.getenv("MODEL_RESILIENCE_WORKER_HEARTBEAT", "1")
                        ),
                        **run["_fixture_cancel"],
                    },
                    indent=2,
                )
            )
        assert calls[scenario] == expected, (scenario, calls[scenario], expected)
        samples = error_samples(events)
        if code:
            assert samples and samples[-1]["error"] == {
                "type": "RuntimeResolutionError",
                "message": code,
            }, events[-2000:]
        evidence.append(
            {
                "scenario": scenario,
                "run_id": run_id,
                "status": status,
                "provider_calls": list(calls[scenario]),
                "worker_attempts": attempts,
                "duration_seconds": round(time.monotonic() - started, 3),
                "summary": summary,
                "error_events": samples,
            }
        )
        if scenario == "cancel":
            response = await client.patch(
                "/api/agents/" + agent["id"],
                json={"model_resilience": agent["model_resilience"]},
            )
            response.raise_for_status()
    response = await client.patch(
        "/api/agents/" + agent["id"], json={"model_resilience": None}
    )
    response.raise_for_status()
    assert not response.json()["model_resilience"]["enabled"]
    _, run, _, state = await run_scenario(client, "disabled", ids[0], calls, dsn)
    assert run["status"] == "success" and calls["disabled"] == ["primary"]
    assert (
        "platform_model_resilience"
        not in state["values"]["messages"][-1]["response_metadata"]
    )
    (tmp_path / "evidence.json").write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence))


async def wait_scheduled_run(client, task_id, run_id=None):
    async with asyncio.timeout(30):
        while True:
            response = await client.get(f"/api/scheduled-tasks/{task_id}/runs")
            response.raise_for_status()
            item = next(
                (
                    item
                    for item in response.json()["items"]
                    if run_id is None or item["run_id"] == run_id
                ),
                None,
            )
            if item and item["status"] not in {"pending", "running"}:
                return item
            await asyncio.sleep(0.1)


async def verify_scheduled(client, agent, ids, calls, tmp_path, project, dsn):
    response = await client.patch(
        "/api/agents/" + agent["id"],
        json={"model_resilience": agent["model_resilience"]},
    )
    response.raise_for_status()
    evidence = []
    for trigger in ("manual", "scheduled", "cron"):
        for scenario, status, code, expected in (
            ("fallback", "success", None, ["primary", "backup"]),
            (
                "exhausted",
                "error",
                "scheduled_task_execution_failed",
                ["primary", "backup", "primary"],
            ),
        ):
            before = len(calls.get(scenario, []))
            task_id = await create_scheduled_task(client, scenario, ids[0], trigger)
            run_id = None
            if trigger == "cron":
                async with await psycopg.AsyncConnection.connect(dsn) as connection:
                    await connection.execute(
                        "UPDATE crons SET next_run_date=now()-interval '1 second' WHERE cron_id=%s",
                        (task_id,),
                    )
            if trigger == "manual":
                response = await client.post(
                    f"/api/scheduled-tasks/{task_id}/trigger",
                    headers={"Idempotency-Key": "scheduled-fixture"},
                )
                response.raise_for_status()
                run_id = response.json()["run_id"]
            item = await wait_scheduled_run(client, task_id, run_id)
            assert item["status"] == status, item
            if code:
                assert item["error_code"] == code, item
            actual = calls[scenario][before:]
            assert actual == expected
            evidence.append(
                {
                    "trigger": trigger,
                    "scenario": scenario,
                    "status": status,
                    "run_id": item["run_id"],
                    "error_code": item.get("error_code"),
                    "provider_calls": actual,
                }
            )
            response = await client.post(f"/api/scheduled-tasks/{task_id}/pause")
            response.raise_for_status()
    task_id = await create_scheduled_task(
        client, "backup-disabled", ids[0], "scheduled"
    )
    response = await client.patch(
        "/api/runtime/models/" + ids[1], json={"enabled": False}
    )
    response.raise_for_status()
    item = await wait_scheduled_run(client, task_id)
    assert item["status"] == "error" and not calls.get("backup-disabled"), item
    evidence.append(
        {
            "trigger": "scheduled",
            "scenario": "backup-disabled",
            "status": item["status"],
            "error_code": item.get("error_code"),
            "provider_calls": [],
        }
    )
    response = await client.patch(
        "/api/runtime/models/" + ids[1], json={"enabled": True}
    )
    response.raise_for_status()
    headers = await service_account_headers(client, project)
    async with httpx.AsyncClient(
        base_url=client.base_url, headers=headers, timeout=35, trust_env=False
    ) as machine:
        response = await machine.patch(
            "/api/agents/" + agent["id"], json={"model_resilience": None}
        )
        # Existing Agent management requires a user ID; machine execution is separate.
        assert (
            response.status_code == 401
            and response.json()["error"]["code"] == "not_authenticated"
        )
        before = len(calls["fallback"])
        task_id = await create_scheduled_task(machine, "fallback", ids[0], "scheduled")
        item = await wait_scheduled_run(machine, task_id)
        assert item["status"] == "success", item
        actual = calls["fallback"][before:]
        assert actual == ["primary", "backup"]
        evidence.append(
            {
                "trigger": "scheduled",
                "actor": "service_account",
                "scenario": "fallback",
                "status": item["status"],
                "provider_calls": actual,
            }
        )
    (tmp_path / "scheduled-evidence.json").write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence))


async def create_scheduled_task(client, scenario, primary_id, trigger):
    schedule = (
        {"cron": "0 0 1 1 *"}
        if trigger in {"manual", "cron"}
        else {
            "schedule_type": "once",
            "run_at": (datetime.now(UTC) + timedelta(seconds=3))
            .replace(microsecond=0)
            .isoformat(),
        }
    )
    response = await client.post(
        "/api/scheduled-tasks",
        json={
            "title": "Resilience fixture",
            "prompt": scenario,
            "agent_key": "reference_agent",
            "context": {"model_id": primary_id},
            **schedule,
        },
    )
    response.raise_for_status()
    return response.json()["id"]


async def service_account_headers(client, project):
    response = await client.post(
        "/api/service-accounts",
        json={"name": "resilience-machine", "platform_roles": ["platform_viewer"]},
    )
    response.raise_for_status()
    account_id = response.json()["id"]
    response = await client.post(
        f"/api/service-accounts/{account_id}/tokens", json={"name": "resilience"}
    )
    response.raise_for_status()
    credential = response.json()["plain_text_token"]
    response = await client.put(
        f"/api/service-accounts/{account_id}/project-grants/{project}",
        json={"role": "project_executor"},
    )
    response.raise_for_status()
    return {
        "authorization": "",
        "x-platform-api-key": credential,
        "x-project-id": project,
    }


async def verify_expired_queue(client, agent, ids, calls, dsn, monkeypatch, tmp_path):
    from platform_api.modules.runtime_gateway.application import service

    original = service.create_model_reference
    monkeypatch.setattr(
        service,
        "create_model_reference",
        lambda **kwargs: original(**{**kwargs, "ttl_seconds": 10}),
    )
    response = await client.patch(
        "/api/agents/" + agent["id"],
        json={
            "model_resilience": {
                **agent["model_resilience"],
                "attempt_timeout_seconds": 20,
                "total_timeout_seconds": 25,
            }
        },
    )
    response.raise_for_status()
    blocker = asyncio.create_task(
        run_scenario(client, "queue-blocker", ids[0], calls, dsn)
    )
    try:
        async with asyncio.timeout(10):
            while not calls.get("queue-blocker"):
                await asyncio.sleep(0.02)
        before = len(calls["fallback"])
        started = time.monotonic()
        run_id, run, _, state = await run_scenario(
            client, "fallback", ids[0], calls, dsn
        )
        elapsed = time.monotonic() - started
        assert elapsed > 10 and run["status"] == "success"
        assert calls["fallback"][before:] == ["primary", "backup"]
        assert (await blocker)[1]["status"] == "success"
        summary = state["values"]["messages"][-1]["response_metadata"][
            "platform_model_resilience"
        ]
        assert summary["attempts"] == 2
        evidence = {
            "scenario": "expired-reference-queue",
            "run_id": run_id,
            "status": run["status"],
            "reference_ttl_seconds": 10,
            "duration_seconds": round(elapsed, 3),
            "provider_calls": calls["fallback"][before:],
            "summary": summary,
        }
        (tmp_path / "queue-evidence.json").write_text(json.dumps(evidence, indent=2))
        print(json.dumps(evidence))
        return run_id
    finally:
        if not blocker.done():
            blocker.cancel()
            await asyncio.gather(blocker, return_exceptions=True)
        monkeypatch.setattr(service, "create_model_reference", original)
        response = await client.patch(
            "/api/agents/" + agent["id"],
            json={"model_resilience": agent["model_resilience"]},
        )
        response.raise_for_status()


def test_isolated_platform_worker_preserves_attempt_budget_and_error_stream(
    monkeypatch, tmp_path
):
    from platform_api import main
    from platform_api.config import Settings

    for executable in ("initdb", "postgres", "redis-server"):
        assert shutil.which(executable), executable + " is required"
    pg_port, redis_port, runtime_port, platform_port, provider_port = [
        free_port() for _ in range(5)
    ]
    platform_url = f"http://127.0.0.1:{platform_port}"
    provider_url = f"http://127.0.0.1:{provider_port}"
    runtime_url = f"http://127.0.0.1:{runtime_port}"
    dsn = f"postgresql://resilience@127.0.0.1:{pg_port}/postgres"
    settings = Settings(
        _env_file=None,
        platform_db_enabled=True,
        platform_db_auto_create=True,
        database_url=f"sqlite:///{tmp_path / 'platform.db'}",
        bootstrap_admin_enabled=True,
        bootstrap_admin_username="resilience-admin",
        bootstrap_admin_password="Resilience-fixture-only-2026!",
        runtime_delegation_secret=SECRET,
        runtime_model_config_secret=SECRET,
        model_config_master_key=Fernet.generate_key().decode(),
        jwt_access_secret="fixture-access-secret-at-least-32-bytes",
        jwt_refresh_secret="fixture-refresh-secret-at-least-32-bytes",
        langgraph_upstream_url=runtime_url,
    )
    monkeypatch.setattr(main, "load_dotenv", lambda: None)
    monkeypatch.setattr(main, "load_settings", lambda: settings)
    app = main.create_app()
    calls = {}
    provider_app = FastAPI()
    install_provider(provider_app, calls)
    config = ROOT / f".model-resilience-worker-{uuid4().hex}.json"
    config.write_text(
        json.dumps(
            {
                "dependencies": ["."],
                "graphs": {
                    "reference_agent": "src/runtime_service/graphs/reference_agent.py:get_agent"
                },
                "auth": {"path": "src/runtime_service/auth/platform.py:auth"},
                "http": {
                    "app": "src/runtime_service/webapp.py:app",
                    "disable_mcp": True,
                },
            }
        )
    )
    env = {
        key: os.environ[key] for key in ("PATH", "HOME", "LANG") if key in os.environ
    }
    env.update(
        PYTHONPATH=os.pathsep.join((str(ROOT / "src"), os.getenv("PYTHONPATH", ""))),
        DATABASE_URI=dsn,
        REDIS_URI=f"redis://127.0.0.1:{redis_port}/0",
        GRAPHHARBOR_ENV="development",
        LG_RUNTIME_PG_AUTO_MIGRATE="false",
        GRAPHHARBOR_REDIS_PREFIX="resilience-fixture",
        GRAPHHARBOR_RUNTIME_CONTEXT_SECRET=SECRET,
        PLATFORM_RUNTIME_DELEGATION_SECRET=SECRET,
        PLATFORM_RUNTIME_DELEGATION_ISSUER="platform-api",
        PLATFORM_RUNTIME_DELEGATION_AUDIENCE="runtime-service",
        PLATFORM_RUNTIME_MODEL_CONFIG_URL=platform_url
        + "/api/runtime/internal/model-config",
        PLATFORM_THREAD_AUTHORIZATION_URL=platform_url
        + "/api/runtime/internal/thread-authorization",
        LANGFUSE_ENABLED="false",
        OTEL_ENABLED="false",
    )
    heartbeat = os.getenv("MODEL_RESILIENCE_WORKER_HEARTBEAT", "1")
    if heartbeat != "default":
        env["LG_BG_JOB_HEARTBEAT"] = heartbeat

    async def run():
        processes = []
        server = uvicorn.Server(
            uvicorn.Config(
                app, host="127.0.0.1", port=platform_port, log_level="critical"
            )
        )
        provider = uvicorn.Server(
            uvicorn.Config(
                provider_app, host="127.0.0.1", port=provider_port, log_level="critical"
            )
        )
        platform_task = None
        provider_task = None
        with (tmp_path / "services.log").open("w") as log:
            try:
                init = await start_process(
                    [
                        "initdb",
                        "-D",
                        str(tmp_path / "pg"),
                        "-U",
                        "resilience",
                        "-A",
                        "trust",
                        "--no-locale",
                        "-E",
                        "UTF8",
                    ],
                    directory=tmp_path,
                    env=env,
                    processes=processes,
                    log=log,
                )
                assert await init.wait() == 0
                postgres = await start_process(
                    [
                        "postgres",
                        "-D",
                        str(tmp_path / "pg"),
                        "-h",
                        "127.0.0.1",
                        "-p",
                        str(pg_port),
                        "-k",
                        "",
                    ],
                    directory=tmp_path,
                    env=env,
                    processes=processes,
                    log=log,
                )
                await start_process(
                    [
                        "redis-server",
                        "--bind",
                        "127.0.0.1",
                        "--port",
                        str(redis_port),
                        "--save",
                        "",
                        "--appendonly",
                        "no",
                    ],
                    directory=tmp_path,
                    env=env,
                    processes=processes,
                    log=log,
                )
                await wait_database(dsn, postgres)
                migration = await start_process(
                    [sys.executable, "-m", "langhost.cli", "migrate"],
                    directory=tmp_path,
                    env=env,
                    processes=processes,
                    log=log,
                )
                assert await migration.wait() == 0, "isolation migration failed"
                from runtime_service.db import upgrade

                await asyncio.to_thread(upgrade, dsn)
                platform_task = asyncio.create_task(server.serve())
                provider_task = asyncio.create_task(provider.serve())
                runtime = await start_process(
                    [
                        sys.executable,
                        "-m",
                        "langhost.cli",
                        "serve",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(runtime_port),
                        "--config",
                        str(config),
                        "--server-log-level",
                        "warning",
                    ],
                    directory=tmp_path,
                    env=env,
                    processes=processes,
                    log=log,
                )
                worker = await start_process(
                    [
                        sys.executable,
                        "-m",
                        "langhost.cli",
                        "worker",
                        "--config",
                        str(config),
                        "--n-jobs-per-worker",
                        "1",
                    ],
                    directory=tmp_path,
                    env=env,
                    processes=processes,
                    log=log,
                )
                async with (
                    httpx.AsyncClient(
                        base_url=platform_url, timeout=35, trust_env=False
                    ) as client,
                    httpx.AsyncClient(
                        base_url=runtime_url, timeout=2, trust_env=False
                    ) as runtime_client,
                ):
                    await wait_ready(client, "/docs")
                    await wait_ready(runtime_client, "/ready", runtime)
                    project = await prepare_platform(app, client)
                    agent, ids = await create_managed_agent(
                        app, client, project, provider_url
                    )
                    await verify_scenarios(client, dsn, calls, ids, agent, tmp_path)
                    if os.getenv("MODEL_RESILIENCE_WORKER_SCENARIOS"):
                        return
                    await verify_scheduled(
                        client, agent, ids, calls, tmp_path, project, dsn
                    )
                    retained_run = await verify_expired_queue(
                        client, agent, ids, calls, dsn, monkeypatch, tmp_path
                    )
                    worker.terminate()
                    assert await worker.wait() == 0
                    await start_process(
                        [
                            sys.executable,
                            "-m",
                            "langhost.cli",
                            "worker",
                            "--config",
                            str(config),
                            "--n-jobs-per-worker",
                            "1",
                        ],
                        directory=tmp_path,
                        env=env,
                        processes=processes,
                        log=log,
                    )
                    before = len(calls.get("after-restart", []))
                    _, run, _, state = await run_scenario(
                        client, "after-restart", ids[0], calls, dsn
                    )
                    assert (
                        run["status"] == "success"
                        and len(calls["after-restart"]) == before + 1
                    )
                    with psycopg.connect(dsn) as connection:
                        assert (
                            connection.execute(
                                "SELECT status FROM runs WHERE run_id=%s",
                                (retained_run,),
                            ).fetchone()[0]
                            == "success"
                        )
                    (tmp_path / "restart-evidence.json").write_text(
                        json.dumps(
                            {
                                "retained_run_id": retained_run,
                                "status_after_restart": "success",
                                "new_run_status": run["status"],
                                "new_run_summary": state["values"]["messages"][-1][
                                    "response_metadata"
                                ]["platform_model_resilience"],
                            },
                            indent=2,
                        )
                    )
            finally:
                await stop_processes(processes)
                server.should_exit = True
                provider.should_exit = True
                if platform_task:
                    await asyncio.wait_for(platform_task, 15)
                if provider_task:
                    await asyncio.wait_for(provider_task, 15)
                config.unlink(missing_ok=True)

    asyncio.run(run())
