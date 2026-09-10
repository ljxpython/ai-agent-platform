from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import sessionmaker

from platform_api.adapters.langgraph import (
    GraphParameterSchemaProvider,
)
from platform_api.config import Settings
from platform_api.core.context.models import ActorContext, ProjectContext
from platform_api.core.schemas import AckResponse
from platform_api.entrypoints.http.dependencies import (
    get_actor_context,
    get_project_context,
)
from platform_api.modules.agents.application import (
    AssistantsService,
    CreateAssistantCommand,
    ListAssistantsQuery,
    UpdateAssistantCommand,
)
from platform_api.modules.agents.domain import AssistantItem, AssistantPage
from platform_api.modules.runtime_catalog.bootstrap import build_runtime_catalog_service

router = APIRouter(tags=["assistants"])


def get_assistants_service(request: Request) -> AssistantsService:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    settings: Settings = request.app.state.settings
    if session_factory is not None and not isinstance(session_factory, sessionmaker):
        session_factory = None
    schema_provider = GraphParameterSchemaProvider(
        build_runtime_catalog_service(
            settings=settings,
            session_factory=session_factory,
        )
    )
    return AssistantsService(
        session_factory=session_factory,
        schema_provider=schema_provider,
    )


@router.get("/api/projects/{project_id}/agents", response_model=AssistantPage)
def list_assistants(
    project_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    query: str | None = Query(default=None),
    graph_id: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: AssistantsService = Depends(get_assistants_service),
) -> AssistantPage:
    return service.list_assistants(
        actor=actor,
        project_id=project_id,
        query=ListAssistantsQuery(
            limit=limit,
            offset=offset,
            query=query,
            graph_id=graph_id,
        ),
    )


@router.post("/api/projects/{project_id}/agents", response_model=AssistantItem)
async def create_assistant(
    request: Request,
    project_id: str,
    payload: CreateAssistantCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: AssistantsService = Depends(get_assistants_service),
) -> AssistantItem:
    request.state.audit_project_id = project_id
    return await service.create_assistant(
        actor=actor,
        project_id=project_id,
        command=payload,
    )


@router.get("/api/agents/{assistant_id}", response_model=AssistantItem)
def get_assistant(
    request: Request,
    assistant_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: AssistantsService = Depends(get_assistants_service),
) -> AssistantItem:
    item = service.get_assistant(actor=actor, assistant_id=assistant_id)
    request.state.audit_project_id = item.project_id
    return item


@router.patch("/api/agents/{assistant_id}", response_model=AssistantItem)
def update_assistant(
    request: Request,
    assistant_id: str,
    payload: UpdateAssistantCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: AssistantsService = Depends(get_assistants_service),
) -> AssistantItem:
    item = service.update_assistant(
        actor=actor,
        assistant_id=assistant_id,
        command=payload,
    )
    request.state.audit_project_id = item.project_id
    return item


@router.delete("/api/agents/{assistant_id}", response_model=AckResponse)
def delete_assistant(
    request: Request,
    assistant_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: AssistantsService = Depends(get_assistants_service),
) -> AckResponse:
    request.state.audit_project_id = service.delete_assistant(
        actor=actor,
        assistant_id=assistant_id,
    )
    return AckResponse()


@router.get("/api/graphs/{graph_id}/assistant-parameter-schema")
async def get_assistant_parameter_schema(
    request: Request,
    graph_id: str,
    actor: ActorContext = Depends(get_actor_context),
    project: ProjectContext = Depends(get_project_context),
    service: AssistantsService = Depends(get_assistants_service),
) -> dict[str, object]:
    if project.project_id:
        request.state.audit_project_id = project.project_id
    return await service.get_parameter_schema(
        actor=actor,
        graph_id=graph_id,
        project_id=project.project_id,
    )
