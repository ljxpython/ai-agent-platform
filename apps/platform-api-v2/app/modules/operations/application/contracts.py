from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.operations.domain import OperationPage, OperationStatus, OperationView


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
    status: OperationStatus | None = None
    requested_by: str | None = Field(default=None, max_length=64)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


__all__ = [
    "CreateOperationCommand",
    "ListOperationsQuery",
    "OperationPage",
    "OperationStatus",
    "OperationView",
]
