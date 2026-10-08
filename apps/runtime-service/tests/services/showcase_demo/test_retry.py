"""Prove the Showcase role boundary through the production DeepAgents factory."""

import asyncio

import pytest
from langchain_core.exceptions import ContextOverflowError, ModelRateLimitError
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from support import BindableFakeMessagesChatModel

from runtime_service.runtime import runtime_context_hash
from runtime_service.runtime.errors import RuntimeExecutionError
from runtime_service.services.demo.showcase_demo import agent

from .test_agent import config


@pytest.mark.parametrize(
    "role,context_failure",
    [("research", False), ("general-purpose", False), ("general-purpose", True)],
)
def test_readonly_owner_and_write_child_preserve_completed_write(
    monkeypatch, tmp_path, role, context_failure
):
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path))
    calls, sdk_options = [], []

    class Model(BindableFakeMessagesChatModel):
        async def _agenerate(self, messages, **kwargs):
            human = next(m.content for m in messages if isinstance(m, HumanMessage))
            last = messages[-1]
            if human == "parent":
                message = (
                    AIMessage(content="done")
                    if isinstance(last, ToolMessage)
                    else AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "task",
                                "id": "delegate",
                                "args": {"subagent_type": role, "description": "child"},
                            }
                        ],
                    )
                )
            else:
                calls.append(
                    "after-write" if isinstance(last, ToolMessage) else "before-write"
                )
                if role == "research":
                    raise ModelRateLimitError("CANARY")
                if not isinstance(last, ToolMessage):
                    message = AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "write_file",
                                "id": "write-once",
                                "args": {
                                    "file_path": "/workspace/result.txt",
                                    "content": "once",
                                },
                            }
                        ],
                    )
                elif context_failure:
                    raise ContextOverflowError("CANARY")
                elif calls.count("after-write") == 1:
                    raise ModelRateLimitError("CANARY")
                else:
                    message = AIMessage(content="written")
            return ChatResult(generations=[ChatGeneration(message=message)])

    def build(*args, **kwargs):
        sdk_options.append(kwargs.get("max_retries"))
        return Model(responses=[])

    monkeypatch.setattr(agent, "build_model", build)

    async def run():
        cfg = config(context={"access_policy": "workspace_write"})
        cfg["metadata"] = {"run_id": "test"}
        cfg["configurable"]["langgraph_auth_user"]["runtime_context_hash"] = (
            runtime_context_hash(cfg["context"])
        )
        graph = await agent.get_agent(cfg)
        graph.checkpointer = InMemorySaver()
        if context_failure:
            with pytest.raises(RuntimeExecutionError, match="context_too_long"):
                await graph.ainvoke(
                    {"messages": [("user", "parent")]}, cfg, context=cfg["context"]
                )
        else:
            result = await graph.ainvoke(
                {"messages": [("user", "parent")]}, cfg, context=cfg["context"]
            )
            assert result["messages"][-1].content == "done"
            if role == "research":
                assert (
                    next(
                        m for m in result["messages"] if isinstance(m, ToolMessage)
                    ).status
                    == "error"
                )
        assert sdk_options and all(value == 0 for value in sdk_options)
        if role == "research":
            assert calls == ["before-write", "before-write"]
            assert not list(tmp_path.rglob("result.txt"))
        else:
            assert calls.count("before-write") == 1
            assert calls.count("after-write") == (1 if context_failure else 2)
            paths = list(tmp_path.rglob("result.txt"))
            assert len(paths) == 1 and paths[0].read_text() == "once"

    asyncio.run(run())
