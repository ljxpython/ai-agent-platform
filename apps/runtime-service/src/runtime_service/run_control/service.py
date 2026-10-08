"""Idempotent stop submission and restart-safe background reconciliation."""

import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress

import httpx
import psycopg
from langgraph_sdk.auth import exceptions

from runtime_service.messaging import MessageInbox
from runtime_service.messaging.reconcile import reconcile_run
from runtime_service.run_control import repository
from runtime_service.run_control.authorization import native_headers, stop_callback
from runtime_service.run_control.report import build_report

logger = logging.getLogger(__name__)


def engine_url():
    return (
        os.getenv("RUNTIME_SELF_URL")
        or os.getenv("RUNTIME_AGENT_SERVER_URL")
        or "http://127.0.0.1:8123"
    ).rstrip("/")


async def engine_receipt(client, row, *, create=False):
    path = f"/threads/{row['thread_id']}/runs"
    stop_id = str(row["stop_id"])
    if create:
        response = await client.post(
            path + "/cancel-active",
            json={
                "cancellation_id": stop_id,
                "action": "interrupt",
                "reconcile_run_ids": row["inbox_run_ids"],
            },
            headers={**native_headers(row, "run-cancel"), "Idempotency-Key": stop_id},
        )
    else:
        response = await client.get(
            path + "/cancellations/" + stop_id,
            headers=native_headers(row, "run-cancellation-read"),
        )
    if not create and response.status_code == 404:
        return None
    response.raise_for_status()
    receipt = response.json()
    if (
        receipt["cancellation_id"] != stop_id
        or receipt["thread_id"] != row["thread_id"]
    ):
        raise ValueError("invalid_cancellation_receipt")
    while receipt.get("next_offset") is not None:
        response = await client.get(
            path + "/cancellations/" + stop_id,
            params={"offset": receipt["next_offset"]},
            headers=native_headers(row, "run-cancellation-read"),
        )
        response.raise_for_status()
        page = response.json()
        if (
            page["cancellation_id"] != stop_id
            or page["thread_id"] != row["thread_id"]
            or page["target_count"] != receipt["target_count"]
        ):
            raise ValueError("invalid_cancellation_receipt")
        receipt["targets"].extend(page["targets"])
        receipt["next_offset"] = page["next_offset"]
        receipt["execution_stopped"] &= page["execution_stopped"]
        receipt["confirmation_unavailable"] = receipt.get(
            "confirmation_unavailable", False
        ) or page.get("confirmation_unavailable", False)
    if len(receipt["targets"]) != receipt["target_count"]:
        raise ValueError("invalid_cancellation_receipt")
    return receipt


async def _audit_phase(row):
    for phase in list(row["audit_pending"]):
        try:
            await stop_callback({**row, "phase": phase})
        except (httpx.HTTPError, ValueError, OSError) as exc:
            logger.warning(
                "Stop audit pending stop_id=%s kind=%s",
                row["stop_id"],
                type(exc).__name__,
            )
            return
        row["audit_pending"].remove(phase)


async def _settle_inbox(row, saver):
    inbox = MessageInbox(os.environ["DATABASE_URI"])
    runs = repository.stop_run_ids(row["engine_receipt"])
    stopped = {target["run_id"] for target in row["engine_receipt"]["targets"]}
    previous = {
        target["run_id"]: target
        for target in row["engine_receipt"].get("reconcile_targets", [])
    }
    start = row["reconciled_count"]
    for run_id in runs[start : start + 10]:
        await reconcile_run(
            inbox,
            saver,
            thread_id=row["thread_id"],
            run_id=run_id,
            terminal_reason="user_stopped"
            if run_id in stopped
            else (
                "run_cancelled"
                if previous.get(run_id, {}).get("status") == "interrupted"
                else "run_ended"
            ),
        )
        row["reconciled_count"] += 1
    return row["reconciled_count"] == len(runs)


