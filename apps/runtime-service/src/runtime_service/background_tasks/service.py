"""No-model reconciliation of owned containers, source Runs and completion intents."""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime

import httpx
import psycopg
from langgraph_sdk.client import LangGraphClient

from runtime_service.background_tasks import repository
from runtime_service.background_tasks.capabilities import query_enabled
from runtime_service.background_tasks.output import (
    check_space,
    delete_output,
    directory,
)
from runtime_service.run_control.authorization import native_headers
from runtime_service.run_control.resources import wait_cleanup
from runtime_service.run_control.service import engine_url
from runtime_service.runtime.errors import (
    BackgroundTaskNotStarted,
    RuntimeWorkspaceError,
)
from runtime_service.workspace.background import (
    create_task_container,
    host_id,
    inspect_task_container,
    read_task_output,
    read_task_receipt,
    remove_task_container,
    start_task_container,
    stop_task_container,
)
from runtime_service.workspace.execution import runtime_backend

logger = logging.getLogger(__name__)


def enabled():
    return os.getenv("RUNTIME_BACKGROUND_TASKS_ENABLED") == "1"


def validate_input(command, timeout):
    if not isinstance(command, str) or not command.strip() or len(command) > 32768:
        raise ValueError("command must be non-empty and at most 32768 characters")
    if type(timeout) is not int or not 1 <= timeout <= 3600:
        raise ValueError("timeout must be between 1 and 3600 seconds")


async def start_task(identity, binding, command, timeout=900):
    validate_input(command, timeout)
    if not query_enabled():
        raise RuntimeWorkspaceError("background_task_not_supported")
    existing = await asyncio.to_thread(repository.read_submission, identity)
    if existing is None:
        if runtime_backend() != "docker":
            raise BackgroundTaskNotStarted("background_task_not_supported")
        if not enabled():
            raise BackgroundTaskNotStarted("background_task_disabled")
        try:
            host = host_id()
        except RuntimeWorkspaceError as exc:
            raise BackgroundTaskNotStarted(exc.code) from exc
    else:
        # The execution host is an immutable receipt fact, not today's start config.
        host = existing["execution_host_id"]
    bound = repository.digest(
        [
            str(binding.workspace),
            binding.image,
            str(binding.skills),
            binding.protected,
            binding.scope,
            binding.graph_id,
            host,
        ]
    )
    request_digest = repository.digest([command, timeout, bound])
    if existing is not None:
        if (
            existing["binding_digest"] != bound
            or existing["request_digest"] != request_digest
        ):
            raise RuntimeWorkspaceError("background_task_idempotency_conflict")
        return existing

    async def reserve():
        await asyncio.to_thread(check_space)
        return await asyncio.to_thread(
            repository.reserve_task, identity, bound, request_digest, host, timeout
        )

    try:
        row, fresh = await reserve()
    except RuntimeWorkspaceError as exc:
        if exc.code != "background_task_log_capacity_reached":
            raise
        await expire_logs(capacity=True)
        row, fresh = await reserve()
    if not fresh:
        return row

    async def submit():
        try:
            state = await create_task_container(row, binding, command, timeout)
            row["container_id"] = state["id"]
            state = await start_task_container(row)
            return await _observe(row, state)
        except RuntimeWorkspaceError:
            return await asyncio.to_thread(
                repository.save,
                row,
                status="unknown",
                cleanup="unconfirmed",
                reason="background_task_control_unavailable",
            )

    work = asyncio.create_task(submit())
    try:
        saved = await asyncio.shield(work)
    except asyncio.CancelledError:
        await wait_cleanup(work)
        await wait_cleanup(
            asyncio.create_task(
                asyncio.to_thread(repository.request_source_cancel, row)
            )
        )
        raise
    return saved or row


def _native_row(row):
    return {
        "stop_id": row["task_id"],
        "auth_facts": {
            "identity": row["owner_id"],
            "tenant_id": row["tenant_id"],
            "project_id": row["project_id"],
            "role": "member",
            "runtime_credential_id": row["credential_id"],
            "runtime_scope": {
                "tenant_id": row["tenant_id"],
                "project_id": row["project_id"],
                "thread_id": row["thread_id"],
                "assistant_id": row["graph_id"],
            },
        },
    }


