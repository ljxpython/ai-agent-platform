from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.modules.runtime_policies.domain import (
    RuntimeGraphPolicyItem,
    RuntimeGraphPolicyValue,
    RuntimeModelPolicyItem,
    RuntimeModelPolicyValue,
    RuntimeToolPolicyItem,
    RuntimeToolPolicyValue,
)


class UpsertRuntimeGraphPolicyCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_enabled: bool = True
    display_order: int | None = Field(default=None, ge=0, le=100000)
    note: str | None = Field(default=None, max_length=4000)


class UpsertRuntimeToolPolicyCommand(BaseModel):
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


class RuntimeGraphPolicyList(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[RuntimeGraphPolicyItem]
    total: int


class RuntimeToolPolicyList(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[RuntimeToolPolicyItem]
    total: int


class RuntimeModelPolicyList(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[RuntimeModelPolicyItem]
    total: int


__all__ = [
    "RuntimeGraphPolicyItem",
    "RuntimeGraphPolicyList",
    "RuntimeGraphPolicyValue",
    "RuntimeModelPolicyItem",
    "RuntimeModelPolicyList",
    "RuntimeModelPolicyValue",
    "RuntimeToolPolicyItem",
    "RuntimeToolPolicyList",
    "RuntimeToolPolicyValue",
    "UpsertRuntimeGraphPolicyCommand",
    "UpsertRuntimeModelPolicyCommand",
    "UpsertRuntimeToolPolicyCommand",
]

