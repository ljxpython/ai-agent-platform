from __future__ import annotations

from uuid import UUID

from app.core.context.models import ActorContext
from app.entrypoints.http.router import api_router
from app.modules.iam.application import AuthorizationRequest, IamPolicyEngine, PermissionCode
from app.modules.project_knowledge.application.service import ProjectKnowledgeService


def test_project_knowledge_permissions_allow_expected_roles() -> None:
    engine = IamPolicyEngine()
    actor = ActorContext(
        user_id='user-1',
        project_roles={'p-1': ('project_editor',)},
    )

    assert engine.evaluate(
        actor=actor,
        authorization=AuthorizationRequest(
            permission=PermissionCode.PROJECT_KNOWLEDGE_READ,
            project_id='p-1',
        ),
    ).allowed
    assert engine.evaluate(
        actor=actor,
        authorization=AuthorizationRequest(
            permission=PermissionCode.PROJECT_KNOWLEDGE_WRITE,
            project_id='p-1',
        ),
    ).allowed
    assert not engine.evaluate(
        actor=actor,
        authorization=AuthorizationRequest(
            permission=PermissionCode.PROJECT_KNOWLEDGE_ADMIN,
            project_id='p-1',
        ),
    ).allowed


def test_project_knowledge_router_is_registered() -> None:
    paths = {route.path for route in api_router.routes}
    assert '/api/projects/{project_id}/knowledge' in paths
    assert '/api/projects/{project_id}/knowledge/documents/upload' in paths
    assert '/api/projects/{project_id}/knowledge/query' in paths


def test_project_knowledge_upload_route_uses_header_based_filename_contract() -> None:
    upload_route = next(
        route
        for route in api_router.routes
        if route.path == '/api/projects/{project_id}/knowledge/documents/upload'
    )
    header_aliases = {param.alias for param in upload_route.dependant.header_params}

    assert 'x-knowledge-filename' in header_aliases


def test_workspace_key_derivation_is_stable() -> None:
    project_uuid = UUID('550e8400-e29b-41d4-a716-446655440000')
    assert ProjectKnowledgeService._workspace_key(project_uuid) == 'kb_550e8400e29b41d4a716446655440000'
