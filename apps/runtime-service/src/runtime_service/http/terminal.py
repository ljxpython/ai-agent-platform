"""Authenticated manual terminal operations; never an Agent tool."""

import asyncio
import base64
import binascii
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from runtime_service.auth.platform import authenticate
from runtime_service.workspace.documents import DocumentError
from runtime_service.workspace.terminal import terminal_enabled, terminals

router = APIRouter(prefix="/internal/threads/{thread_id}/terminals", tags=["terminal"])


class TerminalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    acknowledge_execution: Literal[True]
    rows: int = Field(default=24, ge=2, le=200)
    cols: int = Field(default=80, ge=2, le=400)


class TerminalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_base64: str = Field(min_length=1, max_length=5464)
    sequence: int = Field(ge=0)


class TerminalResize(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rows: int = Field(ge=2, le=200)
    cols: int = Field(ge=2, le=400)


async def _owner(thread_id, authorization, *, write):
    facts = await authenticate(authorization)
    scope = facts.get("runtime_scope", {})
    operation = "terminal-write" if write else "terminal-read"
    if (
        scope.get("operation") != operation
        or scope.get("thread_id") != thread_id
        or not scope.get("tenant_id")
        or not scope.get("project_id")
        or scope.get("assistant_id") not in {"showcase_demo", "dearflow_agent"}
    ):
        raise HTTPException(403, {"code": "terminal_scope_denied"})
    if "runtime.tool.execute" not in facts.get(
        "permissions", []
    ) or "execute" not in facts.get("allowed_tool_names", []):
        raise HTTPException(403, {"code": "terminal_execute_denied"})
    if not terminal_enabled():
        raise HTTPException(409, {"code": "terminal_disabled"})
    return (
        scope["tenant_id"],
        scope["project_id"],
        thread_id,
        scope["assistant_id"],
        facts["identity"],
    )


async def _call(response, function, *args):
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return await asyncio.to_thread(function, *args)
    except DocumentError as exc:
        raise HTTPException(exc.status_code, {"code": exc.code}) from exc


@router.post("")
async def create(
    thread_id: str,
    payload: TerminalCreate,
    response: Response,
    authorization: str | None = Header(default=None),
):
    owner = await _owner(thread_id, authorization, write=True)
    return await _call(
        response,
        terminals.create,
        owner,
        str(payload.request_id),
        payload.rows,
        payload.cols,
    )


@router.get("")
async def listing(
    thread_id: str, response: Response, authorization: str | None = Header(default=None)
):
    owner = await _owner(thread_id, authorization, write=False)
    return await _call(response, terminals.list, owner)


@router.get("/{terminal_id}/output")
async def output(
    thread_id: str,
    terminal_id: str,
    response: Response,
    offset: int = Query(default=0, ge=0),
    authorization: str | None = Header(default=None),
):
    owner = await _owner(thread_id, authorization, write=False)
    return await _call(response, lambda: terminals.get(owner, terminal_id).read(offset))


@router.post("/{terminal_id}/input")
async def send_input(
    thread_id: str,
    terminal_id: str,
    payload: TerminalInput,
    response: Response,
    authorization: str | None = Header(default=None),
):
    owner = await _owner(thread_id, authorization, write=True)
    try:
        data = base64.b64decode(payload.data_base64, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(400, {"code": "terminal_input_invalid"}) from None
    if not 0 < len(data) <= 4096:
        raise HTTPException(413, {"code": "terminal_input_too_large"})
    return await _call(
        response,
        lambda: terminals.get(owner, terminal_id).write(data, payload.sequence),
    )


@router.post("/{terminal_id}/resize")
async def resize(
    thread_id: str,
    terminal_id: str,
    payload: TerminalResize,
    response: Response,
    authorization: str | None = Header(default=None),
):
    owner = await _owner(thread_id, authorization, write=True)
    return await _call(
        response,
        lambda: terminals.get(owner, terminal_id).resize(payload.rows, payload.cols),
    )


@router.delete("/{terminal_id}")
async def close(
    thread_id: str,
    terminal_id: str,
    response: Response,
    authorization: str | None = Header(default=None),
):
    owner = await _owner(thread_id, authorization, write=True)
    return await _call(response, lambda: terminals.get(owner, terminal_id).close())
