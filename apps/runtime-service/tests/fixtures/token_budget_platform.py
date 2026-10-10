"""Token-budget scenarios using the existing isolated service roles."""

import json
import os
import runpy
import sys
from pathlib import Path

if sys.argv[1:2] not in (["platform"], ["provider"]):
    from runtime_service.auth.platform import auth  # noqa: F401


def record(event, **fields):
    from fixtures.tool_error_platform import record as emit

    emit(event, **fields)


async def _graph(config, service):
    from importlib import import_module
    from unittest.mock import patch

    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from support import BindableFakeMessagesChatModel

    module = import_module("runtime_service.services." + service + ".agent")

    class Model(BindableFakeMessagesChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            prompt = next(
                (m.text for m in reversed(messages) if isinstance(m, HumanMessage)),
                "normal",
            )
            count = (
                10
                if "cap" in prompt
                else 8
                if prompt == "warning"
                and not any(isinstance(m, ToolMessage) for m in messages)
                else 4
            )
            usage = (
                None
                if "unknown" in prompt
                else {
                    "input_tokens": count,
                    "output_tokens": 0,
                    "total_tokens": count,
                }
            )
            record("model", prompt=prompt)
            response = AIMessage(content="verified answer", usage_metadata=usage)
            if "resume-worker" in prompt and not any(
                isinstance(m, ToolMessage) for m in messages
            ):
                response = self.call("read_reference", {"topic": "pause"}, usage)
            elif (
                "child" in prompt
                and service in {"dearflow_agent", "demo.showcase_demo"}
                and not any(isinstance(m, ToolMessage) for m in messages)
            ):
                role = "general-purpose" if service == "dearflow_agent" else "research"
                response = self.call(
                    "task",
                    {"subagent_type": role, "description": "cap-child-response"},
                    usage,
                )
            elif prompt in {"cap-tool", "unknown-tool", "warning"} and not any(
                isinstance(m, ToolMessage) for m in messages
            ):
                if service in {"dearflow_agent", "demo.showcase_demo"}:
                    name, args = "read_file", {"file_path": "/workspace/missing.txt"}
                else:
                    name, args = "read_reference", {"topic": "token-probe"}
                response = self.call(name, args, usage)
            self.responses = [response]
            self.i = 0
            return super()._generate(
                messages, stop=stop, run_manager=run_manager, **kwargs
            )

        @staticmethod
        def call(name, args, usage):
            return AIMessage(
                content="",
                tool_calls=[{"name": name, "args": args, "id": "fixture-" + name}],
                usage_metadata=usage,
            )

    model = Model(responses=[AIMessage(content="schema")])
    patches = (
        []
        if os.getenv("TOKEN_PROVIDER_HTTP") == "1"
        else [patch.object(module, "build_model", lambda *args, **kwargs: model)]
    )
    if service == "reference_agent":
        from langchain_core.tools import tool

        @tool
        def read_reference(topic: str) -> str:
            """Read the isolated reference."""
            record("tool", topic=topic)
            if topic == "pause":
                import time

                record("pause", run=config["metadata"]["run_id"])
                while not Path(os.environ["TOKEN_RELEASE_FILE"]).exists():
                    time.sleep(0.05)
            return "verified reference"

        patches.append(patch.object(module, "read_reference", read_reference))
    from contextlib import ExitStack

    with ExitStack() as stack:
        for replacement in patches:
            stack.enter_context(replacement)
        return await module.get_agent(config)


def provider_app():
    import time
    from uuid import uuid4

    from fastapi import FastAPI, Request
    from fastapi.responses import StreamingResponse

    application = FastAPI()

    @application.get("/v1/ready")
    async def ready():
        return {"ready": True}

    @application.post("/v1/chat/completions")
    async def complete(request: Request):
        body = await request.json()
        messages = body["messages"]
        prompt = next(
            (m.get("content", "") for m in reversed(messages) if m["role"] == "user"),
            "normal",
        )
        has_tool = any(m["role"] == "tool" for m in messages)
        count = (
            10
            if "cap" in str(prompt)
            else 8
            if prompt == "warning" and not has_tool
            else 4
        )
        tools = {item["function"]["name"] for item in body.get("tools", [])}
        message = {"role": "assistant", "content": "verified answer"}
        name, args = None, {}
        if not has_tool and "child" in prompt and "task" in tools:
            names = str(body.get("tools", []))
            name, args = (
                "task",
                {
                    "subagent_type": "general-purpose"
                    if "general-purpose" in names
                    else "research",
                    "description": "cap-child-response",
                },
            )
        elif not has_tool and prompt in {
            "cap-tool",
            "unknown-tool",
            "warning",
            "resume-worker",
        }:
            name = "read_reference" if "read_reference" in tools else "read_file"
            args = (
                {"topic": "pause" if prompt == "resume-worker" else "token-probe"}
                if name == "read_reference"
                else {"file_path": "/workspace/missing.txt"}
            )
        if name:
            message.update(
                content="",
                tool_calls=[
                    {
                        "id": "call_" + uuid4().hex,
                        "type": "function",
                        "function": {"name": name, "arguments": json.dumps(args)},
                    }
                ],
            )
        usage = (
            None
            if "unknown" in prompt
            else {"prompt_tokens": count, "completion_tokens": 0, "total_tokens": count}
        )
        record("model", prompt=prompt, tool=name)
        payload = {
            "id": "token_" + uuid4().hex,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "fixture",
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "finish_reason": "tool_calls" if name else "stop",
                }
            ],
        }
        if usage is not None:
            payload["usage"] = usage
        if not body.get("stream"):
            return payload

        async def chunks():
            delta = dict(message)
            if name:
                delta["tool_calls"] = [{"index": 0, **message["tool_calls"][0]}]
            frame = {k: payload[k] for k in ("id", "created", "model")}
            frame["object"] = "chat.completion.chunk"
            yield (
                "data: "
                + json.dumps(
                    {
                        **frame,
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
                        **frame,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {},
                                "finish_reason": payload["choices"][0]["finish_reason"],
                            }
                        ],
                    }
                )
                + "\n\n"
            )
            if usage is not None:
                yield (
                    "data: "
                    + json.dumps({**frame, "choices": [], "usage": usage})
                    + "\n\n"
                )
            yield "data: [DONE]\n\n"

        return StreamingResponse(chunks(), media_type="text/event-stream")

    return application


