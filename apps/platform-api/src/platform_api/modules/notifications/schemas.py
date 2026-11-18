from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class NotificationLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class NotificationCategory(StrEnum):
    AGENT_RUN = "agent_run"
    BUDGET = "budget"
    EVAL = "eval"
    SYSTEM = "system"


class NotificationStatus(StrEnum):
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"


class ChannelType(StrEnum):
    FEISHU = "feishu"
    DINGTALK = "dingtalk"
    WECHAT = "wechat"
    EMAIL = "email"
    WEBHOOK = "webhook"


class NotificationItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recipient_user_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    title: str
    content: str
    level: NotificationLevel
    category: NotificationCategory
    status: NotificationStatus
    action_url: str | None = None
    extra_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    read_at: datetime | None = None


class NotificationPage(BaseModel):
    items: list[NotificationItem]
    total: int
    unread_count: int
    limit: int
    offset: int


class UnreadCountResponse(BaseModel):
    unread_count: int


class NotificationChannelItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    project_ids: list[uuid.UUID] = Field(default_factory=list)
    channel_type: ChannelType
    endpoint_url: str
    secret_token: str | None = None
    is_enabled: bool
    subscribed_events: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CreateChannelRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    project_ids: list[uuid.UUID] = Field(default_factory=list)
    channel_type: ChannelType = ChannelType.FEISHU
    endpoint_url: str = Field(min_length=1)
    secret_token: str | None = None
    is_enabled: bool = True
    subscribed_events: list[str] = Field(
        default_factory=lambda: ["agent_error", "budget_exceeded", "eval_degraded"]
    )


class UpdateChannelRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    project_ids: list[uuid.UUID] | None = None
    endpoint_url: str | None = None
    secret_token: str | None = None
    is_enabled: bool | None = None
    subscribed_events: list[str] | None = None


class TestChannelResponse(BaseModel):
    success: bool
    channel_id: uuid.UUID
    channel_name: str
    message: str


class AlertIncomingPayload(BaseModel):
    source: str = Field(min_length=1, max_length=64)
    alert_type: str = Field(min_length=1, max_length=64)
    target_id: str = Field(min_length=1, max_length=128)
    level: NotificationLevel = NotificationLevel.WARNING
    summary: str = Field(min_length=1, max_length=512)
    project_id: uuid.UUID | None = None
    recipient_user_id: uuid.UUID | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    action_url: str | None = None
