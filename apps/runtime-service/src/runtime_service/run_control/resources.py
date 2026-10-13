"""Record only actual owned resources; no command or path enters receipts."""

import asyncio
import logging
import os
from dataclasses import asdict
from uuid import uuid4

from langgraph.config import get_config
from psycopg.types.json import Jsonb

from runtime_service.db import connect

logger = logging.getLogger(__name__)


def _register(kind, thread, run, node_id=None, operation_id=None, workspace=None):
    resource = uuid4()
    with connect() as connection:
        connection.execute(
            "INSERT INTO runtime_run_resources(resource_id,thread_id,run_id,kind) VALUES(%s,%s,%s,%s)",
            (resource, str(thread), str(run), kind),
        )
        if node_id:
            connection.execute(
                "UPDATE runtime_run_resources SET sandbox_node_id=%s,sandbox_operation_id=%s,sandbox_binding=%s WHERE resource_id=%s",
                (
                    node_id,
                    operation_id,
                    Jsonb(asdict(workspace)) if workspace else None,
                    resource,
                ),
            )
    return resource


def _finish(resource, status):
    if resource is None:
        return
    with connect() as connection:
        connection.execute(
            "UPDATE runtime_run_resources SET status=%s,updated_at=now() WHERE resource_id=%s",
            (status, resource),
        )


async def register_resource(kind, *, node_id=None, operation_id=None, workspace=None):
    try:
        config = get_config()
    except RuntimeError:
        return None
    thread = config.get("configurable", {}).get("thread_id")
    run = config.get("metadata", {}).get("run_id") or config.get(
        "configurable", {}
    ).get("run_id")
    if not thread or not run or not os.getenv("DATABASE_URI"):
        return None
    arguments = (
        (kind, thread, run)
        if node_id is None
        else (kind, thread, run, node_id, operation_id, workspace)
    )
    task = asyncio.create_task(asyncio.to_thread(_register, *arguments))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        resource = await wait_cleanup(task)
        await finish_resource(resource, True)
        raise


async def wait_cleanup(task):
    """Repeated parent cancellation cannot abandon owned cleanup."""
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            continue
    return task.result()


async def finish_resource(resource, confirmed):
    # Cancelled parent tasks must wait for this durable cleanup receipt.
    task = asyncio.create_task(
        asyncio.to_thread(
            _finish,
            resource,
            "cleanup_confirmed" if confirmed else "cleanup_unconfirmed",
        )
    )
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        await wait_cleanup(task)
        raise


def resource_state(thread_id, targets):
    with connect() as connection:
        rows = connection.execute(
            "SELECT status FROM runtime_run_resources WHERE thread_id=%s AND run_id=ANY(%s)",
            (thread_id, targets),
        ).fetchall()
    statuses = {r["status"] for r in rows}
    if "cleanup_unconfirmed" in statuses:
        return "unconfirmed"
    if "active" in statuses:
        return "pending"
    return "confirmed" if rows else "not_required"


def reconcile_remote_resources(thread_id=None, targets=None, *, cancel=False):
    """Recover cleanup facts by the original ID, without replaying commands."""
    from runtime_service.errors import RuntimeWorkspaceError
    from runtime_service.workspace.documents import DocumentError
    from runtime_service.workspace.node_client import call
    from runtime_service.workspace.target import RemoteWorkspace

    host = os.getenv("RUNTIME_EXECUTION_HOST_ID")
    if not host:
        return
    with connect() as connection:
        rows = connection.execute(
            """SELECT r.* FROM runtime_run_resources r
            WHERE r.kind='docker_execute' AND r.status<>'cleanup_confirmed'
                AND r.sandbox_binding->>'execution_host'=%s
                AND (%s::text IS NULL OR r.thread_id=%s)
                AND (%s::text[] IS NULL OR r.run_id=ANY(%s))
            ORDER BY r.updated_at LIMIT 2""",
            (host, thread_id, thread_id, targets, targets),
        ).fetchall()
    for row in rows:
        binding = row["sandbox_binding"]
        root = RemoteWorkspace(**{**binding, "scope": tuple(binding["scope"])})
        try:
            if cancel:
                confirmed = call(
                    root, "cancel", {"resource_id": row["sandbox_operation_id"]}
                )["confirmed"]
            else:
                result = call(
                    root, "operation", {"resource_id": row["sandbox_operation_id"]}
                )
                confirmed = result["status"] == "finished" and result["result"].get(
                    "cleanup_confirmed"
                )
                if not confirmed:
                    confirmed = any(
                        item["id"] == row["sandbox_operation_id"]
                        and item["status"] == "removed"
                        for item in call(root, "discover", {})
                    )
            if confirmed:
                _finish(row["resource_id"], "cleanup_confirmed")
        except (RuntimeWorkspaceError, DocumentError, KeyError, TypeError):
            logger.warning(
                "Remote cleanup still unconfirmed resource_id=%s", row["resource_id"]
            )
        finally:
            with connect() as connection:
                connection.execute(
                    "UPDATE runtime_run_resources SET updated_at=now() WHERE resource_id=%s AND status<>'cleanup_confirmed'",
                    (row["resource_id"],),
                )


async def execute_local(execute, command, timeout=None):
    resource = await register_resource("local_execute")
    task = asyncio.create_task(asyncio.to_thread(execute, command, timeout=timeout))
    try:
        result = await asyncio.shield(task)
    except asyncio.CancelledError:
        # LocalShellBackend bounds commands to <=60s; Python threads cannot be killed.
        confirmed = False
        try:
            done, _ = await wait_cleanup(
                asyncio.create_task(asyncio.wait({task}, timeout=75))
            )
            if done:
                task.result()
                confirmed = True
            else:
                task.add_done_callback(
                    lambda finished: (
                        finished.exception() if not finished.cancelled() else None
                    )
                )
        except Exception:
            logger.warning("Local execution cleanup unconfirmed")
        await finish_resource(resource, confirmed)
        raise
    except BaseException:
        await finish_resource(resource, False)
        raise
    await finish_resource(resource, True)
    return result
