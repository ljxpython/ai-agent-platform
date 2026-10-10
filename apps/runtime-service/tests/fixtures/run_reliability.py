"""Fault injection around the production graph, used only by disposable tests."""

import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

from fixtures.tool_error_platform import platform_app, record

if os.getenv("BACKGROUND_FAULT_MODE_PATH") and sys.argv[1:2] == ["platform"]:
    from platform_api.adapters.langgraph.runtime_gateway_upstream import (
        LangGraphRuntimeGatewayUpstream,
    )
    from platform_api.core.errors import UpstreamServiceError

    original_submit = LangGraphRuntimeGatewayUpstream.create_thread_run

    async def submit_with_lost_ack(upstream, thread_id, payload):
        result = await original_submit(upstream, thread_id, payload)
        fault = Path(os.environ["BACKGROUND_FAULT_MODE_PATH"])
        if (
            payload.get("metadata", {}).get("background_event_id")
            and fault.exists()
            and fault.read_text() == "lost-ack"
        ):
            fault.write_text("ack-lost")
            record("completion-ack-lost", run_id=result["run_id"])
            raise UpstreamServiceError(
                code="langgraph_upstream_timeout",
                status_code=504,
                message="Synthetic response loss",
                upstream="langgraph",
            )
        return result

    LangGraphRuntimeGatewayUpstream.create_thread_run = submit_with_lost_ack

if __name__ != "__main__" or sys.argv[1] not in {"platform", "provider"}:
    from contextlib import asynccontextmanager

    import httpx
    from langfuse.api.client import AsyncLangfuseAPI

    from runtime_service.auth.platform import auth  # noqa: F401
    from runtime_service.observability import query
    from runtime_service.webapp import app

    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with original_lifespan(application):
            async with httpx.AsyncClient(trust_env=False, timeout=2) as transport:
                query._client = AsyncLangfuseAPI(
                    base_url=os.environ["RELIABILITY_OBSERVATIONS_URL"],
                    username="synthetic",
                    password="synthetic",
                    httpx_client=transport,
                )
                try:
                    yield
                finally:
                    query._client = None

    app.router.lifespan_context = lifespan


def recorded(event, **fields):
    path = Path(os.environ["TOOL_ERROR_TEST_FACTS"])
    return [
        value
        for line in (path.read_text().splitlines() if path.exists() else [])
        if (value := json.loads(line)).get("event") == event
        and all(value.get(k) == v for k, v in fields.items())
    ]


async def graph(config):
    from langchain_core.messages import HumanMessage

    from runtime_service.services.dearflow_agent import agent
    from runtime_service.services.dearflow_agent.tools import search

    async def provider(operation, payload):
        record("tool", query=payload["query"])
        return {"results": []}

    search.tavily = provider
    try:
        from runtime_service.middlewares.run_prepare import RunPrepareMiddleware
    except ImportError:
        return await agent.get_agent(config)

    from runtime_service.middlewares import retry, run_prepare
    from runtime_service.observability import langfuse, startup
    from runtime_service.observability.diagnostics import safe_fields, trace_id_for

    def diagnostic(event, fields):
        record(
            "observation",
            observation={
                "id": uuid4().hex,
                "trace_id": trace_id_for(fields),
                "name": event,
                "metadata": {
                    "schema_version": 1,
                    "event": event,
                    **safe_fields(fields),
                },
            },
        )

    for module in (retry, run_prepare, langfuse, startup):
        module.log_diagnostic = diagnostic

    original = agent.WorkspaceMiddleware
    while hasattr(original, "fixture_base"):
        original = original.fixture_base

    class ProbeWorkspace(original):
        fixture_base = original

        def _prepare(self):
            super()._prepare()
            record("prepare", run_id=self.metadata.get("run_id"))
            target = self.workspace.root / "work/retained.txt"
            try:
                with target.open("x") as stream:
                    stream.write("user version")
            except FileExistsError:
                pass
            if getattr(self, "prompt", None) == "infra-pg" and not recorded(
                "pg-disconnect"
            ):
                import psycopg

                record("pg-disconnect")
                with psycopg.connect(os.environ["DATABASE_URI"]) as connection:
                    connection.execute("select pg_terminate_backend(pg_backend_pid())")

        async def abefore_agent(self, state, runtime, config):
            prompt = next(
                (
                    m.content
                    for m in reversed(state["messages"])
                    if isinstance(m, HumanMessage)
                ),
                "",
            )
            self.prompt = prompt
            updates = await super().abefore_agent(state, runtime, config)
            if prompt == "prepare-before" and not recorded(
                "crash-window", prompt=prompt
            ):
                record(
                    "crash-window", prompt=prompt, run_id=self.metadata.get("run_id")
                )
                await asyncio.Event().wait()
            return updates

    assert issubclass(ProbeWorkspace, RunPrepareMiddleware)
    agent.WorkspaceMiddleware = ProbeWorkspace
    from runtime_service.runtime.background_completion import (
        background_completion_execution,
    )

    return await background_completion_execution(
        agent.get_agent, agent_key="dearflow_agent"
    )(config)


