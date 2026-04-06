from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.context.models import ActorContext
from app.entrypoints.http.dependencies import get_actor_context
from app.modules.operations.bootstrap import build_operations_service
from app.modules.operations.application import CreateOperationCommand, ListOperationsQuery, OperationsService
from app.modules.operations.domain import OperationPage, OperationStatus, OperationView

router = APIRouter(prefix="/api/operations", tags=["operations"])


def get_operations_service(request: Request) -> OperationsService:
    settings: Settings = request.app.state.settings
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is not None and not isinstance(session_factory, sessionmaker):
        session_factory = None
    return build_operations_service(settings=settings, session_factory=session_factory)


@router.post("", response_model=OperationView, status_code=202)
async def submit_operation(
    payload: CreateOperationCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: OperationsService = Depends(get_operations_service),
) -> OperationView:
    return await service.submit_operation(actor=actor, command=payload)


@router.get("", response_model=OperationPage)
async def list_operations(
    project_id: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    status: OperationStatus | None = Query(default=None),
    requested_by: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    actor: ActorContext = Depends(get_actor_context),
    service: OperationsService = Depends(get_operations_service),
) -> OperationPage:
    return await service.list_operations(
        actor=actor,
        query=ListOperationsQuery(
            project_id=project_id,
            kind=kind,
            status=status,
            requested_by=requested_by,
            limit=limit,
            offset=offset,
        ),
    )


@router.get("/{operation_id}", response_model=OperationView)
async def get_operation(
    operation_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: OperationsService = Depends(get_operations_service),
) -> OperationView:
    return await service.get_operation(actor=actor, operation_id=operation_id)


@router.post("/{operation_id}/cancel", response_model=OperationView)
async def cancel_operation(
    operation_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: OperationsService = Depends(get_operations_service),
) -> OperationView:
    return await service.cancel_operation(actor=actor, operation_id=operation_id)


@router.get("/{operation_id}/artifact")
async def download_operation_artifact(
    operation_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: OperationsService = Depends(get_operations_service),
) -> FileResponse:
    artifact = await service.get_operation_artifact(actor=actor, operation_id=operation_id)
    return FileResponse(
        path=artifact.path,
        media_type=artifact.media_type,
        filename=artifact.filename,
    )
