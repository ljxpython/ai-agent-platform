from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from platform_api.core.schemas import OffsetPage


class AssistantStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


MODEL_RESILIENCE_KEY = "_platform_model_resilience"
RESILIENT_GRAPH_IDS = frozenset(
    {"reference_agent", "showcase_demo", "dearflow_agent", "workflow_demo"}
)


class ModelResilienceSettings(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = Field(strict=True)
    fallback_model_id: str | None
    max_attempts: int = Field(strict=True, ge=1, le=5)
    attempt_timeout_seconds: float = Field(
        strict=True, ge=1, le=900, allow_inf_nan=False
    )
    total_timeout_seconds: float = Field(
        strict=True, ge=1, le=1200, allow_inf_nan=False
    )

    @field_validator("fallback_model_id")
    @classmethod
    def catalog_id(cls, value: str | None) -> str | None:
        return str(UUID(value)) if value is not None else None

    @model_validator(mode="after")
    def budget(self) -> ModelResilienceSettings:
        if self.total_timeout_seconds < self.attempt_timeout_seconds:
            raise ValueError("total timeout must be at least the attempt timeout")
        return self

    @classmethod
    def disabled(cls) -> ModelResilienceSettings:
        return cls(
            enabled=False,
            fallback_model_id=None,
            max_attempts=3,
            attempt_timeout_seconds=600,
            total_timeout_seconds=900,
        )


def model_resilience_from_context(context: dict[str, Any]) -> ModelResilienceSettings:
    if MODEL_RESILIENCE_KEY not in context:
        return ModelResilienceSettings.disabled()
    return ModelResilienceSettings.model_validate(context[MODEL_RESILIENCE_KEY])


class AssistantItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    project_id: str
    name: str
    description: str = ""
    graph_id: str
    status: AssistantStatus = AssistantStatus.ACTIVE
    context: dict[str, Any] = Field(default_factory=dict)
    model_resilience: ModelResilienceSettings = Field(
        default_factory=ModelResilienceSettings.disabled
    )
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AssistantPage(OffsetPage[AssistantItem]):
    pass
