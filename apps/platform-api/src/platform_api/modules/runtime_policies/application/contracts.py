from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from platform_api.core.schemas import OffsetPage


from platform_api.modules.runtime_policies.domain import (
    RuntimeGraphPolicyItem,
    RuntimeGraphPolicyValue,
    RuntimeModelPolicyItem,
    RuntimeModelPolicyValue,
)


class CreateToolRestriction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    graph_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    subject_type: Literal["project", "user"]
    subject_id: UUID
    tool_name: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    reason: str = Field(min_length=1, max_length=1000)


class ToolRestrictionItem(CreateToolRestriction):
    model_config = ConfigDict(from_attributes=True, frozen=True)
    id: UUID
    project_id: UUID
    created_by: str
    created_at: datetime


class ToolRestrictionList(BaseModel):
    items: list[ToolRestrictionItem]
    total: int


class UpsertRuntimeGraphPolicyCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_enabled: bool = True
    display_order: int | None = Field(default=None, ge=0, le=100000)
    note: str | None = Field(default=None, max_length=4000)


class UpsertRuntimeModelPolicyCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_enabled: bool = True
    is_default_for_project: bool = False
    temperature_default: float | None = Field(default=None, ge=0, le=2)
    note: str | None = Field(default=None, max_length=4000)


class RuntimeGraphPolicyList(OffsetPage[RuntimeGraphPolicyItem]):
    pass


class RuntimeModelPolicyList(OffsetPage[RuntimeModelPolicyItem]):
    pass


__all__ = [
    "RuntimeGraphPolicyItem",
    "RuntimeGraphPolicyList",
    "RuntimeGraphPolicyValue",
    "RuntimeModelPolicyItem",
    "RuntimeModelPolicyList",
    "RuntimeModelPolicyValue",
    "UpsertRuntimeGraphPolicyCommand",
    "UpsertRuntimeModelPolicyCommand",
]
