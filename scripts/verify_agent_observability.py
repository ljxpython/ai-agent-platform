"""Isolated native-worker verification; never uses the active Runtime database.

Reads OBSERVABILITY_ENV_FILE for Langfuse credentials only. Creates a uniquely
named probe database, retained as validation evidence. Run with Runtime Python
and both service src directories in PYTHONPATH.
"""

from __future__ import annotations

import asyncio
import atexit
import json
import logging
import os
import resource
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
from contextlib import asynccontextmanager, contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware

ROOT = Path(__file__).resolve().parents[1]
SECRET = "isolated-observability-probe-secret-at-least-32-bytes"
CANARY = "provider-body-observability-canary-DO-NOT-EXPORT"
BASELINE_REVISION = "0bc15df1840c83750d821c93fb65600d0d483fa4"


@contextmanager
def rollback_agents(enabled):
    if not enabled:
        yield
        return
    from runtime_service import observability, webapp
    from runtime_service.observability import langfuse
    from runtime_service.services.demo.workflow_demo import agent as workflow
    from runtime_service.services.reference_agent import agent as reference

    def baseline(module, path):
        source = subprocess.check_output(
            ["rtk", "proxy", "git", "show", f"{BASELINE_REVISION}:{path}"], cwd=ROOT
        )
        namespace = {"__name__": module.__name__, "__file__": module.__file__}
        exec(compile(source, str(module.__file__), "exec"), namespace)  # noqa: S102 - trusted source at the fixed baseline revision.
        return SimpleNamespace(**namespace)

    previous = baseline(
        langfuse, "apps/runtime-service/src/runtime_service/observability/langfuse.py"
    )
    with (
        patch.object(
            observability, "with_langfuse_tracing", previous.with_langfuse_tracing
        ),
        patch.object(
            observability, "initialize_langfuse", previous.initialize_langfuse
        ),
        patch.object(observability, "close_langfuse", previous.close_langfuse),
    ):
        old_reference = baseline(
            reference,
            "apps/runtime-service/src/runtime_service/services/reference_agent/agent.py",
        )
        old_workflow = baseline(
            workflow,
            "apps/runtime-service/src/runtime_service/services/demo/workflow_demo/agent.py",
        )
        old_webapp = baseline(
            webapp, "apps/runtime-service/src/runtime_service/webapp.py"
        )
    with (
        patch.object(reference, "get_agent", old_reference.get_agent),
        patch.object(workflow, "get_agent", old_workflow.get_agent),
    ):
        yield old_webapp.app


async def probe_workflow_graph(config):
    from runtime_service.services.demo.workflow_demo import agent

    return await agent.get_agent(config)


def interrupt_id(state):
    interrupts = state.get("interrupts") if isinstance(state, dict) else None
    if isinstance(interrupts, dict):
        return next(iter(interrupts), None)
    if isinstance(interrupts, list):
        for item in interrupts:
            if isinstance(item, dict) and item.get("id"):
                return item["id"]
    for task in state.get("tasks", []) if isinstance(state, dict) else []:
        for item in task.get("interrupts", []) if isinstance(task, dict) else []:
            if isinstance(item, dict) and item.get("id"):
                return item["id"]
    return None


async def verify_rollback(
    request,
    create,
    status,
    worker,
    slow_started,
    evidence,
    capture,
    native,
):
    thread, run = await create("rollback-normal")
    assert await worker.run_once() and await status(thread, run) == "success"
    await request("GET", f"/threads/{thread}/runs/{run}/diagnostics", 404)
    assert not any(
        getattr(route, "path", "").endswith("/diagnostics")
        for route in native.state.custom_app.router.routes
    )
    evidence["internal_diagnostics_route_present"] = False
    evidence["cases"]["rollback_routes_removed"] = "passed"
    stream = await request(
        "GET",
        f"/threads/{thread}/runs/{run}/stream",
        params={"last_event_id": "0"},
    )
    assert stream.headers["content-type"].startswith("text/event-stream")
    assert "probe-ok" in stream.text
    evidence["cases"]["rollback_normal_sse"] = "passed"
    evidence["samples"]["rollback_normal"] = {
        "thread_id": thread,
        "run_id": run,
        "status": "success",
    }
    for decision in ("approve", "reject"):
        hitl_thread, hitl_run = await create("需要人工确认", "workflow_demo")
        assert (
            await worker.run_once()
            and await status(hitl_thread, hitl_run) == "interrupted"
        )
        interrupted_state = (
            await request("GET", f"/threads/{hitl_thread}/state")
        ).json()
        active_interrupt_id = interrupt_id(interrupted_state)
        assert active_interrupt_id
        resumed = (
            await request(
                "POST",
                f"/threads/{hitl_thread}/runs",
                headers={"Idempotency-Key": uuid4().hex},
                json={
                    "assistant_id": "workflow_demo",
                    "command": {
                        "resume": {
                            active_interrupt_id: {"decisions": [{"type": decision}]}
                        }
                    },
                },
            )
        ).json()["run_id"]
        assert (
            await worker.run_once() and await status(hitl_thread, resumed) == "success"
        )
        state = (await request("GET", f"/threads/{hitl_thread}/state")).json()
        assert state["values"]["confirmation"] == decision
        evidence["cases"][f"rollback_{decision}_resume"] = "passed"
        evidence["samples"][f"rollback_{decision}"] = {
            "thread_id": hitl_thread,
            "interrupted_run_id": hitl_run,
            "resumed_run_id": resumed,
            "status": "success",
            "confirmation": decision,
        }
    slow_started.clear()
    slow_thread, slow_run = await create("slow")
    executing = asyncio.create_task(worker.run_once())
    await asyncio.wait_for(slow_started.wait(), 10)
    await request(
        "POST",
        f"/threads/{slow_thread}/runs/{slow_run}/cancel",
        json={"action": "interrupt"},
    )
    await executing
    terminal = await status(slow_thread, slow_run)
    assert terminal in {"cancelled", "interrupted"}
    evidence["cases"]["rollback_cancel"] = "passed"
    evidence["samples"]["rollback_cancel"] = {
        "thread_id": slow_thread,
        "run_id": slow_run,
        "status": terminal,
    }
    assert not capture.events
    evidence["cases"]["rollback_previous_capture"] = "passed"
    evidence.update(
        baseline_revision=BASELINE_REVISION,
        collection="previous_revision_with_remote_export_disabled",
        diagnostic_events=0,
        scope="rollback",
    )


