from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.context.models import ActorContext
from app.entrypoints.http.dependencies import get_actor_context
from app.modules.runtime_policies.application import (
    RuntimeGraphPolicyList,
    RuntimeModelPolicyList,
    RuntimePolicyOverlayService,
    RuntimeToolPolicyList,
    UpsertRuntimeGraphPolicyCommand,
    UpsertRuntimeModelPolicyCommand,
    UpsertRuntimeToolPolicyCommand,
)

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
async def list_graph_policies(
    project_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimePolicyOverlayService = Depends(get_runtime_policy_overlay_service),
) -> RuntimeGraphPolicyList:
    return await service.list_graph_policies(actor=actor, project_id=project_id)


@router.put("/graphs/{catalog_id}")
async def upsert_graph_policy(
    project_id: str,
    catalog_id: str,
    payload: UpsertRuntimeGraphPolicyCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimePolicyOverlayService = Depends(get_runtime_policy_overlay_service),
):
    return await service.upsert_graph_policy(
        actor=actor,
        project_id=project_id,
        catalog_id=catalog_id,
        command=payload,
    )


@router.get("/tools", response_model=RuntimeToolPolicyList)
async def list_tool_policies(
    project_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimePolicyOverlayService = Depends(get_runtime_policy_overlay_service),
) -> RuntimeToolPolicyList:
    return await service.list_tool_policies(actor=actor, project_id=project_id)


@router.put("/tools/{catalog_id}")
async def upsert_tool_policy(
    project_id: str,
    catalog_id: str,
    payload: UpsertRuntimeToolPolicyCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimePolicyOverlayService = Depends(get_runtime_policy_overlay_service),
):
    return await service.upsert_tool_policy(
        actor=actor,
        project_id=project_id,
        catalog_id=catalog_id,
        command=payload,
    )


@router.get("/models", response_model=RuntimeModelPolicyList)
async def list_model_policies(
    project_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimePolicyOverlayService = Depends(get_runtime_policy_overlay_service),
) -> RuntimeModelPolicyList:
    return await service.list_model_policies(actor=actor, project_id=project_id)


@router.put("/models/{catalog_id}")
async def upsert_model_policy(
    project_id: str,
    catalog_id: str,
    payload: UpsertRuntimeModelPolicyCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: RuntimePolicyOverlayService = Depends(get_runtime_policy_overlay_service),
):
    return await service.upsert_model_policy(
        actor=actor,
        project_id=project_id,
        catalog_id=catalog_id,
        command=payload,
    )

