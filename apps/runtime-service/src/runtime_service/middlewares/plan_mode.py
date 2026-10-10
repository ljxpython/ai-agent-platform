"""Composable planning restrictions at model and actual tool boundaries."""

from collections.abc import Sequence
from typing import NotRequired

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.tools import BaseTool

from runtime_service.runtime.errors import RuntimeResolutionError
from runtime_service.runtime.planning import (
    PLAN_TOOL_NAMES,
    new_plan,
    read_plan,
)
from runtime_service.runtime.resolver import parse_runtime_context
from runtime_service.tools.plan_mode import PLAN_TOOLS

PLAN_INSTRUCTION = "Planning restriction is active. Research with the exposed tools only; save_plan then submit_plan in separate tool batches. Do not write business files, execute scripts, publish artifacts, change memory/skills, use MCP or delegate tasks before human plan approval. Todo progress is not approval. Missing tools are unavailable. Human review may request changes or end this run."


class PlanModeState(AgentState):
    runtime_plan: NotRequired[dict | None]


class PlanModeMiddleware(AgentMiddleware):
    state_schema = PlanModeState

    def __init__(self, readonly_tools: Sequence[BaseTool] = (), *, child: bool = False):
        super().__init__()
        self.tools = [] if child else list(PLAN_TOOLS)
        self._child = child
        self._readonly = {tool.name: tool for tool in readonly_tools}
        if len(self._readonly) != len(readonly_tools) or set(self._readonly) & set(
            PLAN_TOOL_NAMES
        ):
            raise RuntimeResolutionError("runtime.plan.tool_invalid")

    async def abefore_agent(self, state, runtime):
        if self._child:
            return None
        context = parse_runtime_context(runtime.context)
        current = read_plan(state)
        if current and current.bound_execution_id == context.plan_execution_id:
            return None
        if context.plan_mode or current and current.active:
            return {"runtime_plan": new_plan(context.plan_execution_id).model_dump()}
        return {"runtime_plan": None} if current else None

    @hook_config(can_jump_to=["end"])
    async def abefore_model(self, state, runtime):
        current = read_plan(state)
        if current and current.decision and current.decision.decision == "abandon":
            return {"jump_to": "end"}
        return None

    def _active(self, state, runtime) -> bool:
        plan = read_plan(state)
        context = parse_runtime_context(runtime.context)
        if plan and plan.bound_execution_id != context.plan_execution_id:
            raise RuntimeResolutionError("runtime.plan.state_invalid")
        return plan.active if plan is not None else bool(context.plan_mode)

    def _allowed(self, tool: object) -> bool:
        name = getattr(tool, "name", None)
        if name in PLAN_TOOL_NAMES:
            return not self._child and any(
                tool is candidate for candidate in PLAN_TOOLS
            )
        return name in self._readonly and tool is self._readonly[name]

    def _check_batch(self, calls, *, active: bool, allowed: set[str]):
        if (
            any(call.get("name") in PLAN_TOOL_NAMES for call in calls)
            and len(calls) != 1
        ):
            raise RuntimeResolutionError("runtime.plan.batch_invalid")
        if active and any(call.get("name") not in allowed for call in calls):
            raise RuntimeResolutionError("runtime.plan.tool_denied")

    async def awrap_model_call(self, request, handler):
        active = self._active(request.state, request.runtime)
        tools = request.tools or []
        controls = [t for t in tools if getattr(t, "name", None) in PLAN_TOOL_NAMES]
        if any(not self._allowed(t) for t in controls):
            raise RuntimeResolutionError("runtime.plan.tool_invalid")
        complete = {t.name for t in controls} == set(PLAN_TOOL_NAMES)
        if active:
            if not self._child and not complete:
                raise RuntimeResolutionError("runtime.plan.tools_unavailable")
            tools = [t for t in tools if self._allowed(t)]
            original = request.system_message
            content = original.content if original else ""
            content = (
                [*content, {"type": "text", "text": PLAN_INSTRUCTION}]
                if isinstance(content, list)
                else content + "\n" + PLAN_INSTRUCTION
            )
            request = request.override(
                tools=tools,
                system_message=original.model_copy(update={"content": content})
                if original
                else SystemMessage(content=content),
            )
        response = await handler(request)
        messages = getattr(response, "result", None) or [response]
        allowed = {getattr(tool, "name", None) for tool in tools}
        for message in messages:
            if isinstance(message, AIMessage):
                if not complete and any(
                    call.get("name") == "enter_plan_mode" for call in message.tool_calls
                ):
                    raise RuntimeResolutionError("runtime.plan.tools_unavailable")
                self._check_batch(message.tool_calls, active=active, allowed=allowed)
        return response

    async def awrap_tool_call(self, request, handler):
        active = self._active(request.runtime.state, request.runtime)
        calls = next(
            (
                m.tool_calls
                for m in reversed(request.runtime.state.get("messages", []))
                if isinstance(m, AIMessage)
            ),
            [],
        )
        allowed = set(self._readonly) | (
            set(PLAN_TOOL_NAMES) if not self._child else set()
        )
        self._check_batch(calls, active=active, allowed=allowed)
        name = request.tool_call.get("name")
        if (active or name in PLAN_TOOL_NAMES) and not self._allowed(request.tool):
            raise RuntimeResolutionError("runtime.plan.tool_denied")
        return await handler(request)
