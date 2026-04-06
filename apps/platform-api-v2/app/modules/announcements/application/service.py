from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.core.context.models import ActorContext
from app.core.db import SqlAlchemyUnitOfWork
from app.core.errors import BadRequestError, NotAuthenticatedError, NotFoundError, PlatformApiError, ServiceUnavailableError
from app.modules.announcements.application.contracts import (
    AnnouncementFeedQuery,
    CreateAnnouncementCommand,
    ListAnnouncementsQuery,
    UpdateAnnouncementCommand,
)
from app.modules.announcements.application.ports import StoredAnnouncement
from app.modules.announcements.domain import (
    AnnouncementItem,
    AnnouncementPage,
    AnnouncementScopeType,
    AnnouncementStatus,
    AnnouncementTone,
)
from app.modules.announcements.infra.sqlalchemy.repository import SqlAlchemyAnnouncementsRepository
from app.modules.iam.application import AuthorizationRequest, IamPolicyEngine, PermissionCode


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_uuid(raw: str, *, code: str) -> UUID:
    try:
        return UUID(raw)
    except ValueError as exc:
        raise PlatformApiError(
            code=code,
            status_code=400,
            message=code.replace("_", " "),
        ) from exc


def _parse_actor_user_id(actor: ActorContext) -> UUID:
    if not actor.user_id:
        raise NotAuthenticatedError()
    return _parse_uuid(actor.user_id, code="invalid_actor_user_id")


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
            scope_project_id=str(row.scope_project_id) if row.scope_project_id else None,
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
        return _parse_uuid(normalized, code="invalid_project_id")

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

    async def list_admin_announcements(
        self,
        *,
        actor: ActorContext,
        query: ListAnnouncementsQuery,
    ) -> AnnouncementPage:
        session_factory = self._require_session_factory()
        scope_project_uuid = self._resolve_scope_project_id(query.project_id)
        if not actor.has_platform_role("platform_super_admin"):
            if not query.project_id:
                raise BadRequestError(
                    code="project_scope_required",
                    message="project_id is required for non-platform announcement management",
                )
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PROJECT_ANNOUNCEMENT_WRITE,
                    project_id=query.project_id,
                ),
            )
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyAnnouncementsRepository(uow.session)
            items, total = repository.list_admin_announcements(
                limit=query.limit,
                offset=query.offset,
                query=query.query,
                status=query.status.value if query.status else None,
                scope_type=query.scope_type.value if query.scope_type else None,
                scope_project_id=scope_project_uuid,
            )
            return AnnouncementPage(
                items=[self._announcement_item(item, is_read=False) for item in items],
                total=total,
            )

    async def create_announcement(
        self,
        *,
        actor: ActorContext,
        command: CreateAnnouncementCommand,
    ) -> AnnouncementItem:
        session_factory = self._require_session_factory()
        actor_user_id = _parse_actor_user_id(actor)
        scope_project_id = command.scope_project_id
        self._resolve_scope_project_id(scope_project_id) if scope_project_id else None
        self._require_manage_access(
            actor=actor,
            scope_type=command.scope_type,
            scope_project_id=scope_project_id,
        )
        publish_at = command.publish_at or _now()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyAnnouncementsRepository(uow.session)
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

    async def update_announcement(
        self,
        *,
        actor: ActorContext,
        announcement_id: str,
        command: UpdateAnnouncementCommand,
    ) -> AnnouncementItem:
        session_factory = self._require_session_factory()
        actor_user_id = _parse_actor_user_id(actor)
        announcement_uuid = _parse_uuid(announcement_id, code="invalid_announcement_id")
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyAnnouncementsRepository(uow.session)
            current = repository.get_announcement_by_id(announcement_uuid)
            if current is None:
                raise NotFoundError(message="Announcement not found", code="announcement_not_found")

            fields_set = command.model_fields_set
            scope_type = (
                command.scope_type
                if "scope_type" in fields_set and command.scope_type is not None
                else AnnouncementScopeType(current.scope_type)
            )
            scope_project_id = (
                command.scope_project_id
                if "scope_project_id" in fields_set
                else (str(current.scope_project_id) if current.scope_project_id else None)
            )
            if scope_type == AnnouncementScopeType.GLOBAL:
                scope_project_id = None
            if scope_project_id:
                self._resolve_scope_project_id(scope_project_id)
            self._require_manage_access(
                actor=actor,
                scope_type=scope_type,
                scope_project_id=scope_project_id,
            )
            updated = repository.update_announcement(
                announcement_id=announcement_uuid,
                title=command.title.strip() if "title" in fields_set and isinstance(command.title, str) else current.title,
                summary=command.summary.strip() if "summary" in fields_set and isinstance(command.summary, str) else current.summary,
                body=command.body.strip() if "body" in fields_set and isinstance(command.body, str) else current.body,
                tone=(
                    command.tone
                    if "tone" in fields_set and command.tone is not None
                    else AnnouncementTone(current.tone)
                ).value,
                scope_type=scope_type.value,
                scope_project_id=self._resolve_scope_project_id(scope_project_id) if scope_project_id else None,
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
                raise NotFoundError(message="Announcement not found", code="announcement_not_found")
            return self._announcement_item(updated, is_read=False)

    async def delete_announcement(
        self,
        *,
        actor: ActorContext,
        announcement_id: str,
    ) -> None:
        session_factory = self._require_session_factory()
        announcement_uuid = _parse_uuid(announcement_id, code="invalid_announcement_id")
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyAnnouncementsRepository(uow.session)
            current = repository.get_announcement_by_id(announcement_uuid)
            if current is None:
                raise NotFoundError(message="Announcement not found", code="announcement_not_found")
            self._require_manage_access(
                actor=actor,
                scope_type=AnnouncementScopeType(current.scope_type),
                scope_project_id=str(current.scope_project_id) if current.scope_project_id else None,
            )
            repository.delete_announcement(announcement_id=announcement_uuid)

    async def feed(
        self,
        *,
        actor: ActorContext,
        query: AnnouncementFeedQuery,
    ) -> AnnouncementPage:
        session_factory = self._require_session_factory()
        actor_user_id = _parse_actor_user_id(actor)
        self._require_feed_access(actor=actor, project_id=query.project_id)
        project_uuid = self._resolve_scope_project_id(query.project_id)
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyAnnouncementsRepository(uow.session)
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

    async def mark_read(
        self,
        *,
        actor: ActorContext,
        announcement_id: str,
    ) -> datetime:
        session_factory = self._require_session_factory()
        actor_user_id = _parse_actor_user_id(actor)
        announcement_uuid = _parse_uuid(announcement_id, code="invalid_announcement_id")
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyAnnouncementsRepository(uow.session)
            current = repository.get_announcement_by_id(announcement_uuid)
            if current is None or current.status != AnnouncementStatus.PUBLISHED.value:
                raise NotFoundError(message="Announcement not found", code="announcement_not_found")
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

    async def mark_all_read(
        self,
        *,
        actor: ActorContext,
        query: AnnouncementFeedQuery,
    ) -> int:
        session_factory = self._require_session_factory()
        actor_user_id = _parse_actor_user_id(actor)
        self._require_feed_access(actor=actor, project_id=query.project_id)
        project_uuid = self._resolve_scope_project_id(query.project_id)
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyAnnouncementsRepository(uow.session)
            return repository.mark_all_announcements_read(
                user_id=actor_user_id,
                project_id=project_uuid,
                now=_now(),
            )
