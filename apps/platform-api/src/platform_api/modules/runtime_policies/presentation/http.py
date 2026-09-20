from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import sessionmaker

from platform_api.config import Settings
from platform_api.core.context.models import ActorContext
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.modules.runtime_policies.application import (
    RuntimeGraphPolicyList,
    RuntimeModelPolicyList,
    RuntimePolicyOverlayService,
    UpsertRuntimeGraphPolicyCommand,
    UpsertRuntimeModelPolicyCommand,
)

from platform_api.modules.runtime_policies.application.contracts import CreateToolRestriction, ToolRestrictionItem, ToolRestrictionList
from platform_api.modules.runtime_catalog.presentation.http import get_runtime_catalog_service
from platform_api.modules.runtime_catalog.application.service import RuntimeCatalogService
from platform_api.core.errors import BadRequestError

router = APIRouter(prefix="/api/projects/{project_id}/runtime-policies", tags=["runtime-policies"])


def get_runtime_policy_overlay_service(request: Request) -> RuntimePolicyOverlayService:
    settings: Settings = request.app.state.settings
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is not None and not isinstance(session_factory, sessionmaker):
        session_factory = None
    return RuntimePolicyOverlayService(
        session_factory=session_factory,
        runtime_base_url=settings.langgraph_upstream_url,
    )


@router.get("/graphs", response_model=RuntimeGraphPolicyList)
def list_graph_policies(
    project_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimePolicyOverlayService = Depends(get_runtime_policy_overlay_service),
) -> RuntimeGraphPolicyList:
    return service.list_graph_policies(actor=actor, project_id=project_id)


@router.put("/graphs/{catalog_id}")
def upsert_graph_policy(
    project_id: str,
    catalog_id: str,
    payload: UpsertRuntimeGraphPolicyCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimePolicyOverlayService = Depends(get_runtime_policy_overlay_service),
):
    return service.upsert_graph_policy(
        actor=actor,
        project_id=project_id,
        catalog_id=catalog_id,
        command=payload,
    )


@router.get("/models", response_model=RuntimeModelPolicyList)
def list_model_policies(
    project_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimePolicyOverlayService = Depends(get_runtime_policy_overlay_service),
) -> RuntimeModelPolicyList:
    return service.list_model_policies(actor=actor, project_id=project_id)


@router.put("/models/{catalog_id}")
def upsert_model_policy(
    project_id: str,
    catalog_id: str,
    payload: UpsertRuntimeModelPolicyCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimePolicyOverlayService = Depends(get_runtime_policy_overlay_service),
):
    return service.upsert_model_policy(
        actor=actor,
        project_id=project_id,
        catalog_id=catalog_id,
        command=payload,
    )


@router.get("/tool-restrictions", response_model=ToolRestrictionList)
def list_tool_restrictions(project_id: str, actor: ActorContext = Depends(get_actor_context),
                           service: RuntimePolicyOverlayService = Depends(get_runtime_policy_overlay_service)):
    return service.list_tool_restrictions(actor=actor, project_id=project_id)


@router.post("/tool-restrictions", response_model=ToolRestrictionItem, status_code=201)
async def create_tool_restriction(project_id: str, payload: CreateToolRestriction, request: Request,
                                 actor: ActorContext = Depends(get_actor_context),
                                 service: RuntimePolicyOverlayService = Depends(get_runtime_policy_overlay_service),
                                 catalog: RuntimeCatalogService = Depends(get_runtime_catalog_service)):
    request.state.audit_metadata = payload.model_dump(mode="json")
    await run_in_threadpool(service.validate_restriction_subject, actor=actor, project_id=project_id, command=payload)
    items = await catalog.read_tool_declarations(actor=actor, project_id=project_id)
    if not any(item["tool_key"] == payload.tool_name and payload.graph_id in item["graph_ids"] for item in items):
        raise BadRequestError(code="tool_not_declared", message="Tool is not declared by this graph")
    return await run_in_threadpool(service.create_tool_restriction, actor=actor, project_id=project_id, command=payload)


@router.delete("/tool-restrictions/{restriction_id}", status_code=204)
def delete_tool_restriction(project_id: str, restriction_id: str, request: Request,
                            actor: ActorContext = Depends(get_actor_context),
                            service: RuntimePolicyOverlayService = Depends(get_runtime_policy_overlay_service)):
    deleted = service.delete_tool_restriction(actor=actor, project_id=project_id, restriction_id=restriction_id)
    request.state.audit_metadata = deleted.model_dump(mode="json")
    return Response(status_code=204)
