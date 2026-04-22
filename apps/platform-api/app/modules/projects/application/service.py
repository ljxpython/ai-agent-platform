from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.core.context.models import ActorContext
from app.core.db import SqlAlchemyUnitOfWork
from app.core.errors import (
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.core.identifiers import parse_actor_user_id, parse_uuid
from app.modules.iam.application import AuthorizationRequest, IamPolicyEngine, PermissionCode
from app.modules.iam.domain import ProjectRole
from app.modules.projects.application.contracts import (
    CreateProjectCommand,
    ListProjectMembersQuery,
    ListProjectsQuery,
    UpsertProjectMemberCommand,
)
from app.modules.projects.application.ports import StoredProject, StoredProjectMemberView
from app.modules.projects.domain import (
    ProjectMemberPage,
    ProjectMemberView,
    ProjectPage,
    ProjectStatus,
    ProjectSummary,
)
from app.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository


class ProjectsService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None,
        policy_engine: IamPolicyEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._policy_engine = policy_engine or IamPolicyEngine()

    def _require_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            raise ServiceUnavailableError(
                code="platform_database_not_enabled",
                message="Platform database is not enabled",
            )
        return self._session_factory

    def _project_summary(self, project: StoredProject) -> ProjectSummary:
        return ProjectSummary(
            id=str(project.id),
            tenant_id=str(project.tenant_id),
            name=project.name,
            description=project.description,
            status=ProjectStatus(project.status),
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    def _member_view(self, item: StoredProjectMemberView) -> ProjectMemberView:
        return ProjectMemberView(
            project_id=str(item.project_id),
            user_id=str(item.user_id),
            username=item.username,
            role=item.role,
        )

    async def list_projects(
        self,
        *,
        actor: ActorContext,
        query: ListProjectsQuery,
    ) -> ProjectPage:
        session_factory = self._require_session_factory()
        actor_user_id = parse_actor_user_id(actor)
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyProjectsRepository(uow.session)
            if actor.has_platform_role("platform_super_admin"):
                items, total = repository.list_projects(
                    limit=query.limit,
                    offset=query.offset,
                    query=query.query,
                )
            else:
                items, total = repository.list_projects_for_user(
                    user_id=actor_user_id,
                    limit=query.limit,
                    offset=query.offset,
                    query=query.query,
                )
            return ProjectPage(
                items=[self._project_summary(item) for item in items],
                total=total,
            )

    async def create_project(
        self,
        *,
        actor: ActorContext,
        command: CreateProjectCommand,
    ) -> ProjectSummary:
        session_factory = self._require_session_factory()
        actor_user_id = parse_actor_user_id(actor)
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyProjectsRepository(uow.session)
            tenant = repository.get_or_create_default_tenant()
            project = repository.create_project(
                tenant_id=tenant.id,
                name=command.name.strip(),
                description=command.description.strip(),
            )
            repository.upsert_project_member(
                project_id=project.id,
                user_id=actor_user_id,
                role=ProjectRole.ADMIN,
            )
            return self._project_summary(project)

    async def delete_project(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> None:
        session_factory = self._require_session_factory()
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PROJECT_MEMBER_WRITE,
                project_id=project_id,
            ),
        )
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyProjectsRepository(uow.session)
            project = repository.get_project_by_id(project_uuid)
            if project is None or project.status == "deleted":
                raise NotFoundError(message="Project not found", code="project_not_found")
            repository.soft_delete_project(project_uuid)

    async def list_members(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        query: ListProjectMembersQuery,
    ) -> ProjectMemberPage:
        session_factory = self._require_session_factory()
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PROJECT_MEMBER_READ,
                project_id=project_id,
            ),
        )
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyProjectsRepository(uow.session)
            project = repository.get_project_by_id(project_uuid)
            if project is None or project.status == "deleted":
                raise NotFoundError(message="Project not found", code="project_not_found")
            items = repository.list_project_members(
                project_id=project_uuid,
                query=query.query,
            )
            return ProjectMemberPage(items=[self._member_view(item) for item in items])

    async def upsert_member(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        user_id: str,
        command: UpsertProjectMemberCommand,
    ) -> ProjectMemberView:
        session_factory = self._require_session_factory()
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        target_user_id = parse_uuid(user_id, code="invalid_user_id")
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PROJECT_MEMBER_WRITE,
                project_id=project_id,
            ),
        )
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyProjectsRepository(uow.session)
            project = repository.get_project_by_id(project_uuid)
            if project is None or project.status == "deleted":
                raise NotFoundError(message="Project not found", code="project_not_found")
            if not repository.user_exists(user_id=target_user_id):
                raise NotFoundError(message="User not found", code="user_not_found")

            current_role = repository.get_project_member_role(
                project_id=project_uuid,
                user_id=target_user_id,
            )
            if current_role == ProjectRole.ADMIN and command.role != ProjectRole.ADMIN:
                if repository.count_project_admins(project_id=project_uuid) <= 1:
                    raise ConflictError(
                        code="cannot_downgrade_last_admin",
                        message="Cannot downgrade the last project admin",
                    )

            item = repository.upsert_project_member(
                project_id=project_uuid,
                user_id=target_user_id,
                role=command.role,
            )
            return self._member_view(item)

    async def remove_member(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        user_id: str,
    ) -> None:
        session_factory = self._require_session_factory()
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        target_user_id = parse_uuid(user_id, code="invalid_user_id")
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PROJECT_MEMBER_WRITE,
                project_id=project_id,
            ),
        )
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyProjectsRepository(uow.session)
            project = repository.get_project_by_id(project_uuid)
            if project is None or project.status == "deleted":
                raise NotFoundError(message="Project not found", code="project_not_found")
            role = repository.get_project_member_role(
                project_id=project_uuid,
                user_id=target_user_id,
            )
            if role is None:
                raise NotFoundError(message="Member not found", code="member_not_found")
            if role == ProjectRole.ADMIN and repository.count_project_admins(project_id=project_uuid) <= 1:
                raise ConflictError(
                    code="cannot_remove_last_admin",
                    message="Cannot remove the last project admin",
                )
            repository.remove_project_member(project_id=project_uuid, user_id=target_user_id)
