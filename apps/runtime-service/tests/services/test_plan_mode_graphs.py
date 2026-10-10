import asyncio
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from services.dearflow_agent.test_agent import call, config
from services.dearflow_agent.test_plan_mode import reply
from support import BindableFakeMessagesChatModel

from runtime_service.middlewares.plan_mode import PlanModeMiddleware
from runtime_service.runtime import RuntimeResolutionError, runtime_context_hash


@pytest.mark.parametrize(
    "graph_id,module",
    [
        ("reference_agent", "runtime_service.services.reference_agent.agent"),
        ("showcase_demo", "runtime_service.services.demo.showcase_demo.agent"),
        ("workflow_demo", "runtime_service.services.demo.workflow_demo.agent"),
    ],
)
@pytest.mark.parametrize("decision", ["approve", "request_changes", "abandon"])
def test_graph_plan_interrupt_and_rebuilt_resume(
    monkeypatch, tmp_path, graph_id, module, decision
):
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("RUNTIME_SHOWCASE_EXECUTION_MODE", "local")
    root = import_module(module)
    model = BindableFakeMessagesChatModel(
        responses=[
            call(
                "save_plan",
                {"title": "Plan", "markdown": "Read before execution."},
                "save",
            ),
            call("submit_plan", {}, "submit"),
            AIMessage(content="done"),
        ]
    )
    monkeypatch.setattr(root, "build_model", lambda *args, **kwargs: model)
    cfg = config()
    cfg["context"] = {"plan_mode": True, "plan_execution_id": "graph-execution"}
    cfg["configurable"].update(graph_id=graph_id, assistant_id=graph_id)
    auth = cfg["configurable"]["langgraph_auth_user"]
    auth["runtime_scope"]["assistant_id"] = graph_id
    auth["runtime_context_hash"] = runtime_context_hash(cfg["context"])

    async def run():
        saver = InMemorySaver()
        graph = await root.get_agent(cfg)
        graph.checkpointer = saver
        result = await graph.ainvoke(
            {"messages": [("user", "plan first")]}, cfg, context=cfg["context"]
        )
        pending = result["__interrupt__"][0]
        assert pending.value["type"] == "agent_plan_review"
        graph = await root.get_agent(cfg)
        graph.checkpointer = saver
        result = await graph.ainvoke(
            Command(resume={pending.id: reply(pending, decision, "More detail")}),
            cfg,
            context=cfg["context"],
        )
        state = (await graph.aget_state(cfg)).values
        assert state["runtime_plan"]["active"] == (decision != "approve")
        assert state["runtime_plan"]["decision"]["decision"] == decision
        assert not (await graph.aget_state(cfg)).next

    asyncio.run(run())


def test_showcase_children_use_their_own_readonly_instances(monkeypatch, tmp_path):
    root = import_module("runtime_service.services.demo.showcase_demo.agent")
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("RUNTIME_SHOWCASE_EXECUTION_MODE", "local")
    monkeypatch.setattr(
        root,
        "build_model",
        lambda *args, **kwargs: BindableFakeMessagesChatModel(
            responses=[AIMessage(content="done")]
        ),
    )
    captured = []
    compile_agent = root.create_deep_agent

    def capture(**kwargs):
        captured.extend(kwargs["subagents"])
        return compile_agent(**kwargs)

    monkeypatch.setattr(root, "create_deep_agent", capture)

    async def run():
        from services.showcase_demo.test_agent import config as showcase_config

        await root.get_agent(showcase_config())
        assert {child["name"] for child in captured} >= {"research", "general-purpose"}
        for child in captured:
            filesystem = child["middleware"][0]
            gate = next(
                mw for mw in child["middleware"] if isinstance(mw, PlanModeMiddleware)
            )
            assert not gate.tools
            readonly = next(
                tool for tool in filesystem.tools if tool.name == "read_file"
            )
            runtime = SimpleNamespace(state={}, context={"plan_mode": True})
            handler = AsyncMock()
            request = SimpleNamespace(
                tool_call={"name": readonly.name}, tool=readonly, runtime=runtime
            )
            await gate.awrap_tool_call(request, handler)
            handler.assert_awaited_once()
            handler.reset_mock()
            request.tool_call, request.tool = {"name": "write_file"}, None
            with pytest.raises(
                RuntimeResolutionError, match="runtime.plan.tool_denied"
            ):
                await gate.awrap_tool_call(request, handler)
            handler.assert_not_awaited()

    asyncio.run(run())


def test_showcase_plan_approval_keeps_child_tool_hitl(monkeypatch, tmp_path):
    root = import_module("runtime_service.services.demo.showcase_demo.agent")
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("RUNTIME_SHOWCASE_EXECUTION_MODE", "local")
    model = BindableFakeMessagesChatModel(
        responses=[
            call(
                "save_plan",
                {"title": "Plan", "markdown": "Delegate after approval."},
                "save",
            ),
            call("submit_plan", {}, "submit"),
            call(
                "task",
                {"description": "Write once", "subagent_type": "general-purpose"},
                "task",
            ),
            call(
                "write_file",
                {"file_path": "/workspace/work/child-approved.txt", "content": "once"},
                "write",
            ),
            AIMessage(content="child done"),
            AIMessage(content="parent done"),
        ]
    )
    monkeypatch.setattr(root, "build_model", lambda *args, **kwargs: model)
    cfg = config()
    cfg["context"] = {"plan_mode": True, "plan_execution_id": "execution"}
    cfg["configurable"].update(graph_id="showcase_demo", assistant_id="showcase_demo")
    user = cfg["configurable"]["langgraph_auth_user"]
    user["runtime_scope"]["assistant_id"] = "showcase_demo"
    user["runtime_context_hash"] = runtime_context_hash(cfg["context"])

    async def run():
        graph = await root.get_agent(cfg)
        graph.checkpointer = InMemorySaver()
        result = await graph.ainvoke(
            {"messages": [("user", "plan then delegate")]}, cfg, context=cfg["context"]
        )
        pending = result["__interrupt__"][0]
        result = await graph.ainvoke(
            Command(resume={pending.id: reply(pending, "approve")}),
            cfg,
            context=cfg["context"],
        )
        pending = result["__interrupt__"][0]
        assert pending.value["action_requests"][0]["name"] == "write_file"
        assert not list(tmp_path.rglob("child-approved.txt"))
        await graph.ainvoke(
            Command(resume={pending.id: {"decisions": [{"type": "approve"}]}}),
            cfg,
            context=cfg["context"],
        )
        files = list(tmp_path.rglob("child-approved.txt"))
        assert len(files) == 1 and files[0].read_text() == "once"

    asyncio.run(run())
