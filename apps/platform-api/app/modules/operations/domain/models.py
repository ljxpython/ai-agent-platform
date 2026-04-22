from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.schemas import OffsetPage


class OperationStatus(StrEnum):
    SUBMITTED = "submitted"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OperationArchiveScope(StrEnum):
    EXCLUDE = "exclude"
    INCLUDE = "include"
    ONLY = "only"


class OperationView(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    kind: str
    status: OperationStatus
    requested_by: str
    tenant_id: str | None = None
    project_id: str | None = None
    idempotency_key: str | None = None
    input_payload: dict[str, Any] = Field(default_factory=dict)
    result_payload: dict[str, Any] = Field(default_factory=dict)
    error_payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    cancel_requested_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class OperationPage(OffsetPage[OperationView]):
    pass


class OperationBulkMutationResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    requested_count: int
    updated_count: int
    skipped_count: int
    updated: list[OperationView] = Field(default_factory=list)
    skipped_ids: list[str] = Field(default_factory=list)


class OperationArtifactCleanupResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    storage_backend: str
    retention_hours: int
    scanned_count: int
    removed_count: int
    missing_count: int
    bytes_reclaimed: int
