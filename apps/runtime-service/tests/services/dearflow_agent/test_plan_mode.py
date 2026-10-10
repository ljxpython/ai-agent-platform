import asyncio

import pytest
from langchain_core.messages import AIMessage
from langgraph.types import Command

from runtime_service.runtime import RuntimeResolutionError, runtime_context_hash
from runtime_service.runtime.planning import PLAN_TOOL_NAMES
from runtime_service.services.dearflow_agent.workspace.backend import (
    DearWorkspaceBackend,
)

from .test_agent import build, call, config  # noqa: F401


def planning_config(mode="standard", policy="review", *, planning=True):
    cfg = config()
    cfg["context"] = {
        "execution_mode": mode,
        "access_policy": policy,
        "plan_mode": planning,
        "plan_execution_id": "execution-1",
    }
    cfg["configurable"]["langgraph_auth_user"]["runtime_context_hash"] = (
        runtime_context_hash(cfg["context"])
    )
    return cfg


def reply(pending, decision="approve", feedback=None):
    return {
        "version": 1,
        "type": "agent_plan_response",
        "decision": decision,
        **{key: pending.value[key] for key in ("plan_id", "revision", "content_hash")},
        **({"feedback": feedback} if feedback is not None else {}),
    }


@pytest.mark.parametrize("mode", ["flash", "standard", "pro", "ultra"])
@pytest.mark.parametrize("policy", ["review", "workspace_write", "full_access"])
@pytest.mark.parametrize("planning", [False, True])
def test_mode_policy_planning_matrix(build, mode, policy, planning):  # noqa: F811
    async def run():
        cfg = planning_config(mode, policy, planning=planning)
        graph, cfg = await build(
            [
                call(
                    "write_file",
                    {"file_path": "/workspace/work/output.txt", "content": "written"},
                ),
                AIMessage(content="done"),
            ],
            cfg,
        )
        root = DearWorkspaceBackend("tenant", "project", "dear-thread").root
        if planning:
            with pytest.raises(
                RuntimeResolutionError, match="runtime.plan.tool_denied"
            ):
                await graph.ainvoke(
                    {"messages": [("user", "write")]}, cfg, context=cfg["context"]
                )
            assert not (root / "work/output.txt").exists()
        else:
            result = await graph.ainvoke(
                {"messages": [("user", "write")]}, cfg, context=cfg["context"]
            )
            assert bool(result.get("__interrupt__")) == (policy == "review")
            assert (root / "work/output.txt").exists() == (policy != "review")

    asyncio.run(run())


@pytest.mark.parametrize("mode", ["flash", "standard", "pro", "ultra"])
def test_plan_approval_does_not_change_tool_policy(build, mode):  # noqa: F811
    async def run():
        cfg = planning_config(mode)
        graph, cfg = await build(
            [
                call(
                    "save_plan",
                    {"title": "Plan", "markdown": "Read first, then write."},
                    "save",
                ),
                call("submit_plan", {}, "submit"),
                call(
                    "write_file",
                    {"file_path": "/workspace/work/output.txt", "content": "approved"},
                    "write",
                ),
                AIMessage(content="done"),
            ],
            cfg,
        )
        result = await graph.ainvoke(
            {"messages": [("user", "plan first")]}, cfg, context=cfg["context"]
        )
        pending = result["__interrupt__"][0]
        assert pending.value["type"] == "agent_plan_review"
        assert result["runtime_plan"]["active"]
        result = await graph.ainvoke(
            Command(resume={pending.id: reply(pending)}), cfg, context=cfg["context"]
        )
        assert not result["runtime_plan"]["active"]
        assert (
            result["__interrupt__"][0].value["action_requests"][0]["name"]
            == "write_file"
        )
        assert cfg["context"]["execution_mode"] == mode
        assert not (
            DearWorkspaceBackend("tenant", "project", "dear-thread").root
            / "work/output.txt"
        ).exists()

    asyncio.run(run())


@pytest.mark.parametrize("decision", ["request_changes", "abandon"])
def test_unapproved_decisions_keep_restriction(build, decision):  # noqa: F811
    async def run():
        cfg = planning_config()
        graph, cfg = await build(
            [
                call("save_plan", {"title": "Plan", "markdown": "A draft."}, "save"),
                call("submit_plan", {}, "submit"),
                AIMessage(content="revise"),
            ],
            cfg,
        )
        state = await graph.ainvoke(
            {"messages": [("user", "plan")]}, cfg, context=cfg["context"]
        )
        pending = state["__interrupt__"][0]
        state = await graph.ainvoke(
            Command(resume={pending.id: reply(pending, decision, "Revise it")}),
            cfg,
            context=cfg["context"],
        )
        assert state["runtime_plan"]["active"]
        assert state["runtime_plan"]["decision"]["decision"] == decision
        if decision == "abandon":
            assert state["messages"][-1].type == "tool"
            assert not (await graph.aget_state(cfg)).next

    asyncio.run(run())


def test_mixed_transition_batch_has_no_side_effect(build):  # noqa: F811
    async def run():
        cfg = planning_config(planning=False)
        message = call("enter_plan_mode", {}, "enter")
        message.tool_calls += call(
            "write_file",
            {"file_path": "/workspace/work/bad.txt", "content": "bad"},
            "write",
        ).tool_calls
        graph, cfg = await build([message], cfg)
        with pytest.raises(RuntimeResolutionError, match="runtime.plan.batch_invalid"):
            await graph.ainvoke(
                {"messages": [("user", "enter")]}, cfg, context=cfg["context"]
            )
        assert not (
            DearWorkspaceBackend("tenant", "project", "dear-thread").root
            / "work/bad.txt"
        ).exists()

    asyncio.run(run())


@pytest.mark.parametrize(
    "disabled",
    [PLAN_TOOL_NAMES, ("enter_plan_mode",), ("save_plan",), ("submit_plan",)],
)
def test_disabled_plan_tools_fail_closed(build, disabled):  # noqa: F811
    async def run():
        cfg = planning_config()
        cfg["configurable"]["langgraph_auth_user"]["runtime_policy"][
            "tool_overrides"
        ] = {name: False for name in disabled}
        graph, cfg = await build([AIMessage(content="do nothing")], cfg)
        with pytest.raises(
            RuntimeResolutionError, match="runtime.plan.tools_unavailable"
        ):
            await graph.ainvoke(
                {"messages": [("user", "plan")]}, cfg, context=cfg["context"]
            )

    asyncio.run(run())


@pytest.mark.parametrize("disabled", ["save_plan", "submit_plan"])
def test_autonomous_enter_requires_all_control_tools(build, disabled):  # noqa: F811
    async def run():
        cfg = planning_config(planning=False)
        cfg["configurable"]["langgraph_auth_user"]["runtime_policy"][
            "tool_overrides"
        ] = {disabled: False}
        graph, cfg = await build([call("enter_plan_mode", {}, "enter")], cfg)
        with pytest.raises(
            RuntimeResolutionError, match="runtime.plan.tools_unavailable"
        ):
            await graph.ainvoke(
                {"messages": [("user", "plan")]}, cfg, context=cfg["context"]
            )
        state = (await graph.aget_state(cfg)).values
        assert not state.get("runtime_plan")

    asyncio.run(run())