async def probe_graph(config):
    from runtime_service.services.reference_agent import agent

    scenario = os.getenv("OBSERVABILITY_PROBE_SCENARIO")
    if scenario and (config.get("configurable") or {}).get("langgraph_auth_user"):
        from langchain_core.messages import AIMessage
        from langchain_core.tools import tool

        model = probe_model(fail=True)
        fallback = probe_model(responses=[AIMessage(content="fallback-ok")])
        if scenario == "later_tool_failure":
            fallback = probe_model(
                responses=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "read_reference",
                                "args": {"topic": "probe"},
                                "id": "probe-tool",
                            }
                        ],
                    )
                ]
            )

        @tool
        def read_reference(topic: str) -> str:
            """Inject a tool failure after a recovered model call."""
            raise LookupError(CANARY)

        injected = {
            **config,
            "configurable": {
                **config["configurable"],
                "_runtime_model": model,
                "_runtime_fallback_model": fallback,
            },
        }
        with patch.object(
            agent,
            "read_reference",
            read_reference
            if scenario == "later_tool_failure"
            else agent.read_reference,
        ):
            return await agent.get_agent(injected)
    if os.getenv("OBSERVABILITY_PROBE_FACTORY_FAILURE") == "1" and (
        config.get("configurable") or {}
    ).get("langgraph_auth_user"):
        with patch.object(agent, "build_model", side_effect=RuntimeError(CANARY)):
            return await agent.get_agent(config)
    return await agent.get_agent(config)


def probe_model(*, responses=None, fail=False, fail_on=()):
    from langchain_core.language_models.fake_chat_models import (
        FakeMessagesListChatModel,
    )
    from langchain_core.messages import AIMessage
    from openai import RateLimitError

    class Model(FakeMessagesListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

        def _generate(self, messages, *args, **kwargs):
            if fail or any(
                item.type == "human" and item.content in fail_on for item in messages
            ):
                raise RateLimitError(
                    CANARY,
                    response=httpx.Response(
                        429, request=httpx.Request("POST", "https://provider.invalid")
                    ),
                    body={"error": {"code": "rate_limit_exceeded"}},
                )
            return super()._generate(messages, *args, **kwargs)

    return Model(responses=responses or [AIMessage(content="probe-ok")])


async def probe_showcase_graph(config):
    from langchain_core.messages import AIMessage
    from runtime_service.services.demo.showcase_demo import agent

    if not (config.get("configurable") or {}).get("langgraph_auth_user"):
        return await agent.get_agent(config)
    descriptions = ("isolated-child-one", "isolated-child-two")
    model = probe_model(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "task",
                        "args": {"subagent_type": "research", "description": name},
                        "id": name,
                    }
                    for name in descriptions
                ],
            ),
            AIMessage(content="children-handled"),
        ],
        fail_on=descriptions,
    )
    with patch.object(agent, "build_model", lambda *args, **kwargs: model):
        return await agent.get_agent(config)


@asynccontextmanager
async def serve(app, *, separate_loop=False):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False))
    serving = server.serve(sockets=[sock])
    task = asyncio.create_task(
        asyncio.to_thread(asyncio.run, serving) if separate_loop else serving
    )
    try:
        async with asyncio.timeout(90):
            while not server.started:
                if task.done():
                    await task
                    raise RuntimeError("verification server failed to start")
                await asyncio.sleep(0.02)
        yield f"http://127.0.0.1:{sock.getsockname()[1]}"
    finally:
        server.should_exit = True
        await task
        sock.close()


class Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.events = []

    def emit(self, record):
        message = record.getMessage()
        if message.startswith('{"schema_version"'):
            self.events.append(json.loads(message))


