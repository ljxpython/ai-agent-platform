"""Controlled HTTP provider around the production composition roots."""

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID, uuid4, uuid5

from fixtures.run_reliability import recorded
from fixtures.tool_error_platform import platform_app, record

if __name__ != "__main__" or sys.argv[1] not in {"platform", "provider"}:
    from fixtures.run_reliability import app, auth  # noqa: F401


def install_diagnostics():
    from runtime_service.observability import langfuse, startup
    from runtime_service.observability.diagnostics import safe_fields, trace_id_for

    modules = [langfuse, startup]
    try:
        from runtime_service.middlewares import loop_detection

        modules.append(loop_detection)
    except ImportError:
        pass

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

    for module in modules:
        module.log_diagnostic = diagnostic


async def graph(config):
    from fixtures.run_reliability import graph as dear_graph

    install_diagnostics()
    return await dear_graph(config)


async def showcase_graph(config):
    from runtime_service.services.demo.showcase_demo import agent

    install_diagnostics()
    return await agent.get_agent(config)


async def reference_graph(config):
    from runtime_service.services.reference_agent import agent

    install_diagnostics()
    return await agent.get_agent(config)


async def workflow_graph(config):
    from runtime_service.services.demo.workflow_demo import agent

    install_diagnostics()
    return await agent.get_agent(config)


def control_platform(spec):
    application = platform_app(spec)
    original = application.router.lifespan_context

    @asynccontextmanager
    async def lifespan(instance):
        async with original(instance):
            from platform_api.core.db import session_scope
            from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
            from platform_api.modules.identity.models import UserRecord
            from sqlalchemy import select

            with session_scope(application.state.db_session_factory) as session:
                owner = session.scalar(
                    select(UserRecord).where(UserRecord.username == "tool-error-test")
                )
                for name in ("reference_agent", "workflow_demo"):
                    session.add(
                        AgentRecord(
                            project_id=UUID(spec["project"]),
                            name=name,
                            graph_id=name,
                            created_by=owner.id,
                            updated_by=owner.id,
                        )
                    )
                from dotenv import dotenv_values
                from platform_api.modules.runtime_catalog.application.credentials import (
                    encrypt_api_key,
                )
                from platform_api.modules.runtime_catalog.infra.sqlalchemy.models import (
                    RuntimeCatalogModelRecord,
                )

                if path := os.getenv("LOOP_MODEL_ENV_FILE"):
                    values = dotenv_values(path)
                    session.add(
                        RuntimeCatalogModelRecord(
                            id=uuid5(UUID(spec["model"]), "real"),
                            display_name="f02 real model",
                            provider="deepseek-proxy",
                            protocol="deepseek",
                            base_url=values["DEEPSEEK_PROXY_URL"],
                            model_name="DeepSeek-V4-Flash",
                            api_key_ciphertext=encrypt_api_key(
                                values["DEEPSEEK_PROXY_API_KEY"],
                                master_key=application.state.settings.model_config_master_key,
                            ),
                            context_window_tokens=30000,
                            enabled=True,
                        )
                    )
            yield

    application.router.lifespan_context = lifespan
    return application


