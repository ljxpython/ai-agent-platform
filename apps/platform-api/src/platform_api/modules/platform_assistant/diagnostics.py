"""Bounded checkpoint facts, never raw messages, exception text or approval args."""

import asyncio
import json
import re
from datetime import datetime
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
RUN_STATUSES = {
    "pending",
    "running",
    "success",
    "error",
    "timeout",
    "interrupted",
    "cancelled",
}


def identifier(value):
    return (
        value
        if isinstance(value, str)
        and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value)
        and not re.search(r"(?i)secret|password|api.?key|bearer|sk-", value)
        else None
    )


def _interrupt_flags(
    state, *, tasks_known=False, tasks=None, interrupts_truncated=False
):
    interrupts = []
    if isinstance(state.get("interrupts"), list):
        interrupts_truncated |= len(state["interrupts"]) > 20
        interrupts.extend(state["interrupts"][:20])
    for task in (tasks or [])[:20]:
        if isinstance(task, dict) and isinstance(task.get("interrupts"), list):
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
    known = not interrupts_truncated and (
        tasks_known or isinstance(state.get("interrupts"), list)
    )
    interrupts_observed = True if interrupts else (False if known else None)
    approval_state = True if approval_pending else (False if known else None)
    return interrupts_truncated, interrupts_observed, approval_state


def checkpoint_summary(state, run_id):
    if not isinstance(state, dict) or not isinstance(state.get("metadata"), dict):
        return {"availability": "unavailable", "reason": "invalid_state"}
    if state["metadata"].get("run_id") != run_id:
        return {"availability": "unavailable", "reason": "run_mismatch"}
    tasks = state.get("tasks")
    tasks_known = isinstance(tasks, list)
    tasks = tasks if tasks_known else []
    failures = []
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
    interrupts_truncated, interrupts_observed, approval_pending = _interrupt_flags(
        state,
        tasks_known=tasks_known,
        tasks=tasks,
        interrupts_truncated=len(tasks) > 20,
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
        "interrupts_observed": interrupts_observed,
        "approval_pending": approval_pending,
        "messages": {
            "scope": "checkpoint_state_not_run_delta",
            "counts": counts if isinstance(messages, list) else None,
            "truncated": isinstance(messages, list) and len(messages) > 200,
        },
        "side_effects": "unknown",
    }


_CHECKPOINT_HISTORY_FIRST_PAGE_SIZE = 1
_CHECKPOINT_HISTORY_PAGE_SIZE = 25
_CHECKPOINT_HISTORY_MAX_PAGES = 8


def _history_cursor(state):
    if not isinstance(state, dict):
        return None
    checkpoint = state.get("checkpoint")
    if isinstance(checkpoint, dict) and checkpoint:
        return checkpoint
    cp_id = state.get("checkpoint_id")
    if isinstance(cp_id, str) and cp_id:
        return {"checkpoint_id": cp_id}
    return None


async def read_checkpoint(gateway, *, actor, project_id, thread_id, run_id):
    before = None
    seen_cursors = set()
    any_records = False
    try:
        # Probe latest checkpoint first (limit=1), then paginate backward with `before` if another run wrote more recently.
        async with asyncio.timeout(8):
            for page_index in range(_CHECKPOINT_HISTORY_MAX_PAGES + 1):
                page_limit = (
                    _CHECKPOINT_HISTORY_FIRST_PAGE_SIZE
                    if page_index == 0
                    else _CHECKPOINT_HISTORY_PAGE_SIZE
                )
                payload = {
                    "limit": page_limit,
                    "metadata": {"run_id": run_id},
                }
                if before is not None:
                    payload["before"] = before
                history = await gateway.get_thread_history(
                    actor=actor,
                    project_id=project_id,
                    thread_id=thread_id,
                    payload=payload,
                )
                if not isinstance(history, list):
                    return {"availability": "unavailable", "reason": "invalid_history"}
                if not history:
                    break
                any_records = True
                for item in history:
                    if (
                        isinstance(item, dict)
                        and isinstance(item.get("metadata"), dict)
                        and item["metadata"].get("run_id") == run_id
                    ):
                        return checkpoint_summary(item, run_id)
                if len(history) < page_limit:
                    break
                cursor = _history_cursor(history[-1])
                if cursor is None:
                    break
                cursor_key = json.dumps(cursor, sort_keys=True, default=str)
                if cursor_key in seen_cursors:
                    break
                seen_cursors.add(cursor_key)
                before = cursor
    except PlatformApiError as exc:
        if exc.status_code in {401, 403}:
            raise
        return {"availability": "unavailable", "reason": "state_query_failed"}
    except TimeoutError:
        return {"availability": "unavailable", "reason": "state_query_timeout"}
    if not any_records:
        return {"availability": "empty", "reason": "not_recorded"}
    return {"availability": "unavailable", "reason": "run_mismatch"}


