from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from platform_api.modules.notifications.schemas import (
    ChannelType,
    NotificationCategory,
    NotificationLevel,
    NotificationStatus,
)


class CreateNotificationCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    recipient_user_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    content: str = ""
    level: NotificationLevel = NotificationLevel.INFO
    category: NotificationCategory = NotificationCategory.SYSTEM
    action_url: str | None = None
    extra_metadata: dict[str, Any] = Field(default_factory=dict)


class ListNotificationsQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    recipient_user_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    status: NotificationStatus | None = None
    level: NotificationLevel | None = None
    category: NotificationCategory | None = None
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class CreateChannelCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=128)
    project_id: uuid.UUID | None = None
    channel_type: ChannelType = ChannelType.FEISHU
    endpoint_url: str = Field(min_length=1)
    secret_token: str | None = None
    is_enabled: bool = True
    subscribed_events: list[str] = Field(default_factory=list)


class ListChannelsQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: uuid.UUID | None = None
    channel_type: ChannelType | None = None
    enabled_only: bool = False
