from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from platform_api.core.context.models import ActorContext
from platform_api.core.db import session_scope
from platform_api.core.errors import (
    BadRequestError,
    NotFoundError,
    ServiceUnavailableError,
)
from platform_api.core.identifiers import parse_actor_user_id, parse_uuid
from platform_api.modules.announcements.contracts import (
    AnnouncementFeedQuery,
    CreateAnnouncementCommand,
    ListAnnouncementsQuery,
    UpdateAnnouncementCommand,
)
from platform_api.modules.announcements.records import StoredAnnouncement
from platform_api.modules.announcements.schemas import (
    AnnouncementItem,
    AnnouncementPage,
    AnnouncementScopeType,
    AnnouncementStatus,
    AnnouncementTone,
)
from platform_api.modules.announcements.repository import (
    SqlAlchemyAnnouncementsRepository,
)
from platform_api.modules.iam.application import (
    AuthorizationRequest,
    IamPolicyEngine,
    PermissionCode,
)
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
from platform_api.modules.service_accounts.repository import (
    SqlAlchemyServiceAccountsRepository,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class AnnouncementsService:
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

    def _announcement_item(
        self,
        row: StoredAnnouncement,
        *,
        is_read: bool,
    ) -> AnnouncementItem:
        return AnnouncementItem(
            id=str(row.id),
            title=row.title,
            summary=row.summary,
            body=row.body,
            tone=AnnouncementTone(row.tone),
            scope_type=AnnouncementScopeType(row.scope_type),
            scope_project_id=str(row.scope_project_id)
            if row.scope_project_id
            else None,
            status=AnnouncementStatus(row.status),
            publish_at=row.publish_at,
            expire_at=row.expire_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
            is_read=is_read,
        )

    def _resolve_scope_project_id(self, project_id: str | None) -> UUID | None:
        normalized = project_id.strip() if project_id and project_id.strip() else None
        if normalized is None:
            return None
        return parse_uuid(normalized, code="invalid_project_id")

    def _require_manage_access(
        self,
        *,
        actor: ActorContext,
        scope_type: AnnouncementScopeType,
        scope_project_id: str | None,
    ) -> None:
        if scope_type == AnnouncementScopeType.GLOBAL:
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PLATFORM_ANNOUNCEMENT_WRITE,
                ),
            )
            return
        if not scope_project_id:
            raise BadRequestError(
                code="scope_project_id_required",
                message="Project scope announcement requires scope_project_id",
            )
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PROJECT_ANNOUNCEMENT_WRITE,
                project_id=scope_project_id,
            ),
        )

    def _require_feed_access(
        self,
        *,
        actor: ActorContext,
        project_id: str | None,
    ) -> None:
        if not project_id:
            return
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PROJECT_ANNOUNCEMENT_READ,
                project_id=project_id,
            ),
        )

    def _actor_with_project_role(
        self,
        *,
        session: Session,
        actor: ActorContext,
        project_id: str | None,
    ) -> ActorContext:
        if not project_id or actor.project_role_set(project_id):
            return actor

        role = None
        project_uuid = self._resolve_scope_project_id(project_id)
        if actor.user_id:
            role = SqlAlchemyProjectsRepository(session).get_project_member_role(
                project_id=project_uuid,
                user_id=parse_actor_user_id(actor),
            )
        elif actor.credential_id:
            role = SqlAlchemyServiceAccountsRepository(session).get_project_grant_role(
                credential_id=actor.credential_id,
                project_id=project_uuid,
            )
        if role is None:
            return actor
        return ActorContext(
            user_id=actor.user_id,
            subject=actor.subject,
            email=actor.email,
            principal_type=actor.principal_type,
            authentication_type=actor.authentication_type,
            credential_id=actor.credential_id,
            must_change_password=actor.must_change_password,
            platform_roles=actor.platform_roles,
            project_roles={**actor.project_roles, project_id: (role.value,)},
        )

    def list_admin_announcements(
        self,
        *,
        actor: ActorContext,
        query: ListAnnouncementsQuery,
    ) -> AnnouncementPage:
        session_factory = self._require_session_factory()
        scope_project_uuid = self._resolve_scope_project_id(query.project_id)
        scope_type = AnnouncementScopeType.PROJECT if query.project_id else AnnouncementScopeType.GLOBAL
        if query.scope_type is not None and query.scope_type != scope_type:
            raise BadRequestError(code="announcement_scope_mismatch", message="Choose a project for project announcements, or clear it for global announcements")
        with session_scope(session_factory) as session:
            self._require_manage_access(
                actor=self._actor_with_project_role(session=session, actor=actor, project_id=query.project_id),
                scope_type=scope_type,
                scope_project_id=query.project_id,
            )
            repository = SqlAlchemyAnnouncementsRepository(session)
            items, total = repository.list_admin_announcements(
                limit=query.limit,
                offset=query.offset,
                query=query.query,
                status=query.status.value if query.status else None,
                scope_type=scope_type.value,
                scope_project_id=scope_project_uuid,
            )
            return AnnouncementPage(
                items=[self._announcement_item(item, is_read=False) for item in items],
                total=total,
            )

    def create_announcement(
        self,
        *,
        actor: ActorContext,
        command: CreateAnnouncementCommand,
    ) -> AnnouncementItem:
        session_factory = self._require_session_factory()
        actor_user_id = parse_actor_user_id(actor)
        scope_project_id = command.scope_project_id
        self._resolve_scope_project_id(scope_project_id) if scope_project_id else None
        self._require_manage_access(
            actor=actor,
            scope_type=command.scope_type,
            scope_project_id=scope_project_id,
        )
        publish_at = command.publish_at or _now()
        with session_scope(session_factory) as session:
            repository = SqlAlchemyAnnouncementsRepository(session)
            item = repository.create_announcement(
                title=command.title.strip(),
                summary=command.summary.strip(),
                body=command.body.strip(),
                tone=command.tone.value,
                scope_type=command.scope_type.value,
                scope_project_id=self._resolve_scope_project_id(scope_project_id),
                status=command.status.value,
                publish_at=publish_at,
                expire_at=command.expire_at,
                created_by=actor_user_id,
                updated_by=actor_user_id,
            )
            return self._announcement_item(item, is_read=False)

    def update_announcement(
        self,
        *,
        actor: ActorContext,
        announcement_id: str,
        command: UpdateAnnouncementCommand,
    ) -> AnnouncementItem:
        session_factory = self._require_session_factory()
        actor_user_id = parse_actor_user_id(actor)
        announcement_uuid = parse_uuid(announcement_id, code="invalid_announcement_id")
        with session_scope(session_factory) as session:
            repository = SqlAlchemyAnnouncementsRepository(session)
            current = repository.get_announcement_by_id(announcement_uuid)
            if current is None:
                raise NotFoundError(
                    message="Announcement not found", code="announcement_not_found"
                )

            fields_set = command.model_fields_set
            scope_type = (
                command.scope_type
                if "scope_type" in fields_set and command.scope_type is not None
                else AnnouncementScopeType(current.scope_type)
            )
            scope_project_id = (
                command.scope_project_id
                if "scope_project_id" in fields_set
                else (
                    str(current.scope_project_id) if current.scope_project_id else None
                )
            )
            if scope_type == AnnouncementScopeType.GLOBAL:
                scope_project_id = None
            if scope_project_id:
                self._resolve_scope_project_id(scope_project_id)
            current_scope_type = AnnouncementScopeType(current.scope_type)
            current_scope_project_id = (
                str(current.scope_project_id) if current.scope_project_id else None
            )
            scope_changed = (
                scope_type != current_scope_type
                or scope_project_id != current_scope_project_id
            )
            if scope_changed:
                # 迁移公告必须同时具备源和目标 scope 的管理权限，避免
                # 仅凭目标项目权限把别的项目内容搬过来。
                self._require_manage_access(
                    actor=self._actor_with_project_role(
                        session=session,
                        actor=actor,
                        project_id=current_scope_project_id,
                    ),
                    scope_type=current_scope_type,
                    scope_project_id=current_scope_project_id,
                )
            self._require_manage_access(
                actor=self._actor_with_project_role(
                    session=session,
                    actor=actor,
                    project_id=scope_project_id,
                ),
                scope_type=scope_type,
                scope_project_id=scope_project_id,
            )
            if scope_changed:
                raise BadRequestError(
                    code="announcement_scope_immutable",
                    message="Announcement scope cannot be changed by editing; create an announcement in the intended scope",
                )
            updated = repository.update_announcement(
                announcement_id=announcement_uuid,
                title=command.title.strip()
                if "title" in fields_set and isinstance(command.title, str)
                else current.title,
                summary=command.summary.strip()
                if "summary" in fields_set and isinstance(command.summary, str)
                else current.summary,
                body=command.body.strip()
                if "body" in fields_set and isinstance(command.body, str)
                else current.body,
                tone=(
                    command.tone
                    if "tone" in fields_set and command.tone is not None
                    else AnnouncementTone(current.tone)
                ).value,
                scope_type=scope_type.value,
                scope_project_id=self._resolve_scope_project_id(scope_project_id)
                if scope_project_id
                else None,
                status=(
                    command.status
                    if "status" in fields_set and command.status is not None
                    else AnnouncementStatus(current.status)
                ).value,
                publish_at=(
                    command.publish_at
                    if "publish_at" in fields_set and command.publish_at is not None
                    else current.publish_at or _now()
                ),
                expire_at=(
                    command.expire_at
                    if "expire_at" in fields_set
                    else current.expire_at
                ),
                updated_by=actor_user_id,
            )
            if updated is None:
                raise NotFoundError(
                    message="Announcement not found", code="announcement_not_found"
                )
            return self._announcement_item(updated, is_read=False)

    def delete_announcement(
        self,
        *,
        actor: ActorContext,
        announcement_id: str,
    ) -> None:
        session_factory = self._require_session_factory()
        announcement_uuid = parse_uuid(announcement_id, code="invalid_announcement_id")
        with session_scope(session_factory) as session:
            repository = SqlAlchemyAnnouncementsRepository(session)
            current = repository.get_announcement_by_id(announcement_uuid)
            if current is None:
                raise NotFoundError(
                    message="Announcement not found", code="announcement_not_found"
                )
            self._require_manage_access(
                actor=actor,
                scope_type=AnnouncementScopeType(current.scope_type),
                scope_project_id=str(current.scope_project_id)
                if current.scope_project_id
                else None,
            )
            repository.delete_announcement(announcement_id=announcement_uuid)

    def feed(
        self,
        *,
        actor: ActorContext,
        query: AnnouncementFeedQuery,
    ) -> AnnouncementPage:
        session_factory = self._require_session_factory()
        actor_user_id = parse_actor_user_id(actor)
        self._require_feed_access(actor=actor, project_id=query.project_id)
        project_uuid = self._resolve_scope_project_id(query.project_id)
        with session_scope(session_factory) as session:
            repository = SqlAlchemyAnnouncementsRepository(session)
            items = repository.list_visible_announcements(
                user_id=actor_user_id,
                project_id=project_uuid,
                now=_now(),
            )
            return AnnouncementPage(
                items=[
                    self._announcement_item(item.announcement, is_read=item.is_read)
                    for item in items
                ],
                total=len(items),
            )

    def mark_read(
        self,
        *,
        actor: ActorContext,
        announcement_id: str,
    ) -> datetime:
        session_factory = self._require_session_factory()
        actor_user_id = parse_actor_user_id(actor)
        announcement_uuid = parse_uuid(announcement_id, code="invalid_announcement_id")
        with session_scope(session_factory) as session:
            repository = SqlAlchemyAnnouncementsRepository(session)
            current = repository.get_announcement_by_id(announcement_uuid)
            if current is None or current.status != AnnouncementStatus.PUBLISHED.value:
                raise NotFoundError(
                    message="Announcement not found", code="announcement_not_found"
                )
            if current.scope_type == AnnouncementScopeType.PROJECT.value:
                if current.scope_project_id is None:
                    raise BadRequestError(
                        code="announcement_scope_invalid",
                        message="Project announcement scope is invalid",
                    )
                self._require_feed_access(
                    actor=actor,
                    project_id=str(current.scope_project_id),
                )
            return repository.mark_announcement_read(
                announcement_id=announcement_uuid,
                user_id=actor_user_id,
            )

    def mark_all_read(
        self,
        *,
        actor: ActorContext,
        query: AnnouncementFeedQuery,
    ) -> int:
        session_factory = self._require_session_factory()
        actor_user_id = parse_actor_user_id(actor)
        self._require_feed_access(actor=actor, project_id=query.project_id)
        project_uuid = self._resolve_scope_project_id(query.project_id)
        with session_scope(session_factory) as session:
            repository = SqlAlchemyAnnouncementsRepository(session)
            return repository.mark_all_announcements_read(
                user_id=actor_user_id,
                project_id=project_uuid,
                now=_now(),
            )
