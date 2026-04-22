from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ProjectKnowledgeSpaceView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    provider: str
    display_name: str
    workspace_key: str
    status: str
    service_base_url: str
    runtime_profile_json: dict[str, Any] = Field(default_factory=dict)
    health: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
