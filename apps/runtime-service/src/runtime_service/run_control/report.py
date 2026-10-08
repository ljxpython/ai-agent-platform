"""Bounded evidence from fixed Run checkpoints; never invoke a model or graph."""

import asyncio
import json
import re

from runtime_service.run_control.repository import inbox_counts, stop_run_ids
from runtime_service.run_control.resources import resource_state


def safe_label(value):
    if not isinstance(value, str):
        return None
    if re.search(
        r"(?i)(bearer\s|sk-[a-z0-9]|api[_-]?key|password|authorization|secret|token\s*[=:]|eyJ[a-z0-9_-]+\.[a-z0-9_-]+\.[a-z0-9_-]+|(?<![\w/])/(?!workspace(?:/|$))\S+|[A-Z]:[\\/]|https?://)",
        value,
    ):
        return "[redacted]"
    return value[:256]


def _identifier(value):
    return (
        value
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value)
        else None
    )


def _message_field(message, name):
    return (
        message.get(name) if isinstance(message, dict) else getattr(message, name, None)
    )


def _artifact(message, run_id):
    value = _message_field(message, "artifact") or _message_field(message, "content")
    if isinstance(value, str) and len(value) <= 4096:
        try:
            value = json.loads(value)
        except ValueError:
            return None
    if not isinstance(value, dict) or value.get("version") != 1:
        return None
    digest = value.get("sha256")
    path = value.get("path")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        return None
    if not isinstance(path, str) or not re.fullmatch(
        r"/workspace/outputs/" + digest + r"\.[a-z0-9]{1,8}", path
    ):
        return None
    return {
        "artifact_id": digest,
        "path": path,
        "source_run_id": run_id,
        "source_message_id": _identifier(_message_field(message, "id")),
    }


async def _run_evidence(saver, thread, run):
    config = {"configurable": {"thread_id": thread, "checkpoint_ns": ""}}
    inherited = set()
    async for first in saver.alist(
        config, filter={"run_id": run, "source": "input"}, limit=1
    ):
        inherited = {
            _message_field(m, "id")
            for m in first.checkpoint.get("channel_values", {}).get("messages", [])
        }
    async for snapshot in saver.alist(
        config, filter={"run_id": run, "source": "loop"}, limit=1
    ):
        values = snapshot.checkpoint.get("channel_values", {})
        checkpoint = {
            "run_id": run,
            "checkpoint_id": snapshot.config["configurable"]["checkpoint_id"],
            "checkpoint_at": snapshot.checkpoint.get("ts"),
        }
        progress, artifacts = [], []
        todos = values.get("todos") if isinstance(values.get("todos"), list) else []
        for todo in todos[:21]:
            if isinstance(todo, dict) and todo.get("status") in {
                "pending",
                "in_progress",
                "completed",
            }:
                label = safe_label(todo.get("content"))
                if label:
                    progress.append(
                        {
                            "kind": "saved_plan",
                            "label": label,
                            "observed_status": todo["status"],
                            "source_run_id": run,
                            "source_message_id": None,
                        }
                    )
        messages = (
            values.get("messages") if isinstance(values.get("messages"), list) else []
        )
        external_effect_unknown = any(
            _message_field(message, "id") not in inherited
            and _message_field(message, "tool_calls")
            for message in messages[-100:]
        )
        for message in messages[-100:]:
            message_id = _message_field(message, "id")
            if (
                not message_id
                or message_id in inherited
                or _message_field(message, "type") not in {"tool", "ToolMessage"}
            ):
                continue
            name = _identifier(_message_field(message, "name"))
            if name:
                progress.append(
                    {
                        "kind": "tool_receipt",
                        "label": name,
                        "observed_status": "recorded",
                        "source_run_id": run,
                        "source_message_id": _identifier(message_id),
                    }
                )
            artifact = _artifact(message, run)
            if artifact:
                artifacts.append(artifact)
        return (
            checkpoint,
            progress,
            artifacts,
            len(todos) > 20 or len(messages) > 100,
            external_effect_unknown,
        )
    return None, [], [], False, False


async def build_report(row, saver):
    receipt = row["engine_receipt"]
    targets = stop_run_ids(receipt)
    progress, checkpoints, uncertainties, artifacts = [], [], [], []
    truncated = len(targets) > 20
    external_effect_unknown = False
    # Fetch one latest committed root checkpoint per fixed Run, never latest Thread state.
    for run in targets[:20]:
        checkpoint, items, refs, cut, effect_unknown = await _run_evidence(
            saver, row["thread_id"], run
        )
        if checkpoint:
            checkpoints.append(checkpoint)
        progress.extend(items)
        artifacts.extend(refs)
        truncated |= cut
        external_effect_unknown |= effect_unknown
    if not checkpoints:
        uncertainties.append("checkpoint_unavailable")
    if not progress:
        uncertainties.append("progress_unavailable")
    cleanup = await asyncio.to_thread(resource_state, row["thread_id"], targets)
    if cleanup in {"pending", "unconfirmed"}:
        uncertainties.append("resource_cleanup_unconfirmed")
    # Tool receipts prove only that a result was saved, never remote rollback.
    if external_effect_unknown or any(p["kind"] == "tool_receipt" for p in progress):
        uncertainties.append("external_effect_unknown")
    plans = [p for p in progress if p["kind"] == "saved_plan"]
    tools = [p for p in progress if p["kind"] == "tool_receipt"]
    truncated |= len(plans) > 20 or len(tools) > 10 or len(artifacts) > 20
    latest = max(checkpoints, key=lambda cp: cp["checkpoint_at"] or "", default={})
    return {
        "version": 1,
        "source": "checkpoint_and_receipts",
        "checkpoint_id": latest.get("checkpoint_id"),
        "checkpoint_at": latest.get("checkpoint_at"),
        "checkpoints": checkpoints[:20],
        "progress": plans[:20] + tools[:10],
        "artifacts": artifacts[:20],
        "uncertainties": uncertainties,
        "truncated": truncated,
        "resource_cleanup": cleanup,
        "queue": {
            "pending_cancelled_count": receipt["pending_cancelled_count"],
            **(await asyncio.to_thread(inbox_counts, row["thread_id"], targets)),
        },
    }


def stop_view(row):
    receipt, report = row["engine_receipt"], row["report"]
    return {
        "version": 1,
        "stop_id": str(row["stop_id"]),
        "thread_id": row["thread_id"],
        "phase": row["phase"],
        "requested_at": row["requested_at"].isoformat(),
        "accepted_at": row["accepted_at"].isoformat() if row["accepted_at"] else None,
        "confirmed_at": row["confirmed_at"].isoformat()
        if row["confirmed_at"]
        else None,
        "target_count": receipt["target_count"] if receipt else None,
        "execution_stopped": receipt["execution_stopped"] if receipt else None,
        "resource_cleanup": report["resource_cleanup"] if report else "pending",
        "has_pending_interrupts": receipt["has_pending_interrupts"]
        if receipt
        else None,
        "queue": report["queue"]
        if report
        else {
            "pending_cancelled_count": receipt["pending_cancelled_count"]
            if receipt
            else None,
            "inbox_consumed_count": None,
            "inbox_not_consumed_count": None,
        },
        "report": {
            k: v for k, v in report.items() if k not in {"resource_cleanup", "queue"}
        }
        if report
        else None,
        "reason_code": row["reason_code"],
    }
