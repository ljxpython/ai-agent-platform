"""Thin internal routes; scoped business rules remain in Dear Agent."""
import asyncio
import os

from fastapi import APIRouter, Header, HTTPException, Query

from runtime_service.auth.platform import authenticate
from runtime_service.services.dearflow_agent.memory import MemoryCommand, MemoryStorage
from runtime_service.workspace.documents import DocumentError

router = APIRouter(prefix="/internal/threads/{thread_id}/dear", tags=["dear-governance"])


async def authorize(thread_id, authorization, *, write):
    if os.environ.get("RUNTIME_DEAR_GOVERNANCE_ENABLED") != "1":
        raise HTTPException(409, {"code": "dear_governance_disabled"})
    facts = await authenticate(authorization)
    scope = facts.get("runtime_scope", {})
    principal = facts.get("runtime_principal", {})
    if (scope.get("operation") != ("dear-governance-write" if write else "dear-governance-read")
            or scope.get("thread_id") != thread_id or scope.get("assistant_id") != "dearflow_agent"
            or not all(principal.get(k) for k in ("tenant_id", "project_id", "user_id"))
            or scope.get("tenant_id") != principal["tenant_id"] or scope.get("project_id") != principal["project_id"]):
        raise HTTPException(403, {"code": "dear_governance_scope_denied"})
    return tuple(principal[k] for k in ("tenant_id", "project_id", "user_id"))


async def call(function, *args, **kwargs):
    try:
        return await asyncio.to_thread(function, *args, **kwargs)
    except DocumentError as exc:
        raise HTTPException(exc.status_code, {"code": exc.code}) from exc


@router.get("/memory")
async def read_memory(thread_id: str, query: str = Query(default="", max_length=500), authorization: str | None = Header(default=None)):
    scope = await authorize(thread_id, authorization, write=False)
    return await call(MemoryStorage().read, scope, query)


@router.post("/memory")
async def change_memory(thread_id: str, command: MemoryCommand, authorization: str | None = Header(default=None)):
    scope = await authorize(thread_id, authorization, write=True)
    return await call(MemoryStorage().change, scope, command, thread_id=thread_id, source_id="explicit-management")
