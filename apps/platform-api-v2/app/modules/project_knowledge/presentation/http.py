from __future__ import annotations

from typing import Annotated, Any
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Header, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.context.models import ActorContext
from app.entrypoints.http.dependencies import get_actor_context
from app.modules.operations.application import CreateOperationCommand, OperationsService
from app.modules.operations.bootstrap import build_operations_service
from app.modules.operations.domain import OperationView
from app.modules.project_knowledge.application import (
    DocumentsPageQuery,
    ProjectKnowledgeDeleteEntityRequest,
    ProjectKnowledgeDeleteRelationRequest,
    ProjectKnowledgeEntityUpdateRequest,
    ProjectKnowledgeQueryRequest,
    ProjectKnowledgeRelationUpdateRequest,
    ProjectKnowledgeService,
    UpdateProjectKnowledgeSpaceCommand,
)
from app.modules.project_knowledge.bootstrap import build_project_knowledge_service
from app.modules.project_knowledge.domain import ProjectKnowledgeSpaceView

router = APIRouter(prefix='/api/projects/{project_id}/knowledge', tags=['project-knowledge'])


def _forward_headers(request: Request) -> dict[str, str]:
    request_id = str(getattr(request.state, 'request_id', '') or '').strip()
    return {'x-request-id': request_id} if request_id else {}


def _bind_project_audit_scope(request: Request, project_id: str) -> None:
    request.state.audit_project_id = project_id


def get_project_knowledge_service(request: Request) -> ProjectKnowledgeService:
    settings: Settings = request.app.state.settings
    session_factory = getattr(request.app.state, 'db_session_factory', None)
    if session_factory is not None and not isinstance(session_factory, sessionmaker):
        session_factory = None
    return build_project_knowledge_service(
        settings=settings,
        session_factory=session_factory,
        forwarded_headers=_forward_headers(request),
    )


def get_operations_service(request: Request) -> OperationsService:
    settings: Settings = request.app.state.settings
    session_factory = getattr(request.app.state, 'db_session_factory', None)
    if session_factory is not None and not isinstance(session_factory, sessionmaker):
        session_factory = None
    return build_operations_service(settings=settings, session_factory=session_factory)


