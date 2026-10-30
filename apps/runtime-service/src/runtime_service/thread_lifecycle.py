"""Application handoff for GraphHarbor's durable thread deletion tasks."""

import asyncio
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx
from psycopg.rows import dict_row

from runtime_service.background_tasks.repository import UNRESOLVED
from runtime_service.db import connect
from runtime_service.workspace.scoped import get_thread_local_workspace_root
from runtime_service.workspace.target import (
    NodeConnection,
    RemoteWorkspace,
    sandbox_target,
)


def deletion_pending(db, thread_id):
    """Share the engine thread lock with deletion admission and resource creation."""
    with db.cursor(row_factory=dict_row) as cursor:
        return _deletion_pending(cursor, thread_id)


def _deletion_pending(db, thread_id):
    # Standalone application-schema fixtures have no engine tables.
    if db.execute("SELECT to_regclass('threads') AS name").fetchone()["name"]:
        row = db.execute(
            "SELECT * FROM threads WHERE thread_id::text=%s FOR UPDATE",
            (str(thread_id),),
        ).fetchone()
        if row and row.get("deletion_requested_at"):
            return True
    if db.execute("SELECT to_regclass('thread_deletions') AS name").fetchone()["name"]:
        return (
            db.execute(
                "SELECT 1 FROM thread_deletions WHERE thread_id::text=%s",
                (str(thread_id),),
            ).fetchone()
            is not None
        )
    return False


def _pending(db, thread_id):
    return db.execute(
        f"""SELECT (
        EXISTS(SELECT 1 FROM runtime_background_tasks WHERE thread_id=%(id)s AND {UNRESOLVED})
        OR EXISTS(SELECT 1 FROM runtime_run_resources WHERE thread_id=%(id)s AND status<>'cleanup_confirmed')
        OR EXISTS(SELECT 1 FROM runtime_message_inbox WHERE thread_id=%(id)s AND status IN ('queued','claimed'))
        OR EXISTS(SELECT 1 FROM runtime_stop_requests WHERE thread_id=%(id)s
          AND (phase NOT IN ('stopped','no_active_run','rejected') OR audit_pending<>'[]'::jsonb))
        OR EXISTS(SELECT 1 FROM dear_external_tasks WHERE thread_id=%(id)s
          AND (status IN ('intent','unknown') OR lease_until>now()))) AS pending""",
        {"id": str(thread_id)},
    ).fetchone()["pending"]


def _job(db, event, *, after=False):
    row = db.execute(
        "SELECT * FROM thread_deletions WHERE thread_id::text=%s AND task_id::text=%s",
        (event["thread_id"], event["task_id"]),
    ).fetchone()
    if not row or row["state"] != ("after_delete" if after else "before_delete"):
        raise ValueError("thread_deletion_handoff_invalid")
    if row["metadata"] != event["metadata"]:
        raise ValueError("thread_deletion_scope_invalid")
    if (
        after
        and db.execute(
            "SELECT 1 FROM threads WHERE thread_id::text=%s", (event["thread_id"],)
        ).fetchone()
    ):
        raise ValueError("thread_deletion_not_committed")
    return row


def _before(event):
    from runtime_service.run_control.resources import (
        reconcile_remote_resources,
        reconcile_terminal_resources,
    )
    from runtime_service.workspace.terminal import terminals

    with connect() as db:
        _job(db, event)
        row = db.execute(
            "SELECT graph_id,metadata FROM threads WHERE thread_id::text=%s",
            (event["thread_id"],),
        ).fetchone()
        if row:
            _bind_legacy_local(db, event, row)
    # Other API processes observe the same marker in their terminal janitor.
    terminals.sweep()
    reconcile_terminal_resources(event["thread_id"])
    reconcile_remote_resources(event["thread_id"])
    with connect() as db:
        _job(db, event)
        return not _pending(db, event["thread_id"])


