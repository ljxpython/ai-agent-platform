"""Deterministic read-only failures followed by a real authorized model request."""

import asyncio
import os
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import Field
from support import BindableFakeMessagesChatModel

from runtime_service.runtime import runtime_context_hash
from runtime_service.services.dearflow_agent import agent

from .test_agent import call, config


class RecoveryModel(BindableFakeMessagesChatModel):
    real: Any
    requests: list = Field(default_factory=list)
    initial_calls: int
    count: int = 0

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        self.count += 1
        if self.count <= self.initial_calls:
            return self._generate(
                messages, stop=stop, run_manager=run_manager, **kwargs
            )
        self.requests.append(messages)
        reply = await self.real.ainvoke(messages)
        return ChatResult(generations=[ChatGeneration(message=reply)])


@pytest.mark.parametrize("child", [False, True])
def test_real_model_consumes_safe_main_or_child_error(monkeypatch, tmp_path, child):
    if os.getenv("TOOL_ERROR_LIVE_TEST") != "1":
        pytest.skip("TOOL_ERROR_LIVE_TEST=1 enables authorized read-only model smoke")
    from dotenv import dotenv_values

    env_file = os.environ.get("TOOL_ERROR_MODEL_ENV_FILE")
    assert env_file and Path(env_file).is_file(), (
        "An explicit model env file is required"
    )
    for key, value in dotenv_values(env_file).items():
        if key in {"DEEPSEEK_PROXY_API_KEY", "DEEPSEEK_PROXY_URL"} and value:
            monkeypatch.setenv(key, value)
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("TAVILY_API_KEY", "synthetic")
    monkeypatch.delenv("DATABASE_URI", raising=False)
    models = []
    real_builder = agent.build_model

    def build(resolved, **kwargs):
        if models:
            return models[0]
        initial = [call("search_web", {"query": ""}, "live-error")]
        if child:
            initial.insert(
                0,
                call(
                    "task",
                    {
                        "subagent_type": "general-purpose",
                        "description": "请接收预设的搜索参数错误后，用一句中文说明已有工具失败，不再调用任何工具。",
                    },
                ),
            )
        model = RecoveryModel(
            responses=initial,
            real=real_builder(resolved, **kwargs, max_retries=0),
            initial_calls=len(initial),
        )
        models.append(model)
        return model

    monkeypatch.setattr(agent, "build_model", build)

    async def run():
        cfg = config()
        cfg["context"] = {
            "max_tokens": 2048,
            "execution_mode": "ultra" if child else "standard",
        }
        cfg["configurable"]["langgraph_auth_user"]["runtime_context_hash"] = (
            runtime_context_hash(cfg["context"])
        )
        graph = await agent.get_agent(cfg)
        graph.checkpointer = InMemorySaver()
        async with asyncio.timeout(120):
            result = await graph.ainvoke(
                {
                    "messages": [
                        (
                            "user",
                            "这是一项只读容错验收。收到工具错误后，请用一句中文说明搜索未成功，不再调用任何工具，不要申请写文件或提交任何任务。",
                        )
                    ]
                },
                cfg,
                context=cfg["context"],
            )
        requests = [messages for model in models for messages in model.requests]
        assert any(
            isinstance(m, ToolMessage)
            and m.status == "error"
            and m.tool_call_id == "live-error"
            for messages in requests
            for m in messages
        )
        assert result["messages"][-1].content and not result.get("__interrupt__")
        assert not result["messages"][-1].tool_calls
        print(
            {
                "child": child,
                "real_requests": len(requests),
                "error_consumed": True,
                "answered": True,
            }
        )

    asyncio.run(run())