@router.get('', response_model=ProjectKnowledgeSpaceView)
async def get_project_knowledge_space(
    request: Request,
    project_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> ProjectKnowledgeSpaceView:
    _bind_project_audit_scope(request, project_id)
    return await service.get_space(actor=actor, project_id=project_id)


@router.put('', response_model=ProjectKnowledgeSpaceView)
async def update_project_knowledge_space(
    request: Request,
    project_id: str,
    payload: UpdateProjectKnowledgeSpaceCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> ProjectKnowledgeSpaceView:
    _bind_project_audit_scope(request, project_id)
    return await service.update_space(actor=actor, project_id=project_id, command=payload)


@router.post('/refresh', response_model=ProjectKnowledgeSpaceView)
async def refresh_project_knowledge_space(
    request: Request,
    project_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> ProjectKnowledgeSpaceView:
    _bind_project_audit_scope(request, project_id)
    return await service.refresh_space(actor=actor, project_id=project_id)


@router.post('/documents/upload')
async def upload_project_knowledge_document(
    request: Request,
    project_id: str,
    filename: Annotated[str, Header(alias='x-knowledge-filename')],
    metadata_header: Annotated[str | None, Header(alias='x-knowledge-metadata')] = None,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> dict[str, Any]:
    _bind_project_audit_scope(request, project_id)
    content = await request.body()
    return await service.upload_document(
        actor=actor,
        project_id=project_id,
        filename=unquote(filename).strip() or 'document',
        content=content,
        content_type=request.headers.get('content-type'),
        metadata_header=metadata_header,
    )


@router.post('/documents/scan', response_model=OperationView)
async def scan_project_knowledge_documents(
    request: Request,
    project_id: str,
    actor: ActorContext = Depends(get_actor_context),
    knowledge_service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
    operations_service: OperationsService = Depends(get_operations_service),
) -> OperationView:
    _bind_project_audit_scope(request, project_id)
    await knowledge_service.authorize_scan_submission(actor=actor, project_id=project_id)
    return await operations_service.submit_operation(
        actor=actor,
        command=CreateOperationCommand(
            kind='knowledge.documents.scan',
            project_id=project_id,
            input_payload={},
            metadata={'source': 'project_knowledge.documents.scan'},
        ),
    )


@router.post('/documents/paginated')
async def list_project_knowledge_documents(
    request: Request,
    project_id: str,
    payload: DocumentsPageQuery,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> dict[str, Any]:
    _bind_project_audit_scope(request, project_id)
    return await service.list_documents_paginated(actor=actor, project_id=project_id, query=payload)


@router.get('/documents/track-status/{track_id}')
async def get_project_knowledge_track_status(
    request: Request,
    project_id: str,
    track_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> dict[str, Any]:
    _bind_project_audit_scope(request, project_id)
    return await service.get_track_status(actor=actor, project_id=project_id, track_id=track_id)


@router.get('/documents/pipeline-status')
async def get_project_knowledge_pipeline_status(
    request: Request,
    project_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> dict[str, Any]:
    _bind_project_audit_scope(request, project_id)
    return await service.get_pipeline_status(actor=actor, project_id=project_id)


@router.get('/documents/scan-progress')
async def get_project_knowledge_scan_progress(
    request: Request,
    project_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> dict[str, Any]:
    _bind_project_audit_scope(request, project_id)
    return await service.get_scan_progress(actor=actor, project_id=project_id)


@router.post('/documents/reprocess-failed')
async def reprocess_failed_project_knowledge_documents(
    request: Request,
    project_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> dict[str, Any]:
    _bind_project_audit_scope(request, project_id)
    return await service.reprocess_failed_documents(actor=actor, project_id=project_id)


@router.post('/documents/cancel-pipeline')
async def cancel_project_knowledge_pipeline(
    request: Request,
    project_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> dict[str, Any]:
    _bind_project_audit_scope(request, project_id)
    return await service.cancel_pipeline(actor=actor, project_id=project_id)


@router.delete('/documents', response_model=OperationView)
async def clear_project_knowledge_documents(
    request: Request,
    project_id: str,
    actor: ActorContext = Depends(get_actor_context),
    knowledge_service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
    operations_service: OperationsService = Depends(get_operations_service),
) -> OperationView:
    _bind_project_audit_scope(request, project_id)
    await knowledge_service.authorize_clear_submission(actor=actor, project_id=project_id)
    return await operations_service.submit_operation(
        actor=actor,
        command=CreateOperationCommand(
            kind='knowledge.documents.clear',
            project_id=project_id,
            input_payload={},
            metadata={'source': 'project_knowledge.documents.clear'},
        ),
    )


@router.delete('/documents/{document_id}')
async def delete_project_knowledge_document(
    request: Request,
    project_id: str,
    document_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> dict[str, Any]:
    _bind_project_audit_scope(request, project_id)
    return await service.delete_document(actor=actor, project_id=project_id, document_id=document_id)


@router.get('/documents/{document_id}')
async def get_project_knowledge_document_detail(
    request: Request,
    project_id: str,
    document_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> dict[str, Any]:
    _bind_project_audit_scope(request, project_id)
    return await service.get_document_detail(actor=actor, project_id=project_id, document_id=document_id)


@router.post('/query')
async def query_project_knowledge(
    request: Request,
    project_id: str,
    payload: ProjectKnowledgeQueryRequest,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> dict[str, Any]:
    _bind_project_audit_scope(request, project_id)
    return await service.query(actor=actor, project_id=project_id, request=payload)


@router.post('/query/stream')
async def stream_query_project_knowledge(
    request: Request,
    project_id: str,
    payload: ProjectKnowledgeQueryRequest,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> StreamingResponse:
    _bind_project_audit_scope(request, project_id)
    stream = await service.stream_query(actor=actor, project_id=project_id, request=payload)
    return StreamingResponse(stream, media_type='application/x-ndjson')


@router.get('/graph/label/list')
async def list_project_knowledge_graph_labels(
    request: Request,
    project_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> Any:
    _bind_project_audit_scope(request, project_id)
    return await service.list_graph_labels(actor=actor, project_id=project_id)


@router.get('/graph/label/popular')
async def list_project_knowledge_graph_popular_labels(
    request: Request,
    project_id: str,
    limit: int = Query(default=10, ge=1, le=100),
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> Any:
    _bind_project_audit_scope(request, project_id)
    return await service.list_popular_graph_labels(
        actor=actor,
        project_id=project_id,
        limit=limit,
    )


@router.get('/graph/label/search')
async def search_project_knowledge_graph_labels(
    request: Request,
    project_id: str,
    q: str = Query(..., min_length=1),
    limit: int = Query(default=50, ge=1, le=100),
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> Any:
    _bind_project_audit_scope(request, project_id)
    return await service.search_graph_labels(actor=actor, project_id=project_id, q=q, limit=limit)


@router.get('/graphs')
async def get_project_knowledge_graph(
    request: Request,
    project_id: str,
    label: str = Query(..., min_length=1),
    max_depth: int = Query(default=3, ge=1, le=8),
    max_nodes: int = Query(default=200, ge=1, le=2000),
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> Any:
    _bind_project_audit_scope(request, project_id)
    return await service.get_graph(
        actor=actor,
        project_id=project_id,
        label=label,
        max_depth=max_depth,
        max_nodes=max_nodes,
    )


@router.get('/graph/entity/exists')
async def check_project_knowledge_entity_exists(
    request: Request,
    project_id: str,
    name: str = Query(..., min_length=1),
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> dict[str, Any]:
    _bind_project_audit_scope(request, project_id)
    return await service.check_entity_exists(
        actor=actor,
        project_id=project_id,
        name=name.strip(),
    )


@router.post('/graph/entity/edit')
async def update_project_knowledge_entity(
    request: Request,
    project_id: str,
    payload: ProjectKnowledgeEntityUpdateRequest,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> dict[str, Any]:
    _bind_project_audit_scope(request, project_id)
    return await service.update_entity(actor=actor, project_id=project_id, request=payload)


@router.post('/graph/relation/edit')
async def update_project_knowledge_relation(
    request: Request,
    project_id: str,
    payload: ProjectKnowledgeRelationUpdateRequest,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> dict[str, Any]:
    _bind_project_audit_scope(request, project_id)
    return await service.update_relation(actor=actor, project_id=project_id, request=payload)


@router.delete('/graph/entity')
async def delete_project_knowledge_entity(
    request: Request,
    project_id: str,
    payload: ProjectKnowledgeDeleteEntityRequest,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> dict[str, Any]:
    _bind_project_audit_scope(request, project_id)
    return await service.delete_entity(actor=actor, project_id=project_id, request=payload)


@router.delete('/graph/relation')
async def delete_project_knowledge_relation(
    request: Request,
    project_id: str,
    payload: ProjectKnowledgeDeleteRelationRequest,
    actor: ActorContext = Depends(get_actor_context),
    service: ProjectKnowledgeService = Depends(get_project_knowledge_service),
) -> dict[str, Any]:
    _bind_project_audit_scope(request, project_id)
    return await service.delete_relation(actor=actor, project_id=project_id, request=payload)
