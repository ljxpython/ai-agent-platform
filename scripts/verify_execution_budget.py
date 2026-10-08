"""Opt-in isolated PostgreSQL/Redis Worker and platform HTTP budget verification."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
from uuid import UUID, uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from scripts.verify_agent_observability import ROOT, interrupt_id, serve

SECRET = "isolated-execution-budget-verification-secret-32"


def frames(text):
    result = []
    for frame in text.replace("\r\n", "\n").split("\n\n"):
        data = "\n".join(
            line[5:].strip() for line in frame.splitlines() if line.startswith("data:")
        )
        if data:
            result.append(json.loads(data))
    return result


def notices(text):
    return [
        item["params"]["data"] if "method" in item else item
        for item in frames(text)
        if isinstance(item, dict)
        and (
            item.get("method") == "custom"
            or item.get("type") == "runtime_budget_notice"
        )
        and (item.get("params", {}).get("data", item) or {}).get("type")
        == "runtime_budget_notice"
    ]


def transport_samples(text):
    samples = []
    for frame in text.replace("\r\n", "\n").split("\n\n"):
        payloads = frames(frame)
        if not payloads or not isinstance(payloads[0], dict):
            continue
        payload = payloads[0]
        typed = isinstance(payload.get("params"), dict)
        params = payload.get("params", {})
        data = params.get("data") if typed else payload
        if not isinstance(data, dict):
            continue
        if data.get("type") == "runtime_budget_notice":
            selected = data
        elif isinstance(data.get("error"), dict) and "code" in data["error"]:
            selected = {
                key: data[key]
                for key in ("event", "status", "reason", "error")
                if key in data
            }
        elif str(data.get("code", "")).startswith("runtime_"):
            selected = data
        else:
            continue
        if typed:
            selected = {
                "method": payload.get("method"),
                "params": {
                    key: params[key]
                    for key in ("namespace", "run_id", "seq")
                    if key in params
                }
                | {"data": selected},
            }
        samples.append(
            {
                "event": next(
                    (
                        line[6:].strip()
                        for line in frame.splitlines()
                        if line.startswith("event:")
                    ),
                    None,
                ),
                "id": next(
                    (
                        line[3:].strip()
                        for line in frame.splitlines()
                        if line.startswith("id:")
                    ),
                    None,
                ),
                "payload": selected,
            }
        )
    return samples


async def main():
    import asyncpg
    from cryptography.fernet import Fernet
    from dotenv import dotenv_values
    from langgraph_runtime_pg.migrate import upgrade_head
    from langgraph_runtime_pg.production_worker import ProductionWorker
    from langhost.server import create_app as runtime_app
    from platform_api.core.context.models import ActorContext
    from platform_api.core.db import session_scope
    from platform_api.core.security import create_access_token, hash_password
    from platform_api.main import create_app
    from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
    from platform_api.modules.iam.domain import ProjectRole
    from platform_api.modules.identity.repository import SqlAlchemyIdentityRepository
    from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
    from platform_api.modules.runtime_catalog.application.credentials import (
        encrypt_api_key,
    )
    from platform_api.modules.runtime_catalog.infra.sqlalchemy.models import (
        RuntimeCatalogModelRecord,
    )
    from platform_api.modules.runtime_gateway.application import thread_access
    from runtime_service import webapp
    from runtime_service.db import upgrade as upgrade_application

    model_env = os.getenv("BUDGET_MODEL_ENV_FILE")
    source = dotenv_values(model_env) if model_env else {}

    suffix = uuid4().hex[:12]
    database = f"graphharbor_budget_{suffix}"
    admin_dsn = os.getenv(
        "BUDGET_POSTGRES_ADMIN_DSN", "postgresql://127.0.0.1:5432/postgres"
    )
    connection = await asyncpg.connect(admin_dsn, timeout=10)
    try:
        await connection.execute(f'CREATE DATABASE "{database}"')
    finally:
        await connection.close()
    os.environ.update(
        {
            "DATABASE_URI": admin_dsn.rsplit("/", 1)[0] + "/" + database,
            "REDIS_URI": os.getenv("BUDGET_REDIS_URI", "redis://127.0.0.1:6379/0"),
            "GRAPHHARBOR_REDIS_PREFIX": f"graphharbor:budget:{suffix}",
            "GRAPHHARBOR_ENV": "production",
            "PLATFORM_RUNTIME_DELEGATION_SECRET": SECRET,
            "PLATFORM_RUNTIME_DELEGATION_ISSUER": "platform-api",
            "PLATFORM_RUNTIME_DELEGATION_AUDIENCE": "runtime-service",
            "GRAPHHARBOR_RUNTIME_CONTEXT_SECRET": SECRET,
            "GRAPHHARBOR_RUNTIME_CONTEXT_ISSUER": "graphharbor",
            "GRAPHHARBOR_RUNTIME_CONTEXT_AUDIENCE": "graphharbor-worker",
            "LANGFUSE_ENABLED": "false",
            "OTEL_ENABLED": "false",
            "RUNTIME_BACKEND": "local",
            "RUNTIME_DEAR_GOVERNANCE_ENABLED": "0",
            "AGENT_MODEL_CALL_LIMIT_PER_RUN": "4",
            "AGENT_MODEL_CALL_LIMIT_PER_THREAD": "5",
        }
    )
    os.environ.pop("AGENT_WRAPUP_AFTER_SECONDS", None)
    os.environ.pop("GRAPHHARBOR_RUN_TIMEOUT_SECONDS", None)
    await asyncio.to_thread(upgrade_head, os.environ["DATABASE_URI"])
    await asyncio.to_thread(upgrade_application, os.environ["DATABASE_URI"])
    evidence = {
        "complete": False,
        "database": database,
        "redis_prefix": os.environ["GRAPHHARBOR_REDIS_PREFIX"],
        "cases": {},
        "samples": {},
    }
    output = os.getenv("BUDGET_EVIDENCE_PATH")

    def save():
        if output:
            Path(output).write_text(
                json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
            )

    provider = FastAPI()
    slow_started = asyncio.Event()
    seen_wrapup = []
    provider_counts = {}

    @provider.post("/v1/chat/completions")
    async def completion(request: Request):
        payload = await request.json()
        messages = payload["messages"]
        text = next(
            (m.get("content", "") for m in reversed(messages) if m["role"] == "user"),
            "",
        )
        text = str(text)
        probe = "hitl" if text == "需要人工确认" else text
        if probe not in {
            "normal",
            "loop-end",
            "loop-v2",
            "loop-error",
            "loop-thread",
            "parallel-budget",
            "normal-child",
            "loop-child",
            "loop-graph",
            "loop-tool",
            "soft-finish",
            "slow",
            "hitl",
        }:
            probe = "other"
        provider_counts[probe] = provider_counts.get(probe, 0) + 1
        seen_wrapup.append(
            any(
                "Execution budget is running low" in str(m.get("content"))
                for m in messages
                if m["role"] == "system"
            )
        )
        if text == "slow":
            slow_started.set()
            await asyncio.sleep(3)
        tools = {item["function"]["name"] for item in payload.get("tools", [])}
        loop = text.startswith("loop") or text == "soft-finish"
        calls = []
        tool_messages = [m for m in messages if m["role"] == "tool"]
        if loop and not (text == "soft-finish" and tool_messages):
            name = "read_reference" if "read_reference" in tools else "ls"
            args = (
                {"topic": "budget"}
                if name == "read_reference"
                else {"path": "/workspace/"}
            )
            calls = [
                {
                    "id": "call-" + uuid4().hex,
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(args)},
                }
            ]
        if text == "parallel-budget" and "task" in tools and not tool_messages:
            calls = [
                {
                    "id": "call-" + uuid4().hex,
                    "type": "function",
                    "function": {
                        "name": "task",
                        "arguments": json.dumps(
                            {"description": description, "subagent_type": "research"}
                        ),
                    },
                }
                for description in ("loop-child", "normal-child")
            ]
        if text == "soft-finish" and not tool_messages:
            await asyncio.sleep(0.05)
        message = {"role": "assistant", "content": "" if calls else "budget-probe-ok"}
        if calls:
            message["tool_calls"] = calls
        reason = "tool_calls" if calls else "stop"
        if payload.get("stream"):

            async def chunks():
                delta = dict(message)
                if calls:
                    delta["tool_calls"] = [
                        {"index": i, **call} for i, call in enumerate(calls)
                    ]
                for part, finish in ((delta, None), ({}, reason)):
                    yield (
                        "data: "
                        + json.dumps(
                            {
                                "id": "probe",
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": "probe",
                                "choices": [
                                    {"index": 0, "delta": part, "finish_reason": finish}
                                ],
                            }
                        )
                        + "\n\n"
                    )
                yield "data: [DONE]\n\n"

            return StreamingResponse(chunks(), media_type="text/event-stream")
        return {
            "id": "probe",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "probe",
            "choices": [{"index": 0, "message": message, "finish_reason": reason}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    try:
        with tempfile.TemporaryDirectory(prefix="budget-platform-") as directory:
            os.environ["RUNTIME_WORKSPACE_ROOT"] = str(Path(directory) / "workspaces")
            os.environ["RUNTIME_SHOWCASE_WORKSPACE_ROOT"] = str(
                Path(directory) / "showcase"
            )
            async with serve(provider) as provider_url:
                graphs = {
                    name: f"apps/runtime-service/src/runtime_service/graphs/{name}.py:get_agent"
                    for name in (
                        "reference_agent",
                        "workflow_demo",
                        "showcase_demo",
                        "dearflow_agent",
                    )
                }
                native = runtime_app(
                    {
                        "graphs": graphs,
                        "auth": {
                            "path": "apps/runtime-service/src/runtime_service/auth/platform.py:auth"
                        },
                        "http": {"disable_mcp": True},
                    },
                    base_dir=ROOT,
                    custom_app=webapp.app,
                )
                async with serve(native) as runtime_url:
                    platform = create_app()
                    settings = platform.state.settings
                    settings.platform_db_enabled = settings.platform_db_auto_create = (
                        True
                    )
                    settings.database_url = (
                        f"sqlite:///{Path(directory) / 'platform.db'}"
                    )
                    settings.bootstrap_admin_enabled = False
                    settings.auth_required = True
                    settings.model_config_master_key = Fernet.generate_key().decode()
                    settings.runtime_delegation_secret = (
                        settings.runtime_model_config_secret
                    ) = SECRET
                    settings.langgraph_upstream_url = runtime_url
                    async with serve(platform, separate_loop=True) as platform_url:
                        os.environ["PLATFORM_THREAD_AUTHORIZATION_URL"] = (
                            platform_url + "/api/runtime/internal/thread-authorization"
                        )
                        os.environ["PLATFORM_RUNTIME_MODEL_CONFIG_URL"] = (
                            platform_url + "/api/runtime/internal/model-config"
                        )
                        factory = platform.state.db_session_factory
                        with session_scope(factory) as session:
                            projects = SqlAlchemyProjectsRepository(session)
                            tenant = projects.get_or_create_default_tenant()
                            project = projects.create_project(
                                tenant_id=tenant.id,
                                name="Budget validation",
                                description="",
                            )
                            user = SqlAlchemyIdentityRepository(session).create_user(
                                username="budget-owner",
                                external_subject="budget-owner",
                                password_hash=hash_password("test-only"),
                                email=None,
                                is_super_admin=False,
                                platform_roles=(),
                                must_change_password=False,
                            )
                            peer = SqlAlchemyIdentityRepository(session).create_user(
                                username="budget-peer",
                                external_subject="budget-peer",
                                password_hash=hash_password("test-only"),
                                email=None,
                                is_super_admin=False,
                                platform_roles=(),
                                must_change_password=False,
                            )
                            projects.upsert_project_member(
                                project_id=project.id,
                                user_id=user.id,
                                role=ProjectRole.EXECUTOR,
                            )
                            projects.upsert_project_member(
                                project_id=project.id,
                                user_id=peer.id,
                                role=ProjectRole.EXECUTOR,
                            )
                            other = projects.create_project(
                                tenant_id=tenant.id,
                                name="Budget other project",
                                description="",
                            )
                            projects.upsert_project_member(
                                project_id=other.id,
                                user_id=user.id,
                                role=ProjectRole.EXECUTOR,
                            )
                            for graph in graphs:
                                session.add(
                                    AgentRecord(
                                        project_id=project.id,
                                        name=graph,
                                        graph_id=graph,
                                        created_by=user.id,
                                        updated_by=user.id,
                                    )
                                )
                            model_id = uuid4()
                            session.add(
                                RuntimeCatalogModelRecord(
                                    id=model_id,
                                    display_name="budget-probe",
                                    provider="openai",
                                    protocol="openai",
                                    model_name="probe",
                                    base_url=provider_url + "/v1",
                                    api_key_ciphertext=encrypt_api_key(
                                        "test-only",
                                        master_key=settings.model_config_master_key,
                                    ),
                                    enabled=True,
                                )
                            )
                            project_id, user_id = str(project.id), str(user.id)
                            peer_id, other_id = str(peer.id), str(other.id)
                        headers = {
                            "x-project-id": project_id,
                            "authorization": "Bearer "
                            + create_access_token(
                                user_id=user_id,
                                username="budget-owner",
                                settings=settings,
                            ),
                        }
                        peer_headers = {
                            "x-project-id": project_id,
                            "authorization": "Bearer "
                            + create_access_token(
                                user_id=peer_id,
                                username="budget-peer",
                                settings=settings,
                            ),
                        }
                        worker = ProductionWorker(
                            native.state.graph_registry, owner="budget-verification"
                        )
                        async with httpx.AsyncClient(
                            base_url=platform_url,
                            headers=headers,
                            timeout=90,
                            trust_env=False,
                        ) as client:

                            async def request(method, path, expected=200, **kwargs):
                                response = await client.request(
                                    method, "/api/langgraph" + path, **kwargs
                                )
                                assert response.status_code == expected, (
                                    path,
                                    response.status_code,
                                    response.text[:300],
                                )
                                return response

                            async def create(
                                text,
                                graph="reference_agent",
                                *,
                                thread=None,
                                recursion=1000,
                                version="v3",
                                subgraphs=False,
                            ):
                                if thread is None:
                                    thread = (
                                        await request(
                                            "POST", "/threads", json={"graph_id": graph}
                                        )
                                    ).json()["thread_id"]
                                result = (
                                    await request(
                                        "POST",
                                        f"/threads/{thread}/runs",
                                        headers={"Idempotency-Key": uuid4().hex},
                                        json={
                                            "assistant_id": graph,
                                            "version": version,
                                            "stream_subgraphs": subgraphs,
                                            "input": {
                                                "messages": [
                                                    {"role": "user", "content": text}
                                                ]
                                            },
                                            "context": {"model_id": str(model_id)},
                                            "config": {"recursion_limit": recursion},
                                        },
                                    )
                                ).json()
                                return thread, result["run_id"]

                            async def inspect(thread, run, expected):
                                result = (
                                    await request(
                                        "GET", f"/threads/{thread}/runs/{run}"
                                    )
                                ).json()
                                assert result["status"] == expected, result
                                assert "error" not in result
                                stream = (
                                    await request(
                                        "GET",
                                        f"/threads/{thread}/runs/{run}/stream",
                                        params={"last_event_id": "0"},
                                    )
                                ).text
                                state = (
                                    await request("GET", f"/threads/{thread}/state")
                                ).json()
                                assert not any(
                                    key in json.dumps(state)
                                    for key in (
                                        "runtime_budget_latches",
                                        "runtime_wrapup_start",
                                        "thread_model_call_count",
                                    )
                                )
                                return stream, state

                            async def case(
                                name,
                                text,
                                graph="reference_agent",
                                expected="success",
                                **kwargs,
                            ):
                                thread, run = await create(text, graph, **kwargs)
                                assert await worker.run_once()
                                stream, state = await inspect(thread, run, expected)
                                evidence["samples"][name] = {
                                    "thread_id": thread,
                                    "run_id": run,
                                    "status": expected,
                                    "notices": notices(stream),
                                    "transport": transport_samples(stream),
                                }
                                save()
                                print(
                                    "budget-case " + name + " " + expected, flush=True
                                )
                                return thread, run, stream, state

                            for graph in graphs:
                                _, _, stream, _ = await case(
                                    "normal_" + graph, "normal", graph
                                )
                                assert not notices(stream)
                                evidence["cases"]["normal_" + graph] = "passed"

                            end_thread, end_run, stream, state = await case(
                                "model_end", "loop-end"
                            )
                            assert [n["code"] for n in notices(stream)] == [
                                "model_call_limit_approaching",
                                "model_call_limit_reached",
                            ]
                            marker = state["values"]["messages"][-1][
                                "additional_kwargs"
                            ]["runtime_budget_notice"]
                            assert marker == notices(stream)[-1]
                            replay = (
                                await request(
                                    "GET",
                                    f"/threads/{end_thread}/runs/{end_run}/stream",
                                    params={"last_event_id": "0"},
                                )
                            ).text
                            assert notices(replay) == notices(stream)
                            evidence["cases"]["end_marker_and_replay"] = "passed"
                            evidence["samples"]["end_marker"] = marker
                            history = (
                                await request(
                                    "POST",
                                    f"/threads/{end_thread}/history",
                                    json={"limit": 1},
                                )
                            ).json()
                            assert "runtime_budget_notice" in json.dumps(history)
                            evidence["cases"]["history_end_marker"] = "passed"

                            async with asyncio.timeout(15):
                                async with client.stream(
                                    "POST",
                                    f"/api/langgraph/threads/{end_thread}/stream/events",
                                    json={
                                        "channels": ["custom", "lifecycle"],
                                        "since": 0,
                                    },
                                ) as response:
                                    assert response.status_code == 200
                                    chunks = []
                                    protocol_notices = []
                                    async for line in response.aiter_lines():
                                        chunks.append(line)
                                        if not line:
                                            protocol_notices.extend(
                                                notices("\n".join(chunks))
                                            )
                                            chunks.clear()
                                            if len(protocol_notices) == 2:
                                                break
                                    assert protocol_notices == notices(stream)
                            evidence["cases"]["protocol_custom_replay"] = "passed"

                            _, _, old_stream, _ = await case(
                                "v2_model_end", "loop-v2", version="v2"
                            )
                            assert [n["code"] for n in notices(old_stream)] == [
                                "model_call_limit_approaching",
                                "model_call_limit_reached",
                            ]
                            evidence["cases"]["ordinary_v2_custom"] = "passed"

                            thread, _, stream, _ = await case(
                                "model_error", "loop-error", "showcase_demo", "error"
                            )
                            assert "runtime_model_call_limit_reached" in stream
                            assert any(
                                n["code"] == "model_call_limit_reached"
                                for n in notices(stream)
                            )
                            evidence["cases"]["model_error"] = "passed"
                            worker = ProductionWorker(
                                native.state.graph_registry,
                                owner="budget-verification-restarted",
                            )
                            _, _, stream, _ = await case(
                                "thread_exhausted",
                                "loop-thread",
                                "showcase_demo",
                                "error",
                                thread=thread,
                            )
                            assert any(
                                n["code"] == "model_call_limit_reached"
                                and n["budget_scope"] == "thread"
                                for n in notices(stream)
                            )
                            evidence["cases"]["thread_persistence_worker_recreate"] = (
                                "passed"
                            )

                            _, _, stream, _ = await case(
                                "parallel_child_limit",
                                "parallel-budget",
                                "showcase_demo",
                                "error",
                                subgraphs=True,
                            )
                            child_notices = notices(stream)
                            assert child_notices and all(
                                notice["scope"] == "subagent"
                                for notice in child_notices
                            )
                            assert any(
                                notice["code"] == "model_call_limit_reached"
                                for notice in child_notices
                            )
                            assert "runtime_model_call_limit_reached" in stream
                            assert provider_counts["normal-child"] == 1
                            assert provider_counts["loop-child"] == 4
                            assert all(
                                sample["payload"]["params"]["namespace"]
                                for sample in transport_samples(stream)
                                if sample["payload"].get("method") == "custom"
                            )
                            evidence["cases"][
                                "parallel_child_error_preserves_parent_native_outcome"
                            ] = "passed"

                            _, _, stream, _ = await case(
                                "graph_low", "loop-graph", expected="error", recursion=1
                            )
                            assert "runtime_graph_step_limit_reached" in stream
                            evidence["cases"]["graph_low_no_hook"] = "passed"
                            _, _, stream, _ = await case(
                                "graph_warning",
                                "loop-graph",
                                expected="error",
                                recursion=20,
                            )
                            assert any(
                                n["code"] == "graph_step_limit_approaching"
                                for n in notices(stream)
                            )
                            evidence["cases"]["graph_warning"] = "passed"

                            os.environ["AGENT_TOOL_CALL_LIMIT_PER_RUN"] = "1"
                            _, _, stream, _ = await case(
                                "tool_limit", "loop-tool", "showcase_demo", "error"
                            )
                            assert "runtime_tool_call_limit_reached" in stream
                            os.environ.pop("AGENT_TOOL_CALL_LIMIT_PER_RUN")
                            evidence["cases"]["tool_limit"] = "passed"

                            os.environ["AGENT_WRAPUP_AFTER_SECONDS"] = "0.01"
                            before = len(seen_wrapup)
                            _, _, stream, _ = await case("soft_finish", "soft-finish")
                            assert (
                                sum(
                                    n["code"] == "wrapup_started"
                                    for n in notices(stream)
                                )
                                == 1
                            )
                            assert any(seen_wrapup[before:])
                            os.environ.pop("AGENT_WRAPUP_AFTER_SECONDS")
                            evidence["cases"]["soft_finish"] = "passed"

                            os.environ["GRAPHHARBOR_RUN_TIMEOUT_SECONDS"] = "1"
                            worker = ProductionWorker(
                                native.state.graph_registry,
                                owner="budget-verification-timeout",
                            )
                            _, _, stream, _ = await case(
                                "hard_timeout", "slow", expected="timeout"
                            )
                            assert "runtime_run_timeout" in stream
                            os.environ.pop("GRAPHHARBOR_RUN_TIMEOUT_SECONDS")
                            worker = ProductionWorker(
                                native.state.graph_registry,
                                owner="budget-verification-after-timeout",
                            )
                            evidence["cases"]["hard_timeout"] = "passed"

                            hitl_thread, hitl_run = await create(
                                "需要人工确认", "workflow_demo"
                            )
                            assert await worker.run_once()
                            _, state = await inspect(
                                hitl_thread, hitl_run, "interrupted"
                            )
                            active_id = interrupt_id(state)
                            assert active_id
                            resumed = (
                                await request(
                                    "POST",
                                    f"/threads/{hitl_thread}/runs",
                                    headers={"Idempotency-Key": uuid4().hex},
                                    json={
                                        "assistant_id": "workflow_demo",
                                        "command": {
                                            "resume": {
                                                active_id: {
                                                    "decisions": [{"type": "approve"}]
                                                }
                                            }
                                        },
                                    },
                                )
                            ).json()["run_id"]
                            assert await worker.run_once()
                            await inspect(hitl_thread, resumed, "success")
                            evidence["cases"]["hitl_resume"] = "passed"

                            slow_started.clear()
                            cancel_thread, cancel_run = await create("slow")
                            executing = asyncio.create_task(worker.run_once())
                            await asyncio.wait_for(slow_started.wait(), 20)
                            await request(
                                "POST",
                                f"/threads/{cancel_thread}/runs/{cancel_run}/cancel",
                                json={"action": "interrupt"},
                            )
                            await executing
                            result = (
                                await request(
                                    "GET", f"/threads/{cancel_thread}/runs/{cancel_run}"
                                )
                            ).json()
                            assert result["status"] in {"interrupted", "cancelled"}
                            evidence["cases"]["cancel_real_terminal"] = "passed"

                            for payload in (
                                {"input": {"thread_model_call_count": 0}},
                                {
                                    "command": {
                                        "resume": {"x": {"runtime_wrapup_start": 0}}
                                    }
                                },
                                {
                                    "input": {
                                        "messages": [
                                            {
                                                "role": "assistant",
                                                "content": "fake",
                                                "additional_kwargs": {
                                                    "runtime_budget_notice": {}
                                                },
                                            }
                                        ]
                                    }
                                },
                            ):
                                await request(
                                    "POST",
                                    f"/threads/{end_thread}/runs",
                                    expected=400,
                                    json={"assistant_id": "reference_agent", **payload},
                                )
                            evidence["cases"]["public_write_injection_denied"] = (
                                "passed"
                            )

                            for path in (
                                f"/threads/{end_thread}/state",
                                f"/threads/{end_thread}/runs/{end_run}/stream",
                            ):
                                await request(
                                    "GET", path, expected=403, headers=peer_headers
                                )
                                await request(
                                    "GET",
                                    path,
                                    expected=403,
                                    headers={**headers, "x-project-id": other_id},
                                )
                            owner = ActorContext(
                                user_id=user_id,
                                project_roles={project_id: ("project_executor",)},
                            )
                            for actions, expected in ((["read"], 200), ([], 403)):
                                await asyncio.to_thread(
                                    thread_access.share,
                                    factory,
                                    actor=owner,
                                    project_id=project_id,
                                    thread_id=end_thread,
                                    user_id=peer_id,
                                    actions=actions,
                                )
                                await request(
                                    "GET",
                                    f"/threads/{end_thread}/state",
                                    expected=expected,
                                    headers=peer_headers,
                                )
                            evidence["cases"]["scope_isolation_and_read_revocation"] = (
                                "passed"
                            )

                            from langgraph_runtime_pg.database import connect
                            from langgraph_runtime_pg.models import ThreadRow

                            async with connect() as connection:
                                record = await connection.session.get(
                                    ThreadRow, UUID(end_thread)
                                )
                                record.event_pruned_through = 2
                            expired = await request(
                                "POST",
                                f"/threads/{end_thread}/stream/events",
                                expected=410,
                                json={"channels": ["custom"], "since": 1},
                            )
                            assert expired.json()["error"]["code"] == "cursor_expired"
                            await request(
                                "GET", f"/threads/{end_thread}/runs/{end_run}"
                            )
                            await request("GET", f"/threads/{end_thread}/state")
                            evidence["cases"]["protocol_410_native_snapshot"] = "passed"

                            from langchain.agents.middleware import (
                                ModelCallLimitMiddleware,
                            )
                            from runtime_service.services.reference_agent import (
                                agent as reference,
                            )

                            def previous_limit(**kwargs):
                                return ModelCallLimitMiddleware(
                                    **{
                                        key: value
                                        for key, value in kwargs.items()
                                        if key
                                        in {
                                            "run_limit",
                                            "thread_limit",
                                            "exit_behavior",
                                        }
                                    }
                                )

                            with patch.object(
                                reference, "ExecutionBudgetMiddleware", previous_limit
                            ):
                                _, _, stream, _ = await case(
                                    "rollback", "normal", thread=end_thread
                                )
                                assert not notices(stream)
                            evidence["cases"]["old_limiter_reads_checkpoint"] = "passed"
                            if all(
                                source.get(key)
                                for key in (
                                    "DEEPSEEK_PROXY_URL",
                                    "DEEPSEEK_PROXY_API_KEY",
                                    "DEEPSEEK_PROXY_DEFAULT_MODEL",
                                )
                            ):
                                with session_scope(factory) as session:
                                    record = session.get(
                                        RuntimeCatalogModelRecord, model_id
                                    )
                                    record.provider = record.protocol = "deepseek"
                                    record.model_name = str(
                                        source["DEEPSEEK_PROXY_DEFAULT_MODEL"]
                                    )
                                    record.base_url = str(source["DEEPSEEK_PROXY_URL"])
                                    record.api_key_ciphertext = encrypt_api_key(
                                        str(source["DEEPSEEK_PROXY_API_KEY"]),
                                        master_key=settings.model_config_master_key,
                                    )
                                _, _, real_stream, _ = await case(
                                    "real_model_normal",
                                    "Reply with exactly: budget-smoke-ok",
                                )
                                assert "budget-smoke-ok" in real_stream
                                assert not notices(real_stream)
                                evidence["cases"]["real_model_normal"] = "passed"
                            else:
                                evidence["cases"]["real_model_normal"] = (
                                    "blocked: BUDGET_MODEL_ENV_FILE lacks proxy configuration"
                                )
                            evidence["provider_call_counts"] = provider_counts
                            evidence["complete"] = all(
                                result == "passed"
                                for result in evidence["cases"].values()
                            )
                            save()
    finally:
        save()
    print(
        json.dumps(
            {
                "complete": evidence["complete"],
                "database": database,
                "cases": evidence["cases"],
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