def provider_app():
    from fastapi import Request
    from fastapi.responses import StreamingResponse
    from fixtures.run_reliability import provider_app as observations_app

    application = observations_app()
    application.router.routes = [
        route
        for route in application.router.routes
        if getattr(route, "path", "") != "/v1/chat/completions"
    ]

    @application.post("/v1/chat/completions")
    async def completion(request: Request):
        body = await request.json()
        messages = body["messages"]
        last_user = next(
            i for i in reversed(range(len(messages))) if messages[i]["role"] == "user"
        )
        prompt = messages[last_user]["content"]
        prompt = str(prompt)
        count = len(recorded("f02-model", prompt=prompt)) + 1
        rounds = sum(m["role"] == "tool" for m in messages[last_user + 1 :])
        record(
            "f02-model",
            prompt=prompt,
            count=count,
            rounds=rounds,
            wrapup=any(
                "Execution budget is running low" in str(m.get("content"))
                for m in messages
                if m["role"] == "system"
            ),
        )
        if prompt == "f02-crash" and count == 4:
            record("f02-crash-window", prompt=prompt)
            await asyncio.Event().wait()
        if prompt in {"f02-cancel", "f02-inbox"} and rounds == 3:
            record("f02-waiting", prompt=prompt)
            release = Path(os.environ["TOOL_ERROR_TEST_FACTS"] + "." + prompt)
            while not release.exists() and not await request.is_disconnected():
                await asyncio.sleep(0.05)
        names = {tool["function"]["name"] for tool in body.get("tools", [])}
        calls = []
        loop = "loop" in prompt or prompt in {
            "f02-crash",
            "f02-disabled",
            "f02-warn-finish",
            "f02-pages",
            "f02-alternating",
            "f02-changing",
            "f02-inbox",
            "f02-cancel",
        }
        finish = (
            (
                prompt
                in {"f02-pages", "f02-alternating", "f02-changing", "f02-disabled"}
                and rounds >= 6
            )
            or prompt == "f02-warn-finish"
            and rounds >= 3
        )
        if loop and not finish:
            name = (
                "read_reference"
                if "read_reference" in names
                else "ls"
                if "ls" in names
                else "read_file"
            )
            args = (
                {"topic": "same"}
                if name == "read_reference"
                else {"path": "/"}
                if name == "ls"
                else {"file_path": "/workspace/work/retained.txt"}
            )
            if prompt == "f02-pages":
                name, args = (
                    "read_file",
                    {
                        "file_path": "/workspace/work/retained.txt",
                        "offset": rounds,
                        "limit": 1,
                    },
                )
            if prompt == "f02-alternating":
                args = {"path": "/" if rounds % 2 else "/workspace/work/"}
            if prompt == "f02-changing":
                name, args = "read_file", {"file_path": "/workspace/work/retained.txt"}
                for path in Path(os.environ["RUNTIME_WORKSPACE_ROOT"]).rglob(
                    "retained.txt"
                ):
                    path.write_text(f"version {rounds}")
            calls = [
                {
                    "id": "call-" + uuid4().hex,
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(args)},
                }
            ]
        if prompt == "f02-parent" and not rounds:
            role = "research" if "fetch_documentation" in names else "general-purpose"
            calls = [
                {
                    "id": "task-" + uuid4().hex,
                    "type": "function",
                    "function": {
                        "name": "task",
                        "arguments": json.dumps(
                            {"subagent_type": role, "description": "f02-child-loop"}
                        ),
                    },
                }
            ]
        if prompt == "f02-parallel" and not rounds:
            calls = [
                {
                    "id": "task-" + uuid4().hex,
                    "type": "function",
                    "function": {
                        "name": "task",
                        "arguments": json.dumps(
                            {
                                "subagent_type": "general-purpose",
                                "description": f"f02-child-{index}-warn-finish",
                            }
                        ),
                    },
                }
                for index in range(2)
            ]
        if prompt.startswith("f02-child-") and prompt.endswith("warn-finish"):
            calls = (
                []
                if rounds >= 3
                else [
                    {
                        "id": "call-" + uuid4().hex,
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": json.dumps(
                                {"file_path": "/workspace/work/retained.txt"}
                            ),
                        },
                    }
                ]
            )
        if prompt == "f02-approval" and not rounds:
            calls = [
                {
                    "id": "write-" + uuid4().hex,
                    "type": "function",
                    "function": {
                        "name": "write_file",
                        "arguments": json.dumps(
                            {
                                "file_path": "/workspace/work/approved.txt",
                                "content": "once",
                            }
                        ),
                    },
                }
            ]
        message = {
            "role": "assistant",
            "content": "" if calls else "f02-done",
            **({"tool_calls": calls} if calls else {}),
        }
        reason = "tool_calls" if calls else "stop"
        response = {
            "id": uuid4().hex,
            "object": "chat.completion",
            "model": "fixture",
            "choices": [{"index": 0, "message": message, "finish_reason": reason}],
            "usage": {"prompt_tokens": 2, "completion_tokens": 2, "total_tokens": 4},
        }
        if not body.get("stream"):
            return response

        async def chunks():
            delta = {
                **message,
                **(
                    {
                        "tool_calls": [
                            {"index": i, **call} for i, call in enumerate(calls)
                        ]
                    }
                    if calls
                    else {}
                ),
            }
            for part, finish_reason in ((delta, None), ({}, reason)):
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
                                    "delta": part,
                                    "finish_reason": finish_reason,
                                }
                            ],
                        }
                    )
                    + "\n\n"
                )
            yield "data: [DONE]\n\n"

        return StreamingResponse(chunks(), media_type="text/event-stream")

    return application


if __name__ == "__main__":
    import uvicorn

    role, path = sys.argv[1:]
    spec = json.loads(Path(path).read_text())
    os.environ["RUNTIME_SELF_URL"] = spec["runtime_url"]
    os.environ["PLATFORM_RUNTIME_MESSAGE_AUTH_URL"] = (
        f"http://127.0.0.1:{spec['platform_port']}/api/runtime/internal/message-authorization"
    )
    if role == "platform" or role == "provider":
        application = control_platform(spec) if role == "platform" else provider_app()
        uvicorn.run(
            application,
            host="127.0.0.1",
            port=spec[role + "_port"],
            log_level="error",
            access_log=False,
        )
    elif role == "runtime":
        from langhost.server import create_app

        uvicorn.run(
            create_app(spec["config"], base_dir=Path(path).parent),
            host="127.0.0.1",
            port=spec["runtime_port"],
            log_level="error",
            access_log=False,
        )
    elif role == "worker":
        from importlib import import_module

        from langgraph_runtime_pg.production_worker import ProductionWorker, run_worker

        original = ProductionWorker.run_forever

        async def ready(worker):
            Path(spec["worker_ready"]).write_text(str(os.getpid()))
            await original(worker)

        ProductionWorker.run_forever = ready
        for module in (
            "runtime_service.services.dearflow_agent.agent",
            "runtime_service.services.demo.showcase_demo.agent",
            "runtime_service.services.reference_agent.agent",
        ):
            import_module(module)
        asyncio.run(run_worker(Path(path).parent / "langgraph.json"))
