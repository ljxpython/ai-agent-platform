from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FeedbackBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    expected_revision: int = Field(ge=0)
    rating: Literal["positive", "negative", "withdrawn"]
    reason: Literal["incorrect", "incomplete", "unsafe", "other"] | None = None
    comment: str = Field(default="", max_length=1000)


class ExportBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    export_id: UUID
    event_id: UUID
    data_class: Literal["synthetic"]
    purpose: Literal["regression"]
    scenario: str = Field(min_length=1, max_length=12000)
    expected: str = Field(min_length=1, max_length=4000)
    synthetic_attestation: Literal[True]
    expires_in_hours: int = Field(default=24, ge=1, le=24)


class ProjectionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    export_id: UUID
    event_id: UUID
    status: Literal["linked", "unavailable"]
    links: dict[str, UUID] = Field(default_factory=dict, max_length=100)
    reason: Literal["trace_missing", "run_missing", "retry_exhausted"] | None = None


class InspectionExportBody(BaseModel):
    """Explicit per-run consent; production text remains closed in this release."""

    model_config = ConfigDict(extra="forbid")
    export_id: UUID
    thread_id: UUID
    run_id: UUID
    agent_id: UUID
    purpose: Literal["quality_inspection"]
    data_class: Literal["synthetic"]
    synthetic_attestation: Literal[True]
    input: str = Field(min_length=1, max_length=12000)
    output: str = Field(min_length=1, max_length=12000)
    allowed_fields: tuple[Literal["input"], Literal["output"]] = ("input", "output")
    judge_route: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$")
    budget_policy_version: str = Field(
        min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_.-]+$"
    )
    expires_in_hours: int = Field(default=1, ge=1, le=24)


class AuthorizationBatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    export_ids: list[UUID] = Field(min_length=1, max_length=1000)