async def benchmark_queries(client, thread_id, run_id):
    from runtime_service.http import diagnostics as diagnostics_http
    from runtime_service.observability import query

    measurements = {}
    query_impl = diagnostics_http.query_run_diagnostics
    query_latencies = []
    upstream_failures = []
    get_many_impl = query._client.observations.get_many

    async def observed_get_many(**kwargs):
        try:
            return await get_many_impl(**kwargs)
        except Exception as exc:
            upstream_failures.append(
                {
                    "error_type": type(exc).__name__,
                    "status": getattr(exc, "status_code", None),
                }
            )
            raise

    async def observed_query(**kwargs):
        started = time.perf_counter()
        try:
            return await query_impl(**kwargs)
        finally:
            query_latencies.append((time.perf_counter() - started) * 1000)

    for name, concurrency, endpoint in (
        ("single_diagnostics", 1, "/diagnostics"),
        ("ten_diagnostics", 10, "/diagnostics"),
        ("fifty_native_reads", 50, ""),
        ("fifty_diagnostics", 50, "/diagnostics"),
    ):

        async def sample(endpoint=endpoint):
            started = time.perf_counter()
            try:
                response = await client.get(
                    f"/api/langgraph/threads/{thread_id}/runs/{run_id}{endpoint}",
                    timeout=120,
                )
                assert CANARY not in response.text
                payload = response.json()
                error = payload.get("error")
                code = error.get("code") if isinstance(error, dict) else None
                return {
                    "status": response.status_code,
                    "availability": payload.get("availability"),
                    "error_code": code,
                    "latency_ms": (time.perf_counter() - started) * 1000,
                }
            except httpx.HTTPError as exc:
                return {
                    "status": type(exc).__name__,
                    "latency_ms": (time.perf_counter() - started) * 1000,
                }

        query_latencies.clear()
        upstream_failures.clear()
        with (
            patch.object(diagnostics_http, "query_run_diagnostics", observed_query),
            patch.object(query._client.observations, "get_many", observed_get_many),
        ):
            rows = await asyncio.gather(*(sample() for _ in range(concurrency)))
        latencies = [item["latency_ms"] for item in rows]
        measurements[name] = {
            "concurrency": concurrency,
            "client_timeout_seconds": 120,
            "success": sum(item["status"] == 200 for item in rows),
            "outcomes": {
                str(status): sum(item["status"] == status for item in rows)
                for status in {item["status"] for item in rows}
            },
            "availability": {
                str(state): sum(item.get("availability") == state for item in rows)
                for state in {item.get("availability") for item in rows}
            },
            "error_codes": {
                str(code): sum(item.get("error_code") == code for item in rows)
                for code in {item.get("error_code") for item in rows}
            },
            "p50_ms": round(statistics.median(latencies), 2),
            "p95_ms": round(sorted(latencies)[int(0.95 * (len(rows) - 1))], 2),
            "process_maxrss": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            "maxrss_unit": "bytes" if sys.platform == "darwin" else "KiB",
            "langfuse_query": {
                "count": len(query_latencies),
                "p50_ms": round(statistics.median(query_latencies), 2),
                "p95_ms": round(
                    sorted(query_latencies)[int(0.95 * (len(query_latencies) - 1))], 2
                ),
            }
            if query_latencies
            else None,
            "langfuse_failures": list(upstream_failures),
        }
        print(json.dumps({"query_measurement": name, **measurements[name]}), flush=True)
    return measurements


