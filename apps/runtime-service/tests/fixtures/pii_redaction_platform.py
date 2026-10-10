"""Disposable provider and production-root wiring for privacy acceptance."""

import asyncio
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

from fixtures.tool_error_platform import platform_app, record

if __name__ != "__main__" or sys.argv[1] not in {"platform", "provider"}:
    from runtime_service.auth.platform import auth  # noqa: F401
    from runtime_service.webapp import app  # noqa: F401

EMAIL = "alice@example.test"
PHONE = "13800138000"


async def graph(config):
    from runtime_service.services.dearflow_agent import agent
    from runtime_service.services.dearflow_agent.tools import search

    async def synthetic_search(operation, payload):
        record("tool", query=payload["query"])
        return {
            "results": [
                {
                    "url": "https://example.test/source",
                    "title": "synthetic",
                    "content": EMAIL + " " + PHONE,
                }
            ]
        }

    search.tavily = synthetic_search
    return await agent.get_agent(config)


async def showcase_graph(config):
    from runtime_service.services.demo.showcase_demo.agent import get_agent

    return await get_agent(config)


def provider_app():
    from fastapi import FastAPI, Request
    from fastapi.responses import StreamingResponse

    application = FastAPI()

    @application.get("/v1/ready")
    async def ready():
        return {"ready": True}

    @application.post("/v1/chat/completions")
    async def completion(request: Request):
        body = await request.json()
        record("http-model", body=body)
        messages = body["messages"]
        prompt = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        names = {t["function"]["name"] for t in body.get("tools", [])}
        args = None
        if messages[-1]["role"] != "tool":
            if (
                isinstance(prompt, str)
                and prompt.startswith("approval")
                and "write_file" in names
            ):
                name, args = (
                    "write_file",
                    {"file_path": "/workspace/work/approved.txt", "content": EMAIL},
                )
            elif (
                isinstance(prompt, str)
                and prompt.startswith("child")
                and "task" in names
            ):
                name, args = (
                    "task",
                    {
                        "subagent_type": "general-purpose",
                        "description": "child research " + EMAIL,
                    },
                )
            elif "search_web" in names:
                name, args = "search_web", {"query": "synthetic " + EMAIL}
        suggestion = any(
            "你负责为对话生成后续问题建议" in str(m.get("content")) for m in messages
        )
        delta = {
            "role": "assistant",
            "content": '["继续研究"]' if suggestion else "safe answer",
        }
        if args is not None:
            delta = {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "fixture-" + name + "-" + uuid4().hex,
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(args)},
                    }
                ],
            }
        if not body.get("stream"):
            from fastapi.responses import JSONResponse

            message = {**delta}
            if "tool_calls" in message:
                message["tool_calls"] = [
                    {k: v for k, v in call.items() if k != "index"}
                    for call in message["tool_calls"]
                ]
            return JSONResponse(
                {
                    "id": "fixture",
                    "object": "chat.completion",
                    "model": "fixture",
                    "choices": [
                        {
                            "index": 0,
                            "message": message,
                            "finish_reason": "tool_calls" if args else "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 10,
                        "completion_tokens": 5,
                        "total_tokens": 15,
                    },
                }
            )

        async def stream():
            frame = {
                "id": "fixture",
                "object": "chat.completion.chunk",
                "model": "fixture",
                "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
            }
            yield "data: " + json.dumps(frame) + "\n\n"
            frame["choices"] = [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "tool_calls" if args else "stop",
                }
            ]
            yield "data: " + json.dumps(frame) + "\n\ndata: [DONE]\n\n"

        return StreamingResponse(stream(), media_type="text/event-stream")

    return application


if __name__ == "__main__":
    import uvicorn

    role, spec_path = sys.argv[1:]
    spec = json.loads(Path(spec_path).read_text())
    if role == "provider":
        application, bind_port = provider_app(), spec["provider_port"]
    elif role == "platform":
        application, bind_port = platform_app(spec), spec["platform_port"]
    elif role == "runtime":
        from langhost.server import create_app

        os.environ.update(
            DEEPSEEK_PROXY_URL=spec["provider_url"],
            DEEPSEEK_PROXY_API_KEY="synthetic",
            DEEPSEEK_PROXY_DEFAULT_MODEL="fixture",
        )
        application = create_app(
            spec["config"], base_dir=Path(spec_path).parent, custom_app=app
        )
        bind_port = spec["runtime_port"]
    else:
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
        ):
            import_module(module)
        asyncio.run(run_worker(Path(spec_path).parent / "langgraph.json"))
        raise SystemExit(0)
    uvicorn.run(
        application,
        host="127.0.0.1",
        port=bind_port,
        access_log=False,
        log_level="error",
    )
