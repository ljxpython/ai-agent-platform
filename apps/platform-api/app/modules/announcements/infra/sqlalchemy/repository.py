from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.modules.announcements.application.ports import (
    StoredAnnouncement,
    StoredAnnouncementFeedItem,
)
from app.modules.announcements.infra.sqlalchemy.models import (
    AnnouncementReadRecord,
    AnnouncementRecord,
)


def _to_announcement(record: AnnouncementRecord) -> StoredAnnouncement:
    return StoredAnnouncement(
        id=record.id,
        title=record.title,
        summary=record.summary,
        body=record.body,
        tone=record.tone,
        scope_type=record.scope_type,
        scope_project_id=record.scope_project_id,
        status=record.status,
        publish_at=record.publish_at,
        expire_at=record.expire_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


class SqlAlchemyAnnouncementsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_admin_announcements(
        self,
        *,
        limit: int,
        offset: int,
        query: str | None,
        status: str | None,
        scope_type: str | None,
        scope_project_id: UUID | None,
    ) -> tuple[list[StoredAnnouncement], int]:
        base_stmt = select(AnnouncementRecord)
        if query and query.strip():
            normalized = f"%{query.strip().lower()}%"
            base_stmt = base_stmt.where(
                func.lower(AnnouncementRecord.title).like(normalized)
                | func.lower(AnnouncementRecord.summary).like(normalized)
                | func.lower(AnnouncementRecord.body).like(normalized)
            )
        if status and status.strip():
            base_stmt = base_stmt.where(AnnouncementRecord.status == status.strip())
        if scope_type and scope_type.strip():
            base_stmt = base_stmt.where(AnnouncementRecord.scope_type == scope_type.strip())
        if scope_project_id is not None:
            base_stmt = base_stmt.where(AnnouncementRecord.scope_project_id == scope_project_id)

        stmt = (
            base_stmt.order_by(desc(AnnouncementRecord.publish_at), desc(AnnouncementRecord.created_at))
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        rows = list(self.session.scalars(stmt).all())
        total = int(self.session.scalar(count_stmt) or 0)
        return [_to_announcement(row) for row in rows], total

    def get_announcement_by_id(self, announcement_id: UUID) -> StoredAnnouncement | None:
        record = self.session.get(AnnouncementRecord, announcement_id)
        return _to_announcement(record) if record is not None else None

    def create_announcement(
        self,
        *,
        title: str,
        summary: str,
        body: str,
        tone: str,
        scope_type: str,
        scope_project_id: UUID | None,
        status: str,
        publish_at: datetime,
        expire_at: datetime | None,
        created_by: UUID | None,
        updated_by: UUID | None,
    ) -> StoredAnnouncement:
        record = AnnouncementRecord(
            title=title,
            summary=summary,
            body=body,
            tone=tone,
            scope_type=scope_type,
            scope_project_id=scope_project_id,
            status=status,
            publish_at=publish_at,
            expire_at=expire_at,
            created_by=created_by,
            updated_by=updated_by,
        )
        self.session.add(record)
        self.session.flush()
        return _to_announcement(record)

    def update_announcement(
        self,
        *,
        announcement_id: UUID,
        title: str,
        summary: str,
        body: str,
        tone: str,
        scope_type: str,
        scope_project_id: UUID | None,
        status: str,
        publish_at: datetime,
        expire_at: datetime | None,
        updated_by: UUID | None,
    ) -> StoredAnnouncement | None:
        record = self.session.get(AnnouncementRecord, announcement_id)
        if record is None:
            return None
        record.title = title
        record.summary = summary
        record.body = body
        record.tone = tone
        record.scope_type = scope_type
        record.scope_project_id = scope_project_id
        record.status = status
        record.publish_at = publish_at
        record.expire_at = expire_at
        record.updated_by = updated_by
        self.session.flush()
        return _to_announcement(record)

    def delete_announcement(self, *, announcement_id: UUID) -> None:
        record = self.session.get(AnnouncementRecord, announcement_id)
        if record is None:
            return
        self.session.delete(record)
        self.session.flush()

    def list_visible_announcements(
        self,
        *,
        user_id: UUID,
        project_id: UUID | None,
        now: datetime,
    ) -> list[StoredAnnouncementFeedItem]:
        visibility_clause = (
            AnnouncementRecord.scope_type == "global"
            if project_id is None
            else (
                (AnnouncementRecord.scope_type == "global")
                | (
                    (AnnouncementRecord.scope_type == "project")
                    & (AnnouncementRecord.scope_project_id == project_id)
                )
            )
        )
        stmt = (
            select(AnnouncementRecord)
            .where(
                AnnouncementRecord.status == "published",
                AnnouncementRecord.publish_at <= now,
                (
                    AnnouncementRecord.expire_at.is_(None)
                    | (AnnouncementRecord.expire_at >= now)
                ),
                visibility_clause,
            )
            .order_by(desc(AnnouncementRecord.publish_at), desc(AnnouncementRecord.created_at))
        )
        announcements = list(self.session.scalars(stmt).all())
        if not announcements:
            return []
        announcement_ids = [item.id for item in announcements]
        read_stmt = select(AnnouncementReadRecord.announcement_id).where(
            AnnouncementReadRecord.user_id == user_id,
            AnnouncementReadRecord.announcement_id.in_(announcement_ids),
        )
        read_ids = set(self.session.scalars(read_stmt).all())
        return [
            StoredAnnouncementFeedItem(
                announcement=_to_announcement(item),
                is_read=item.id in read_ids,
            )
            for item in announcements
        ]

    def mark_announcement_read(
        self,
        *,
        announcement_id: UUID,
        user_id: UUID,
    ) -> datetime:
        stmt = select(AnnouncementReadRecord).where(
            AnnouncementReadRecord.announcement_id == announcement_id,
            AnnouncementReadRecord.user_id == user_id,
        )
        record = self.session.scalar(stmt)
        now = datetime.now(timezone.utc)
        if record is None:
            record = AnnouncementReadRecord(
                announcement_id=announcement_id,
                user_id=user_id,
                read_at=now,
            )
            self.session.add(record)
            self.session.flush()
            return record.read_at
        record.read_at = now
        self.session.flush()
        return record.read_at

    def mark_all_announcements_read(
        self,
        *,
        user_id: UUID,
        project_id: UUID | None,
        now: datetime,
    ) -> int:
        changed = 0
        for item in self.list_visible_announcements(user_id=user_id, project_id=project_id, now=now):
            if item.is_read:
                continue
            self.mark_announcement_read(
                announcement_id=item.announcement.id,
                user_id=user_id,
            )
            changed += 1
        return changed
