from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class StoredAnnouncement:
    id: UUID
    title: str
    summary: str
    body: str
    tone: str
    scope_type: str
    scope_project_id: UUID | None
    status: str
    publish_at: datetime | None
    expire_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class StoredAnnouncementFeedItem:
    announcement: StoredAnnouncement
    is_read: bool


class AnnouncementsRepositoryProtocol(Protocol):
    def list_admin_announcements(
        self,
        *,
        limit: int,
        offset: int,
        query: str | None,
        status: str | None,
        scope_type: str | None,
        scope_project_id: UUID | None,
    ) -> tuple[list[StoredAnnouncement], int]: ...

    def get_announcement_by_id(self, announcement_id: UUID) -> StoredAnnouncement | None: ...

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
    ) -> StoredAnnouncement: ...

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
    ) -> StoredAnnouncement | None: ...

    def delete_announcement(self, *, announcement_id: UUID) -> None: ...

    def list_visible_announcements(
        self,
        *,
        user_id: UUID,
        project_id: UUID | None,
        now: datetime,
    ) -> list[StoredAnnouncementFeedItem]: ...

    def mark_announcement_read(
        self,
        *,
        announcement_id: UUID,
        user_id: UUID,
    ) -> datetime: ...

    def mark_all_announcements_read(
        self,
        *,
        user_id: UUID,
        project_id: UUID | None,
        now: datetime,
    ) -> int: ...
