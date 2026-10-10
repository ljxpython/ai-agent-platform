"""Public v1 projections contain no command, credential, path or control handle."""

import base64
import json

from runtime_service.background_tasks.repository import TERMINAL


def task_view(row, actions=("read", "logs", "cancel")):
    return {
        "version": 1,
        "task_id": str(row["task_id"]),
        "thread_id": row["thread_id"],
        "graph_id": row["graph_id"],
        "origin_run_id": row["origin_run_id"],
        **{
            key: row[key]
            for key in (
                "status",
                "reason_code",
                "exit_code",
                "created_at",
                "started_at",
                "finished_at",
                "deadline_at",
                "updated_at",
                "cleanup_state",
            )
        },
        "output": {
            "available": row["output_available"],
            "retained_bytes": row["log_bytes"],
            "omitted_bytes": row["omitted_bytes"],
            "truncated": row["output_truncated"],
            "updated_at": row["log_updated_at"],
        },
        "delivery": {
            "state": row["delivery_state"],
            "event_id": str(row["event_id"])
            if row["delivery_state"] != "not_ready"
            else None,
            "run_id": row["delivery_run_id"],
            "reason_code": row["delivery_reason"],
        },
        "allowed_actions": [
            a
            for a in actions
            if a != "cancel"
            or row["status"] not in TERMINAL
            or row["cleanup_state"] in {"pending", "unconfirmed"}
        ],
    }


def list_view(scope, result, limit, actions=("read", "logs", "cancel")):
    rows, unresolved, latest = result
    cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        cursor = (
            base64.urlsafe_b64encode(
                json.dumps(
                    [last["created_at"].isoformat(), str(last["task_id"])]
                ).encode()
            )
            .decode()
            .rstrip("=")
        )
    return {
        "version": 1,
        "thread_id": scope["thread_id"],
        "items": [task_view(row, actions) for row in rows[:limit]],
        "next_cursor": cursor,
        "has_unresolved": unresolved,
        "latest_delivery_run_id": latest,
    }


def output_view(row, text):
    return {
        "version": 1,
        "task_id": str(row["task_id"]),
        "thread_id": row["thread_id"],
        "available": text is not None,
        "text": text or "",
        "retained_bytes": row["log_bytes"],
        "omitted_bytes": row["omitted_bytes"],
        "truncated": row["output_truncated"]
        or text is not None
        and len(text.encode()) < row["log_bytes"],
        "updated_at": row["log_updated_at"],
    }