async def graph(config):
    return await _graph(config, "dearflow_agent")


async def showcase_graph(config):
    return await _graph(config, "demo.showcase_demo")


async def reference_graph(config):
    return await _graph(config, "reference_agent")


async def workflow_graph(config):
    return await _graph(config, "demo.workflow_demo")


def export_contract(evidence, destination):
    import copy
    import sys
    from unittest.mock import patch

    platform_src = Path(__file__).resolve().parents[4] / "apps/platform-api/src"
    if str(platform_src) not in sys.path:
        sys.path.insert(0, str(platform_src))
    from platform_api.adapters.langgraph.sdk_client import project_execution_error
    from platform_api.modules.runtime_gateway.application.usage import (
        RunUsage,
        TokenBudgetSummary,
    )

    from runtime_service.observability.usage import RuntimeUsageCallback
    from runtime_service.runtime.token_budget import RunTokenBudget, TokenBudgetPolicy

    samples = {
        name: RunUsage.model_validate(evidence["samples"][origin]).model_dump(
            mode="json"
        )
        for name, origin in (
            ("normal", "reference_agent:normal"),
            ("exhausted", "reference_agent:cap-tool"),
            ("unverifiable", "reference_agent:unknown-tool"),
            ("natural_final_at_cap", "reference_agent:cap-final"),
            ("warning_then_natural_final", "warning"),
        )
    }
    old = copy.deepcopy(samples["normal"])
    old.pop("token_budget")
    samples["old_payload_no_budget"] = old
    samples["disabled"] = {**old, "token_budget": None}
    notices = []
    for code, tokens, quality in (
        ("token_budget_approaching", 8, "reported"),
        ("token_budget_exhausted", 14, "reported"),
        ("token_budget_unverifiable", None, "missing"),
    ):
        usage = RuntimeUsageCallback(
            {
                "tenant_id": "test",
                "project_id": "test",
                "thread_id": old["thread_id"],
                "run_id": old["run_id"],
                "graph_id": "reference_agent",
            }
        )
        usage.token_budget = RunTokenBudget(TokenBudgetPolicy(10, 8))
        usage.token_budget.record_call("fixture", total_tokens=tokens, quality=quality)
        usage.bind_budget_writer(notices.append)
        with patch(
            "runtime_service.middlewares.execution_budget.get_config",
            return_value={"metadata": {"run_id": old["run_id"]}},
        ):
            usage._emit_budget_notice(code)
    assert len(notices) == 3
    result = {
        "version": 1,
        "schemas": {
            "TokenBudgetSummary": TokenBudgetSummary.model_json_schema(),
            "RunUsage": RunUsage.model_json_schema(),
        },
        "samples": samples,
        "notices": notices,
        "errors": [
            project_execution_error({"type": kind, "message": "SECRET_CANARY"})
            for kind in ("TokenBudgetExceededError", "TokenBudgetUnverifiableError")
        ],
        "sample_origins": {
            "http": list(samples)[:5],
            "controlled_contract": [
                "old_payload_no_budget",
                "disabled",
                "notices",
                "errors",
            ],
        },
    }
    assert "SECRET_CANARY" not in json.dumps(result)
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    role, spec_path = sys.argv[1:]
    if role == "provider":
        import uvicorn

        spec = json.loads(Path(spec_path).read_text())
        uvicorn.run(
            provider_app(),
            host="127.0.0.1",
            port=spec["provider_port"],
            log_level="error",
            access_log=False,
        )
    elif role == "platform":
        from contextlib import asynccontextmanager
        from uuid import UUID

        import uvicorn
        from fixtures.tool_error_platform import platform_app
        from platform_api.core.db import session_scope
        from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
        from sqlalchemy import select

        spec = json.loads(Path(spec_path).read_text())
        application = platform_app(spec)
        original = application.router.lifespan_context

        @asynccontextmanager
        async def lifespan(application):
            async with original(application):
                with session_scope(application.state.db_session_factory) as session:
                    base = session.scalar(
                        select(AgentRecord).where(
                            AgentRecord.project_id == UUID(spec["project"])
                        )
                    )
                    for name in ("reference_agent", "workflow_demo"):
                        if session.scalar(
                            select(AgentRecord).where(
                                AgentRecord.project_id == base.project_id,
                                AgentRecord.graph_id == name,
                            )
                        ):
                            continue
                        session.add(
                            AgentRecord(
                                project_id=base.project_id,
                                name=name,
                                graph_id=name,
                                created_by=base.created_by,
                                updated_by=base.updated_by,
                            )
                        )
                yield

        application.router.lifespan_context = lifespan
        uvicorn.run(
            application,
            host="127.0.0.1",
            port=spec["platform_port"],
            log_level="error",
            access_log=False,
        )
    else:
        if role == "worker":
            from importlib import import_module

            for service in ("reference_agent", "demo.workflow_demo"):
                import_module("runtime_service.services." + service + ".agent")
        runpy.run_module("fixtures.tool_error_platform", run_name="__main__")
