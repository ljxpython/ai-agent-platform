"""Actual execution gates remain effective without a preceding model call."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langchain.agents.middleware.types import ModelRequest
from langchain.tools import tool
from langchain_core.messages import AIMessage, SystemMessage

from runtime_service.middlewares.plan_mode import PlanModeMiddleware
from runtime_service.runtime import RuntimeResolutionError
from runtime_service.runtime.planning import new_plan
from runtime_service.tools.plan_mode import PLAN_TOOLS


@tool
def readonly() -> str:
    """Read a trusted resource."""
    return "read"


def request_for(name, actual_tool=None, *, active=True, calls=None):
    state = {"runtime_plan": new_plan("execution").model_dump()} if active else {}
    if calls is not None:
        state["messages"] = [AIMessage(content="", tool_calls=calls)]
    return SimpleNamespace(
        tool_call={"name": name, "args": {}, "id": "attack"},
        tool=actual_tool,
        runtime=SimpleNamespace(
            state=state, context={"plan_execution_id": "execution"}
        ),
    )


@pytest.mark.parametrize(
    "name", ["write_file", "execute", "task", "mcp_write", "unknown"]
)
def test_direct_hidden_tool_never_reaches_handler(name):
    handler = AsyncMock()
    with pytest.raises(RuntimeResolutionError, match="runtime.plan.tool_denied"):
        asyncio.run(PlanModeMiddleware().awrap_tool_call(request_for(name), handler))
    handler.assert_not_awaited()


def test_same_name_readonly_substitution_is_not_trusted():
    fake = readonly.model_copy()
    handler = AsyncMock()
    middleware = PlanModeMiddleware([readonly])
    with pytest.raises(RuntimeResolutionError, match="runtime.plan.tool_denied"):
        asyncio.run(middleware.awrap_tool_call(request_for("readonly", fake), handler))
    handler.assert_not_awaited()
    asyncio.run(middleware.awrap_tool_call(request_for("readonly", readonly), handler))
    handler.assert_awaited_once()


@pytest.mark.parametrize("active", [False, True])
def test_forged_control_tool_is_denied_even_outside_planning(active):
    handler = AsyncMock()
    fake = PLAN_TOOLS[0].model_copy()
    with pytest.raises(RuntimeResolutionError, match="runtime.plan.tool_denied"):
        asyncio.run(
            PlanModeMiddleware().awrap_tool_call(
                request_for(fake.name, fake, active=active), handler
            )
        )
    handler.assert_not_awaited()


@pytest.mark.parametrize("control", PLAN_TOOLS)
def test_child_has_no_plan_control_tool(control):
    handler = AsyncMock()
    with pytest.raises(RuntimeResolutionError, match="runtime.plan.tool_denied"):
        asyncio.run(
            PlanModeMiddleware(child=True).awrap_tool_call(
                request_for(control.name, control, active=False), handler
            )
        )
    handler.assert_not_awaited()


def test_direct_mixed_batch_rejects_readonly_before_any_execution():
    calls = [
        {"name": "readonly", "args": {}, "id": "read"},
        {"name": "execute", "args": {}, "id": "write"},
    ]
    handler = AsyncMock()
    with pytest.raises(RuntimeResolutionError, match="runtime.plan.tool_denied"):
        asyncio.run(
            PlanModeMiddleware([readonly]).awrap_tool_call(
                request_for("readonly", readonly, calls=calls), handler
            )
        )
    handler.assert_not_awaited()


def test_new_execution_preserves_restriction_and_discards_old_identity():
    async def run():
        middleware = PlanModeMiddleware()
        plan = new_plan("old").model_dump()
        runtime = SimpleNamespace(
            context={"plan_execution_id": "new", "plan_mode": False}
        )
        updated = await middleware.abefore_agent({"runtime_plan": plan}, runtime)
        assert updated["runtime_plan"]["active"]
        assert updated["runtime_plan"]["plan_id"] != plan["plan_id"]
        assert updated["runtime_plan"]["bound_execution_id"] == "new"
        assert await middleware.abefore_agent(updated, runtime) is None
        with pytest.raises(RuntimeResolutionError, match="runtime.plan.state_invalid"):
            await middleware.awrap_tool_call(
                SimpleNamespace(
                    tool_call={"name": "readonly"},
                    tool=readonly,
                    runtime=SimpleNamespace(
                        state={"runtime_plan": plan}, context=runtime.context
                    ),
                ),
                AsyncMock(),
            )

    asyncio.run(run())


def test_planning_keeps_structured_system_blocks_and_metadata():
    original = SystemMessage(
        content=[
            {"type": "text", "text": "original", "cache_control": {"type": "ephemeral"}}
        ],
        name="system",
        additional_kwargs={"marker": "keep"},
    )
    request = ModelRequest(
        model=None,
        tools=list(PLAN_TOOLS),
        messages=[],
        system_message=original,
        state={"runtime_plan": new_plan("execution").model_dump()},
        runtime=SimpleNamespace(context={"plan_execution_id": "execution"}),
    )

    async def handler(filtered):
        assert filtered.system_message.content[0] == original.content[0]
        assert filtered.system_message.additional_kwargs == original.additional_kwargs
        assert filtered.system_message.name == original.name
        assert len(original.content) == 1
        return AIMessage(content="done")

    asyncio.run(PlanModeMiddleware().awrap_model_call(request, handler))
