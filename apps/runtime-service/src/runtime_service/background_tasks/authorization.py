"""A stopped task permits only receipt reads and cancellation of its fixed Run."""

import asyncio
from uuid import UUID

from langgraph_sdk import Auth

from runtime_service.db import connect
from runtime_service.run_control.authorization import cancellation_context_hash
from runtime_service.runtime.auth import _user_value


def _receipt(task_id):
    with connect() as connection:
        return connection.execute(
            "SELECT * FROM runtime_background_tasks WHERE task_id=%s", (task_id,)
        ).fetchone()


async def authorize_completion_cleanup(ctx, value):
    from runtime_service.runtime.auth import verified_delegation_from_user

    try:
        facts = verified_delegation_from_user(ctx.user)
        task_id = UUID(facts.policy.version.removeprefix("background-control-v1:"))
        row = await asyncio.to_thread(_receipt, task_id)
        if (
            row is None
            or not row["stop_id"]
            or row["tenant_id"] != facts.principal.tenant_id
            or row["project_id"] != facts.principal.project_id
            or row["owner_id"] != facts.principal.user_id
            or row["credential_id"] != facts.credential_id
            or row["graph_id"] != facts.scope.assistant_id
            or row["thread_id"] != facts.scope.thread_id
            or facts.context_hash != cancellation_context_hash(task_id)
            or str(ctx.resource) != "threads"
            or str(value.get("thread_id")) != row["thread_id"]
            or not row["delivery_run_id"]
            or str(value.get("run_id")) != row["delivery_run_id"]
            or (facts.scope.operation, str(ctx.action))
            not in {("read", "read"), ("run-cancel", "update")}
            or value.get("action", "interrupt") != "interrupt"
        ):
            raise ValueError()
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise Auth.exceptions.HTTPException(
            status_code=403, detail="Background cleanup scope denied"
        ) from exc
    return {"project_id": row["project_id"]}


def is_completion_cleanup(user):
    version = _user_value(user, "policy_version")
    return isinstance(version, str) and version.startswith("background-control-v1:")
