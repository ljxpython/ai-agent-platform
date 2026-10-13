"""One exact remote workspace, with live Runtime facts and durable tombstones."""

import time

from runtime_service.background_tasks.repository import UNRESOLVED
from runtime_service.db import connect
from runtime_service.workspace.documents import DocumentError
from runtime_service.workspace.scoped import thread_scope_hash
from runtime_service.workspace.target import NodeConnection, RemoteWorkspace


def pending_facts(db, thread):
    return db.execute(
        f"""SELECT
        EXISTS(SELECT 1 FROM threads WHERE thread_id::text=%(thread)s) AS retained,
        (EXISTS(SELECT 1 FROM runs WHERE thread_id::text=%(thread)s
            AND status NOT IN ('success','error','timeout','cancelled'))
        OR EXISTS(SELECT 1 FROM runtime_background_tasks WHERE thread_id=%(thread)s AND {UNRESOLVED})
        OR EXISTS(SELECT 1 FROM runtime_run_resources WHERE thread_id=%(thread)s AND status<>'cleanup_confirmed')
        OR EXISTS(SELECT 1 FROM runtime_message_inbox WHERE thread_id=%(thread)s AND status IN ('queued','claimed'))
        OR EXISTS(SELECT 1 FROM crons WHERE thread_id::text=%(thread)s AND enabled)) AS pending""",
        {"thread": thread},
    ).fetchone()


def cleanup(scope, graph, *, action="report", candidate_token=None, verified_by=None):
    if action not in {"report", "mark", "apply"}:
        raise ValueError("invalid cleanup action")
    connection = NodeConnection.load()
    with connect() as db:
        db.execute("SET LOCAL lock_timeout='3s'")
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (
                connection.execution_host
                + ":"
                + thread_scope_hash(*scope)
                + ":"
                + graph,
            ),
        )
        row = db.execute(
            """SELECT * FROM runtime_workspace_locations
            WHERE execution_host=%s AND tenant_id=%s AND project_id=%s AND thread_id=%s AND graph_id=%s FOR UPDATE""",
            (connection.execution_host, *scope, graph),
        ).fetchone()
        if not row or row["target"] != "remote" or row["node_id"] != connection.node_id:
            raise DocumentError("workspace_cleanup_binding_invalid", 409)
        root = RemoteWorkspace(
            tuple(scope),
            graph,
            row["execution_host"],
            row["node_id"],
            row["workspace_id"],
        )
        if action != "report":
            # The missing Thread has no row to lock. Manual apply briefly blocks new work.
            db.execute(
                "LOCK TABLE threads,runs,crons,runtime_background_tasks,runtime_run_resources,runtime_message_inbox IN SHARE MODE"
            )
        facts = pending_facts(db, scope[2])
        if action == "report":
            result = root.call("cleanup.report")
            return {
                **result,
                "runtime_protected": facts["retained"] or facts["pending"],
            }
        if facts["retained"] or facts["pending"]:
            raise DocumentError("workspace_cleanup_protected", 409)
        if action == "mark":
            if not verified_by or not verified_by.strip():
                raise ValueError("verified_by is required")
            result = root.call(
                "cleanup.mark",
                evidence={
                    "kind": "verified_orphan",
                    "verified_by": verified_by,
                    "confirmed_at": time.time(),
                    "thread_absent": True,
                    "pending_work_absent": True,
                },
            )
        else:
            if row["status"] != "deleting" or not candidate_token:
                raise DocumentError("workspace_cleanup_protected", 409)
            result = root.call("cleanup.apply", candidate_token=candidate_token)
        db.execute(
            """UPDATE runtime_workspace_locations SET status=%s WHERE
            execution_host=%s AND tenant_id=%s AND project_id=%s AND thread_id=%s AND graph_id=%s""",
            (result["status"], connection.execution_host, *scope, graph),
        )
        return result
