"""Historical task rows pin their Node independently of today's backend switch."""

import asyncio
from uuid import NAMESPACE_URL, UUID, uuid5

from runtime_service.errors import (
    BackgroundTaskNotStarted,
    RuntimeWorkspaceError,
    WorkspaceExecutionNotStarted,
)
from runtime_service.workspace.node_client import call
from runtime_service.workspace.scoped import thread_scope_hash
from runtime_service.workspace.target import RemoteWorkspace


async def background_call(row, action, **arguments):
    scope = (str(row["tenant_id"]), str(row["project_id"]), str(row["thread_id"]))
    root = RemoteWorkspace(
        scope,
        row["graph_id"],
        row["execution_host_id"],
        row["sandbox_node_id"],
        thread_scope_hash(*scope),
    )
    resource_id = UUID(str(row["task_id"])).hex
    operation_id = (
        resource_id
        if action == "create"
        else uuid5(NAMESPACE_URL, resource_id + ":" + action).hex
    )
    try:
        return await asyncio.to_thread(
            call,
            root,
            "background." + action,
            {"resource_id": resource_id, **arguments},
            operation_id=operation_id,
        )
    except WorkspaceExecutionNotStarted as exc:
        if action == "create":
            raise BackgroundTaskNotStarted("background_task_not_supported") from exc
        raise RuntimeWorkspaceError("background_task_control_unavailable") from exc
    except Exception as exc:
        if isinstance(exc, asyncio.CancelledError):
            raise
        raise RuntimeWorkspaceError("background_task_control_unavailable") from exc
