from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AuditPlane(StrEnum):
    CONTROL_PLANE = "control_plane"
    RUNTIME_GATEWAY = "runtime_gateway"
    SYSTEM_INTERNAL = "system_internal"


class AuditResult(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AuditEvent(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    request_id: str
    plane: AuditPlane
    action: str
    target_type: str | None = None
    target_id: str | None = None
    actor_user_id: str | None = None
    actor_subject: str | None = None
    tenant_id: str | None = None
    project_id: str | None = None
    result: AuditResult
    method: str
    path: str
    status_code: int
    duration_ms: int
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
