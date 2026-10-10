"""Both real composition roots hide unavailable starts and consume safe errors."""

import asyncio
import json
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import Field
from support import BindableFakeMessagesChatModel, with_run_budget

from runtime_service.background_tasks import service
from runtime_service.middlewares.message_queue import MessageQueueMiddleware
from runtime_service.runtime.errors import RuntimeWorkspaceError
from runtime_service.runtime.resolver import runtime_context_hash
from runtime_service.services.dearflow_agent import agent as dearflow
from runtime_service.services.demo.showcase_demo import agent as showcase
from runtime_service.tools import background

from .test_tools_and_assembly import invocation


class User(dict):
    identity = "owner"
    is_authenticated = True


class RecordingModel(BindableFakeMessagesChatModel):
    seen_messages: list = Field(default_factory=list)
    seen_tools: list = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        self.seen_tools.append({tool.name for tool in tools})
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen_messages.append(messages)
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


@pytest.fixture(params=[(showcase, "showcase_demo"), (dearflow, "dearflow_agent")])
def build(request, monkeypatch, tmp_path):
    factory, graph_id = request.param
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path / "showcase"))
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path / "dearflow"))
    monkeypatch.setenv("DATABASE_URI", "isolated-test-only")
    monkeypatch.setenv("RUNTIME_EXECUTION_HOST_ID", "test-host")
    monkeypatch.setenv("RUNTIME_BACKGROUND_TASKS_ENABLED", "1")
    monkeypatch.setattr(
        MessageQueueMiddleware, "abefore_model", AsyncMock(return_value=None)
    )
    runtime, _, _ = invocation(tmp_path)
    user = User(runtime.server_info.user)
    user["runtime_scope"]["assistant_id"] = graph_id
    user["runtime_policy"]["allowed_model_ids"] = [factory._DEFAULTS.model_id]
    context = {"access_policy": "workspace_write"}
    user["runtime_context_hash"] = runtime_context_hash(context)
    cfg = with_run_budget(
        {
            "context": context,
            "configurable": {
                "thread_id": runtime.execution_info.thread_id,
                "assistant_id": graph_id,
                "graph_id": graph_id,
                "langgraph_auth_user": user,
            },
        }
    )

    async def create(responses):
        model = RecordingModel(responses=responses)
        monkeypatch.setattr(factory, "build_model", lambda *args, **kwargs: model)
        graph = await factory.get_agent(cfg)
        graph.checkpointer = InMemorySaver()
        return graph, cfg, model

    return create


def call(name, args):
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": "call"}]
    )


@pytest.mark.parametrize(
    "key,value,query,start",
    [
        ("RUNTIME_BACKEND", "docker", True, True),
        ("RUNTIME_BACKEND", "local", True, False),
        ("RUNTIME_BACKGROUND_TASKS_ENABLED", "0", True, False),
        ("RUNTIME_EXECUTION_HOST_ID", "", True, False),
        ("RUNTIME_EXECUTION_HOST_ID", "invalid host", True, False),
        ("DATABASE_URI", "", False, False),
    ],
)
def test_model_tool_visibility_matches_capabilities(
    build, monkeypatch, key, value, query, start
):
    monkeypatch.setenv("RUNTIME_BACKEND", "docker")
    monkeypatch.setenv(key, value)

    async def run():
        graph, cfg, model = await build([AIMessage(content="completed")])
        result = await graph.ainvoke(
            {"messages": [("user", "short command")]}, cfg, context=cfg["context"]
        )
        assert result["messages"][-1].content == "completed"
        names = model.seen_tools[0]
        assert "execute" in names
        assert ("background_task" in names) is query
        assert ("cancel_background_task" in names) is query
        assert ("background_execute" in names) is start

    asyncio.run(run())


def test_flag_disabled_after_assembly_returns_native_error_and_model_continues(
    build, monkeypatch
):
    monkeypatch.setenv("RUNTIME_BACKEND", "docker")
    read = Mock(return_value=None)
    reserve, create = Mock(), AsyncMock()
    monkeypatch.setattr(service.repository, "read_submission", read)
    monkeypatch.setattr(service.repository, "reserve_task", reserve)
    monkeypatch.setattr(service, "create_task_container", create)

    async def run():
        graph, cfg, model = await build(
            [
                call("background_execute", {"command": "sleep 300", "timeout": 300}),
                AIMessage(content="The long command needs a supported environment."),
            ]
        )
        monkeypatch.setenv("RUNTIME_BACKGROUND_TASKS_ENABLED", "0")
        result = await graph.ainvoke(
            {"messages": [("user", "long command")]}, cfg, context=cfg["context"]
        )
        message = next(m for m in result["messages"] if isinstance(m, ToolMessage))
        assert message.status == "error" and message.tool_call_id == "call"
        payload = json.loads(message.content)
        assert payload["code"] == "background_task_disabled"
        assert payload["outcome"] == "not_started" and "最大60秒" in payload["error"]
        assert message in model.seen_messages[-1]
        assert all("background_execute" not in tools for tools in model.seen_tools)
        assert result["messages"][-1].content.endswith("supported environment.")

    asyncio.run(run())
    read.assert_called_once()
    reserve.assert_not_called()
    create.assert_not_awaited()


def test_unverified_workspace_error_still_stops_model(build, monkeypatch):
    monkeypatch.setenv("RUNTIME_BACKEND", "docker")
    error = RuntimeWorkspaceError("background_task_not_supported")
    monkeypatch.setattr(service.repository, "read_submission", Mock(side_effect=error))

    async def run():
        graph, cfg, model = await build(
            [
                call("background_execute", {"command": "printf done", "timeout": 30}),
                AIMessage(content="must not continue"),
            ]
        )
        with pytest.raises(RuntimeWorkspaceError) as caught:
            await graph.ainvoke(
                {"messages": [("user", "command")]}, cfg, context=cfg["context"]
            )
        assert caught.value is error and len(model.seen_messages) == 1

    asyncio.run(run())


def test_checkpoint_rebuild_keeps_receipt_route_hidden_from_model(build, monkeypatch):
    monkeypatch.setenv("RUNTIME_BACKEND", "docker")
    receipt = {"task_id": "original-task", "status": "unknown"}
    replay = AsyncMock(return_value=receipt)
    monkeypatch.setattr(background, "start_task", replay)
    monkeypatch.setattr(background, "task_view", lambda row: row)

    async def run():
        original, cfg, _ = await build(
            [call("background_execute", {"command": "sleep 300", "timeout": 300})]
        )
        original.interrupt_before_nodes = ["tools"]
        await original.ainvoke(
            {"messages": [("user", "long command")]}, cfg, context=cfg["context"]
        )
        assert (await original.aget_state(cfg)).next == ("tools",)
        replay.assert_not_awaited()

        monkeypatch.setenv("RUNTIME_BACKEND", "local")
        monkeypatch.setenv("RUNTIME_BACKGROUND_TASKS_ENABLED", "0")
        rebuilt, _, model = await build([AIMessage(content="Receipt remains unknown.")])
        rebuilt.checkpointer = original.checkpointer
        result = await rebuilt.ainvoke(None, cfg, context=cfg["context"])
        message = next(m for m in result["messages"] if isinstance(m, ToolMessage))
        assert json.loads(message.content) == receipt
        assert "background_execute" not in model.seen_tools[0]
        assert result["messages"][-1].content == "Receipt remains unknown."

    asyncio.run(run())
    replay.assert_awaited_once()
