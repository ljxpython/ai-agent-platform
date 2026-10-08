"""Real isolated API/Runtime/Worker/PG/Redis chain using a controlled HTTP provider.

Requires USAGE_POSTGRES_ADMIN_DSN and USAGE_REDIS_URI for disposable resources.
Retains uniquely named databases, emits numeric evidence, never touches the live stack.
Run with both service src directories and the repository root in PYTHONPATH.
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import statistics
import tempfile
import time
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import psycopg
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from langgraph_runtime_pg.migrate import upgrade_head
from langgraph_runtime_pg.production_worker import ProductionWorker
from langhost.server import create_app as runtime_app
from psycopg import sql

from scripts.verify_agent_observability import interrupt_id, serve

ROOT = Path(__file__).resolve().parents[1]
SECRET = "usage-isolated-verification-secret-at-least-32-bytes"
CANARY = "usage-private-prompt-canary"


def export_contract(evidence, directory):
    from platform_api.core.errors.payload import build_error_response
    from platform_api.modules.runtime_catalog.domain.models import (
        PricingInput,
        PricingSnapshot,
    )
    from platform_api.modules.runtime_gateway.application.usage import (
        RunUsage,
        ThreadUsage,
    )
    from runtime_service.observability.usage import empty_tokens
    from runtime_service.observability.usage_query import empty_summary

    samples = {
        "run_complete_page1": evidence["samples"]["run"],
        "thread_complete": evidence["samples"]["thread"],
        "run_unknown_price": evidence["samples"]["unknown"],
        "run_zero_calls": evidence["samples"]["zero"],
        "run_collection_degraded": evidence["samples"]["fault"],
        "run_child": evidence["samples"]["child"],
    }
    for name, reason in (
        ("run_not_recorded", "not_recorded"),
        ("run_backend_unavailable", "backend_unavailable"),
        ("run_disabled", "disabled"),
    ):
        samples[name] = {
            **evidence["samples"]["run"],
            **empty_summary(reason),
            "finalized": False,
            "calls": {"items": [], "next_cursor": None},
        }
    ttl = copy.deepcopy(samples["run_complete_page1"])
    counts = {
        "input_tokens": 1000,
        "output_tokens": 100,
        "total_tokens": 1100,
        "cache_read_tokens": 200,
        "cache_creation_tokens": 100,
        "cache_creation_5m_tokens": 40,
        "cache_creation_1h_tokens": 60,
        "reasoning_tokens": 30,
    }
    ttl.update(
        tokens=counts,
        known_tokens=counts,
        coverage={
            **ttl["coverage"],
            "observed_call_count": 1,
            "reported_call_count": 1,
        },
    )
    ttl["cost"].update(
        estimated_cost_usd="0.002580000000", known_cost_usd="0.002580000000"
    )
    ttl["calls"]["items"][0].update(tokens=counts, cost=copy.deepcopy(ttl["cost"]))
    ttl["calls"]["next_cursor"] = None
    samples["run_cache_ttl"] = ttl
    partial = copy.deepcopy(ttl)
    missing = copy.deepcopy(partial["calls"]["items"][0])
    missing.update(model_call_id=str(uuid4()), tokens=empty_tokens(), quality="missing")
    missing["cost"].update(
        status="unknown",
        estimated_cost_usd=None,
        known_cost_usd=None,
        unpriced_call_count=1,
    )
    partial.update(
        availability="partial",
        tokens=empty_tokens(),
        calls={"items": [partial["calls"]["items"][0], missing], "next_cursor": None},
        coverage={
            **partial["coverage"],
            "observed_call_count": 2,
            "missing_usage_call_count": 1,
        },
    )
    partial["cost"].update(
        status="partial", estimated_cost_usd=None, unpriced_call_count=1
    )
    samples["run_partial_missing_usage"] = partial
    running = copy.deepcopy(ttl)
    running.update(
        run_status="running",
        finalized=False,
        availability="partial",
        tokens=empty_tokens(),
    )
    running["cost"].update(status="partial", estimated_cost_usd=None)
    samples["run_running"] = running
    errors = []
    for status, code, message in (
        (401, "not_authenticated", "Authentication required"),
        (403, "forbidden", "Permission denied"),
        (404, "run_not_found", "Run not found"),
        (400, "invalid_usage_query", "Invalid usage pagination"),
        (422, "validation_failed", "Validation failed"),
        (502, "langgraph_upstream_invalid_response", "Invalid Runtime usage"),
        (503, "langgraph_upstream_unavailable", "Runtime unavailable"),
        (504, "langgraph_upstream_timeout", "Runtime request timed out"),
    ):
        errors.append(
            {
                "http_status": status,
                "body": json.loads(
                    build_error_response(
                        status_code=status,
                        code=code,
                        message=message,
                        request_id="fixture-query",
                    ).body
                ),
            }
        )
    schemas = {
        schema.__name__: schema.model_json_schema()
        for schema in (RunUsage, ThreadUsage, PricingInput, PricingSnapshot)
    }
    for name, value in samples.items():
        samples[name] = (
            (ThreadUsage if name.startswith("thread_") else RunUsage)
            .model_validate(value)
            .model_dump(mode="json")
        )
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    (target / "usage-v1.json").write_text(
        json.dumps(
            {
                "version": 1,
                "schemas": schemas,
                "samples": samples,
                "errors": errors,
                "sample_origins": {
                    "http": [
                        "run_complete_page1",
                        "thread_complete",
                        "run_unknown_price",
                        "run_zero_calls",
                        "run_collection_degraded",
                        "run_child",
                    ],
                    "controlled_contract": [
                        "run_cache_ttl",
                        "run_partial_missing_usage",
                        "run_running",
                        "run_not_recorded",
                        "run_backend_unavailable",
                        "run_disabled",
                    ],
                },
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n"
    )


def migrate_platform(dsn):
    config = Config()
    config.set_main_option(
        "script_location", str(ROOT / "apps/platform-api/migrations")
    )
    config.set_main_option(
        "sqlalchemy.url", dsn.replace("postgresql://", "postgresql+psycopg://")
    )
    command.upgrade(config, "head")


async def main():
    from platform_api.core.db import session_scope
    from platform_api.core.security import (
        create_access_token,
        create_runtime_delegation_token,
        empty_runtime_context_hash,
    )
    from platform_api.main import create_app
    from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
    from platform_api.modules.iam.domain import ProjectRole
    from platform_api.modules.identity.repository import SqlAlchemyIdentityRepository
    from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
    from platform_api.modules.runtime_catalog.application.credentials import (
        encrypt_api_key,
    )
    from platform_api.modules.runtime_catalog.application.service import (
        RuntimeCatalogService,
    )
    from platform_api.modules.runtime_catalog.infra.sqlalchemy.models import (
        RuntimeCatalogModelRecord,
    )
    from runtime_service import webapp
    from runtime_service.db import upgrade
    from runtime_service.db.repositories import usage as repository

    admin = os.environ["USAGE_POSTGRES_ADMIN_DSN"]
    prefix = uuid4().hex[:12]
    databases = ["agent_usage_runtime_" + prefix, "agent_usage_platform_" + prefix]
    with psycopg.connect(admin, autocommit=True) as conn:
        for name in databases:
            conn.execute(
                sql.SQL("CREATE DATABASE {} ENCODING 'UTF8' TEMPLATE template0").format(
                    sql.Identifier(name)
                )
            )
    runtime_dsn, platform_dsn = [
        admin.rsplit("/", 1)[0] + "/" + name for name in databases
    ]
    os.environ.update(
        DATABASE_URI=runtime_dsn.replace("postgresql://", "postgresql+asyncpg://"),
        REDIS_URI=os.environ["USAGE_REDIS_URI"],
        GRAPHHARBOR_REDIS_PREFIX="graphharbor:usage:" + prefix,
        GRAPHHARBOR_ENV="production",
        RUNTIME_USAGE_ENABLED="true",
        LANGFUSE_ENABLED="false",
        OTEL_ENABLED="false",
        PLATFORM_RUNTIME_DELEGATION_SECRET=SECRET,
        PLATFORM_RUNTIME_DELEGATION_ISSUER="platform-api",
        PLATFORM_RUNTIME_DELEGATION_AUDIENCE="runtime-service",
        GRAPHHARBOR_RUNTIME_CONTEXT_SECRET=SECRET,
        GRAPHHARBOR_RUNTIME_CONTEXT_ISSUER="graphharbor",
        GRAPHHARBOR_RUNTIME_CONTEXT_AUDIENCE="graphharbor-worker",
    )
    await asyncio.to_thread(upgrade_head, os.environ["DATABASE_URI"])
    await asyncio.to_thread(upgrade, runtime_dsn)
    await asyncio.to_thread(migrate_platform, platform_dsn)
    provider = FastAPI()
    calls = []
    write_times = []
    query_times = []
    first_tokens = {}
    connection_samples = []
    sampling_done = asyncio.Event()
    queue_events = {}
    original_upsert = repository.upsert_call

    def timed_write(identity, call):
        started = time.perf_counter()
        try:
            return original_upsert(identity, call)
        finally:
            write_times.append((time.perf_counter() - started) * 1000)

    repository.upsert_call = timed_write

    @provider.post("/v1/chat/completions")
    async def completion(request: Request):
        payload = await request.json()
        tools = {item["function"]["name"] for item in payload.get("tools", [])}
        messages = payload["messages"]
        last_user = max(
            (i for i, m in enumerate(messages) if m["role"] == "user"), default=0
        )
        has_tool = any(m["role"] == "tool" for m in messages[last_user:])
        if any("queued-message-" in str(m.get("content", "")) for m in messages):
            has_tool = True
        if queue_events and not queue_events["started"].is_set():
            queue_events["started"].set()
            await queue_events["release"].wait()
        message = {"role": "assistant", "content": "probe-ok"}
        if not has_tool and "task" in tools:
            message = {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_" + uuid4().hex,
                        "type": "function",
                        "function": {
                            "name": "task",
                            "arguments": json.dumps(
                                {
                                    "description": "Summarize evidence",
                                    "subagent_type": "research",
                                }
                            ),
                        },
                    }
                ],
            }
        elif not has_tool and "read_reference" in tools:
            message = {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_" + uuid4().hex,
                        "type": "function",
                        "function": {
                            "name": "read_reference",
                            "arguments": json.dumps({"topic": "runtime"}),
                        },
                    }
                ],
            }
        calls.append(
            {"model": payload["model"], "tool_call": bool(message.get("tool_calls"))}
        )
        usage = {
            "prompt_tokens": 1000,
            "completion_tokens": 100,
            "total_tokens": 1100,
            "prompt_tokens_details": {"cached_tokens": 200},
            "completion_tokens_details": {"reasoning_tokens": 30},
        }
        if not payload.get("stream"):
            return {
                "id": "probe",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "usage-probe",
                "choices": [
                    {
                        "index": 0,
                        "message": message,
                        "finish_reason": "tool_calls"
                        if message.get("tool_calls")
                        else "stop",
                    }
                ],
                "usage": usage,
            }

        async def chunks():
            delta = {"role": "assistant", "content": message["content"]}
            if message.get("tool_calls"):
                delta["tool_calls"] = [{"index": 0, **message["tool_calls"][0]}]
            for content in (
                {"choices": [{"index": 0, "delta": delta, "finish_reason": None}]},
                {
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": "tool_calls"
                            if message.get("tool_calls")
                            else "stop",
                        }
                    ]
                },
                {"choices": [], "usage": usage},
            ):
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "id": "probe",
                            "object": "chat.completion.chunk",
                            "created": int(time.time()),
                            "model": "usage-probe",
                            **content,
                        }
                    )
                    + "\n\n"
                )
            yield "data: [DONE]\n\n"

        return StreamingResponse(chunks(), media_type="text/event-stream")

    evidence = {
        "complete": False,
        "databases": databases,
        "provider": "controlled_http_fixture",
        "cases": {},
        "samples": {},
    }

    async def sample_connections():
        async with await psycopg.AsyncConnection.connect(
            admin, autocommit=True
        ) as conn:
            while not sampling_done.is_set():
                cursor = await conn.execute(
                    "SELECT datname, count(*), count(*) FILTER (WHERE state='idle in transaction') FROM pg_stat_activity WHERE datname=ANY(%s) GROUP BY datname",
                    (databases,),
                )
                connection_samples.append(
                    [
                        (
                            name.decode() if isinstance(name, bytes) else name,
                            count,
                            idle,
                        )
                        for name, count, idle in await cursor.fetchall()
                    ]
                )
                await asyncio.sleep(0.02)

    sampler = asyncio.create_task(sample_connections())
    with tempfile.TemporaryDirectory(prefix="agent-usage-workspaces-") as workspace:
        os.environ["RUNTIME_SHOWCASE_WORKSPACE_ROOT"] = workspace
        async with serve(provider) as provider_url:
            native = runtime_app(
                {
                    "graphs": {
                        "reference_agent": "apps/runtime-service/src/runtime_service/services/reference_agent/agent.py:get_agent",
                        "showcase_demo": "apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py:get_agent",
                        "workflow_demo": "apps/runtime-service/src/runtime_service/services/demo/workflow_demo/agent.py:get_agent",
                    },
                    "auth": {
                        "path": "apps/runtime-service/src/runtime_service/auth/platform.py:auth"
                    },
                    "http": {"disable_mcp": True},
                },
                base_dir=ROOT,
                custom_app=webapp.app,
            )
            async with serve(native) as runtime_url:
                os.environ["RUNTIME_SELF_URL"] = runtime_url
                platform = create_app()
                settings = platform.state.settings
                settings.platform_db_enabled = True
                settings.platform_db_auto_create = False
                settings.database_url = platform_dsn.replace(
                    "postgresql://", "postgresql+psycopg://"
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
                    os.environ["PLATFORM_RUNTIME_MESSAGE_AUTH_URL"] = (
                        platform_url + "/api/runtime/internal/message-authorization"
                    )
                    factory = platform.state.db_session_factory
                    model_id = uuid4()
                    pricing = RuntimeCatalogService._price_snapshot(
                        {
                            "currency": "USD",
                            "basis": "per_million_tokens",
                            "input": "2.0000000000",
                            "output": "8.0000000000",
                            "cache_read": "0.2000000000",
                            "cache_write": None,
                            "cache_write_5m": None,
                            "cache_write_1h": None,
                        }
                    )
                    with session_scope(factory) as session:
                        projects = SqlAlchemyProjectsRepository(session)
                        tenant = projects.get_or_create_default_tenant()
                        project = projects.create_project(
                            tenant_id=tenant.id, name="Usage", description=""
                        )
                        other = projects.create_project(
                            tenant_id=tenant.id, name="Other", description=""
                        )
                        identities = SqlAlchemyIdentityRepository(session)
                        users = [
                            identities.create_user(
                                username=name,
                                external_subject=name,
                                password_hash="unused",
                                email=None,
                                is_super_admin=False,
                                platform_roles=(),
                                must_change_password=False,
                            ).id
                            for name in ("owner", "peer")
                        ]
                        for user in users:
                            projects.upsert_project_member(
                                project_id=project.id,
                                user_id=user,
                                role=ProjectRole.EXECUTOR,
                            )
                        session.add_all(
                            [
                                AgentRecord(
                                    project_id=project.id,
                                    name=graph,
                                    graph_id=graph,
                                    created_by=users[0],
                                    updated_by=users[0],
                                )
                                for graph in (
                                    "reference_agent",
                                    "showcase_demo",
                                    "workflow_demo",
                                )
                            ]
                        )
                        session.add(
                            RuntimeCatalogModelRecord(
                                id=model_id,
                                display_name="Usage probe",
                                provider="openai",
                                protocol="openai",
                                model_name="usage-probe",
                                base_url=provider_url + "/v1",
                                api_key_ciphertext=encrypt_api_key(
                                    "isolated-secret-key",
                                    master_key=settings.model_config_master_key,
                                ),
                                pricing_json=pricing,
                                enabled=True,
                            )
                        )
                        project_id, other_id = str(project.id), str(other.id)
                    headers = {
                        "x-project-id": project_id,
                        "authorization": "Bearer "
                        + create_access_token(
                            user_id=str(users[0]), username="owner", settings=settings
                        ),
                    }
                    peer_headers = {
                        **headers,
                        "authorization": "Bearer "
                        + create_access_token(
                            user_id=str(users[1]), username="peer", settings=settings
                        ),
                    }
                    worker = ProductionWorker(
                        native.state.graph_registry, owner="usage-probe"
                    )
                    async with httpx.AsyncClient(
                        base_url=platform_url,
                        headers=headers,
                        timeout=30,
                        trust_env=False,
                    ) as client:

                        async def request(method, path, expected=200, **kwargs):
                            started = time.perf_counter()
                            response = await client.request(
                                method, "/api/langgraph" + path, **kwargs
                            )
                            assert response.status_code == expected, (
                                path,
                                response.status_code,
                                response.text[:500],
                            )
                            if path.endswith("/usage"):
                                assert (
                                    CANARY not in response.text
                                    and "isolated-secret-key" not in response.text
                                    and provider_url not in response.text
                                )
                                if expected == 200:
                                    assert (
                                        response.headers["cache-control"] == "no-store"
                                    )
                                    query_times.append(
                                        (time.perf_counter() - started) * 1000
                                    )
                            return response

                        async def create(
                            graph="reference_agent",
                            thread=None,
                            command=None,
                            input_payload=None,
                            checkpoint_id=None,
                            queued=False,
                            timing=None,
                        ):
                            if thread is None:
                                thread = (
                                    await request(
                                        "POST", "/threads", json={"graph_id": graph}
                                    )
                                ).json()["thread_id"]
                            payload = {
                                "assistant_id": graph,
                                **(
                                    {"context": {"model_id": str(model_id)}}
                                    if command is None
                                    else {}
                                ),
                                **(
                                    {"command": command}
                                    if command
                                    else {
                                        "input": input_payload
                                        or {
                                            "messages": [
                                                {"role": "user", "content": CANARY}
                                            ]
                                        }
                                    }
                                ),
                            }
                            if checkpoint_id:
                                payload["checkpoint_id"] = checkpoint_id
                            run = (
                                await request(
                                    "POST",
                                    f"/threads/{thread}/runs",
                                    headers={"Idempotency-Key": uuid4().hex},
                                    json=payload,
                                )
                            ).json()["run_id"]
                            started = time.perf_counter()

                            async def first_text():
                                event = None
                                async with client.stream(
                                    "GET",
                                    f"/api/langgraph/threads/{thread}/runs/{run}/stream",
                                    params={
                                        "stream_mode": "messages",
                                        "last_event_id": "0",
                                    },
                                ) as response:
                                    assert response.status_code == 200
                                    async for line in response.aiter_lines():
                                        if line.startswith("event:"):
                                            event = line[6:].strip()
                                        elif (
                                            event == "messages"
                                            and line.startswith("data:")
                                            and "probe-ok" in line
                                        ):
                                            return {
                                                "ms": round(
                                                    (time.perf_counter() - started)
                                                    * 1000,
                                                    3,
                                                ),
                                                "event": event,
                                            }
                                raise AssertionError("No model text in live SSE")

                            observing = (
                                asyncio.create_task(first_text()) if timing else None
                            )
                            if queued:
                                queue_events.update(
                                    started=asyncio.Event(), release=asyncio.Event()
                                )
                                executing = asyncio.create_task(worker.run_once())
                                try:
                                    await asyncio.wait_for(
                                        queue_events["started"].wait(), timeout=30
                                    )
                                    for index in range(2):
                                        await request(
                                            "POST",
                                            f"/threads/{thread}/messages",
                                            expected=202,
                                            headers={"Idempotency-Key": uuid4().hex},
                                            json={
                                                "target_run_id": run,
                                                "client_message_id": str(uuid4()),
                                                "content": "queued-message-"
                                                + str(index),
                                            },
                                        )
                                finally:
                                    queue_events["release"].set()
                                assert await executing
                                queue_events.clear()
                            else:
                                assert await worker.run_once()
                            elapsed = (time.perf_counter() - started) * 1000
                            if observing:
                                first_tokens[timing] = await asyncio.wait_for(
                                    observing, timeout=30
                                )
                            state = (
                                await request("GET", f"/threads/{thread}/runs/{run}")
                            ).json()
                            assert state["status"] in {"success", "interrupted"}, state
                            return thread, run, elapsed

                        thread, run, enabled_time = await create(timing="enabled")
                        path = f"/threads/{thread}/runs/{run}/usage"
                        first = (await request("GET", path, params={"limit": 1})).json()
                        assert (
                            first["coverage"]["observed_call_count"] == 2
                            and first["tokens"]["total_tokens"] == 2200
                        ), first
                        assert (
                            first["cost"]["estimated_cost_usd"] == "0.004880000000"
                        ), first
                        second_page = (
                            await request(
                                "GET",
                                path,
                                params={
                                    "limit": 1,
                                    "cursor": first["calls"]["next_cursor"],
                                },
                            )
                        ).json()
                        assert (
                            second_page["tokens"] == first["tokens"]
                            and not first["truncated"]
                        )
                        replay = await request(
                            "GET",
                            f"/threads/{thread}/runs/{run}/stream",
                            params={"last_event_id": "0"},
                        )
                        assert "text/event-stream" in replay.headers["content-type"]
                        assert (await request("GET", path)).json()["coverage"][
                            "observed_call_count"
                        ] == 2
                        evidence["cases"]["native_model_tool_pagination_replay"] = (
                            "passed"
                        )
                        _, second_run, _ = await create(thread=thread)
                        combined = (
                            await request("GET", f"/threads/{thread}/usage")
                        ).json()
                        assert (
                            combined["recorded_run_count"] == 2
                            and combined["tokens"]["total_tokens"] == 4400
                        )
                        assert (
                            combined["cost"]["estimated_cost_usd"] == "0.009760000000"
                        )
                        evidence["cases"]["thread_two_runs"] = "passed"
                        child_thread, child_run, _ = await create("showcase_demo")
                        child_usage = (
                            await request(
                                "GET", f"/threads/{child_thread}/runs/{child_run}/usage"
                            )
                        ).json()
                        assert child_usage["coverage"]["observed_call_count"] == 3, (
                            child_usage
                        )
                        assert any(
                            c["scope"] == "subagent"
                            for c in child_usage["calls"]["items"]
                        ), child_usage
                        evidence["cases"]["native_deep_agent_child"] = "passed"
                        await request("GET", path, expected=403, headers=peer_headers)
                        await request(
                            "GET",
                            path,
                            expected=403,
                            headers={**headers, "x-project-id": other_id},
                        )
                        await request(
                            "GET",
                            f"/threads/{child_thread}/runs/{run}/usage",
                            expected=404,
                        )
                        await request("GET", path, expected=400, params={"limit": 201})
                        await request(
                            "GET", path, expected=400, params={"cursor": "bad"}
                        )
                        await request(
                            "GET",
                            f"/threads/{thread}/usage",
                            expected=400,
                            params={"created_from": "2026-01-01T00:00:00Z"},
                        )
                        evidence["cases"]["acl_scope_and_input_boundaries"] = "passed"
                        hitl_thread, hitl_run, _ = await create(
                            "workflow_demo",
                            input_payload={
                                "messages": [{"role": "user", "content": CANARY}],
                                "requires_confirmation": True,
                            },
                        )
                        paused = (
                            await request(
                                "GET", f"/threads/{hitl_thread}/runs/{hitl_run}/usage"
                            )
                        ).json()
                        assert (
                            paused["run_status"] == "interrupted"
                            and paused["tokens"]["total_tokens"] == 0
                            and paused["cost"]["status"] == "not_applicable"
                        ), paused
                        state = (
                            await request("GET", f"/threads/{hitl_thread}/state")
                        ).json()
                        active_interrupt = interrupt_id(state)
                        assert active_interrupt
                        _, resumed_hitl_run, _ = await create(
                            "workflow_demo",
                            thread=hitl_thread,
                            command={
                                "resume": {
                                    active_interrupt: {
                                        "decisions": [{"type": "approve"}]
                                    }
                                }
                            },
                        )
                        hitl_usage = (
                            await request(
                                "GET",
                                f"/threads/{hitl_thread}/runs/{resumed_hitl_run}/usage",
                            )
                        ).json()
                        assert (
                            resumed_hitl_run != hitl_run
                            and hitl_usage["tokens"]["total_tokens"] == 2200
                        ), hitl_usage
                        assert (
                            await request("GET", f"/threads/{hitl_thread}/usage")
                        ).json()["recorded_run_count"] == 2
                        evidence["cases"]["native_hitl_resume_and_zero_call"] = "passed"
                        queue_thread, queue_run, _ = await create(queued=True)
                        queue_usage = (
                            await request(
                                "GET", f"/threads/{queue_thread}/runs/{queue_run}/usage"
                            )
                        ).json()
                        assert (
                            queue_usage["coverage"]["observed_call_count"] == 2
                            and queue_usage["tokens"]["total_tokens"] == 2200
                        ), queue_usage
                        queue_state = (
                            await request("GET", f"/threads/{queue_thread}/state")
                        ).json()
                        assert (
                            sum(
                                "queued-message-" in str(m.get("content", ""))
                                for m in queue_state["values"]["messages"]
                            )
                            == 2
                        )
                        evidence["cases"][
                            "native_two_queued_human_messages_same_run"
                        ] = "passed"
                        history = (
                            await request(
                                "POST",
                                f"/threads/{child_thread}/history",
                                json={"limit": 50},
                            )
                        ).json()
                        checkpoint = next(
                            row["checkpoint"]["checkpoint_id"]
                            for row in history
                            if not row["values"].get("messages")
                        )
                        fork = (
                            await request(
                                "POST",
                                f"/threads/{child_thread}/fork",
                                json={
                                    "checkpoint_id": checkpoint,
                                    "title": "Usage fork",
                                },
                            )
                        ).json()["thread_id"]
                        assert (await request("GET", f"/threads/{fork}/usage")).json()[
                            "unavailable_reason"
                        ] == "not_recorded"
                        await create("showcase_demo", thread=fork)
                        assert (await request("GET", f"/threads/{fork}/usage")).json()[
                            "tokens"
                        ]["total_tokens"] == 3300
                        assert (
                            await request("GET", f"/threads/{child_thread}/usage")
                        ).json()["tokens"]["total_tokens"] == 3300
                        await create(
                            "showcase_demo",
                            thread=child_thread,
                            checkpoint_id=checkpoint,
                        )
                        assert (
                            await request("GET", f"/threads/{child_thread}/usage")
                        ).json()["tokens"]["total_tokens"] == 6600
                        assert (
                            await request(
                                "GET", f"/threads/{child_thread}/runs/{child_run}/usage"
                            )
                        ).json()["tokens"]["total_tokens"] == 3300
                        evidence["cases"][
                            "native_fork_checkpoint_replay_retains_history"
                        ] = "passed"
                        with psycopg.connect(runtime_dsn) as lock:
                            lock.execute(
                                "LOCK TABLE runtime_usage_calls IN ACCESS EXCLUSIVE MODE"
                            )
                            fault_thread, fault_run, _ = await create()
                            fault_usage = (
                                await request(
                                    "GET",
                                    f"/threads/{fault_thread}/runs/{fault_run}/usage",
                                )
                            ).json()
                            assert (
                                fault_usage["unavailable_reason"]
                                == "backend_unavailable"
                            ), fault_usage
                        fault_usage = (
                            await request(
                                "GET", f"/threads/{fault_thread}/runs/{fault_run}/usage"
                            )
                        ).json()
                        assert fault_usage["availability"] in {"unavailable", "partial"}
                        fault_stream = await request(
                            "GET",
                            f"/threads/{fault_thread}/runs/{fault_run}/stream",
                            params={"last_event_id": "0"},
                        )
                        assert "probe-ok" in fault_stream.text
                        evidence["cases"][
                            "ledger_lock_failure_preserves_native_agent_sse"
                        ] = "passed"
                        with session_scope(factory) as session:
                            record = session.get(RuntimeCatalogModelRecord, model_id)
                            record.pricing_json = RuntimeCatalogService._price_snapshot(
                                {
                                    **{
                                        k: v
                                        for k, v in pricing.items()
                                        if k not in {"version", "source", "updated_at"}
                                    },
                                    "input": "4.0000000000",
                                }
                            )
                        assert (await request("GET", path)).json()["cost"][
                            "estimated_cost_usd"
                        ] == "0.004880000000"
                        worker = ProductionWorker(
                            native.state.graph_registry, owner="usage-restarted-worker"
                        )
                        _, changed_run, _ = await create(thread=thread)
                        changed = (
                            await request(
                                "GET", f"/threads/{thread}/runs/{changed_run}/usage"
                            )
                        ).json()
                        assert (
                            changed["cost"]["pricing_versions"]
                            != first["cost"]["pricing_versions"]
                        )
                        assert (
                            changed["cost"]["estimated_cost_usd"] == "0.008080000000"
                        ), changed
                        evidence["cases"]["worker_restart_price_snapshot"] = "passed"
                        with session_scope(factory) as session:
                            session.get(
                                RuntimeCatalogModelRecord, model_id
                            ).pricing_json = None
                        _, unknown_run, _ = await create(thread=thread)
                        unknown = (
                            await request(
                                "GET", f"/threads/{thread}/runs/{unknown_run}/usage"
                            )
                        ).json()
                        assert (
                            unknown["tokens"]["total_tokens"] == 2200
                            and unknown["cost"]["status"] == "unknown"
                        )
                        evidence["cases"][
                            "cleared_price_preserves_tokens_and_history"
                        ] = "passed"
                        os.environ["RUNTIME_USAGE_ENABLED"] = "false"
                        _, disabled_run, disabled_time = await create(
                            thread=thread, timing="disabled"
                        )
                        assert (
                            await request(
                                "GET", f"/threads/{thread}/runs/{disabled_run}/usage"
                            )
                        ).json()["availability"] == "disabled"
                        assert (await request("GET", path)).json()["tokens"][
                            "total_tokens"
                        ] == 2200
                        os.environ["RUNTIME_USAGE_ENABLED"] = "true"
                        _, resumed_run, _ = await create(thread=thread)
                        assert (
                            await request(
                                "GET", f"/threads/{thread}/runs/{resumed_run}/usage"
                            )
                        ).json()["coverage"]["observed_call_count"] == 2
                        evidence["cases"]["disable_history_reenable"] = "passed"
                        deletion_token = create_runtime_delegation_token(
                            subject=str(users[0]),
                            tenant_id=str(tenant.id),
                            project_id=project_id,
                            role="project_executor",
                            permissions=[],
                            policy_version="probe",
                            allowed_model_ids=[str(model_id)],
                            tool_overrides={},
                            tool_policy_version="probe",
                            scope={
                                "tenant_id": str(tenant.id),
                                "project_id": project_id,
                                "assistant_id": "reference_agent",
                                "thread_id": thread,
                                "operation": "run-delete",
                            },
                            context_hash=empty_runtime_context_hash(),
                            settings=settings,
                        )
                        async with httpx.AsyncClient(
                            base_url=runtime_url, timeout=20
                        ) as internal:
                            deleted = await internal.delete(
                                f"/threads/{thread}/runs/{second_run}",
                                headers={"authorization": "Bearer " + deletion_token},
                            )
                            assert deleted.status_code in {200, 204}, deleted.text
                        await request(
                            "GET",
                            f"/threads/{thread}/runs/{second_run}/usage",
                            expected=404,
                        )
                        assert (
                            await request("GET", f"/threads/{thread}/usage")
                        ).json()["recorded_run_count"] == 5
                        evidence["cases"]["deleted_native_run_retains_thread_cost"] = (
                            "passed"
                        )
                        with session_scope(factory) as session:
                            session.delete(
                                session.get(RuntimeCatalogModelRecord, model_id)
                            )
                        assert (await request("GET", path)).json()["cost"] == first[
                            "cost"
                        ]
                        evidence["cases"][
                            "deleted_catalog_retains_historical_price"
                        ] = "passed"
                        with psycopg.connect(runtime_dsn) as conn:
                            persisted = conn.execute(
                                "SELECT to_jsonb(c)::text FROM runtime_usage_calls c"
                            ).fetchall()
                            assert all(
                                CANARY not in row[0]
                                and "isolated-secret-key" not in row[0]
                                and provider_url not in row[0]
                                for row in persisted
                            )
                        evidence["cases"]["numeric_only_ledger_projection"] = "passed"
                        with psycopg.connect(runtime_dsn) as conn:
                            retained = conn.execute(
                                "SELECT count(*) FROM runtime_usage_calls WHERE thread_id=%s",
                                (fork,),
                            ).fetchone()[0]
                        await request("DELETE", f"/threads/{fork}")
                        await request("GET", f"/threads/{fork}/usage", expected=403)
                        with psycopg.connect(runtime_dsn) as conn:
                            assert (
                                conn.execute(
                                    "SELECT count(*) FROM runtime_usage_calls WHERE thread_id=%s",
                                    (fork,),
                                ).fetchone()[0]
                                == retained
                                > 0
                            )
                        evidence["cases"][
                            "deleted_thread_denies_query_retains_ledger"
                        ] = "passed"
                        with session_scope(factory) as session:
                            SqlAlchemyProjectsRepository(session).remove_project_member(
                                project_id=UUID(project_id), user_id=users[0]
                            )
                        await request("GET", path, expected=403)
                        evidence["cases"]["current_member_revocation"] = "passed"
                        evidence["samples"] = {
                            "run": first,
                            "thread": combined,
                            "child": child_usage,
                            "unknown": unknown,
                            "changed_price": changed,
                            "zero": paused,
                            "resumed_hitl": hitl_usage,
                            "queue": queue_usage,
                            "fault": fault_usage,
                        }
                        evidence["performance"] = {
                            "provider_calls": len(calls),
                            "write_count": len(write_times),
                            "write_p50_ms": round(statistics.median(write_times), 3),
                            "write_p95_ms": round(
                                sorted(write_times)[int(len(write_times) * 0.95) - 1], 3
                            ),
                            "query_count": len(query_times),
                            "query_p50_ms": round(statistics.median(query_times), 3),
                            "query_p95_ms": round(
                                sorted(query_times)[int(len(query_times) * 0.95) - 1], 3
                            ),
                            "enabled_agent_ms": round(enabled_time, 3),
                            "disabled_agent_ms": round(disabled_time, 3),
                            "live_sse_first_model_text": first_tokens,
                        }
                        evidence["complete"] = True
    sampling_done.set()
    await sampler
    evidence["performance"]["connection_sampling"] = {
        "interval_ms": 20,
        "sample_count": len(connection_samples),
        "peak_runtime_connections": max(
            (
                count
                for rows in connection_samples
                for name, count, _ in rows
                if name == databases[0]
            ),
            default=0,
        ),
        "peak_platform_connections": max(
            (
                count
                for rows in connection_samples
                for name, count, _ in rows
                if name == databases[1]
            ),
            default=0,
        ),
        "peak_idle_in_transaction": max(
            (sum(idle for _, _, idle in rows) for rows in connection_samples), default=0
        ),
    }
    repository.upsert_call = original_upsert
    if os.getenv("USAGE_EVIDENCE_PATH"):
        Path(os.environ["USAGE_EVIDENCE_PATH"]).write_text(
            json.dumps(evidence, indent=2) + "\n"
        )
    if os.getenv("USAGE_EXPORT_CONTRACT_DIR"):
        export_contract(evidence, os.environ["USAGE_EXPORT_CONTRACT_DIR"])
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
