"""Atomic storage binding; configuration changes never move existing data."""

import os

from runtime_service.db import connect
from runtime_service.errors import RuntimeWorkspaceError
from runtime_service.workspace.target import (
    NodeConnection,
    RemoteWorkspace,
    sandbox_target,
)


def bind(scope, graph, local_root):
    from runtime_service.workspace.scoped import thread_scope_hash

    target = sandbox_target()
    connection = NodeConnection.load() if target == "remote" else None
    host = (
        connection.execution_host
        if connection
        else os.getenv("RUNTIME_EXECUTION_HOST_ID", "")
    )
    node = connection.node_id if connection else None
    storage_path = str(local_root.absolute()) if target == "local" else None
    workspace_id = thread_scope_hash(*scope)
    if os.getenv("DATABASE_URI") and host:
        with connect() as db:
            from runtime_service.thread_lifecycle import deletion_pending

            if deletion_pending(db, scope[2]):
                raise RuntimeWorkspaceError("runtime.workspace.unavailable")
            db.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                (host + ":" + workspace_id + ":" + graph,),
            )
            existing = db.execute(
                """SELECT * FROM runtime_workspace_locations WHERE
                execution_host=%s AND tenant_id=%s AND project_id=%s AND thread_id=%s AND graph_id=%s""",
                (host, *scope, graph),
            ).fetchone()
            if not existing and target == "remote" and local_root.exists():
                raise RuntimeWorkspaceError("runtime.workspace.unavailable")
            db.execute(
                """INSERT INTO runtime_workspace_locations
                (execution_host,tenant_id,project_id,thread_id,graph_id,target,node_id,workspace_id,storage_path)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                (host, *scope, graph, target, node, workspace_id, storage_path),
            )
            row = db.execute(
                """SELECT * FROM runtime_workspace_locations WHERE
                execution_host=%s AND tenant_id=%s AND project_id=%s AND thread_id=%s AND graph_id=%s""",
                (host, *scope, graph),
            ).fetchone()
            if row["status"] != "retained" or (
                row["target"],
                row["node_id"],
                row["workspace_id"],
                row["storage_path"],
            ) != (target, node, workspace_id, storage_path):
                raise RuntimeWorkspaceError("runtime.workspace.unavailable")
    elif target == "remote":
        raise RuntimeWorkspaceError("runtime.workspace.unavailable")
    return (
        RemoteWorkspace(scope, graph, host, node, workspace_id)
        if target == "remote"
        else local_root
    )
