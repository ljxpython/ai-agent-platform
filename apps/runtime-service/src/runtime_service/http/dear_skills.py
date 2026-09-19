"""Private owner-scoped skill management; no thread or client-authored identity."""
import base64
import binascii
import os
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from runtime_service.auth.platform import authenticate
from runtime_service.http.dear_governance import call
from runtime_service.services.dearflow_agent import skill_catalog as catalog
from runtime_service.services.dearflow_agent.skill_governance import SkillStorage

router = APIRouter(prefix="/internal/dear/skills", tags=["dear-skills"])
Source = Literal["public", "custom"]


class Upload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    package_base64: str = Field(min_length=1, max_length=1398104)


class Update(Upload):
    expected_revision: str = Field(min_length=1, max_length=64)


class Toggle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: StrictBool
    expected_revision: str = Field(min_length=1, max_length=64)


async def authorize(authorization, *, write=False):
    facts = await authenticate(authorization)
    scope, principal = facts.get("runtime_scope", {}), facts.get("runtime_principal", {})
    if (scope.get("operation") != ("dear-skills-write" if write else "dear-skills-read")
            or scope.get("assistant_id") != "dearflow_agent" or scope.get("thread_id") is not None
            or not all(principal.get(k) for k in ("tenant_id", "project_id", "user_id"))
            or any(scope.get(k) != principal.get(k) for k in ("tenant_id", "project_id"))):
        raise HTTPException(403, {"code": "dear_skills_scope_denied"})
    if write and not enabled():
        raise HTTPException(409, {"code": "dear_skills_disabled"})
    return tuple(principal[k] for k in ("tenant_id", "project_id", "user_id"))


def enabled():
    return os.environ.get("RUNTIME_DEAR_GOVERNANCE_ENABLED") == "1"


def decode(command):
    try:
        return base64.b64decode(command.package_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise HTTPException(400, {"code": "invalid_skill_package"}) from exc


@router.get("")
async def list_skills(authorization: str | None = Header(default=None)):
    scope = await authorize(authorization)
    custom = await call(SkillStorage().list, scope) if enabled() else []
    items = [*await call(catalog.public_catalog), *custom]
    return {"items": [{k: v for k, v in i.items() if k != "manifest"} for i in items],
            "capabilities": {"can_read": True, "can_write": enabled(), "custom_management_enabled": enabled()},
            "limits": {"package_bytes": 1048576, "unpacked_bytes": 1048576, "file_bytes": 262144,
                       "entries": 100, "custom_skills": 50}}


@router.post("/custom", status_code=201)
async def create(command: Upload, authorization: str | None = Header(default=None)):
    scope = await authorize(authorization, write=True)
    return await call(SkillStorage().create, scope, decode(command), source="explicit-management")


@router.put("/custom/{slug}")
async def update(slug: str, command: Update, authorization: str | None = Header(default=None)):
    scope = await authorize(authorization, write=True)
    return await call(SkillStorage().update, scope, slug, decode(command), expected_revision=command.expected_revision)


@router.patch("/custom/{slug}")
async def toggle(slug: str, command: Toggle, authorization: str | None = Header(default=None)):
    scope = await authorize(authorization, write=True)
    return await call(SkillStorage().set_enabled, scope, slug, **command.model_dump())


@router.delete("/custom/{slug}", status_code=204)
async def delete(slug: str, expected_revision: str = Query(min_length=1, max_length=64), authorization: str | None = Header(default=None)):
    scope = await authorize(authorization, write=True)
    await call(SkillStorage().delete, scope, slug, expected_revision=expected_revision)
    return Response(status_code=204)


@router.get("/{source}/{slug}")
async def detail(source: Source, slug: str, authorization: str | None = Header(default=None)):
    scope = await authorize(authorization)
    if source == "custom" and not enabled():
        raise HTTPException(409, {"code": "dear_skills_disabled"})
    return await call(catalog.detail, scope, source, slug)


@router.get("/{source}/{slug}/content")
async def content(source: Source, slug: str, path: str = Query(min_length=1, max_length=1024), revision: str = Query(min_length=1, max_length=64), authorization: str | None = Header(default=None)):
    scope = await authorize(authorization)
    if source == "custom" and not enabled():
        raise HTTPException(409, {"code": "dear_skills_disabled"})
    return await call(catalog.content, scope, source, slug, path, revision)
