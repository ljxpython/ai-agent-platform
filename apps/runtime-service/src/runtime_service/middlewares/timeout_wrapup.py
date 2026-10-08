"""Optional invocation-scoped soft wrapup; the Worker owns hard timeouts."""

from __future__ import annotations

import math
import os
import time
from typing import Annotated, NotRequired

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import AgentState, PrivateStateAttr
from langgraph.channels import UntrackedValue

from runtime_service.middlewares.execution_budget import (
    add_wrapup_instruction,
    build_budget_notice,
    emit_budget_notice,
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
        after_seconds: float,
        *,
        clock=time.monotonic,
        writer=None,
        graph_key="agent",
    ):
        super().__init__()
        if (
            isinstance(after_seconds, bool)
            or not isinstance(after_seconds, (int, float))
            or not math.isfinite(after_seconds)
            or after_seconds <= 0
        ):
            raise ValueError("after_seconds must be a finite positive number")
        self.after_seconds = float(after_seconds)
        self.clock = clock
        self.writer = writer
        self.graph_key = graph_key

    def before_agent(self, state, runtime):
        return {"runtime_wrapup_start": self.clock(), "runtime_wrapup_started": False}

    async def abefore_agent(self, state, runtime):
        return self.before_agent(state, runtime)

    def before_model(self, state, runtime):
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

    async def abefore_model(self, state, runtime):
        return self.before_model(state, runtime)

    def wrap_model_call(self, request, handler):
        return handler(
            add_wrapup_instruction(request)
            if request.state.get("runtime_wrapup_started")
            else request
        )

    async def awrap_model_call(self, request, handler):
        return await handler(
            add_wrapup_instruction(request)
            if request.state.get("runtime_wrapup_started")
            else request
        )


__all__ = ["TimeoutWrapupMiddleware", "resolve_wrapup_after_seconds"]
