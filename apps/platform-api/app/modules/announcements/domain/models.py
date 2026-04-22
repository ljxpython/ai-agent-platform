from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from app.core.schemas import OffsetPage


class AnnouncementTone(StrEnum):
    INFO = "info"
    WARNING = "warning"
    SUCCESS = "success"


class AnnouncementScopeType(StrEnum):
    GLOBAL = "global"
    PROJECT = "project"


class AnnouncementStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class AnnouncementItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    summary: str = ""
    body: str = ""
    tone: AnnouncementTone = AnnouncementTone.INFO
    scope_type: AnnouncementScopeType = AnnouncementScopeType.GLOBAL
    scope_project_id: str | None = None
    status: AnnouncementStatus = AnnouncementStatus.DRAFT
    publish_at: datetime | None = None
    expire_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    is_read: bool = False


class AnnouncementPage(OffsetPage[AnnouncementItem]):
    pass
