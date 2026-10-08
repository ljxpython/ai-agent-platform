"""Best-effort model wrapup before the Worker's shared hard deadline or soft threshold."""

from __future__ import annotations

import math
import os
import time
from time import monotonic
from typing import Annotated, NotRequired

from langchain.agents.middleware import AgentMiddleware, ModelRequest
from langchain.agents.middleware.types import AgentState, PrivateStateAttr
from langchain_core.messages import SystemMessage
from langgraph.channels import UntrackedValue

from runtime_service.middlewares.execution_budget import (
    add_wrapup_instruction,
    build_budget_notice,
    emit_budget_notice,
)
from runtime_service.runtime.run_budget import RunBudget

TIMEOUT_WRAPUP_INSTRUCTION = (
    "The current run is nearing its execution deadline. Stop starting new investigations "
    "or long-running work and wrap up now. Report completed work, unfinished work, "
    "verified artifact paths, and any necessary next steps. Preserve progress only through "
    "available authorized actions. Keep all approval and permission requirements. "
    "Do not claim unverified writes, remote actions, or a complete result succeeded."
)


def resolve_wrapup_after_seconds() -> float | None:
    raw = os.getenv("AGENT_WRAPUP_AFTER_SECONDS", "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(
            "AGENT_WRAPUP_AFTER_SECONDS must be finite and positive"
        ) from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError("AGENT_WRAPUP_AFTER_SECONDS must be finite and positive")
    return value


class TimeoutWrapupState(AgentState):
    runtime_wrapup_start: NotRequired[
        Annotated[float, UntrackedValue, PrivateStateAttr]
    ]
    runtime_wrapup_started: NotRequired[
        Annotated[bool, UntrackedValue, PrivateStateAttr]
    ]


class TimeoutWrapupMiddleware(AgentMiddleware):
    state_schema = TimeoutWrapupState

    def __init__(
        self,
        budget: RunBudget | float | None = None,
        *,
        clock=time.monotonic,
        writer=None,
        graph_key="agent",
    ) -> None:
        super().__init__()
        self.clock = clock
        self.writer = writer
        self.graph_key = graph_key

        if budget is not None and not isinstance(budget, RunBudget):
            if (
                isinstance(budget, bool)
                or not isinstance(budget, (int, float))
                or not math.isfinite(budget)
                or budget <= 0
            ):
                raise ValueError("after_seconds must be a finite positive number")
            self.after_seconds: float | None = float(budget)
            self.budget: RunBudget | None = None
        else:
            self.after_seconds = None
            self.budget = budget

    def before_agent(self, state, runtime):
        if self.after_seconds is not None:
            return {
                "runtime_wrapup_start": self.clock(),
                "runtime_wrapup_started": False,
            }
        return {}

    async def abefore_agent(self, state, runtime):
        return self.before_agent(state, runtime)

    def before_model(self, state, runtime):
        if self.after_seconds is not None:
            now = self.clock()
            start = state.get("runtime_wrapup_start", now)
            elapsed = max(0.0, now - start)
            started = bool(state.get("runtime_wrapup_started"))
            if elapsed >= self.after_seconds and not started:
                emit_budget_notice(
                    build_budget_notice(
                        code="wrapup_started",
                        budget_scope="run",
                        unit="seconds",
                        graph_key=self.graph_key,
                        limit=self.after_seconds,
                        used=elapsed,
                    ),
                    runtime,
                    writer=self.writer,
                )
                started = True
            return {"runtime_wrapup_start": start, "runtime_wrapup_started": started}
        return {}

    async def abefore_model(self, state, runtime):
        return self.before_model(state, runtime)

    def wrap_model_call(self, request, handler):
        if self.after_seconds is not None:
            return handler(
                add_wrapup_instruction(request)
                if request.state.get("runtime_wrapup_started")
                else request
            )
        return handler(request)

    async def awrap_model_call(self, request: ModelRequest, handler):
        if self.budget is not None:
            if (
                self.budget.wrapup_reserve_seconds == 0
                or monotonic() < self.budget.soft_deadline_monotonic
            ):
                return await handler(request)
            original = request.system_message
            blocks = (
                list(original.content)
                if original is not None and isinstance(original.content, list)
                else [{"type": "text", "text": original.content}]
                if original is not None
                else []
            )
            if not any(
                TIMEOUT_WRAPUP_INSTRUCTION
                in (block if isinstance(block, str) else block.get("text", ""))
                for block in blocks
            ):
                blocks.append({"type": "text", "text": TIMEOUT_WRAPUP_INSTRUCTION})
                system_message = (
                    original.model_copy(update={"content": blocks})
                    if original is not None
                    else SystemMessage(content=blocks)
                )
                request = request.override(system_message=system_message)
            return await handler(request)

        if self.after_seconds is not None:
            return await handler(
                add_wrapup_instruction(request)
                if request.state.get("runtime_wrapup_started")
                else request
            )

        return await handler(request)


__all__ = [
    "TimeoutWrapupMiddleware",
    "TimeoutWrapupState",
    "resolve_wrapup_after_seconds",
    "TIMEOUT_WRAPUP_INSTRUCTION",
]
