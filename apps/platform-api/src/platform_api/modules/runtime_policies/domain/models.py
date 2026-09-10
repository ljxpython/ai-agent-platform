from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RuntimeGraphPolicyValue(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_enabled: bool = True
    display_order: int | None = None
    note: str | None = None
    updated_at: datetime | None = None


class RuntimeToolPolicyValue(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_enabled: bool = True
    display_order: int | None = None
    note: str | None = None
    updated_at: datetime | None = None


class RuntimeModelPolicyValue(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_enabled: bool = True
    is_default_for_project: bool = False
    temperature_default: float | None = Field(default=None, ge=0, le=2)
    note: str | None = None
    updated_at: datetime | None = None


class RuntimeGraphPolicyItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    catalog_id: str
    graph_id: str
    display_name: str
    description: str
    source_type: str
    sync_status: str
    last_synced_at: datetime | None = None
    policy: RuntimeGraphPolicyValue


class RuntimeToolPolicyItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    catalog_id: str
    tool_key: str
    name: str
    source: str
    description: str
    sync_status: str
    last_synced_at: datetime | None = None
    policy: RuntimeToolPolicyValue


class RuntimeModelPolicyItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    catalog_id: str
    model_id: str
    display_name: str
    is_default_runtime: bool
    sync_status: str
    last_synced_at: datetime | None = None
    policy: RuntimeModelPolicyValue

