"""Budget notices layered on the official counters and graph managed values."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from typing import Annotated, Any, Literal, NotRequired

from langchain.agents.middleware import ModelRequest, hook_config
from langchain.agents.middleware.model_call_limit import (
    ModelCallLimitExceededError,
    ModelCallLimitMiddleware,
    ModelCallLimitState,
)
from langchain.agents.middleware.types import PrivateStateAttr
from langgraph.channels import UntrackedValue
from langgraph.config import get_config
from langgraph.errors import GraphBubbleUp
from langgraph.managed.is_last_step import RemainingStepsManager
from typing_extensions import TypedDict

from runtime_service.observability.diagnostics import log_diagnostic

WRAPUP_INSTRUCTION = (
    "Execution budget is running low. Finish the current task using the information "
    "already available. Do not start new investigations or delegate new work. "
    "Clearly report completed and unfinished items and a useful continuation point. "
    "Do not perform unapproved writes or claim unfinished work is complete."
)


class GraphBudgetState(TypedDict):
    remaining_steps: Annotated[int, PrivateStateAttr, RemainingStepsManager]
    runtime_budget_latches: NotRequired[
        Annotated[set[str], UntrackedValue, PrivateStateAttr]
    ]
    runtime_budget_wrapup: NotRequired[
        Annotated[bool, UntrackedValue, PrivateStateAttr]
    ]


class ExecutionBudgetState(ModelCallLimitState, GraphBudgetState):
    pass


def build_budget_notice(
    *,
    code: str,
    budget_scope: str,
    unit: str,
    scope: str = "primary",
    graph_key: str = "agent",
    limit: int | float | None = None,
    used: int | float | None = None,
    remaining: int | float | None = None,
) -> dict[str, Any] | None:
    try:
        config = get_config()
    except RuntimeError:
        return None
    run_id = (config.get("metadata") or {}).get("run_id")
    if not isinstance(run_id, str) or not 0 < len(run_id) <= 128:
        return None
    # Node task IDs change every step; only the enclosing graph identifies this budget.
    node_ns = str((config.get("configurable") or {}).get("checkpoint_ns", ""))
    graph_ns = node_ns.rsplit("|", 1)[0] if "|" in node_ns else ""
    namespace_id = hashlib.sha256(f"{graph_key}:{graph_ns}".encode()).hexdigest()[:20]
    return {
        "version": 1,
        "type": "runtime_budget_notice",
        "notice_id": f"budget:{run_id}:{namespace_id}:{budget_scope}:{code}",
        "run_id": run_id,
        "scope": scope,
        "budget_scope": budget_scope,
        "code": code,
        "limit": limit,
        "used": used,
        "remaining": remaining,
        "unit": unit,
    }


def emit_budget_notice(notice, runtime, *, writer=None) -> None:
    if notice is None:
        return
    log_diagnostic("runtime.budget.notice", notice)
    try:
        (writer or runtime.stream_writer)(notice)
    except GraphBubbleUp:
        raise
    except Exception:
        log_diagnostic(
            "runtime.budget.notice_delivery_failed",
            {
                "run_id": notice["run_id"],
                "code": notice["code"],
                "scope": notice["scope"],
            },
        )


def add_wrapup_instruction(request: ModelRequest) -> ModelRequest:
    message = request.system_message
    content = message.content if message is not None else ""
    if isinstance(content, list):
        if any(
            WRAPUP_INSTRUCTION
            in (block if isinstance(block, str) else str(block.get("text", "")))
            for block in content
        ):
            return request
        content = [*content, {"type": "text", "text": WRAPUP_INSTRUCTION}]
    elif WRAPUP_INSTRUCTION in content:
        return request
    else:
        content = (
            f"{content}\n\n{WRAPUP_INSTRUCTION}" if content else WRAPUP_INSTRUCTION
        )
    from langchain_core.messages import SystemMessage

    system_message = (
        message.model_copy(update={"content": content})
        if message
        else SystemMessage(content=content)
    )
    return request.override(system_message=system_message)


def check_graph_budget(
    state: Mapping[str, Any],
    runtime,
    *,
    warning_steps: int = 8,
    scope: str = "primary",
    graph_key: str = "agent",
    writer=None,
) -> dict[str, Any]:
    remaining = state.get("remaining_steps")
    latches = set(state.get("runtime_budget_latches", ()))
    if type(remaining) is not int or remaining > warning_steps:
        return {}
    key = "graph_step_limit_approaching"
    if key not in latches:
        config = get_config()
        limit = config.get("recursion_limit")
        limit = limit if type(limit) is int else None
        emit_budget_notice(
            build_budget_notice(
                code=key,
                budget_scope="graph",
                unit="graph_supersteps",
                scope=scope,
                graph_key=graph_key,
                limit=limit,
                used=max(0, limit - remaining) if limit is not None else None,
                remaining=max(0, remaining),
            ),
            runtime,
            writer=writer,
        )
        latches.add(key)
    return {"runtime_budget_latches": latches, "runtime_budget_wrapup": True}


class ExecutionBudgetMiddleware(ModelCallLimitMiddleware):
    state_schema = ExecutionBudgetState

    def __init__(
        self,
        *,
        run_limit: int | None = None,
        thread_limit: int | None = None,
        exit_behavior: Literal["end", "error"] = "end",
        warning_calls: int = 3,
        warning_steps: int = 8,
        scope: Literal["primary", "subagent"] = "primary",
        graph_key: str = "agent",
        writer: Callable | None = None,
        wrapup_requested: bool = False,
    ) -> None:
        super().__init__(
            run_limit=run_limit, thread_limit=thread_limit, exit_behavior=exit_behavior
        )
        if any(
            type(value) is not int or value < 0
            for value in (warning_calls, warning_steps)
        ):
            raise ValueError("budget warning margins must be non-negative integers")
        self.warning_calls = warning_calls
        self.warning_steps = warning_steps
        self.scope = scope
        self.graph_key = graph_key
        self.writer = writer
        self.wrapup_requested = wrapup_requested

    def _model_notices(self, state, runtime, *, reached: bool):
        latches = set(state.get("runtime_budget_latches", ()))
        notices = []
        for budget_scope, limit, used in (
            ("thread", self.thread_limit, state.get("thread_model_call_count", 0)),
            ("run", self.run_limit, state.get("run_model_call_count", 0)),
        ):
            if limit is None:
                continue
            remaining = max(0, limit - used)
            if (reached and used < limit) or (
                not reached and remaining > self.warning_calls
            ):
                continue
            code = f"model_call_limit_{'reached' if reached else 'approaching'}"
            key = f"{budget_scope}:{code}"
            notice = build_budget_notice(
                code=code,
                budget_scope=budget_scope,
                unit="model_calls",
                scope=self.scope,
                graph_key=self.graph_key,
                limit=limit,
                used=used,
                remaining=remaining,
            )
            if key not in latches:
                emit_budget_notice(notice, runtime, writer=self.writer)
                latches.add(key)
            if notice is not None:
                notices.append(notice)
        return latches, notices

    @hook_config(can_jump_to=["end"])
    def before_model(self, state, runtime):
        try:
            result = super().before_model(state, runtime)
        except ModelCallLimitExceededError:
            self._model_notices(state, runtime, reached=True)
            raise
        if result is not None:
            latches, notices = self._model_notices(state, runtime, reached=True)
            if notices:
                result["messages"] = [
                    message.model_copy(
                        update={
                            "additional_kwargs": {
                                **message.additional_kwargs,
                                "runtime_budget_notice": notices[0],
                            }
                        }
                    )
                    for message in result["messages"]
                ]
            return {**result, "runtime_budget_latches": latches}
        latches, _ = self._model_notices(state, runtime, reached=False)
        graph_update = check_graph_budget(
            {**state, "runtime_budget_latches": latches},
            runtime,
            warning_steps=self.warning_steps,
            scope=self.scope,
            graph_key=self.graph_key,
            writer=self.writer,
        )
        return {
            "runtime_budget_latches": latches,
            **graph_update,
            "runtime_budget_wrapup": bool(
                latches or graph_update or state.get("runtime_budget_wrapup")
            ),
        }

    def wrap_model_call(self, request, handler):
        return handler(
            add_wrapup_instruction(request)
            if self.wrapup_requested or request.state.get("runtime_budget_wrapup")
            else request
        )

    async def awrap_model_call(self, request, handler):
        return await handler(
            add_wrapup_instruction(request)
            if self.wrapup_requested or request.state.get("runtime_budget_wrapup")
            else request
        )


__all__ = [
    "ExecutionBudgetMiddleware",
    "ExecutionBudgetState",
    "GraphBudgetState",
    "add_wrapup_instruction",
    "build_budget_notice",
    "check_graph_budget",
    "emit_budget_notice",
]
