"""Thread-bound stop actions; control metadata never grants Run execution."""

import asyncio
import base64
import binascii
import json
import os
from uuid import UUID

import psycopg
from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict

from runtime_service.auth.platform import authenticate, authorize_thread_targets
from runtime_service.run_control import repository
from runtime_service.run_control.report import stop_view

router = APIRouter(prefix="/internal/threads/{thread_id}", tags=["run-control"])


class StopBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


async def _storage_call(function, *args):
    if not os.getenv("DATABASE_URI"):
        raise HTTPException(503, {"code": "stop_storage_unavailable"})
    try:
        return await asyncio.to_thread(function, *args)
    except psycopg.Error as exc:
        raise HTTPException(503, {"code": "stop_storage_unavailable"}) from exc


async def _authorize(authorization, thread, operation):
    facts = await authenticate(authorization)
    scope = facts["runtime_scope"]
    if scope["operation"] != operation or scope["thread_id"] != str(thread):
        raise HTTPException(403, {"code": "stop_scope_denied"})
    await authorize_thread_targets(
        facts, [str(thread)], action="edit" if operation == "thread-stop" else "read"
    )
    return facts


@router.post("/cancel", status_code=202)
async def cancel_thread(
    request: Request,
    thread_id: UUID,
    body: StopBody,
    response: Response,
    authorization: str | None = Header(default=None),
    idempotency_key: str = Header(min_length=1, max_length=128),
):
    _query(request, set())
    facts = await _authorize(authorization, thread_id, "thread-stop")
    row = await _storage_call(
        repository.request_stop, facts, str(thread_id), idempotency_key
    )
    response.headers["Cache-Control"] = "no-store"
    return stop_view(row)


@router.get("/stop-requests/{stop_id}")
async def get_stop(
    request: Request,
    thread_id: UUID,
    stop_id: UUID,
    response: Response,
    authorization: str | None = Header(default=None),
):
    _query(request, set())
    facts = await _authorize(authorization, thread_id, "thread-stop-read")
    row = await _storage_call(repository.read_stop, facts["runtime_scope"], stop_id)
    if row is None:
        raise HTTPException(404, {"code": "stop_request_not_found"})
    response.headers["Cache-Control"] = "no-store"
    return stop_view(row)


@router.get("/stop-requests")
async def list_stop(
    request: Request,
    thread_id: UUID,
    response: Response,
    authorization: str | None = Header(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=256),
):
    _query(request, {"limit", "cursor"})
    facts = await _authorize(authorization, thread_id, "thread-stop-read")
    before = None
    if cursor:
        try:
            from datetime import datetime

            before = json.loads(
                base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
            )
            if (
                not isinstance(before, list)
                or len(before) != 2
                or datetime.fromisoformat(before[0]).tzinfo is None
            ):
                raise ValueError()
            UUID(before[1])
        except (ValueError, TypeError, KeyError, binascii.Error, OverflowError) as exc:
            raise HTTPException(422, {"code": "invalid_stop_cursor"}) from exc
    rows = await _storage_call(
        repository.list_stops, facts["runtime_scope"], limit, before
    )
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = (
            base64.urlsafe_b64encode(
                json.dumps(
                    [last["requested_at"].isoformat(), str(last["stop_id"])]
                ).encode()
            )
            .decode()
            .rstrip("=")
        )
    response.headers["Cache-Control"] = "no-store"
    return {
        "items": [stop_view(row) for row in rows[:limit]],
        "next_cursor": next_cursor,
    }


def _query(request, allowed):
    if set(request.query_params) - allowed or any(
        len(request.query_params.getlist(key)) != 1 for key in request.query_params
    ):
        raise HTTPException(422, {"code": "invalid_stop_query"})