def _iso_time(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value if isinstance(value, str) else None


def summarize_runs(raw_runs, *, limit=20):
    items = (
        raw_runs
        if isinstance(raw_runs, list)
        else raw_runs.get("runs", raw_runs.get("items", []))
        if isinstance(raw_runs, dict)
        else []
    )
    items = [item for item in items if isinstance(item, dict)]
    ordered = sorted(
        items,
        key=lambda item: _iso_time(item.get("created_at")) or "",
        reverse=True,
    )
    truncated = len(ordered) > limit
    runs = []
    for item in ordered[:limit]:
        status = item.get("status")
        error = item.get("error")
        context = (
            ((item.get("kwargs") or {}).get("context") or {})
            if isinstance(item.get("kwargs"), dict)
            else {}
        )
        runs.append(
            {
                "run_id": identifier(item.get("run_id")),
                "status": status
                if isinstance(status, str) and status in RUN_STATUSES
                else "unknown",
                "created_at": _iso_time(item.get("created_at")),
                "updated_at": _iso_time(item.get("updated_at")),
                "error_code": error
                if isinstance(error, str) and error in ERROR_CODES
                else ("unclassified_error" if error else None),
                "configuration": {
                    key: value
                    for key, value in context.items()
                    if key in {"model_id", "access_policy", "plan_mode"}
                    and isinstance(value, (str, bool))
                },
            }
        )
    return runs, truncated


def activity_summary(state, *, limit_messages=200):
    if not isinstance(state, dict):
        return {"availability": "unavailable", "reason": "invalid_state"}
    values = state.get("values")
    raw_messages = values.get("messages") if isinstance(values, dict) else None
    if not isinstance(raw_messages, list):
        return {"availability": "empty", "reason": "no_messages"}
    messages_truncated = len(raw_messages) > limit_messages
    messages = [m for m in raw_messages[-limit_messages:] if isinstance(m, dict)]

    tool_outcomes = {}
    for msg in messages:
        kind = msg.get("type") or msg.get("role")
        if kind == "tool":
            call_id = msg.get("tool_call_id")
            if isinstance(call_id, str) and call_id:
                tool_outcomes[call_id] = (
                    "error" if msg.get("status") == "error" else "success"
                )

    turns = []
    current = None
    for msg in messages:
        kind = msg.get("type") or msg.get("role")
        if kind in {"human", "user"}:
            current = {
                "turn_index": len(turns) + 1,
                "ai_messages": 0,
                "tool_calls": [],
                "tool_calls_truncated": False,
            }
            turns.append(current)
        elif kind in {"ai", "assistant"}:
            if current is None:
                current = {
                    "turn_index": len(turns) + 1,
                    "ai_messages": 0,
                    "tool_calls": [],
                    "tool_calls_truncated": False,
                }
                turns.append(current)
            current["ai_messages"] += 1
            raw_calls = msg.get("tool_calls")
            if isinstance(raw_calls, list):
                for tc in raw_calls:
                    if not isinstance(tc, dict):
                        continue
                    if len(current["tool_calls"]) >= 50:
                        current["tool_calls_truncated"] = True
                        break
                    call_id = tc.get("id")
                    current["tool_calls"].append(
                        {
                            "tool_name": identifier(tc.get("name")) or "unknown_tool",
                            "status": tool_outcomes.get(call_id, "unknown")
                            if isinstance(call_id, str)
                            else "unknown",
                        }
                    )

    tasks = state.get("tasks") if isinstance(state.get("tasks"), list) else []
    _, interrupts_observed, approval_pending = _interrupt_flags(
        state,
        tasks_known=isinstance(state.get("tasks"), list),
        tasks=tasks,
        interrupts_truncated=len(tasks) > 20,
    )
    return {
        "availability": "available",
        "scope": "bounded_thread_state_redacted",
        "total_turns_observed": len(turns),
        "messages_truncated": messages_truncated,
        "turns": turns,
        "interrupts_observed": interrupts_observed,
        "approval_pending": approval_pending,
        "redacted_fields": ["message_content", "tool_args", "tool_output"],
    }


async def read_thread_activity_state(gateway, *, actor, project_id, thread_id):
    try:
        async with asyncio.timeout(8):
            state = await gateway.get_thread_state(
                actor=actor,
                project_id=project_id,
                thread_id=thread_id,
                params={"subgraphs": False},
            )
    except PlatformApiError as exc:
        if exc.status_code in {401, 403}:
            raise
        return {"availability": "unavailable", "reason": "state_query_failed"}
    except TimeoutError:
        return {"availability": "unavailable", "reason": "state_query_timeout"}
    return activity_summary(state)