async def source_failed(row):
    async with httpx.AsyncClient(
        base_url=engine_url(), timeout=5, trust_env=False
    ) as client:
        response = await client.get(
            f"/threads/{row['thread_id']}/runs/{row['origin_run_id']}",
            headers=native_headers(_native_row(row), "read"),
        )
    if response.status_code in {403, 404}:
        return True
    response.raise_for_status()
    value = response.json()
    if value.get("status") in {"error", "timeout"}:
        return True
    if value.get("status") != "interrupted":
        return False
    # GraphHarbor persists lifecycle replay; GET status alone cannot distinguish HITL.
    async with httpx.AsyncClient(
        base_url=engine_url(),
        headers=native_headers(_native_row(row), "read"),
        timeout=5,
        trust_env=False,
    ) as transport:
        client = LangGraphClient(transport)
        async with asyncio.timeout(5):
            count, size = 0, 0
            async for part in client.runs.join_stream(
                row["thread_id"],
                row["origin_run_id"],
                stream_mode="lifecycle",
                last_event_id="0",
            ):
                count += 1
                size += len(json.dumps(part.data).encode())
                if count > 256 or size > 2 * 1024 * 1024:
                    raise ValueError("background_source_replay_limit")
                data = part.data
                if isinstance(data, dict) and data.get("method") == "lifecycle":
                    data = data.get("params", {}).get("data", {})
                if isinstance(data, dict) and data.get("status") == "interrupted":
                    if data.get("reason") == "hitl_interrupt":
                        return False
                    if data.get("reason") in {"cancel_requested", "rollback"}:
                        return True
    raise ValueError("background_source_reason_unavailable")


async def _observe(row, state, *, deadline=False):
    if state is None:
        if row["status"] in repository.TERMINAL:
            status = row["status"]
        elif row["cancel_requested_at"]:
            status = "cancelled"
        else:
            # A missing container may have executed and been removed externally.
            status = "unknown"
        return await asyncio.to_thread(
            repository.save,
            row,
            status=status,
            cleanup="unconfirmed"
            if status == "unknown"
            else "confirmed"
            if row.get("container_id")
            else "not_required",
            reason="background_task_resource_missing" if status == "unknown" else None,
        )
    output = await read_task_output(row)
    if state["Running"]:
        return await asyncio.to_thread(
            repository.save,
            row,
            status="running",
            cleanup="pending",
            state=state,
            output=output,
        )
    if state["Status"] == "created":
        status = "cancelled" if row["cancel_requested_at"] else "failed"
        reason = (
            None if row["cancel_requested_at"] else "background_task_start_unconfirmed"
        )
    elif state["Status"] in {"exited", "dead"}:
        code = state["ExitCode"]
        receipt = await read_task_receipt({**row, "container_id": state["id"]})
        if row["cancel_requested_at"]:
            status, reason = "cancelled", None
        elif deadline or receipt and receipt["outcome"] == code == 20:
            status, reason = "timed_out", "background_task_deadline_exceeded"
        elif receipt and receipt["outcome"] == code == 0 and not state.get("OOMKilled"):
            status, reason = "succeeded", None
        else:
            status, reason = (
                "failed",
                "background_task_oom"
                if state.get("OOMKilled")
                else "background_task_command_failed",
            )
        state = {**state, "ExitCode": receipt["exit_code"] if receipt else None}
    else:
        return await asyncio.to_thread(
            repository.save,
            row,
            status="unknown",
            cleanup="unconfirmed",
            reason="background_task_control_unavailable",
        )
    # Persist the final snapshot before Docker log storage is removed.
    saved = await asyncio.to_thread(
        repository.save,
        row,
        status=status,
        cleanup="pending",
        state=state,
        output=output,
        reason=reason,
        delay=0,
    )
    return saved


