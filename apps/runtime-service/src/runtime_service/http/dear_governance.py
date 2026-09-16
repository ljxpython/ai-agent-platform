"""Thin internal routes; scoped business rules remain in Dear Agent."""
import asyncio
import base64
import binascii
import os
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from runtime_service.auth.platform import authenticate
from runtime_service.services.dearflow_agent.memory import MemoryCommand, MemoryStorage
from runtime_service.services.dearflow_agent.skill_governance import SkillStorage
from runtime_service.workspace.documents import DocumentError

router = APIRouter(prefix="/internal/threads/{thread_id}/dear", tags=["dear-governance"])


class SkillCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["candidate", "activate", "revoke"]
    slug: str = Field(default="", max_length=64)
    digest: str = Field(default="", max_length=64)
    expected_revision: int = Field(default=0, ge=0)
    package_base64: str = Field(default="", max_length=1398104)


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


@router.get("/skills")
async def read_skills(thread_id: str, authorization: str | None = Header(default=None)):
    scope = await authorize(thread_id, authorization, write=False)
    return {"versions": await call(SkillStorage().list, scope)}


@router.post("/skills")
async def change_skills(thread_id: str, command: SkillCommand, authorization: str | None = Header(default=None)):
    scope = await authorize(thread_id, authorization, write=True)
    if command.action == "candidate":
        try:
            raw = base64.b64decode(command.package_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise HTTPException(400, {"code": "invalid_skill_package"}) from exc
        return await call(SkillStorage().create, scope, raw, source="explicit-management")
    return await call(SkillStorage().activate, scope, command.slug, command.digest,
                      expected_revision=command.expected_revision, revoke=command.action == "revoke")
