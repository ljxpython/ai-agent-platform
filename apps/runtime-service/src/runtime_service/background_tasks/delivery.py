"""One stable completion event through Platform; lost ACKs reuse its identity."""

import hashlib
import hmac
import json
import os
import time
from datetime import UTC, datetime

import httpx

from runtime_service.auth.acl_client import post_acl
from runtime_service.background_tasks import repository
from runtime_service.runtime.errors import RuntimeAuthError


async def callback(operation, payload):
    endpoint = os.getenv("PLATFORM_THREAD_AUTHORIZATION_URL", "")
    secret = os.getenv("PLATFORM_RUNTIME_DELEGATION_SECRET", "")
    if not endpoint.endswith("/thread-authorization") or not secret:
        raise RuntimeAuthError("background_task_authorization_unavailable")
    stamp = str(int(time.time()))
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    signature = hmac.new(
        secret.encode(), f"{stamp}\n{operation}\n{canonical}".encode(), hashlib.sha256
    ).hexdigest()
    response = await post_acl(
        endpoint.removesuffix("/thread-authorization") + "/" + operation,
        payload,
        {"x-runtime-acl-timestamp": stamp, "x-runtime-acl-signature": signature},
    )
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict):
        raise RuntimeAuthError("background_task_authorization_unavailable")
    return value


def event_payload(row):
    return {
        "version": 1,
        **{
            k: row[k]
            for k in (
                "tenant_id",
                "project_id",
                "owner_id",
                "credential_id",
                "graph_id",
                "thread_id",
                "origin_run_id",
                "status",
                "exit_code",
            )
        },
        "task_id": str(row["task_id"]),
        "event_id": str(row["event_id"]),
    }


async def deliver_completion(row):
    import asyncio

    from runtime_service.background_tasks.service import enabled

    previous = row["delivery_state"]
    uncertain = previous in {"unknown", "dispatching"}
    stopped_inflight = bool(row.get("stop_id") and row.get("delivery_inflight"))
    uncertain = uncertain or stopped_inflight
    expired = datetime.now(UTC) >= row["notification_deadline_at"]
    if not uncertain and (expired or row["delivery_attempts"] >= 5):
        return await asyncio.to_thread(
            repository.finish_delivery,
            row,
            "expired",
            reason="background_task_delivery_expired",
        )
    if not uncertain and not enabled():
        return await asyncio.to_thread(
            repository.finish_delivery,
            row,
            "blocked",
            reason="background_task_disabled",
        )
    intent = (
        row
        if stopped_inflight
        else await asyncio.to_thread(repository.delivery_intent, row)
    )
    if intent is None:
        return None
    try:
        result = await callback(
            "background-task-delivery",
            {
                **event_payload(row),
                "reconcile_only": uncertain,
            },
        )
        state = result.get("state")
        run_id = result.get("run_id")
        if state not in {
            "accepted",
            "pending",
            "blocked",
            "suppressed",
            "unknown",
            "expired",
        } or (state == "accepted" and not isinstance(run_id, str)):
            raise ValueError("invalid_background_delivery")
        return await asyncio.to_thread(
            repository.finish_delivery,
            row,
            state,
            run_id=run_id,
            reason=result.get("reason_code"),
        )
    except (httpx.HTTPError, RuntimeAuthError, ValueError):
        return await asyncio.to_thread(
            repository.finish_delivery,
            row,
            "unknown",
            reason="background_task_delivery_unavailable",
            attempted=True,
        )