async def _reconcile(row):
    from runtime_service.background_tasks.delivery import deliver_completion

    try:
        if (
            row["stop_id"]
            and row["delivery_run_id"]
            and not row["delivery_cancel_confirmed"]
        ):
            await cancel_completion_run(row)
        if row["cleanup_state"] in {"pending", "unconfirmed"}:
            if not row["cancel_requested_at"]:
                try:
                    if await source_failed(row):
                        current = await asyncio.to_thread(
                            repository.request_source_cancel, row
                        )
                        row.update(
                            cancel_requested_at=current["cancel_requested_at"],
                            delivery_state=current["delivery_state"],
                        )
                except (httpx.HTTPError, ValueError, TimeoutError):
                    logger.warning(
                        "Background source unavailable task_id=%s", row["task_id"]
                    )
            state = await inspect_task_container(row)
            deadline = (
                datetime.now(UTC) >= row["deadline_at"]
                and state is not None
                and state["Running"]
            )
            if row["cancel_requested_at"] or deadline:
                state = await stop_task_container(row)
            if (
                state is not None
                and not state["Running"]
                and row["status"] in repository.TERMINAL
            ):
                removed = await remove_task_container(row)
                return await asyncio.to_thread(
                    repository.save,
                    row,
                    status=row["status"],
                    cleanup="confirmed" if removed else "unconfirmed",
                    state=state,
                    reason=row["reason_code"],
                )
            return await _observe(row, state, deadline=deadline)
        uncertain = row["delivery_state"] in {"unknown", "dispatching"} or row.get(
            "delivery_inflight"
        )
        if not row["stop_id"] and not uncertain and await source_failed(row):
            await asyncio.to_thread(repository.request_source_cancel, row)
            return await asyncio.to_thread(
                repository.finish_delivery,
                row,
                "suppressed",
                reason="background_task_denied",
            )
        await deliver_completion(row)
    except (
        RuntimeWorkspaceError,
        OSError,
        psycopg.Error,
        httpx.HTTPError,
        ValueError,
        TimeoutError,
    ) as exc:
        logger.warning(
            "Background reconciliation unavailable task_id=%s kind=%s",
            row["task_id"],
            type(exc).__name__,
        )


async def cancel_completion_run(row):
    path = f"/threads/{row['thread_id']}/runs/{row['delivery_run_id']}"
    async with httpx.AsyncClient(
        base_url=engine_url(), timeout=5, trust_env=False
    ) as client:
        policy = "background-control-v1:" + str(row["task_id"])
        response = await client.get(
            path,
            headers=native_headers(_native_row(row), "read", policy_version=policy),
        )
        response.raise_for_status()
        if response.json().get("status") in {"pending", "running"}:
            response = await client.post(
                path + "/cancel",
                params={"action": "interrupt"},
                headers=native_headers(
                    _native_row(row), "run-cancel", policy_version=policy
                ),
            )
            response.raise_for_status()
            response = await client.get(
                path,
                headers=native_headers(_native_row(row), "read", policy_version=policy),
            )
            response.raise_for_status()
        if response.json().get("status") in {
            "success",
            "error",
            "timeout",
            "interrupted",
        }:
            await asyncio.to_thread(repository.confirm_delivery_cancel, row)


async def reconcile_due(task_id=None):
    row = await asyncio.to_thread(repository.claim_due, host_id(), task_id)
    if row is None:
        return None
    work = asyncio.create_task(_reconcile(row))

    async def heartbeat():
        while not work.done():
            await asyncio.sleep(10)
            if not await asyncio.to_thread(repository.renew, row):
                work.cancel()
                return

    renewal = asyncio.create_task(heartbeat())
    try:
        await work
        return row
    finally:
        renewal.cancel()
        with suppress(asyncio.CancelledError):
            await renewal


async def cancel_task(scope, task_id):
    return await asyncio.to_thread(repository.request_cancel, scope, task_id)


async def expire_logs(*, capacity=False):
    for row in await asyncio.to_thread(
        repository.logs_to_expire, host_id(), capacity=capacity
    ):
        await asyncio.to_thread(delete_output, row)
        await asyncio.to_thread(repository.expire_output, row)


async def _loop():
    while True:
        try:
            for _ in range(20):
                if await reconcile_due() is None:
                    break
            await expire_logs()
        except Exception as exc:
            logger.warning(
                "Background recovery unavailable kind=%s", type(exc).__name__
            )
        await asyncio.sleep(1)


@asynccontextmanager
async def background_tasks_lifespan():
    if not os.getenv("DATABASE_URI") or not os.getenv("RUNTIME_EXECUTION_HOST_ID"):
        if enabled() and runtime_backend() == "docker":
            raise RuntimeWorkspaceError("background_task_not_supported")
        yield
        return
    host_id()

    def validate_storage():
        with directory():
            pass

    await asyncio.to_thread(validate_storage)
    work = asyncio.create_task(_loop(), name="runtime-background-reconciler")
    try:
        yield
    finally:
        work.cancel()
        with suppress(asyncio.CancelledError):
            await work
