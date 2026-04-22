from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.context.models import ActorContext
from app.entrypoints.http.dependencies import get_actor_context
from app.modules.operations.bootstrap import build_operations_service
from app.modules.operations.application import (
    BulkArchiveOperationsCommand,
    BulkCancelOperationsCommand,
    BulkRestoreOperationsCommand,
    CreateOperationCommand,
    ListOperationsQuery,
    OperationsService,
)
from app.modules.operations.domain import (
    OperationArchiveScope,
    OperationArtifactCleanupResult,
    OperationBulkMutationResult,
    OperationPage,
    OperationStatus,
    OperationView,
)
from app.modules.operations.application.service import build_operation_page_signature

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
    kinds: list[str] | None = Query(default=None),
    status: OperationStatus | None = Query(default=None),
    statuses: list[OperationStatus] | None = Query(default=None),
    requested_by: str | None = Query(default=None),
    archive_scope: OperationArchiveScope = Query(default=OperationArchiveScope.EXCLUDE),
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
            kinds=tuple(kinds or ()),
            status=status,
            statuses=tuple(statuses or ()),
            requested_by=requested_by,
            archive_scope=archive_scope,
            limit=limit,
            offset=offset,
        ),
    )


@router.get("/stream")
async def stream_operations(
    request: Request,
    project_id: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    kinds: list[str] | None = Query(default=None),
    status: OperationStatus | None = Query(default=None),
    statuses: list[OperationStatus] | None = Query(default=None),
    requested_by: str | None = Query(default=None),
    archive_scope: OperationArchiveScope = Query(default=OperationArchiveScope.EXCLUDE),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    actor: ActorContext = Depends(get_actor_context),
    service: OperationsService = Depends(get_operations_service),
) -> StreamingResponse:
    query = ListOperationsQuery(
        project_id=project_id,
        kind=kind,
        kinds=tuple(kinds or ()),
        status=status,
        statuses=tuple(statuses or ()),
        requested_by=requested_by,
        archive_scope=archive_scope,
        limit=limit,
        offset=offset,
    )
    initial_page = await service.list_operations(actor=actor, query=query)
    initial_signature = build_operation_page_signature(initial_page)

    async def event_stream():
        yield b": operations-stream-connected\n\n"
        yield _encode_sse("page", initial_page.model_dump(mode="json"))
        async for page in service.watch_operations(
            actor=actor,
            query=query,
            initial_signature=initial_signature,
        ):
            if await request.is_disconnected():
                break
            if page is None:
                yield _encode_sse(
                    "heartbeat",
                    {"at": datetime.now(timezone.utc).isoformat()},
                )
                continue
            yield _encode_sse("page", page.model_dump(mode="json"))

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/artifacts/cleanup", response_model=OperationArtifactCleanupResult)
async def cleanup_operation_artifacts(
    limit: int = Query(default=100, ge=1, le=1000),
    actor: ActorContext = Depends(get_actor_context),
    service: OperationsService = Depends(get_operations_service),
) -> OperationArtifactCleanupResult:
    return await service.cleanup_expired_artifacts(actor=actor, limit=limit)


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


@router.post("/bulk/cancel", response_model=OperationBulkMutationResult)
async def bulk_cancel_operations(
    payload: BulkCancelOperationsCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: OperationsService = Depends(get_operations_service),
) -> OperationBulkMutationResult:
    return await service.bulk_cancel_operations(actor=actor, command=payload)


@router.post("/bulk/archive", response_model=OperationBulkMutationResult)
async def bulk_archive_operations(
    payload: BulkArchiveOperationsCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: OperationsService = Depends(get_operations_service),
) -> OperationBulkMutationResult:
    return await service.bulk_archive_operations(actor=actor, command=payload)


@router.post("/bulk/restore", response_model=OperationBulkMutationResult)
async def bulk_restore_operations(
    payload: BulkRestoreOperationsCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: OperationsService = Depends(get_operations_service),
) -> OperationBulkMutationResult:
    return await service.bulk_restore_operations(actor=actor, command=payload)


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


def _encode_sse(event: str, payload: dict[str, object]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode("utf-8")
