from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.operations.domain import (
    OperationArchiveScope,
    OperationBulkMutationResult,
    OperationPage,
    OperationStatus,
    OperationView,
)


class CreateOperationCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str = Field(min_length=1, max_length=128)
    project_id: str | None = Field(default=None, max_length=64)
    idempotency_key: str | None = Field(default=None, max_length=128)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ListOperationsQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str | None = Field(default=None, max_length=64)
    kind: str | None = Field(default=None, max_length=128)
    kinds: tuple[str, ...] = Field(default_factory=tuple)
    status: OperationStatus | None = None
    statuses: tuple[OperationStatus, ...] = Field(default_factory=tuple)
    requested_by: str | None = Field(default=None, max_length=64)
    archive_scope: OperationArchiveScope = OperationArchiveScope.EXCLUDE
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class BulkCancelOperationsCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation_ids: tuple[str, ...] = Field(default_factory=tuple, min_length=1, max_length=200)


class BulkArchiveOperationsCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation_ids: tuple[str, ...] = Field(default_factory=tuple, min_length=1, max_length=200)


class BulkRestoreOperationsCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    operation_ids: tuple[str, ...] = Field(default_factory=tuple, min_length=1, max_length=200)


__all__ = [
    "BulkArchiveOperationsCommand",
    "BulkCancelOperationsCommand",
    "BulkRestoreOperationsCommand",
    "CreateOperationCommand",
    "ListOperationsQuery",
    "OperationArchiveScope",
    "OperationBulkMutationResult",
    "OperationPage",
    "OperationStatus",
    "OperationView",
]
