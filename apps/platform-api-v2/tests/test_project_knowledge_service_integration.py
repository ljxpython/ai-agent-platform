from __future__ import annotations

import unittest
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy import create_engine

from app.core.context.models import ActorContext
from app.core.db import build_session_factory, create_core_tables, session_scope
from app.core.errors import ForbiddenError
from app.modules.operations.application import CreateOperationCommand, OperationsService
from app.modules.project_knowledge.application import (
    DocumentsPageQuery,
    ProjectKnowledgeQueryRequest,
    ProjectKnowledgeService,
)
from app.modules.project_knowledge.presentation.http import (
    clear_project_knowledge_documents,
    scan_project_knowledge_documents,
)
from app.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository


class _RecordingKnowledgeUpstream:
    def __init__(self) -> None:
        self.upload_calls: list[dict[str, object]] = []
        self.json_calls: list[dict[str, object]] = []

    async def upload_document(
        self,
        *,
        workspace_key: str,
        filename: str,
        content: bytes,
        content_type: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        self.upload_calls.append(
            {
                'workspace_key': workspace_key,
                'filename': filename,
                'content': content,
                'content_type': content_type,
                'extra_headers': extra_headers,
            }
        )
        return {'workspace_key': workspace_key, 'filename': filename}

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        workspace_key: str,
        payload: object = None,
        params: dict[str, object] | None = None,
    ) -> dict[str, object]:
        self.json_calls.append(
            {
                'method': method,
                'path': path,
                'workspace_key': workspace_key,
                'payload': payload,
                'params': params,
            }
        )
        if method == 'GET' and path == '/documents':
            return {
                'statuses': {
                    'PROCESSED': [
                        {
                            'id': 'doc-alpha',
                            'file_path': 'alpha.pdf',
                            'status': 'processed',
                            'content_summary': 'summary for alpha.pdf',
                            'metadata': {'workspace_key': workspace_key},
                        },
                        {
                            'id': 'doc-beta',
                            'file_path': 'beta.pdf',
                            'status': 'processed',
                            'content_summary': 'summary for beta.pdf',
                            'metadata': {'workspace_key': workspace_key},
                        },
                    ]
                }
            }
        if method == 'GET' and path in {'/documents/doc-alpha/detail', '/documents/doc-beta/detail'}:
            return {
                'id': path.split('/')[-2],
                'file_path': 'alpha.pdf' if 'alpha' in path else 'beta.pdf',
                'status': 'processed',
                'content_summary': 'detail summary',
                'full_content': 'full content body',
                'chunks': [
                    {
                        'chunk_id': 'chunk-1',
                        'content': 'chunk content',
                        'file_path': 'alpha.pdf' if 'alpha' in path else 'beta.pdf',
                        'reference_id': '1',
                    }
                ],
                'metadata': {'workspace_key': workspace_key},
            }
        return {
            'method': method,
            'path': path,
            'workspace_key': workspace_key,
            'payload': payload,
            'params': params,
        }

    async def get_health(self, *, workspace_key: str) -> dict[str, object]:
        return {'workspace_key': workspace_key, 'status': 'ok'}


class ProjectKnowledgeServiceIntegrationTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.engine = create_engine('sqlite+pysqlite:///:memory:')
        create_core_tables(self.engine)
        self.session_factory = build_session_factory(self.engine)
        self.upstream = _RecordingKnowledgeUpstream()
        self.service = ProjectKnowledgeService(
            session_factory=self.session_factory,
            upstream=self.upstream,
            service_base_url='http://knowledge.test',
        )

        with session_scope(self.session_factory) as session:
            repository = SqlAlchemyProjectsRepository(session)
            tenant = repository.get_or_create_default_tenant()
            self.project_a = repository.create_project(
                tenant_id=tenant.id,
                name='Project A',
                description='knowledge-a',
            )
            self.project_b = repository.create_project(
                tenant_id=tenant.id,
                name='Project B',
                description='knowledge-b',
            )

        self.editor_actor = ActorContext(
            user_id='editor-1',
            project_roles={
                str(self.project_a.id): ('project_editor',),
                str(self.project_b.id): ('project_editor',),
            },
        )
        self.admin_actor = ActorContext(
            user_id='admin-1',
            project_roles={
                str(self.project_a.id): ('project_admin',),
            },
        )
        self.executor_actor = ActorContext(
            user_id='executor-1',
            project_roles={
                str(self.project_a.id): ('project_executor',),
            },
        )

    async def test_project_scoped_requests_keep_distinct_workspace_keys(self) -> None:
        query = ProjectKnowledgeQueryRequest(query='how does auth work?')
        page = DocumentsPageQuery()

        await self.service.upload_document(
            actor=self.editor_actor,
            project_id=str(self.project_a.id),
            filename='alpha.pdf',
            content=b'alpha',
            content_type='application/pdf',
        )
        await self.service.list_documents_paginated(
            actor=self.editor_actor,
            project_id=str(self.project_a.id),
            query=page,
        )
        await self.service.get_scan_progress(
            actor=self.editor_actor,
            project_id=str(self.project_a.id),
        )
        await self.service.query(
            actor=self.editor_actor,
            project_id=str(self.project_a.id),
            request=query,
        )
        await self.service.get_document_detail(
            actor=self.editor_actor,
            project_id=str(self.project_a.id),
            document_id='doc-alpha',
        )
        await self.service.reprocess_failed_documents(
            actor=self.editor_actor,
            project_id=str(self.project_a.id),
        )
        await self.service.cancel_pipeline(
            actor=self.editor_actor,
            project_id=str(self.project_a.id),
        )
        await self.service.list_popular_graph_labels(
            actor=self.editor_actor,
            project_id=str(self.project_a.id),
            limit=5,
        )
        await self.service.get_graph(
            actor=self.editor_actor,
            project_id=str(self.project_a.id),
            label='Auth',
            max_depth=2,
            max_nodes=20,
        )
        await self.service.delete_document(
            actor=self.editor_actor,
            project_id=str(self.project_a.id),
            document_id='doc-alpha',
        )

        await self.service.upload_document(
            actor=self.editor_actor,
            project_id=str(self.project_b.id),
            filename='beta.pdf',
            content=b'beta',
            content_type='application/pdf',
        )
        await self.service.list_documents_paginated(
            actor=self.editor_actor,
            project_id=str(self.project_b.id),
            query=page,
        )
        await self.service.get_scan_progress(
            actor=self.editor_actor,
            project_id=str(self.project_b.id),
        )
        await self.service.query(
            actor=self.editor_actor,
            project_id=str(self.project_b.id),
            request=query,
        )
        await self.service.get_document_detail(
            actor=self.editor_actor,
            project_id=str(self.project_b.id),
            document_id='doc-beta',
        )
        await self.service.reprocess_failed_documents(
            actor=self.editor_actor,
            project_id=str(self.project_b.id),
        )
        await self.service.cancel_pipeline(
            actor=self.editor_actor,
            project_id=str(self.project_b.id),
        )
        await self.service.list_popular_graph_labels(
            actor=self.editor_actor,
            project_id=str(self.project_b.id),
            limit=5,
        )
        await self.service.get_graph(
            actor=self.editor_actor,
            project_id=str(self.project_b.id),
            label='Billing',
            max_depth=2,
            max_nodes=20,
        )
        await self.service.delete_document(
            actor=self.editor_actor,
            project_id=str(self.project_b.id),
            document_id='doc-beta',
        )

        workspace_a = ProjectKnowledgeService._workspace_key(self.project_a.id)
        workspace_b = ProjectKnowledgeService._workspace_key(self.project_b.id)

        self.assertNotEqual(workspace_a, workspace_b)
        self.assertEqual(
            [call['workspace_key'] for call in self.upstream.upload_calls],
            [workspace_a, workspace_b],
        )
        self.assertEqual(
            [call['workspace_key'] for call in self.upstream.json_calls],
            [
                workspace_a,
                workspace_a,
                workspace_a,
                workspace_a,
                workspace_a,
                workspace_a,
                workspace_a,
                workspace_a,
                workspace_a,
                workspace_b,
                workspace_b,
                workspace_b,
                workspace_b,
                workspace_b,
                workspace_b,
                workspace_b,
                workspace_b,
                workspace_b,
            ],
        )

    async def test_knowledge_operation_permission_prechecks_match_backend_policy(self) -> None:
        await self.service.authorize_scan_submission(
            actor=self.editor_actor,
            project_id=str(self.project_a.id),
        )

        with self.assertRaises(ForbiddenError):
            await self.service.authorize_scan_submission(
                actor=self.executor_actor,
                project_id=str(self.project_a.id),
            )

        await self.service.authorize_clear_submission(
            actor=self.admin_actor,
            project_id=str(self.project_a.id),
        )

        with self.assertRaises(ForbiddenError):
            await self.service.authorize_clear_submission(
                actor=self.editor_actor,
                project_id=str(self.project_a.id),
            )

    async def test_documents_status_filter_is_normalized_for_upstream_contract(self) -> None:
        await self.service.list_documents_paginated(
            actor=self.editor_actor,
            project_id=str(self.project_a.id),
            query=DocumentsPageQuery(status_filter='FAILED'),
        )

        latest_call = self.upstream.json_calls[-1]
        self.assertEqual(latest_call['path'], '/documents/paginated')
        self.assertEqual(latest_call['payload']['status_filter'], 'failed')

    async def test_clear_documents_requires_admin_during_worker_execution(self) -> None:
        with self.assertRaises(ForbiddenError):
            await self.service.clear_documents(
                actor=self.editor_actor,
                project_id=str(self.project_a.id),
            )

        result = await self.service.clear_documents(
            actor=self.admin_actor,
            project_id=str(self.project_a.id),
        )
        self.assertEqual(result['method'], 'DELETE')
        self.assertEqual(result['path'], '/documents')

    async def test_generic_operation_submit_enforces_knowledge_specific_permissions(self) -> None:
        operations_service = OperationsService(session_factory=self.session_factory)

        submitted_scan = await operations_service.submit_operation(
            actor=self.editor_actor,
            command=CreateOperationCommand(
                kind='knowledge.documents.scan',
                project_id=str(self.project_a.id),
            ),
        )
        self.assertEqual(submitted_scan.kind, 'knowledge.documents.scan')

        with self.assertRaises(ForbiddenError):
            await operations_service.submit_operation(
                actor=self.executor_actor,
                command=CreateOperationCommand(
                    kind='knowledge.documents.scan',
                    project_id=str(self.project_a.id),
                ),
            )

        with self.assertRaises(ForbiddenError):
            await operations_service.submit_operation(
                actor=self.editor_actor,
                command=CreateOperationCommand(
                    kind='knowledge.documents.clear',
                    project_id=str(self.project_a.id),
                ),
            )

        submitted_clear = await operations_service.submit_operation(
            actor=self.admin_actor,
            command=CreateOperationCommand(
                kind='knowledge.documents.clear',
                project_id=str(self.project_a.id),
            ),
        )
        self.assertEqual(submitted_clear.kind, 'knowledge.documents.clear')

    async def test_operation_routes_require_knowledge_precheck_before_submit(self) -> None:
        calls: list[str] = []

        async def authorize_scan_submission(*, actor: ActorContext, project_id: str) -> None:
            calls.append(f'scan-auth:{project_id}:{actor.user_id}')

        async def authorize_clear_submission(*, actor: ActorContext, project_id: str) -> None:
            calls.append(f'clear-auth:{project_id}:{actor.user_id}')

        async def submit_operation(*, actor: ActorContext, command: object) -> dict[str, object]:
            calls.append(f'submit:{getattr(command, "kind", "?")}:{actor.user_id}')
            return {'id': str(uuid4())}

        request = SimpleNamespace(state=SimpleNamespace())
        knowledge_service = SimpleNamespace(
            authorize_scan_submission=authorize_scan_submission,
            authorize_clear_submission=authorize_clear_submission,
        )
        operations_service = SimpleNamespace(submit_operation=submit_operation)

        await scan_project_knowledge_documents(
            request=request,
            project_id='project-scan',
            actor=self.editor_actor,
            knowledge_service=knowledge_service,
            operations_service=operations_service,
        )
        await clear_project_knowledge_documents(
            request=request,
            project_id='project-clear',
            actor=self.admin_actor,
            knowledge_service=knowledge_service,
            operations_service=operations_service,
        )

        self.assertEqual(request.state.audit_project_id, 'project-clear')
        self.assertEqual(
            calls,
            [
                'scan-auth:project-scan:editor-1',
                'submit:knowledge.documents.scan:editor-1',
                'clear-auth:project-clear:admin-1',
                'submit:knowledge.documents.clear:admin-1',
            ],
        )


if __name__ == '__main__':
    unittest.main()