async def _advance_claim(row):
    from langgraph_runtime_pg.checkpoint import get_checkpointer

    try:
        await _audit_phase(row)
        if row["phase"] in {"stopped", "no_active_run", "rejected"}:
            return await asyncio.to_thread(
                repository.save_stop, row, phase=row["phase"], reason=row["reason_code"]
            )
        async with httpx.AsyncClient(
            base_url=engine_url(), timeout=10, trust_env=False
        ) as client:
            current = await engine_receipt(client, row)
            if current is None:
                if row["engine_receipt"] is not None:
                    raise ValueError("cancellation_receipt_unavailable")
                if not await stop_callback(row, authorize=True):
                    return await _save_phase(row, "rejected", reason="stop_denied")
                current = await engine_receipt(client, row, create=True)
        row["engine_receipt"] = current
        # Commit the fixed boundary before reading checkpoints or releasing the barrier.
        row = await asyncio.to_thread(
            repository.save_stop, row, phase="stopping", receipt=current, release=False
        )
        if row is None:
            return None
        await _audit_phase(row)
        if not current["execution_stopped"]:
            unavailable = current.get("confirmation_unavailable", False)
            return await _save_phase(
                row,
                "confirmation_unavailable" if unavailable else "stopping",
                reason="stop_confirmation_unavailable" if unavailable else None,
            )
        saver = get_checkpointer()
        if not await _settle_inbox(row, saver):
            return await asyncio.to_thread(repository.save_stop, row, phase="stopping")
        report = await build_report(row, saver)
        phase = "stopped" if current["target_count"] else "no_active_run"
        if report["resource_cleanup"] in {"pending", "unconfirmed"}:
            phase = "confirmation_unavailable"
        return await _save_phase(
            row,
            phase,
            report=report,
            reason="resource_cleanup_unconfirmed"
            if phase == "confirmation_unavailable"
            else None,
        )
    except exceptions.HTTPException as exc:
        denied = row["engine_receipt"] is None and exc.status_code == 403
        return await _save_phase(
            row,
            "rejected" if denied else "confirmation_unavailable",
            reason="stop_denied" if denied else "stop_confirmation_unavailable",
        )
    except (httpx.HTTPError, ValueError, OSError, psycopg.Error, TimeoutError) as exc:
        logger.warning(
            "Stop reconciliation unavailable stop_id=%s kind=%s status=%s",
            row["stop_id"],
            type(exc).__name__,
            exc.response.status_code
            if isinstance(exc, httpx.HTTPStatusError)
            else None,
        )
        return await _save_phase(
            row, "confirmation_unavailable", reason="stop_confirmation_unavailable"
        )


async def _save_phase(row, phase, **kwargs):
    saved = await asyncio.to_thread(
        repository.save_stop, row, phase=phase, receipt=row["engine_receipt"], **kwargs
    )
    return saved


async def _renew_lease(row, work):
    while not work.done():
        await asyncio.sleep(10)
        if not await asyncio.to_thread(repository.renew_stop, row):
            work.cancel()
            return


async def advance_stop(stop_id=None):
    row = await asyncio.to_thread(repository.claim_stop, stop_id)
    if row is None:
        return None
    work = asyncio.create_task(_advance_claim(row))
    heartbeat = asyncio.create_task(_renew_lease(row, work))
    try:
        return await work
    finally:
        heartbeat.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat


async def _reconcile_loop():
    while True:
        try:
            await advance_stop()
        except Exception as exc:
            logger.warning("Stop recovery unavailable kind=%s", type(exc).__name__)
        await asyncio.sleep(1)


@asynccontextmanager
async def run_control_lifespan():
    if not os.getenv("DATABASE_URI"):
        yield
        return
    from runtime_service.db import upgrade

    await asyncio.to_thread(upgrade)
    task = asyncio.create_task(_reconcile_loop(), name="runtime-stop-reconciler")
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