def _bind_legacy_local(db, event, thread):
    """Adopt only a canonical legacy path derived from persisted thread scope."""
    from runtime_service.runtime.capabilities import graph_capabilities
    from runtime_service.workspace.scoped import thread_scope_hash

    graph = thread["graph_id"]
    if not graph or not graph_capabilities(graph)["workspace"]:
        return
    existing = db.execute(
        "SELECT 1 FROM runtime_workspace_locations WHERE thread_id=%s AND graph_id=%s",
        (event["thread_id"], graph),
    ).fetchone()
    if existing:
        return
    tenant = thread["metadata"].get("tenant_id")
    project = event["metadata"].get("project_id")
    host = os.environ.get("RUNTIME_EXECUTION_HOST_ID")
    scopes = db.execute(
        """SELECT tenant_id,project_id FROM runtime_usage_runs
        WHERE thread_id=%s AND graph_id=%s
        UNION SELECT tenant_id,project_id FROM runtime_background_tasks
        WHERE thread_id=%s AND graph_id=%s""",
        (event["thread_id"], graph, event["thread_id"], graph),
    ).fetchall()
    if scopes:
        if (
            len(scopes) != 1
            or scopes[0]["project_id"] != project
            or (tenant and tenant != scopes[0]["tenant_id"])
        ):
            raise ValueError("legacy_workspace_scope_conflict")
        tenant = scopes[0]["tenant_id"]
    if not tenant or not project or not host:
        raise ValueError("legacy_workspace_scope_unconfirmed")
    # A changed remote target cannot establish where an unbound legacy workspace lived.
    if sandbox_target() != "local":
        raise ValueError("legacy_workspace_location_unconfirmed")
    scope = (tenant, project, event["thread_id"])
    root = get_thread_local_workspace_root(*scope, graph)
    if root.parent.exists() or root.parent.is_symlink():
        db.execute(
            """INSERT INTO runtime_workspace_locations
            (execution_host,tenant_id,project_id,thread_id,graph_id,target,workspace_id,storage_path)
            VALUES(%s,%s,%s,%s,%s,'local',%s,%s) ON CONFLICT DO NOTHING""",
            (host, *scope, graph, thread_scope_hash(*scope), str(root.absolute())),
        )


async def before_delete(event):
    return await asyncio.to_thread(_before, event)


def workspace_unused(root):
    """Verify process handles and mounts before cleanup can be confirmed."""
    parent = root.parent
    if not parent.exists() and not parent.is_symlink():
        return
    if any(path.is_symlink() for path in (root, parent, *parent.parents)):
        raise ValueError("workspace_cleanup_symlink")
    if not shutil.rmtree.avoids_symlink_attacks:
        raise ValueError("workspace_cleanup_unsupported")
    for directory, dirs, _ in os.walk(parent, followlinks=False):
        if os.path.ismount(directory):
            raise ValueError("workspace_cleanup_mounted")
        dirs[:] = [name for name in dirs if not Path(directory, name).is_symlink()]
    # Process handles are independent of engine Run state, including local terminals.
    result = subprocess.run(
        ["lsof", "-t", "+D", str(parent)], capture_output=True, timeout=5, check=False
    )
    if result.returncode != 1 or result.stdout.strip() or result.stderr.strip():
        raise ValueError("workspace_cleanup_in_use_or_unconfirmed")


def _remove_local(root):
    """Only a derived, unmounted, unused scope directory may be removed."""
    workspace_unused(root)
    if root.parent.exists():
        shutil.rmtree(root.parent)


