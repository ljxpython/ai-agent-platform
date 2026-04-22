from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.announcements.domain import (
    AnnouncementScopeType,
    AnnouncementStatus,
    AnnouncementTone,
)


class ListAnnouncementsQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
    query: str | None = Field(default=None, max_length=255)
    status: AnnouncementStatus | None = None
    scope_type: AnnouncementScopeType | None = None
    project_id: str | None = None


class CreateAnnouncementCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(default="", max_length=512)
    body: str = ""
    tone: AnnouncementTone = AnnouncementTone.INFO
    scope_type: AnnouncementScopeType = AnnouncementScopeType.GLOBAL
    scope_project_id: str | None = None
    status: AnnouncementStatus = AnnouncementStatus.PUBLISHED
    publish_at: datetime | None = None
    expire_at: datetime | None = None


class UpdateAnnouncementCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    title: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = Field(default=None, max_length=512)
    body: str | None = None
    tone: AnnouncementTone | None = None
    scope_type: AnnouncementScopeType | None = None
    scope_project_id: str | None = None
    status: AnnouncementStatus | None = None
    publish_at: datetime | None = None
    expire_at: datetime | None = None


class AnnouncementFeedQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str | None = None
