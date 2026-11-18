from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProjectionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    export_id: UUID
    event_id: UUID
    status: Literal["linked", "unavailable"]
    links: dict[str, UUID] = Field(default_factory=dict, max_length=100)
    reason: Literal["trace_missing", "run_missing", "retry_exhausted"] | None = None


class AuthorizationBatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    export_ids: list[UUID] = Field(min_length=1, max_length=1000)