async def benchmark_startup():
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.language_models.fake_chat_models import FakeListChatModel
    from runtime_service.observability import langfuse
    from runtime_service.observability.startup import StartupDiagnostics
    from runtime_service.services.reference_agent import agent

    class Model(FakeListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

    class BaselineStartup(StartupDiagnostics):
        @contextmanager
        def phase(self, name):
            yield

        def _emit(self, event, record):
            pass

    class Timing(BaseCallbackHandler):
        def __init__(self):
            self.started = time.perf_counter()
            self.values = {}

        def on_chat_model_start(self, *args, **kwargs):
            self.values.setdefault(
                "first_model_ms", (time.perf_counter() - self.started) * 1000
            )

        def on_llm_new_token(self, *args, **kwargs):
            self.values.setdefault(
                "first_token_ms", (time.perf_counter() - self.started) * 1000
            )

    async def sample():
        timing = Timing()
        graph = await agent.get_agent(
            {
                "metadata": {"run_id": str(uuid4())},
                "callbacks": [timing],
                "configurable": {"_runtime_model": Model(responses=["probe-ok"])},
            }
        )
        timing.values["factory_ms"] = (time.perf_counter() - timing.started) * 1000
        start = time.perf_counter()
        async for _ in graph.astream(
            {"messages": [{"role": "user", "content": "hello"}]}, stream_mode="messages"
        ):
            pass
        timing.values["graph_ms"] = (time.perf_counter() - start) * 1000
        return timing.values

    measurements = {}
    for enabled in (False, True):
        with (
            patch.object(langfuse, "_client", None),
            patch.dict(os.environ, {"LANGFUSE_ENABLED": "false"}),
            patch.object(
                agent,
                "StartupDiagnostics",
                StartupDiagnostics if enabled else BaselineStartup,
            ),
            patch.object(
                langfuse,
                "log_diagnostic",
                langfuse.log_diagnostic if enabled else lambda *args: None,
            ),
        ):
            for _ in range(3):
                await sample()
            tracemalloc.start()
            rows = [await sample() for _ in range(50)]
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            measurements["enabled" if enabled else "baseline"] = {
                key: {
                    "p50_ms": round(statistics.median(row[key] for row in rows), 3),
                    "p95_ms": round(sorted(row[key] for row in rows)[47], 3),
                }
                for key in (
                    "factory_ms",
                    "first_model_ms",
                    "first_token_ms",
                    "graph_ms",
                )
            }
            measurements["enabled" if enabled else "baseline"]["python_peak_bytes"] = (
                peak
            )
    return {"samples_per_mode": 50, "remote_export": "disabled", **measurements}


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
    from runtime_service.db import upgrade as upgrade_runtime_application
    from runtime_service.observability import langfuse, query

    env_file = os.getenv("OBSERVABILITY_ENV_FILE")
    source = dotenv_values(env_file) if env_file else {}
    rollback_only = os.getenv("OBSERVABILITY_VERIFY_PROFILE") == "rollback"
    for key in (
        "LANGFUSE_ENABLED",
        "LANGFUSE_PUBLIC_KEY",
        "LANGFUSE_SECRET_KEY",
        "LANGFUSE_BASE_URL",
        "LANGFUSE_TRACING_ENVIRONMENT",
    ):
        if source.get(key):
            os.environ[key] = str(source[key])
    if rollback_only:
        os.environ.update({"LANGFUSE_ENABLED": "false", "OTEL_ENABLED": "false"})
    suffix = uuid4().hex[:12]
    database = f"graphharbor_observability_{suffix}"
    admin_dsn = os.getenv(
        "OBSERVABILITY_POSTGRES_ADMIN_DSN",
        "postgresql://lijiaxin@127.0.0.1:5432/postgres",
    )
    connection = await asyncpg.connect(admin_dsn, timeout=20)
    try:
        await connection.execute(f'CREATE DATABASE "{database}"')
    finally:
        await connection.close()
    dsn = admin_dsn.rsplit("/", 1)[0] + "/" + database
    os.environ.update(
        {
            "DATABASE_URI": dsn.replace("postgresql://", "postgresql+asyncpg://"),
            "REDIS_URI": "redis://127.0.0.1:6379/0",
            "GRAPHHARBOR_REDIS_PREFIX": f"graphharbor:observability:{suffix}",
            "GRAPHHARBOR_ENV": "production",
            "PLATFORM_RUNTIME_DELEGATION_SECRET": SECRET,
            "PLATFORM_RUNTIME_DELEGATION_ISSUER": "platform-api",
            "PLATFORM_RUNTIME_DELEGATION_AUDIENCE": "runtime-service",
            "GRAPHHARBOR_RUNTIME_CONTEXT_SECRET": SECRET,
            "GRAPHHARBOR_RUNTIME_CONTEXT_ISSUER": "graphharbor",
            "GRAPHHARBOR_RUNTIME_CONTEXT_AUDIENCE": "graphharbor-worker",
        }
    )
    await asyncio.to_thread(upgrade_head, os.environ["DATABASE_URI"])
    await asyncio.to_thread(upgrade_runtime_application, os.environ["DATABASE_URI"])
    provider = FastAPI()
    provider_calls = []
    slow_started = asyncio.Event()

    @provider.post("/v1/chat/completions")
    async def completion(request: Request):
        payload = await request.json()
        text = next(
            (
                message.get("content", "")
                for message in reversed(payload["messages"])
                if message.get("role") == "user"
            ),
            "",
        )
        provider_calls.append(str(text))
        if text == "rate-limit":
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limit_exceeded",
                        "type": "rate_limit_error",
                        "message": CANARY,
                    }
                },
            )
        if text == "slow":
            slow_started.set()
            await asyncio.sleep(3)
        if payload.get("stream"):

            async def chunks():
                for delta, reason in (
                    ({"role": "assistant", "content": "probe-ok"}, None),
                    ({}, "stop"),
                ):
                    yield (
                        "data: "
                        + json.dumps(
                            {
                                "id": "probe",
                                "object": "chat.completion.chunk",
                                "created": int(time.time()),
                                "model": "probe",
                                "choices": [
                                    {
                                        "index": 0,
                                        "delta": delta,
                                        "finish_reason": reason,
                                    }
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
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "probe-ok"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

    capture = Capture()
    request_timings = {}
    query_failures = []

    def record_timing(name, started):
        request_timings.setdefault(name, []).append(
            (time.perf_counter() - started) * 1000
        )

    def timing_summary():
        return {
            name: {
                "count": len(rows),
                "p50_ms": round(statistics.median(rows), 2),
                "p95_ms": round(sorted(rows)[int(0.95 * (len(rows) - 1))], 2),
            }
            for name, rows in request_timings.items()
        }

    diagnostic_logger = logging.getLogger("runtime_service.observability.diagnostics")
    diagnostic_logger.setLevel(logging.INFO)
    diagnostic_logger.addHandler(capture)
    evidence = {
        "complete": False,
        "database": database,
        "redis_prefix": os.environ["GRAPHHARBOR_REDIS_PREFIX"],
        "cases": {},
        "samples": {},
        "http_samples": {},
        "langfuse_query_failures": query_failures,
    }

    def save_evidence():
        output = os.getenv("OBSERVABILITY_EVIDENCE_PATH")
        if output:
            Path(output).write_text(
                json.dumps(evidence, indent=2, ensure_ascii=False) + "\n"
            )

    atexit.register(save_evidence)
    with (
        tempfile.TemporaryDirectory(prefix="observability-platform-") as directory,
        rollback_agents(rollback_only) as rollback_app,
    ):
        async with serve(provider) as provider_url:
            native = runtime_app(
                {
                    "graphs": {
                        "reference_agent": "scripts/verify_agent_observability.py:probe_graph",
                        "showcase_demo": "scripts/verify_agent_observability.py:probe_showcase_graph",
                        "workflow_demo": (
                            "scripts/verify_agent_observability.py:probe_workflow_graph"
                            if rollback_only
                            else "apps/runtime-service/src/runtime_service/services/demo/workflow_demo/agent.py:get_agent"
                        ),
                    },
                    "auth": {
                        "path": "apps/runtime-service/src/runtime_service/auth/platform.py:auth"
                    },
                    "http": {"disable_mcp": True},
                },
                base_dir=ROOT,
                custom_app=rollback_app or webapp.app,
            )

            async def runtime_timing(request, call_next):
                started = time.perf_counter()
                try:
                    return await call_next(request)
                finally:
                    name = (
                        "runtime.diagnostics"
                        if request.url.path.endswith("/diagnostics")
                        else "runtime.native_read"
                        if request.method == "GET" and "/threads/" in request.url.path
                        else "runtime.other"
                    )
                    record_timing(name, started)

            native.add_middleware(BaseHTTPMiddleware, dispatch=runtime_timing)
            async with serve(native) as runtime_url:
                if query._client is not None:
                    get_many_impl = query._client.observations.get_many

                    async def capture_query_failure(**kwargs):
                        try:
                            return await get_many_impl(**kwargs)
                        except Exception as exc:
                            query_failures.append(
                                {
                                    "error_type": type(exc).__name__,
                                    "status": getattr(exc, "status_code", None),
                                }
                            )
                            raise

                    query._client.observations.get_many = capture_query_failure
                platform = create_app()
                if rollback_only:
                    platform.router.routes = [
                        route
                        for route in platform.router.routes
                        if not getattr(route, "path", "").endswith("/diagnostics")
                    ]

                @platform.middleware("http")
                async def platform_timing(request, call_next):
                    started = time.perf_counter()
                    try:
                        return await call_next(request)
                    finally:
                        name = (
                            "platform.acl"
                            if request.url.path.endswith("/thread-authorization")
                            else "platform.diagnostics"
                            if request.url.path.endswith("/diagnostics")
                            else "platform.other"
                        )
                        record_timing(name, started)

                settings = platform.state.settings
                settings.platform_db_enabled = settings.platform_db_auto_create = True
                settings.database_url = f"sqlite:///{Path(directory) / 'platform.db'}"
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
                    model_id = uuid4()
                    with session_scope(factory) as session:
                        projects = SqlAlchemyProjectsRepository(session)
                        tenant = projects.get_or_create_default_tenant()
                        project = projects.create_project(
                            tenant_id=tenant.id, name="Observability", description=""
                        )
                        other = projects.create_project(
                            tenant_id=tenant.id, name="Other", description=""
                        )
                        identities = SqlAlchemyIdentityRepository(session)
                        users = [
                            identities.create_user(
                                username=name,
                                external_subject=name,
                                password_hash=hash_password("test-password"),
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
                                    "workflow_demo",
                                    "showcase_demo",
                                )
                            ]
                        )
                        session.add(
                            RuntimeCatalogModelRecord(
                                id=model_id,
                                display_name="probe",
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
                        native.state.graph_registry, owner="observability-probe"
                    )
                    async with httpx.AsyncClient(
                        base_url=platform_url,
                        headers=headers,
                        timeout=20,
                        trust_env=False,
                    ) as client:

                        async def request(method, path, expected=200, **kwargs):
                            response = await client.request(
                                method, "/api/langgraph" + path, **kwargs
                            )
                            assert response.status_code == expected, (
                                method,
                                path,
                                response.status_code,
                                response.text[:500],
                            )
                            if expected >= 400:
                                assert CANARY not in response.text
                                evidence["http_samples"][str(expected)] = (
                                    response.json()
                                )
                            return response

                        async def create(prompt, graph="reference_agent", thread=None):
                            if thread is None:
                                thread = (
                                    await request(
                                        "POST", "/threads", json={"graph_id": graph}
                                    )
                                ).json()["thread_id"]
                            run = (
                                await request(
                                    "POST",
                                    f"/threads/{thread}/runs",
                                    headers={"Idempotency-Key": uuid4().hex},
                                    json={
                                        "assistant_id": graph,
                                        "input": {
                                            "messages": [
                                                {"role": "user", "content": prompt}
                                            ]
                                        },
                                        "context": {"model_id": str(model_id)},
                                    },
                                )
                            ).json()
                            return thread, run["run_id"]

                        async def status(thread, run):
                            return (
                                await request("GET", f"/threads/{thread}/runs/{run}")
                            ).json()["status"]

                        async def diagnostics(thread, run, recorded=True, ready=None):
                            if recorded and langfuse._client is not None:
                                await asyncio.to_thread(langfuse._client.flush)
                            result = None
                            for _ in range(40 if recorded else 1):
                                response = await request(
                                    "GET", f"/threads/{thread}/runs/{run}/diagnostics"
                                )
                                assert response.headers["cache-control"] == "no-store"
                                result = response.json()
                                evidence["samples"]["last_query"] = result
                                assert CANARY not in response.text
                                if not recorded or (
                                    ready(result)
                                    if ready
                                    else result["graph_executions"]
                                    and result["startup"]
                                ):
                                    break
                                await asyncio.sleep(1)
                            return result

                        if rollback_only:
                            await verify_rollback(
                                request,
                                create,
                                status,
                                worker,
                                slow_started,
                                evidence,
                                capture,
                                native,
                            )
                            evidence["complete"] = True
                            save_evidence()
                            diagnostic_logger.removeHandler(capture)
                            print(json.dumps(evidence, ensure_ascii=False))
                            return

                        thread, run = await create("rate-limit")
                        assert await worker.run_once()
                        assert await status(thread, run) == "error"
                        failed = await diagnostics(
                            thread,
                            run,
                            ready=lambda item: (
                                item["model_errors"]
                                and item["graph_executions"]
                                and item["startup"]
                            ),
                        )
                        assert (
                            failed["model_errors"]
                            and failed["model_errors"][0]["code"]
                            == "provider_rate_limited"
                        ), failed
                        assert (
                            failed["correlation"]["execution_request_id"]
                            != failed["request_id"]
                        )
                        assert failed["trace"]["url"] is None
                        matching = [
                            event
                            for event in capture.events
                            if event.get("run_id") == run
                        ]
                        assert any(
                            event.get("code") == "provider_rate_limited"
                            for event in matching
                        )
                        assert CANARY not in json.dumps(matching)
                        evidence["cases"]["native_429_safe_query"] = "passed"
                        evidence["samples"]["provider_rate_limited"] = failed
                        async with client.stream(
                            "POST",
                            f"/api/langgraph/threads/{thread}/stream/events",
                            json={"channels": ["lifecycle"], "since": 0},
                        ) as stream:
                            assert stream.status_code == 200
                            async with asyncio.timeout(10):
                                async for line in stream.aiter_lines():
                                    assert CANARY not in line
                                    if line.startswith("data:"):
                                        event = json.loads(line[5:])
                                        if (
                                            event["params"]["data"].get("status")
                                            == "error"
                                        ):
                                            break
                                else:
                                    raise AssertionError("missing failed lifecycle")
                        events = await request(
                            "GET",
                            f"/threads/{thread}/runs/{run}/stream",
                            params={"last_event_id": "0"},
                        )
                        frames = []
                        for frame in events.text.split("\n\n"):
                            name = next(
                                (
                                    line[6:].strip()
                                    for line in frame.splitlines()
                                    if line.startswith("event:")
                                ),
                                None,
                            )
                            if name:
                                frames.append(
                                    {"event": name, "contains_canary": CANARY in frame}
                                )
                        assert CANARY not in events.text, frames
                        assert '"error"' in events.text, (
                            "missing error terminal",
                            frames,
                        )
                        state = await request("GET", f"/threads/{thread}/state")
                        assert CANARY not in state.text
                        for path in (
                            f"/threads/{thread}",
                            f"/threads/{thread}/runs/{run}",
                        ):
                            assert CANARY not in (await request("GET", path)).text
                        history = await request(
                            "POST", f"/threads/{thread}/history", json={"limit": 10}
                        )
                        assert CANARY not in history.text
                        await request(
                            "GET",
                            f"/threads/{thread}/runs/{run}/diagnostics",
                            403,
                            headers=peer_headers,
                        )
                        await request(
                            "GET",
                            f"/threads/{thread}/runs/{run}/diagnostics",
                            403,
                            headers={**headers, "x-project-id": other_id},
                        )
                        await request(
                            "GET", f"/threads/{thread}/runs/{uuid4()}/diagnostics", 404
                        )
                        evidence["cases"]["public_error_and_scope_isolation"] = "passed"
                        owner = ActorContext(
                            user_id=str(users[0]),
                            project_roles={project_id: ("project_executor",)},
                        )
                        for actions, expected_status in ((["read"], 200), ([], 403)):
                            await asyncio.to_thread(
                                thread_access.share,
                                factory,
                                actor=owner,
                                project_id=project_id,
                                thread_id=thread,
                                user_id=str(users[1]),
                                actions=actions,
                            )
                            await request(
                                "GET",
                                f"/threads/{thread}/runs/{run}/diagnostics",
                                expected_status,
                                headers=peer_headers,
                            )
                        evidence["cases"]["shared_read_and_real_revocation"] = "passed"
                        await request(
                            "GET",
                            f"/threads/{thread}/runs/{run}/diagnostics",
                            401,
                            headers={**headers, "authorization": ""},
                        )
                        good_thread, good_run = await create("hello")
                        assert (
                            await worker.run_once()
                            and await status(good_thread, good_run) == "success"
                        )
                        good = await diagnostics(good_thread, good_run)
                        assert (
                            not good["model_errors"]
                            and good["startup"]
                            and good["graph_executions"]
                        )
                        evidence["cases"]["native_success"] = "passed"
                        evidence["samples"]["success"] = good
                        if os.getenv("OBSERVABILITY_VERIFY_PROFILE") == "query":
                            request_timings.clear()
                            evidence["performance"] = await benchmark_queries(
                                client, good_thread, good_run
                            )
                            evidence["request_timings"] = timing_summary()
                            assert await status(good_thread, good_run) == "success"
                            evidence.update(complete=True, scope="query_capacity")
                            save_evidence()
                            return
                        _, second_run = await create("rate-limit", thread=good_thread)
                        assert await worker.run_once()
                        assert await status(good_thread, second_run) == "error"
                        second = await diagnostics(
                            good_thread,
                            second_run,
                            ready=lambda item: bool(
                                item["model_errors"] and item["trace"]
                            ),
                        )
                        original = await diagnostics(
                            good_thread,
                            good_run,
                            ready=lambda item: bool(
                                item["trace"]
                                and item["graph_executions"]
                                and item["startup"]
                            ),
                        )
                        assert (
                            original["run_status"] == "success"
                            and not original["model_errors"]
                        )
                        assert second["trace"] and original["trace"], (second, original)
                        assert (
                            second["trace"]["trace_id"] != original["trace"]["trace_id"]
                        )
                        evidence["cases"]["same_thread_run_isolation"] = "passed"
                        evidence["samples"]["same_thread_second_run"] = second
                        for scenario, expected in (
                            ("fallback", "success"),
                            ("later_tool_failure", "error"),
                        ):
                            from runtime_service.services.reference_agent import (
                                agent as reference,
                            )

                            with (
                                patch.dict(
                                    os.environ,
                                    {"OBSERVABILITY_PROBE_SCENARIO": scenario},
                                ),
                                patch.object(
                                    reference,
                                    "_DEFAULTS",
                                    replace(
                                        reference._DEFAULTS, model_id=str(model_id)
                                    ),
                                ),
                            ):
                                recovered_thread, recovered_run = await create(scenario)
                                assert await worker.run_once()
                            assert (
                                await status(recovered_thread, recovered_run)
                                == expected
                            )
                            recovered = await diagnostics(
                                recovered_thread,
                                recovered_run,
                                ready=lambda item: bool(
                                    item["model_errors"] and item["graph_executions"]
                                ),
                            )
                            assert len(recovered["model_errors"]) == 1
                            assert (
                                recovered["graph_executions"][0]["error_code"] is None
                            )
                            evidence["cases"]["native_" + scenario] = "passed"
                            evidence["samples"][scenario] = recovered
                        from runtime_service.services.demo.showcase_demo import (
                            agent as showcase,
                        )

                        with (
                            patch.dict(
                                os.environ,
                                {
                                    "RUNTIME_BACKEND": "local",
                                    "RUNTIME_SHOWCASE_WORKSPACE_ROOT": str(
                                        Path(directory) / "workspaces"
                                    ),
                                },
                            ),
                            patch.object(
                                showcase,
                                "_DEFAULTS",
                                replace(showcase._DEFAULTS, model_id=str(model_id)),
                            ),
                        ):
                            child_thread, child_run = await create(
                                "parallel research", "showcase_demo"
                            )
                            assert await worker.run_once()
                        children = await diagnostics(
                            child_thread,
                            child_run,
                            ready=lambda item: len(item["model_errors"]) == 2,
                        )
                        assert len(children["model_errors"]) == 2
                        assert all(
                            item["scope"] == "subagent"
                            for item in children["model_errors"]
                        )
                        assert (
                            len(
                                {
                                    tuple(item["namespace"])
                                    for item in children["model_errors"]
                                }
                            )
                            == 2
                        )
                        evidence["cases"]["parallel_subagent_run_identity"] = "passed"
                        evidence["samples"]["parallel_subagents"] = children
                        from platform_api.adapters.langgraph.runtime_gateway_upstream import (
                            LangGraphRuntimeGatewayUpstream,
                        )
                        from platform_api.core.errors import UpstreamServiceError

                        for http_status, error_code in (
                            (502, "langgraph_upstream_unavailable"),
                            (503, "runtime_delegation_not_configured"),
                            (504, "langgraph_upstream_timeout"),
                        ):
                            failure = UpstreamServiceError(
                                upstream="langgraph",
                                status_code=http_status,
                                code=error_code,
                                message="Isolated diagnostics upstream unavailable",
                            )
                            with patch.object(
                                LangGraphRuntimeGatewayUpstream,
                                "get_run_diagnostics",
                                AsyncMock(side_effect=failure),
                            ):
                                await request(
                                    "GET",
                                    f"/threads/{good_thread}/runs/{good_run}/diagnostics",
                                    http_status,
                                )
                        evidence["cases"]["safe_http_fault_envelopes"] = "passed"
                        os.environ["OBSERVABILITY_PROBE_FACTORY_FAILURE"] = "1"
                        factory_thread, factory_run = await create("factory-failure")
                        assert (
                            await worker.run_once()
                            and await status(factory_thread, factory_run) == "error"
                        )
                        os.environ.pop("OBSERVABILITY_PROBE_FACTORY_FAILURE")
                        startup_failure = await diagnostics(
                            factory_thread,
                            factory_run,
                            ready=lambda item: item["startup"] is not None,
                        )
                        assert (
                            startup_failure["startup"]
                            and not startup_failure["graph_executions"]
                        )
                        evidence["cases"]["native_factory_failure"] = "passed"
                        evidence["samples"]["factory_failure"] = startup_failure
                        hitl_thread, hitl_run = await create(
                            "需要人工确认", "workflow_demo"
                        )
                        assert (
                            await worker.run_once()
                            and await status(hitl_thread, hitl_run) == "interrupted"
                        )
                        hitl = await diagnostics(hitl_thread, hitl_run)
                        assert not hitl["model_errors"]
                        evidence["cases"]["hitl_not_provider_failure"] = "passed"
                        evidence["samples"]["interrupted"] = hitl
                        slow_thread, slow_run = await create("slow")
                        executing = asyncio.create_task(worker.run_once())
                        await asyncio.wait_for(slow_started.wait(), 10)
                        await request(
                            "POST",
                            f"/threads/{slow_thread}/runs/{slow_run}/cancel",
                            json={"action": "interrupt"},
                        )
                        await executing
                        assert await status(slow_thread, slow_run) in {
                            "cancelled",
                            "interrupted",
                        }
                        cancellation = await diagnostics(slow_thread, slow_run)
                        assert not cancellation["model_errors"]
                        evidence["cases"]["native_cancel"] = "passed"
                        evidence["samples"]["cancelled"] = cancellation

                        evidence["performance"] = await benchmark_queries(
                            client, good_thread, good_run
                        )
                        evidence["request_timings"] = timing_summary()
                        assert await status(good_thread, good_run) == "success"
                        with (
                            patch.object(query, "_client", None),
                            patch.object(langfuse, "_client", None),
                            patch.dict(os.environ, {"LANGFUSE_ENABLED": "false"}),
                        ):
                            old_thread, old_run = await create("rollback-normal")
                            assert (
                                await worker.run_once()
                                and await status(old_thread, old_run) == "success"
                            )
                            disabled = await diagnostics(
                                old_thread, old_run, recorded=False
                            )
                            assert disabled["availability"] == "disabled"
                        evidence["cases"]["disabled_capture_normal_run"] = "passed"
                        evidence["samples"]["disabled"] = disabled
                        for reason in ("not_recorded", "backend_unavailable"):
                            get_many = AsyncMock(return_value={"data": [], "meta": {}})
                            if reason == "backend_unavailable":
                                get_many.side_effect = httpx.ConnectError(
                                    "isolated Langfuse outage"
                                )
                            with patch.object(
                                query,
                                "_client",
                                SimpleNamespace(
                                    observations=SimpleNamespace(get_many=get_many)
                                ),
                            ):
                                unavailable = await diagnostics(
                                    good_thread, good_run, recorded=False
                                )
                            assert unavailable["unavailable_reason"] == reason
                            assert unavailable["run_status"] == "success"
                            evidence["samples"][reason] = unavailable
                        evidence["cases"]["query_outage_does_not_change_run"] = "passed"
                        if all(
                            source.get(name)
                            for name in (
                                "DEEPSEEK_PROXY_URL",
                                "DEEPSEEK_PROXY_API_KEY",
                                "DEEPSEEK_PROXY_DEFAULT_MODEL",
                            )
                        ):
                            for expected_status, provider_model in (
                                (
                                    "success",
                                    str(source["DEEPSEEK_PROXY_DEFAULT_MODEL"]),
                                ),
                                ("error", "observability-invalid-model-" + suffix),
                            ):
                                with session_scope(factory) as session:
                                    record = session.get(
                                        RuntimeCatalogModelRecord, model_id
                                    )
                                    record.provider = record.protocol = "deepseek"
                                    record.model_name = provider_model
                                    record.base_url = str(source["DEEPSEEK_PROXY_URL"])
                                    record.api_key_ciphertext = encrypt_api_key(
                                        str(source["DEEPSEEK_PROXY_API_KEY"]),
                                        master_key=settings.model_config_master_key,
                                    )
                                real_thread, real_run = await create(
                                    "Reply with exactly: observability-smoke-ok"
                                )
                                async with asyncio.timeout(90):
                                    assert await worker.run_once()
                                assert (
                                    await status(real_thread, real_run)
                                    == expected_status
                                )
                                result = await diagnostics(real_thread, real_run)
                                assert bool(result["model_errors"]) == (
                                    expected_status == "error"
                                )
                                if expected_status == "error":
                                    assert (
                                        result["model_errors"][0]["code"]
                                        == "model_unavailable"
                                    )
                                evidence["cases"][
                                    "real_deepseek_" + expected_status
                                ] = "passed"
                                evidence["samples"][
                                    "real_deepseek_" + expected_status
                                ] = result
                        else:
                            evidence["cases"]["real_deepseek_smoke"] = (
                                "blocked: missing configuration"
                            )
                        evidence["startup_performance"] = await benchmark_startup()
                        evidence["provider_calls"] = len(provider_calls)
                        evidence["diagnostic_events"] = len(capture.events)
                        evidence["export_metrics"] = (
                            langfuse.get_observability_metrics()
                        )
    diagnostic_logger.removeHandler(capture)
    evidence["complete"] = True
    evidence["request_timings"] = timing_summary()
    save_evidence()
    print(
        json.dumps(
            {key: value for key, value in evidence.items() if key != "samples"},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
