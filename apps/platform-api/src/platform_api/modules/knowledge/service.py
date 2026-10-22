"""Fresh membership checks precede provider IO; Session never crosses an await."""

from uuid import UUID

from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from platform_api.core.errors import (
    ForbiddenError,
    NotFoundError,
    PlatformApiError,
    ServiceUnavailableError,
)
from platform_api.modules.iam.application import (
    AuthorizationRequest,
    IamPolicyEngine,
    PermissionCode,
)
from platform_api.modules.identity.actors import (
    load_service_account_actor,
    load_user_actor,
)
from platform_api.modules.knowledge.schemas import (
    KnowledgeCapabilities,
    KnowledgeDocumentPage,
    KnowledgeJob,
    KnowledgeJobPage,
)
from platform_api.modules.projects.models import ProjectRecord


def current_actor(factory, subject, credential_id, principal_type, project_id):
    if principal_type == "service_account":
        actor = load_service_account_actor(
            session_factory=factory,
            subject=subject,
            credential_id=credential_id,
            project_id=project_id,
        )
    else:
        actor = (
            load_user_actor(
                session_factory=factory, user_id=subject, project_id=project_id
            )
            if credential_id is None
            else None
        )
    if actor is None:
        raise ForbiddenError(
            code="knowledge_upload_denied", message="Knowledge access denied"
        )
    return actor


def require_scope(factory, actor, project_id, tenant_id, *, upload=False):
    if factory is None:
        raise ServiceUnavailableError(
            code="platform_database_not_enabled",
            message="Platform database unavailable",
        )
    actor = current_actor(
        factory,
        actor.user_id or actor.subject,
        actor.credential_id,
        actor.principal_type,
        project_id,
    )
    IamPolicyEngine().require(
        actor=actor,
        authorization=AuthorizationRequest(
            permission=PermissionCode.PROJECT_KNOWLEDGE_UPLOAD
            if upload
            else PermissionCode.PROJECT_KNOWLEDGE_READ,
            project_id=project_id,
        ),
    )
    with factory() as session:
        project = session.get(ProjectRecord, UUID(project_id))
        if (
            project is None
            or project.status != "active"
            or tenant_id not in {"__default", str(project.tenant_id)}
        ):
            raise NotFoundError(code="project_not_found", message="Project not found")
    return actor


class KnowledgeService:
    def __init__(self, factory, settings, client, tenant_id="__default"):
        self.factory, self.settings, self.client, self.tenant_id = (
            factory,
            settings,
            client,
            tenant_id,
        )

    async def read(self, actor, project_id, path, params=None):
        await run_in_threadpool(
            require_scope, self.factory, actor, project_id, self.tenant_id
        )
        resource = self.settings.knowledge_mcp_bindings.get(
            f"{self.tenant_id}:{project_id}"
        )
        connection = (
            self.settings.knowledge_connections.get(resource) if resource else None
        )
        if connection is not None and connection.scope != {
            "tenant_id": self.tenant_id,
            "project_id": project_id,
        }:
            raise NotFoundError(
                code="knowledge_not_found", message="Knowledge resource not found"
            )
        if connection is None and resource is None and self.settings.knowledge_secret:
            from platform_api.config import KnowledgeConnection
            from platform_api.modules.knowledge.authorization import mint_knowledge_jwt

            kb_id = "kb_" + UUID(project_id).hex
            token = mint_knowledge_jwt(
                secret=self.settings.knowledge_secret,
                tenant_id=self.tenant_id,
                project_id=project_id,
                knowledge_base_id=kb_id,
            )
            base_url = getattr(
                self.settings,
                "knowledge_gateway_base_url",
                "http://152.136.27.196:8000",
            )
            connection = KnowledgeConnection(
                base_url=base_url,
                token=token,
                scope={"tenant_id": self.tenant_id, "project_id": project_id},
                knowledge_base_id=kb_id,
            )
        if connection is None:
            if path == "capabilities":
                return KnowledgeCapabilities(
                    version=1,
                    read_enabled=False,
                    upload_enabled=False,
                    supported_mime_types=[],
                    max_file_bytes=20 * 1024 * 1024,
                    disabled_reason="knowledge_not_configured",
                )
            raise NotFoundError(
                code="knowledge_not_found", message="Knowledge resource not found"
            )
        payload = await self.client.get(connection, path, params)
        await run_in_threadpool(
            require_scope, self.factory, actor, project_id, self.tenant_id
        )
        model = (
            KnowledgeCapabilities
            if path == "capabilities"
            else KnowledgeDocumentPage
            if path == "documents"
            else KnowledgeJobPage
            if path == "jobs"
            else KnowledgeJob
        )
        try:
            result = model.model_validate(payload)
            if (
                isinstance(result, KnowledgeCapabilities)
                and not self.settings.knowledge_upload_enabled
            ):
                result.upload_enabled = False
                result.disabled_reason = "knowledge_upload_disabled"
            if isinstance(result, KnowledgeJob) and path != "jobs/" + result.job_id:
                raise ValueError("knowledge_job_mismatch")
            if isinstance(result, (KnowledgeDocumentPage, KnowledgeJobPage)) and (
                len(result.items) > params["limit"] or result.total < len(result.items)
            ):
                raise ValueError("knowledge_page_mismatch")
            return result
        except (ValidationError, ValueError, TypeError) as exc:
            raise PlatformApiError(
                code="knowledge_unavailable",
                status_code=502,
                message="Invalid knowledge response",
            ) from exc
