"""Member reads and a separately signed internal authorization boundary."""

import json
from dataclasses import replace
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from starlette.concurrency import run_in_threadpool

from platform_api.adapters.knowledge.client import KnowledgeClient
from platform_api.core.context import replace_current_request_context
from platform_api.core.context.models import ActorContext, ProjectContext, TenantContext
from platform_api.core.errors import BadRequestError, PlatformApiError
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.modules.knowledge.authorization import (
    authorize_operation,
    parse_operation,
)
from platform_api.modules.knowledge.schemas import (
    JobId,
    KnowledgeCapabilities,
    KnowledgeDocumentPage,
    KnowledgeJob,
    KnowledgeJobPage,
)
from platform_api.modules.knowledge.service import KnowledgeService

router = APIRouter(tags=["project-knowledge"])


def _query(request, allowed):
    if set(request.query_params) - allowed or any(
        len(request.query_params.getlist(k)) != 1 for k in request.query_params
    ):
        raise BadRequestError(
            code="invalid_knowledge_query", message="Invalid knowledge query"
        )


def get_knowledge_service(request: Request):
    return KnowledgeService(
        getattr(request.app.state, "db_session_factory", None),
        request.app.state.settings,
        KnowledgeClient(request.app.state.knowledge_http),
        request.state.platform_context.tenant.tenant_id,
    )


@router.get(
    "/api/projects/{project_id}/knowledge/capabilities",
    response_model=KnowledgeCapabilities,
)
async def capabilities(
    request: Request,
    project_id: UUID,
    actor: ActorContext = Depends(get_actor_context),
    service=Depends(get_knowledge_service),
):
    _query(request, set())
    return await service.read(actor, str(project_id), "capabilities")


@router.get(
    "/api/projects/{project_id}/knowledge/documents",
    response_model=KnowledgeDocumentPage,
)
async def documents(
    request: Request,
    project_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    actor: ActorContext = Depends(get_actor_context),
    service=Depends(get_knowledge_service),
):
    _query(request, {"limit", "offset"})
    return await service.read(
        actor, str(project_id), "documents", {"limit": limit, "offset": offset}
    )


@router.get(
    "/api/projects/{project_id}/knowledge/jobs", response_model=KnowledgeJobPage
)
async def jobs(
    request: Request,
    project_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    actor: ActorContext = Depends(get_actor_context),
    service=Depends(get_knowledge_service),
):
    _query(request, {"limit", "offset"})
    return await service.read(
        actor, str(project_id), "jobs", {"limit": limit, "offset": offset}
    )


@router.get(
    "/api/projects/{project_id}/knowledge/jobs/{job_id}", response_model=KnowledgeJob
)
async def job(
    request: Request,
    project_id: UUID,
    job_id: JobId,
    actor: ActorContext = Depends(get_actor_context),
    service=Depends(get_knowledge_service),
):
    _query(request, set())
    return await service.read(actor, str(project_id), "jobs/" + job_id)


@router.post("/api/runtime/internal/knowledge/authorize")
async def authorize(request: Request):
    _query(request, set())
    if request.headers.get("content-type", "").split(";", 1)[0] != "application/json":
        raise BadRequestError(code="invalid_knowledge_request", message="JSON required")
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 16384:
            raise PlatformApiError(
                code="invalid_knowledge_request",
                message="Authorization too large",
                status_code=413,
            )
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise BadRequestError(
            code="invalid_knowledge_request", message="Invalid JSON"
        ) from exc
    operation = parse_operation(request.app.state.settings, payload)
    result, actor = await run_in_threadpool(
        authorize_operation,
        getattr(request.app.state, "db_session_factory", None),
        request.app.state.settings,
        operation,
    )
    context = replace(
        request.state.platform_context,
        actor=actor,
        project=ProjectContext(project_id=str(operation.project_id)),
        tenant=TenantContext(tenant_id=operation.tenant_id),
    )
    request.state.platform_context = context
    replace_current_request_context(context)
    request.state.audit_metadata = {
        "operation": operation.operation,
        "knowledge_request_id": operation.request_id,
        "job_id": operation.job_id,
        "resource_id": operation.resource_id,
    }
    return result
