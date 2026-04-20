from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.core.context.models import ActorContext
from app.core.db import SqlAlchemyUnitOfWork
from app.core.errors import BadRequestError, NotFoundError, ServiceUnavailableError
from app.core.identifiers import parse_uuid
from app.modules.iam.application import AuthorizationRequest, IamPolicyEngine, PermissionCode
from app.modules.project_knowledge.application.contracts import (
    DocumentsPageQuery,
    ProjectKnowledgeDeleteEntityRequest,
    ProjectKnowledgeDeleteRelationRequest,
    ProjectKnowledgeEntityUpdateRequest,
    ProjectKnowledgeQueryRequest,
    ProjectKnowledgeRelationUpdateRequest,
    UpdateProjectKnowledgeSpaceCommand,
)
from app.modules.project_knowledge.domain import ProjectKnowledgeSpaceView
from app.modules.project_knowledge.infra import SqlAlchemyProjectKnowledgeRepository
from app.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository


class ProjectKnowledgeService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None,
        upstream: Any,
        service_base_url: str,
        policy_engine: IamPolicyEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._upstream = upstream
        self._service_base_url = service_base_url.rstrip('/')
        self._policy_engine = policy_engine or IamPolicyEngine()

    def _require_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            raise ServiceUnavailableError(
                code='platform_database_not_enabled',
                message='Platform database is not enabled',
            )
        return self._session_factory

    def _require_project_access(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        permission: PermissionCode,
    ) -> UUID:
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(permission=permission, project_id=project_id),
        )
        return parse_uuid(project_id, code='invalid_project_id')

    @staticmethod
    def _workspace_key(project_uuid: UUID) -> str:
        return f'kb_{project_uuid.hex}'

    def _space_view(self, row: Any, *, health: dict[str, Any] | None = None) -> ProjectKnowledgeSpaceView:
        return ProjectKnowledgeSpaceView(
            id=str(row.id),
            project_id=str(row.project_id),
            provider=row.provider,
            display_name=row.display_name,
            workspace_key=row.workspace_key,
            status=row.status,
            service_base_url=row.service_base_url,
            runtime_profile_json=dict(row.runtime_profile_json or {}),
            health=health,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def _project_display_name(self, project: Any) -> str:
        if project is None:
            return '项目知识空间'
        normalized = (project.name or '').strip()
        return f'{normalized} 知识空间' if normalized else '项目知识空间'

    def _get_or_create_space(self, *, uow: SqlAlchemyUnitOfWork, project_uuid: UUID) -> Any:
        repository = SqlAlchemyProjectKnowledgeRepository(uow.session)
        row = repository.get_by_project_id(project_uuid)
        if row is not None:
            return row
        projects_repository = SqlAlchemyProjectsRepository(uow.session)
        project = projects_repository.get_project_by_id(project_uuid)
        if project is None or project.status == 'deleted':
            raise NotFoundError(message='Project not found', code='project_not_found')
        return repository.create_space(
            project_id=project_uuid,
            provider='lightrag',
            display_name=self._project_display_name(project),
            workspace_key=self._workspace_key(project_uuid),
            status='active',
            service_base_url=self._service_base_url,
            runtime_profile_json={},
        )

    async def get_space(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        include_health: bool = True,
    ) -> ProjectKnowledgeSpaceView:
        project_uuid = self._require_project_access(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_READ,
        )
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            row = self._get_or_create_space(uow=uow, project_uuid=project_uuid)
            health = (
                await self._upstream.get_health(workspace_key=row.workspace_key)
                if include_health
                else None
            )
            return self._space_view(row, health=health)

    async def update_space(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        command: UpdateProjectKnowledgeSpaceCommand,
    ) -> ProjectKnowledgeSpaceView:
        project_uuid = self._require_project_access(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_ADMIN,
        )
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            row = self._get_or_create_space(uow=uow, project_uuid=project_uuid)
            repository = SqlAlchemyProjectKnowledgeRepository(uow.session)
            updated = repository.update_space(
                row=row,
                display_name=command.display_name.strip() if command.display_name else None,
                runtime_profile_json=command.runtime_profile_json,
            )
            health = await self._upstream.get_health(workspace_key=updated.workspace_key)
            return self._space_view(updated, health=health)

    async def refresh_space(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> ProjectKnowledgeSpaceView:
        project_uuid = self._require_project_access(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_ADMIN,
        )
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            row = self._get_or_create_space(uow=uow, project_uuid=project_uuid)
            health = await self._upstream.get_health(workspace_key=row.workspace_key)
            return self._space_view(row, health=health)

    async def upload_document(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        filename: str,
        content: bytes,
        content_type: str | None,
        metadata_header: str | None = None,
    ) -> dict[str, Any]:
        workspace_key = await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_WRITE,
        )
        extra_headers: dict[str, str] | None = None
        if metadata_header and metadata_header.strip():
            try:
                parsed = json.loads(metadata_header)
            except ValueError:
                raise BadRequestError(
                    code='invalid_knowledge_metadata',
                    message='x-knowledge-metadata must be a valid JSON object',
                )
            if isinstance(parsed, dict):
                extra_headers = {
                    'x-knowledge-metadata': json.dumps(
                        parsed,
                        ensure_ascii=False,
                        separators=(',', ':'),
                    )
                }
            else:
                raise BadRequestError(
                    code='invalid_knowledge_metadata',
                    message='x-knowledge-metadata must be a valid JSON object',
                )
        return await self._upstream.upload_document(
            workspace_key=workspace_key,
            filename=filename,
            content=content,
            content_type=content_type,
            extra_headers=extra_headers,
        )

    async def trigger_scan(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> dict[str, Any]:
        workspace_key = await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_WRITE,
        )
        return await self._upstream.request_json(
            'POST', '/documents/scan', workspace_key=workspace_key
        )

    async def authorize_scan_submission(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> None:
        await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_WRITE,
        )

    async def list_documents_paginated(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        query: DocumentsPageQuery,
    ) -> dict[str, Any]:
        workspace_key = await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_READ,
        )
        payload = query.model_dump(mode='json', exclude_none=True)
        status_filter = payload.get('status_filter')
        if isinstance(status_filter, str) and status_filter.strip():
            payload['status_filter'] = status_filter.strip().lower()
        return await self._upstream.request_json(
            'POST',
            '/documents/paginated',
            workspace_key=workspace_key,
            payload=payload,
        )

    async def get_track_status(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        track_id: str,
    ) -> dict[str, Any]:
        workspace_key = await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_READ,
        )
        return await self._upstream.request_json(
            'GET',
            f'/documents/track_status/{track_id}',
            workspace_key=workspace_key,
        )

    async def get_pipeline_status(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> dict[str, Any]:
        workspace_key = await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_READ,
        )
        return await self._upstream.request_json(
            'GET', '/documents/pipeline_status', workspace_key=workspace_key
        )

    async def get_scan_progress(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> dict[str, Any]:
        pipeline = await self.get_pipeline_status(actor=actor, project_id=project_id)
        total_files = int(pipeline.get('batchs') or 0)
        current_batch = int(pipeline.get('cur_batch') or 0)
        progress = 0
        if total_files > 0:
            progress = int(min(max(current_batch, 0), total_files) / total_files * 100)
        return {
            'is_scanning': bool(pipeline.get('busy')),
            'current_file': str(pipeline.get('job_name') or pipeline.get('latest_message') or ''),
            'indexed_count': max(current_batch - 1, 0) if bool(pipeline.get('busy')) else current_batch,
            'total_files': total_files,
            'progress': progress,
        }

    async def reprocess_failed_documents(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> dict[str, Any]:
        workspace_key = await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_WRITE,
        )
        return await self._upstream.request_json(
            'POST', '/documents/reprocess_failed', workspace_key=workspace_key
        )

    async def cancel_pipeline(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> dict[str, Any]:
        workspace_key = await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_WRITE,
        )
        return await self._upstream.request_json(
            'POST', '/documents/cancel_pipeline', workspace_key=workspace_key
        )

    async def clear_documents(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> dict[str, Any]:
        workspace_key = await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_ADMIN,
        )
        return await self._upstream.request_json(
            'DELETE', '/documents', workspace_key=workspace_key
        )

    async def authorize_clear_submission(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> None:
        await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_ADMIN,
        )

    async def delete_document(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        document_id: str,
    ) -> dict[str, Any]:
        workspace_key = await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_WRITE,
        )
        return await self._upstream.request_json(
            'DELETE',
            '/documents/delete_document',
            workspace_key=workspace_key,
            payload={'doc_ids': [document_id], 'delete_file': True, 'delete_llm_cache': False},
        )

    async def get_document_detail(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        document_id: str,
    ) -> dict[str, Any]:
        workspace_key = await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_READ,
        )
        payload = await self._upstream.request_json(
            'GET',
            f'/documents/{document_id}/detail',
            workspace_key=workspace_key,
        )
        if isinstance(payload, dict) and str(payload.get('id') or '') == document_id:
            return payload
        raise NotFoundError(message='Knowledge document not found', code='knowledge_document_not_found')

    async def query(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        request: ProjectKnowledgeQueryRequest,
    ) -> dict[str, Any]:
        workspace_key = await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_READ,
        )
        return await self._upstream.request_json(
            'POST',
            '/query',
            workspace_key=workspace_key,
            payload=request.model_dump(mode='json', exclude_none=True),
        )

    async def stream_query(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        request: ProjectKnowledgeQueryRequest,
    ):
        workspace_key = await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_READ,
        )
        return self._upstream.stream_bytes(
            'POST',
            '/query/stream',
            workspace_key=workspace_key,
            payload=request.model_dump(mode='json', exclude_none=True),
        )

    async def list_graph_labels(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> Any:
        workspace_key = await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_READ,
        )
        return await self._upstream.request_json(
            'GET', '/graph/label/list', workspace_key=workspace_key
        )

    async def list_popular_graph_labels(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        limit: int,
    ) -> Any:
        workspace_key = await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_READ,
        )
        return await self._upstream.request_json(
            'GET',
            '/graph/label/popular',
            workspace_key=workspace_key,
            params={'limit': limit},
        )

    async def search_graph_labels(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        q: str,
        limit: int,
    ) -> Any:
        workspace_key = await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_READ,
        )
        return await self._upstream.request_json(
            'GET',
            '/graph/label/search',
            workspace_key=workspace_key,
            params={'q': q, 'limit': limit},
        )

    async def get_graph(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        label: str,
        max_depth: int,
        max_nodes: int,
    ) -> Any:
        workspace_key = await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_READ,
        )
        return await self._upstream.request_json(
            'GET',
            '/graphs',
            workspace_key=workspace_key,
            params={'label': label, 'max_depth': max_depth, 'max_nodes': max_nodes},
        )

    async def check_entity_exists(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        name: str,
    ) -> dict[str, Any]:
        workspace_key = await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_READ,
        )
        return await self._upstream.request_json(
            'GET',
            '/graph/entity/exists',
            workspace_key=workspace_key,
            params={'name': name},
        )

    async def update_entity(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        request: ProjectKnowledgeEntityUpdateRequest,
    ) -> dict[str, Any]:
        workspace_key = await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_WRITE,
        )
        return await self._upstream.request_json(
            'POST',
            '/graph/entity/edit',
            workspace_key=workspace_key,
            payload=request.model_dump(mode='json', exclude_none=True),
        )

    async def update_relation(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        request: ProjectKnowledgeRelationUpdateRequest,
    ) -> dict[str, Any]:
        workspace_key = await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_WRITE,
        )
        return await self._upstream.request_json(
            'POST',
            '/graph/relation/edit',
            workspace_key=workspace_key,
            payload=request.model_dump(mode='json', exclude_none=True),
        )

    async def delete_entity(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        request: ProjectKnowledgeDeleteEntityRequest,
    ) -> dict[str, Any]:
        workspace_key = await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_WRITE,
        )
        return await self._upstream.request_json(
            'DELETE',
            '/documents/delete_entity',
            workspace_key=workspace_key,
            payload=request.model_dump(mode='json', exclude_none=True),
        )

    async def delete_relation(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        request: ProjectKnowledgeDeleteRelationRequest,
    ) -> dict[str, Any]:
        workspace_key = await self._resolve_workspace_key(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_KNOWLEDGE_WRITE,
        )
        return await self._upstream.request_json(
            'DELETE',
            '/documents/delete_relation',
            workspace_key=workspace_key,
            payload=request.model_dump(mode='json', exclude_none=True),
        )

    async def _resolve_workspace_key(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        permission: PermissionCode,
    ) -> str:
        project_uuid = self._require_project_access(
            actor=actor,
            project_id=project_id,
            permission=permission,
        )
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            row = self._get_or_create_space(uow=uow, project_uuid=project_uuid)
            return row.workspace_key
