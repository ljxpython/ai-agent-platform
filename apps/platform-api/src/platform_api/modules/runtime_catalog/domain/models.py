from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class PricingInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    currency: Literal["USD"] = "USD"
    basis: Literal["per_million_tokens"] = "per_million_tokens"
    input: str | None = None
    output: str | None = None
    cache_read: str | None = None
    cache_write: str | None = None
    cache_write_5m: str | None = None
    cache_write_1h: str | None = None

    @field_validator(
        "input",
        "output",
        "cache_read",
        "cache_write",
        "cache_write_5m",
        "cache_write_1h",
        mode="before",
    )
    @classmethod
    def validate_rate(cls, value):
        import re

        if value is None:
            return None
        if not isinstance(value, str) or not re.fullmatch(
            r"[0-9]{1,10}(?:\.[0-9]{1,10})?", value
        ):
            raise ValueError(
                "Price must be a nonnegative decimal string with at most 10 decimal places"
            )
        return format(Decimal(value), ".10f")


class PricingSnapshot(PricingInput):
    version: UUID
    source: Literal["configured_catalog"]
    updated_at: AwareDatetime


class RuntimeModelCatalogItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    display_name: str
    provider: str
    base_url: str
    protocol: str
    model: str
    enabled: bool
    credential_configured: bool
    context_window_tokens: int | None = None
    scope_type: str = "platform"
    project_id: str | None = None
    pricing: PricingSnapshot | None = None


class RuntimeModelCreate(BaseModel):
    provider: str
    display_name: str
    base_url: str
    protocol: str
    model: str
    api_key: str
    enabled: bool = True
    context_window_tokens: int | None = Field(default=None, gt=0, strict=True)
    scope_type: str = "platform"
    project_id: str | None = None
    pricing: PricingInput | None = None


class RuntimeModelUpdate(BaseModel):
    provider: str | None = None
    display_name: str | None = None
    base_url: str | None = None
    protocol: str | None = None
    model: str | None = None
    api_key: str | None = None
    enabled: bool | None = None
    context_window_tokens: int | None = Field(default=None, gt=0, strict=True)
    pricing: PricingInput | None = None


class RuntimeModelCatalogList(BaseModel):
    model_config = ConfigDict(frozen=True)

    count: int
    models: list[RuntimeModelCatalogItem]


class RuntimeToolCatalogItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    runtime_id: str
    tool_key: str
    graph_ids: list[str]
    name: str
    source: str = ""
    description: str = ""
    sync_status: str
    last_seen_at: datetime | None = None
    last_synced_at: datetime | None = None


class RuntimeToolCatalogList(BaseModel):
    model_config = ConfigDict(frozen=True)

    count: int
    tools: list[RuntimeToolCatalogItem]
    last_synced_at: datetime | None = None


class RuntimeGraphCatalogItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    runtime_id: str
    graph_id: str
    display_name: str
    description: str = ""
    source_type: str
    sync_status: str
    last_seen_at: datetime | None = None
    last_synced_at: datetime | None = None


class RuntimeGraphCatalogList(BaseModel):
    model_config = ConfigDict(frozen=True)

    count: int
    graphs: list[RuntimeGraphCatalogItem]
    last_synced_at: datetime | None = None


class RuntimeCatalogRefreshResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    ok: bool = True
    count: int
    last_synced_at: datetime | None = None
