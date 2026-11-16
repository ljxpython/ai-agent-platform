"""Idempotent user-requested assistant setup, using existing projects and catalog."""

from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select

from platform_api.core.errors import ForbiddenError, ServiceUnavailableError
from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
from platform_api.modules.identity.models import UserRecord
from platform_api.modules.projects.models import ProjectMemberRecord, ProjectRecord
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
from platform_api.modules.runtime_catalog.infra.sqlalchemy.models import (
    RuntimeCatalogGraphRecord,
    RuntimeCatalogModelRecord,
)
from platform_api.modules.runtime_policies.application.service import enabled_model_ids
from platform_api.modules.runtime_policies.infra.sqlalchemy.models import (
    ProjectGraphPolicyRecord,
)


def bootstrap(factory, actor, project_id=None):
    if not actor or not actor.user_id or actor.must_change_password:
        raise ForbiddenError(
            code="assistant_identity_denied", message="需要有效用户身份。"
        )
    user_id = UUID(actor.user_id)
    personal = not project_id
    project_uuid = (
        UUID(project_id)
        if project_id
        else uuid5(NAMESPACE_URL, "platform-assistant:" + actor.user_id)
    )
    with factory.begin() as session:
        user = session.scalar(
            select(UserRecord).where(UserRecord.id == user_id).with_for_update()
        )
        if not user or user.status != "active":
            raise ForbiddenError(
                code="assistant_identity_denied", message="用户已停用。"
            )
        project = session.get(ProjectRecord, project_uuid)
        if personal and project is None:
            tenant = SqlAlchemyProjectsRepository(
                session
            ).get_or_create_default_tenant()
            project = ProjectRecord(
                id=project_uuid,
                tenant_id=tenant.id,
                code="assistant-" + actor.user_id,
                name="个人助手",
                description="仅用于本人的平台助手会话与额度归属。",
            )
            session.add(project)
            session.flush()
            session.add(
                ProjectMemberRecord(
                    project_id=project_uuid, user_id=user_id, role="project_executor"
                )
            )
            session.flush()
        member = session.scalar(
            select(ProjectMemberRecord).where(
                ProjectMemberRecord.project_id == project_uuid,
                ProjectMemberRecord.user_id == user_id,
            )
        )
        if not project or project.status != "active" or not member:
            raise ForbiddenError(
                code="assistant_project_denied", message="项目不可用或成员权限已撤销。"
            )
        graph = session.scalar(
            select(RuntimeCatalogGraphRecord).where(
                RuntimeCatalogGraphRecord.graph_key == "platform_assistant",
                RuntimeCatalogGraphRecord.runtime_id == "default",
                RuntimeCatalogGraphRecord.sync_status == "ready",
                RuntimeCatalogGraphRecord.is_deleted.is_(False),
            )
        )
        if graph is None:
            raise ServiceUnavailableError(
                code="assistant_catalog_unavailable",
                message="请管理员同步 Runtime Graph 目录。",
            )
        policy = session.scalar(
            select(ProjectGraphPolicyRecord).where(
                ProjectGraphPolicyRecord.project_id == project_uuid,
                ProjectGraphPolicyRecord.graph_catalog_id == graph.id,
            )
        )
        if policy is not None and not policy.is_enabled:
            raise ForbiddenError(
                code="assistant_graph_denied", message="此项目已停用平台助手。"
            )
        model_ids = enabled_model_ids(session, project_id=project_uuid)
        models = session.scalars(
            select(RuntimeCatalogModelRecord)
            .where(RuntimeCatalogModelRecord.id.in_([UUID(x) for x in model_ids]))
            .order_by(RuntimeCatalogModelRecord.id)
        ).all()
        if not models:
            raise ServiceUnavailableError(
                code="assistant_model_unavailable", message="请管理员配置可用模型。"
            )
        model = next(
            (m for m in models if m.model_name == "deepseek-v4.1-flash"), models[0]
        )
        assistant = session.scalar(
            select(AgentRecord).where(
                AgentRecord.project_id == project_uuid,
                AgentRecord.graph_id == "platform_assistant",
            )
        )
        if assistant is None:
            assistant = AgentRecord(
                project_id=project_uuid,
                name="平台助手",
                graph_id="platform_assistant",
                description="排障、使用指导与交流",
                context={"model_id": str(model.id)},
                created_by=user_id,
                updated_by=user_id,
            )
            session.add(assistant)
            session.flush()
        if assistant.status != "active":
            raise ForbiddenError(
                code="assistant_graph_denied", message="此项目的助手已停用。"
            )
        return {
            "project_id": str(project_uuid),
            "personal_project": (project.code or "").startswith("assistant-"),
            "assistant_id": "platform_assistant",
            "agent_id": str(assistant.id),
            "model_id": assistant.context.get("model_id", str(model.id)),
            "history": True,
        }
