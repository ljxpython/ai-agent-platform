from __future__ import annotations

from typing import Any
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class AckResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool = True


class OffsetPage(BaseModel, Generic[T]):
    model_config = ConfigDict(frozen=True)

    items: list[T] = Field(default_factory=list)
    total: int = 0


class ErrorBody(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: str
    message: str
    details: list[dict[str, Any]] = Field(default_factory=list)
    extra: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    error: ErrorBody
    request_id: str | None = None
