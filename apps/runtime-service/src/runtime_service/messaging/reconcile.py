"""Reconcile business receipts using committed checkpoint history only."""

from __future__ import annotations

import asyncio
from typing import Any

from runtime_service.messaging.inbox import MessageInbox


async def reconcile_run(
    inbox: MessageInbox,
    saver: Any,
    *,
    thread_id: str,
    run_id: str,
    terminal_reason: str | None = None,
) -> int:
    """Read every committed root snapshot for the target run before closing it.

    Never infer non-delivery from a missing/latest checkpoint or pending writes.
    Errors propagate, leaving queue records retryable instead of falsely closed.
    """
    count = 0
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    async for snapshot in saver.alist(config, filter={"run_id": run_id}):
        if snapshot.metadata.get("source") != "loop":
            continue
        checkpoint = snapshot.config["configurable"]
        if checkpoint.get("checkpoint_ns", ""):
            continue
        claim = snapshot.checkpoint.get("channel_values", {}).get(
            "runtime_message_claim", {}
        )
        if claim.get("run_id") != run_id:
            continue
        count += await asyncio.to_thread(
            inbox.reconcile_checkpoint,
            thread_id=thread_id,
            target_run_id=run_id,
            checkpoint_id=checkpoint["checkpoint_id"],
            message_ids=claim.get("message_ids", []),
        )
    if terminal_reason is not None:
        await asyncio.to_thread(
            inbox.mark_run_not_consumed,
            thread_id=thread_id,
            target_run_id=run_id,
            reason=terminal_reason,
        )
    return count
