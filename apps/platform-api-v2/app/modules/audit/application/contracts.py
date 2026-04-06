from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.audit.domain import AuditEvent, AuditPlane, AuditResult


class ListAuditEventsQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str | None = None
    plane: AuditPlane | None = None
    action: str | None = Field(default=None, max_length=128)
    target_type: str | None = Field(default=None, max_length=128)
    target_id: str | None = Field(default=None, max_length=128)
    actor_user_id: str | None = Field(default=None, max_length=64)
    method: str | None = Field(default=None, max_length=16)
    result: AuditResult | None = None
    status_code: int | None = Field(default=None, ge=100, le=599)
    created_from: datetime | None = None
    created_to: datetime | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class AuditEventPage(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[AuditEvent]
    total: int
