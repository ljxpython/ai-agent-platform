from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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
