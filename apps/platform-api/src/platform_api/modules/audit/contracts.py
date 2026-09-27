from __future__ import annotations

from datetime import datetime, timedelta
from unicodedata import category
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from platform_api.core.schemas import OffsetPage
from platform_api.modules.audit.schemas import AuditEvent, AuditPlane, AuditResult


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
    request_id: str | None = None
    submission_id: UUID | None = None
    thread_id: str | None = None
    run_id: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_correlation(self) -> "ListAuditEventsQuery":
        for value, limit in (
            (self.request_id, 64),
            (self.thread_id, 128),
            (self.run_id, 128),
        ):
            if value is not None and (
                not value
                or len(value) > limit
                or any(category(char) == "Cc" for char in value)
            ):
                raise ValueError("invalid audit correlation identifier")
        if self.submission_id or self.thread_id or self.run_id:
            start, end = self.created_from, self.created_to
            if (
                start is None
                or end is None
                or (start.tzinfo is None) != (end.tzinfo is None)
            ):
                raise ValueError("audit correlation query requires a time range")
            if end < start or end - start > timedelta(days=7):
                raise ValueError("audit correlation query exceeds seven days")
        return self


class AuditEventPage(OffsetPage[AuditEvent]):
    pass
