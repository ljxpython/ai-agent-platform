"""Bounded checkpoint facts, never raw messages, exception text or approval args."""

import asyncio
import re
from typing import get_args

from platform_api.core.errors import PlatformApiError
from platform_api.modules.runtime_gateway.domain.error_codes import (
    ModelErrorCode,
    WorkspaceErrorCode,
)

ERROR_CODES = {
    *get_args(ModelErrorCode),
    *get_args(WorkspaceErrorCode),
    "runtime.execution_failed",
    "runtime.loop.detected",
    "step_limit",
    "sandbox_unreachable",
}


def identifier(value):
    return (
        value
        if isinstance(value, str)
        and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value)
        and not re.search(r"(?i)secret|password|api.?key|bearer|sk-", value)
        else None
    )


def checkpoint_summary(state, run_id):
    if not isinstance(state, dict) or not isinstance(state.get("metadata"), dict):
        return {"availability": "unavailable", "reason": "invalid_state"}
    if state["metadata"].get("run_id") != run_id:
        return {"availability": "unavailable", "reason": "run_mismatch"}
    tasks = state.get("tasks")
    tasks_known = isinstance(tasks, list)
    tasks = tasks if tasks_known else []
    failures, interrupts = [], []
    interrupts_truncated = len(tasks) > 20
    if isinstance(state.get("interrupts"), list):
        interrupts_truncated |= len(state["interrupts"]) > 20
        interrupts.extend(state["interrupts"][:20])
    for task in tasks[:20]:
        if not isinstance(task, dict):
            continue
        if task.get("error"):
            error = task["error"]
            failures.append(
                {
                    "node": identifier(task.get("name")),
                    "error_code": error
                    if isinstance(error, str) and error in ERROR_CODES
                    else "unclassified_error",
                }
            )
        if isinstance(task.get("interrupts"), list):
            interrupts_truncated |= len(task["interrupts"]) > 20
            interrupts.extend(task["interrupts"][:20])
    # Only inspect interrupt shape; its value may contain business data or secrets.
    approval_pending = any(
        isinstance(item, dict)
        and isinstance(item.get("value"), dict)
        and isinstance(item["value"].get("action_requests"), list)
        and bool(item["value"]["action_requests"])
        and isinstance(item["value"].get("review_configs"), list)
        and bool(item["value"]["review_configs"])
        for item in interrupts
    )
    values = state.get("values")
    messages = values.get("messages") if isinstance(values, dict) else None
    counts = {"human": 0, "ai": 0, "tool": 0, "other": 0}
    if isinstance(messages, list):
        for message in messages[-200:]:
            kind = message.get("type") if isinstance(message, dict) else None
            counts[
                kind
                if isinstance(kind, str) and kind in {"human", "ai", "tool"}
                else "other"
            ] += 1
    checkpoint = state.get("checkpoint")
    return {
        "availability": "available",
        "scope": "latest_checkpoint_for_target_run",
        "run_id": run_id,
        "graph_id": identifier(state["metadata"].get("graph_id")),
        "checkpoint_id": identifier(
            checkpoint.get("checkpoint_id")
            if isinstance(checkpoint, dict)
            else state.get("checkpoint_id")
        ),
        "failed_tasks": failures,
        "tasks_truncated": len(tasks) > 20,
        "interrupts_truncated": interrupts_truncated,
        "interrupt_scope": "current_checkpoint_only",
        "interrupts_observed": True
        if interrupts
        else (
            False
            if not interrupts_truncated
            and (tasks_known or isinstance(state.get("interrupts"), list))
            else None
        ),
        "approval_pending": True
        if approval_pending
        else (
            False
            if not interrupts_truncated
            and (tasks_known or isinstance(state.get("interrupts"), list))
            else None
        ),
        "messages": {
            "scope": "checkpoint_state_not_run_delta",
            "counts": counts if isinstance(messages, list) else None,
            "truncated": isinstance(messages, list) and len(messages) > 200,
        },
        "side_effects": "unknown",
    }


async def read_checkpoint(gateway, *, actor, project_id, thread_id, run_id):
    try:
        # Includes current ACL checks and the upstream read; stay below the tool's 15s timeout.
        async with asyncio.timeout(8):
            history = await gateway.get_thread_history(
                actor=actor,
                project_id=project_id,
                thread_id=thread_id,
                payload={"limit": 1, "metadata": {"run_id": run_id}},
            )
    except PlatformApiError as exc:
        if exc.status_code in {401, 403}:
            raise
        return {"availability": "unavailable", "reason": "state_query_failed"}
    except TimeoutError:
        return {"availability": "unavailable", "reason": "state_query_timeout"}
    if not isinstance(history, list):
        return {"availability": "unavailable", "reason": "invalid_history"}
    if not history:
        return {"availability": "empty", "reason": "not_recorded"}
    return checkpoint_summary(history[0], run_id)
