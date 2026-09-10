from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from platform_api.core.schemas import OffsetPage


class AssistantStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class AssistantItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    project_id: str
    name: str
    description: str = ""
    graph_id: str
    status: AssistantStatus = AssistantStatus.ACTIVE
    context: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AssistantPage(OffsetPage[AssistantItem]):
    pass