async def production_dear_graph(config):
    from runtime_service.graphs.dearflow_agent import get_agent

    return await get_agent(config)


async def production_showcase_graph(config):
    from runtime_service.graphs.showcase_demo import get_agent

    return await get_agent(config)


def provider_app():
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse, StreamingResponse

    app = FastAPI()

    @app.get("/v1/ready")
    async def ready():
        return {"ready": True}

    @app.get("/api/public/v2/observations")
    async def observations(request: Request):
        selected = [item["observation"] for item in recorded("observation")]
        trace_id = request.query_params.get("traceId") or request.query_params.get(
            "trace_id"
        )
        if trace_id:
            selected = [item for item in selected if item["trace_id"] == trace_id]
        return {
            "data": [
                {
                    "id": item["id"],
                    "traceId": item["trace_id"],
                    "name": item["name"],
                    "metadata": item["metadata"],
                    "type": "EVENT",
                    "startTime": "2026-10-07T00:00:00Z",
                    "endTime": "2026-10-07T00:00:00Z",
                    "projectId": "synthetic-observations",
                    "parentObservationId": None,
                }
                for item in selected[-100:]
            ],
            "meta": {},
        }

    @app.post("/v1/chat/completions")
    async def completion(request: Request):
        body = await request.json()
        messages = body["messages"]
        prompt = next(m["content"] for m in reversed(messages) if m["role"] == "user")
        after_tool = messages[-1]["role"] == "tool"
        key = prompt + ("-after-tool" if after_tool else "")
        count = len(recorded("http-model", key=key)) + 1
        record("http-model", key=key, count=count)
        if prompt == "background-source-error" and after_tool:
            return JSONResponse(
                {"error": {"message": "PROVIDER_CANARY", "type": "permission_error"}},
                status_code=403,
            )
        if (
            prompt in {"background-source-timeout", "background-source-cancel"}
            and after_tool
        ):
            await asyncio.sleep(120)
        if prompt in {"timeout", "run-deadline", "background-gate-block"}:
            await asyncio.sleep(60)
        if prompt == "prepare-after" and count == 1:
            record("crash-window", prompt=prompt)
            await asyncio.Event().wait()
        if prompt == "database" and count == 1:
            record("database-window", prompt=prompt)
            await asyncio.sleep(3)
        if prompt == "cancel":
            await asyncio.sleep(0.6)
        if (
            prompt in {"exhausted", "cancel"}
            or (
                (prompt in {"retry", "child-exhausted", "child-retry"} or after_tool)
                and count == 1
            )
            or prompt == "child-exhausted"
        ):
            return JSONResponse(
                {
                    "error": {
                        "message": "PROVIDER_CANARY secret=synthetic",
                        "type": "rate_limit_error",
                        "code": "rate_limit_exceeded",
                    }
                },
                status_code=429,
            )
        if prompt == "denied":
            return JSONResponse(
                {"error": {"message": "PROVIDER_CANARY", "type": "permission_error"}},
                status_code=403,
            )
        if prompt.startswith("Workspace background task "):
            record("completion-model", prompt=prompt)
        child = prompt in {"child", "parallel"}
        tools = []
        if (
            prompt.startswith("background-")
            and prompt != "background-gate-block"
            and not after_tool
        ):
            commands = {
                "background-short": ("sleep 2; printf BACKGROUND_DONE", 30),
                "background-long": ("printf started; sleep 120; printf finished", 180),
                "background-timeout": ("sleep 120", 2),
                "background-exit124": ("exit 124", 30),
                "background-drain-short": ("sleep 15; printf DRAIN_DONE", 90),
                "background-after-stop": ("sleep 15; printf AFTER_STOP", 90),
            }
            command, timeout = commands.get(prompt, commands["background-long"])
            tools = [
                {
                    "id": "background-start-" + prompt,
                    "type": "function",
                    "function": {
                        "name": "background_execute",
                        "arguments": json.dumps(
                            {"command": command, "timeout": timeout}
                        ),
                    },
                }
            ]
        if not after_tool and (child or prompt == "write-retry"):
            names = (
                ["child-exhausted"]
                if prompt == "child"
                else ["child-partial", "child-retry"]
            )
            tools = (
                [
                    {
                        "id": "task-" + name,
                        "type": "function",
                        "function": {
                            "name": "task",
                            "arguments": json.dumps(
                                {
                                    "subagent_type": "general-purpose",
                                    "description": name,
                                }
                            ),
                        },
                    }
                    for name in names
                ]
                if child
                else [
                    {
                        "id": "write-once",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": json.dumps(
                                {
                                    "file_path": "/workspace/work/once.txt",
                                    "content": "once",
                                }
                            ),
                        },
                    }
                ]
            )
        if prompt in {"partial", "child-partial"}:

            async def broken():
                delta = {"content": "VISIBLE_ONCE"}
                yield (
                    "data: "
                    + json.dumps(
                        {
                            "id": "partial",
                            "object": "chat.completion.chunk",
                            "model": "fixture",
                            "choices": [
                                {"index": 0, "delta": delta, "finish_reason": None}
                            ],
                        }
                    )
                    + "\n\n"
                )
                await asyncio.sleep(0.05)
                raise ConnectionResetError("PROVIDER_CANARY")

            return StreamingResponse(broken(), media_type="text/event-stream")
        response = {
            "id": "fixture-" + uuid4().hex,
            "object": "chat.completion",
            "model": "fixture",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "" if tools else "recovered",
                        **({"tool_calls": tools} if tools else {}),
                    },
                    "finish_reason": "tool_calls" if tools else "stop",
                }
            ],
            "usage": {"prompt_tokens": 2, "completion_tokens": 2, "total_tokens": 4},
        }
        if not body.get("stream"):
            return response

        async def chunks():
            delta = response["choices"][0]["message"]
            if tools:
                delta = {
                    "role": "assistant",
                    "tool_calls": [
                        {"index": i, **tool} for i, tool in enumerate(tools)
                    ],
                }
            yield (
                "data: "
                + json.dumps(
                    {
                        "id": response["id"],
                        "object": "chat.completion.chunk",
                        "model": "fixture",
                        "choices": [
                            {"index": 0, "delta": delta, "finish_reason": None}
                        ],
                    }
                )
                + "\n\n"
            )
            yield (
                "data: "
                + json.dumps(
                    {
                        "id": response["id"],
                        "object": "chat.completion.chunk",
                        "model": "fixture",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {},
                                "finish_reason": response["choices"][0][
                                    "finish_reason"
                                ],
                            }
                        ],
                    }
                )
                + "\n\n"
            )
            yield "data: [DONE]\n\n"

        return StreamingResponse(chunks(), media_type="text/event-stream")

    return app


if __name__ == "__main__":
    import uvicorn

    role, path = sys.argv[1:]
    spec = json.loads(Path(path).read_text())
    if role in {"provider", "platform"}:
        app = provider_app() if role == "provider" else platform_app(spec)
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=spec[role + "_port"],
            log_level="error",
            access_log=False,
        )
    elif role == "runtime":
        from langhost.server import create_app

        uvicorn.run(
            create_app(spec["config"], base_dir=Path(path).parent),
            host=os.getenv("TOOL_ERROR_TEST_BIND", "127.0.0.1"),
            port=int(os.getenv("TOOL_ERROR_TEST_RUNTIME_PORT", spec["runtime_port"])),
            log_level="error",
            access_log=False,
        )
    elif role == "worker":
        from importlib import import_module

        from langgraph_runtime_pg.production_worker import ProductionWorker, run_worker

        original_run_forever = ProductionWorker.run_forever

        async def ready_worker(worker):
            Path(spec["worker_ready"]).write_text(str(os.getpid()))
            await original_run_forever(worker)

        ProductionWorker.run_forever = ready_worker
        import_module("runtime_service.services.dearflow_agent.agent")

        asyncio.run(run_worker(Path(path).parent / "langgraph.json"))