def _clean_application(event):
    thread = event["thread_id"]
    with connect() as db:
        _job(db, event, after=True)
        if _pending(db, thread):
            return False
        locations = db.execute(
            "SELECT * FROM runtime_workspace_locations WHERE thread_id=%s AND status<>'purged'",
            (thread,),
        ).fetchall()
    for row in locations:
        if row["project_id"] != event["metadata"].get("project_id"):
            raise ValueError("workspace_cleanup_scope_invalid")
        scope = (row["tenant_id"], row["project_id"], thread)
        if row["target"] == "remote":
            connection = NodeConnection.load()
            if (row["execution_host"], row["node_id"]) != (
                connection.execution_host,
                connection.node_id,
            ):
                raise ValueError("workspace_cleanup_host_unavailable")
            root = RemoteWorkspace(
                scope,
                row["graph_id"],
                row["execution_host"],
                row["node_id"],
                row["workspace_id"],
            )
            candidate = root.call(
                "cleanup.mark",
                evidence={
                    "kind": "deleted_thread",
                    "verified_by": event["task_id"],
                    "confirmed_at": time.time(),
                    "thread_absent": True,
                    "pending_work_absent": True,
                },
            )
            result = root.call(
                "cleanup.apply", candidate_token=candidate["candidate_token"]
            )
            if result["status"] != "purged":
                return False
        else:
            if row["execution_host"] != os.environ.get("RUNTIME_EXECUTION_HOST_ID"):
                raise ValueError("workspace_cleanup_host_unavailable")
            root = get_thread_local_workspace_root(*scope, row["graph_id"])
            if str(root.absolute()) != row["storage_path"]:
                raise ValueError("workspace_cleanup_binding_invalid")
            _remove_local(root)
        with connect() as db:
            db.execute(
                "UPDATE runtime_workspace_locations SET status='purged' WHERE execution_host=%s AND tenant_id=%s AND project_id=%s AND thread_id=%s AND graph_id=%s",
                (row["execution_host"], *scope, row["graph_id"]),
            )
    # Preserve compact idempotency/usage facts; remove conversation and tool payloads.
    from runtime_service.background_tasks import output, repository

    with connect() as db:
        logs = db.execute(
            "SELECT * FROM runtime_background_tasks WHERE thread_id=%s AND log_reserved",
            (thread,),
        ).fetchall()
    for row in logs:
        if row["execution_host_id"] != os.environ.get("RUNTIME_EXECUTION_HOST_ID"):
            raise ValueError("background_cleanup_host_unavailable")
        output.delete_output(row)
        repository.expire_output(row)
    with connect() as db:
        db.execute("SET LOCAL lock_timeout='500ms'")
        db.execute("SET LOCAL statement_timeout='5s'")
        db.execute(
            "UPDATE runtime_message_inbox SET payload='{}'::jsonb WHERE thread_id=%s",
            (thread,),
        )
        db.execute(
            "UPDATE dear_external_tasks SET request='{}'::jsonb,result='{}'::jsonb WHERE thread_id=%s AND status='succeeded'",
            (thread,),
        )
        db.execute(
            "DELETE FROM runtime_run_resources WHERE thread_id=%s AND status='cleanup_confirmed'",
            (thread,),
        )
    return True


async def _notify_platform(event):
    source = os.environ.get("GRAPHHARBOR_TERMINAL_WEBHOOK_URL", "")
    secret = os.environ.get("GRAPHHARBOR_TERMINAL_WEBHOOK_SECRET", "")
    key_id = os.environ.get("GRAPHHARBOR_TERMINAL_WEBHOOK_KEY_ID", "runtime-v1")
    parts = urlsplit(source)
    if (
        parts.scheme not in {"http", "https"}
        or not parts.netloc
        or not secret
        or parts.username
        or parts.query
        or parts.fragment
    ):
        raise ValueError("thread_deletion_callback_unconfigured")
    path = "/api/runtime/internal/thread-deletion"
    url = urlunsplit((parts.scheme, parts.netloc, path, "", ""))
    body = json.dumps(
        {key: event[key] for key in ("task_id", "thread_id")}
        | {
            "project_id": event["metadata"].get("project_id"),
        },
        separators=(",", ":"),
    ).encode()
    stamp = str(int(time.time()))
    signature = hmac.new(
        secret.encode(),
        f"{key_id}\n{stamp}\nPOST\n{path}\n".encode() + body,
        hashlib.sha256,
    ).hexdigest()
    async with httpx.AsyncClient(
        timeout=5, follow_redirects=False, trust_env=False
    ) as client:
        response = await client.post(
            url,
            content=body,
            headers={
                "content-type": "application/json",
                "x-run-completion-key-id": key_id,
                "x-run-completion-timestamp": stamp,
                "x-run-completion-signature": "sha256=" + signature,
                "x-run-completion-event-id": event["task_id"],
            },
        )
        response.raise_for_status()


async def after_delete(event):
    if not await asyncio.to_thread(_clean_application, event):
        return False
    await _notify_platform(event)
    return True
