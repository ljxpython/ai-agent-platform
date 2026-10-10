"""Current ACL and exact delegations for metadata, logs and cancellation."""

import asyncio
import base64
import binascii
import json
from datetime import datetime
from uuid import UUID

import psycopg
from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict

from runtime_service.auth.platform import authenticate, authorize_thread_targets
from runtime_service.background_tasks import repository
from runtime_service.background_tasks.output import read_output
from runtime_service.background_tasks.schemas import list_view, output_view, task_view
from runtime_service.runtime.errors import RuntimeWorkspaceError
from runtime_service.runtime.tool_access import require_tool_access

router = APIRouter(
    prefix="/internal/threads/{thread_id}/background-tasks", tags=["background-tasks"]
)


class CancelBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


async def storage(function, *args):
    try:
        return await asyncio.to_thread(function, *args)
    except (psycopg.Error, OSError, KeyError, RuntimeWorkspaceError) as exc:
        raise HTTPException(
            503, {"code": "background_task_storage_unavailable"}
        ) from exc


async def authorize(authorization, thread_id, operation):
    facts = await authenticate(authorization)
    scope = facts["runtime_scope"]
    if scope["operation"] != operation or scope["thread_id"] != str(thread_id):
        raise HTTPException(403, {"code": "background_task_denied"})
    require_tool_access(
        facts,
        "cancel_background_task"
        if operation == "background-task-cancel"
        else "background_task",
    )
    await authorize_thread_targets(
        facts,
        [str(thread_id)],
        action="edit" if operation == "background-task-cancel" else "read",
    )
    return facts


def query(request, allowed):
    if set(request.query_params) - allowed or any(
        len(request.query_params.getlist(key)) != 1 for key in request.query_params
    ):
        raise HTTPException(422, {"code": "invalid_background_task_query"})


def cursor_value(cursor):
    if not cursor:
        return None
    try:
        value = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        if (
            not isinstance(value, list)
            or len(value) != 2
            or datetime.fromisoformat(value[0]).tzinfo is None
        ):
            raise ValueError()
        UUID(value[1])
        return value
    except (ValueError, TypeError, KeyError, binascii.Error, OverflowError) as exc:
        raise HTTPException(422, {"code": "invalid_background_task_cursor"}) from exc


async def task(scope, task_id):
    row = await storage(repository.read_task, scope, task_id)
    if row is None:
        raise HTTPException(404, {"code": "background_task_not_found"})
    return row


def actions(facts):
    allowed = ["read", "logs"]
    try:
        require_tool_access(facts, "cancel_background_task")
        allowed.append("cancel")
    except HTTPException:
        pass
    return allowed


@router.get("")
async def list_background_tasks(
    request: Request,
    thread_id: UUID,
    response: Response,
    authorization: str | None = Header(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    before: str | None = Query(default=None, max_length=256),
):
    query(request, {"limit", "before"})
    facts = await authorize(authorization, thread_id, "background-task-read")
    result = await storage(
        repository.list_tasks, facts["runtime_scope"], limit, cursor_value(before)
    )
    response.headers["Cache-Control"] = "no-store"
    return list_view(facts["runtime_scope"], result, limit, actions(facts))


@router.get("/{task_id}")
async def get_background_task(
    request: Request,
    thread_id: UUID,
    task_id: UUID,
    response: Response,
    authorization: str | None = Header(default=None),
):
    query(request, set())
    facts = await authorize(authorization, thread_id, "background-task-read")
    row = await task(facts["runtime_scope"], task_id)
    response.headers["Cache-Control"] = "no-store"
    return task_view(row, actions(facts))


@router.get("/{task_id}/output")
async def get_background_output(
    request: Request,
    thread_id: UUID,
    task_id: UUID,
    response: Response,
    authorization: str | None = Header(default=None),
):
    query(request, set())
    facts = await authorize(authorization, thread_id, "background-task-log-read")
    row = await task(facts["runtime_scope"], task_id)
    response.headers["Cache-Control"] = "no-store"
    return output_view(row, await storage(read_output, row))


@router.post("/{task_id}/cancel", status_code=202)
async def cancel_background_task(
    request: Request,
    thread_id: UUID,
    task_id: UUID,
    body: CancelBody,
    response: Response,
    authorization: str | None = Header(default=None),
    idempotency_key: str = Header(min_length=1, max_length=128),
):
    query(request, set())
    facts = await authorize(authorization, thread_id, "background-task-cancel")
    await task(facts["runtime_scope"], task_id)
    row = await storage(repository.request_cancel, facts["runtime_scope"], task_id)
    response.headers["Cache-Control"] = "no-store"
    return task_view(row)
