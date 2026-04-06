from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RuntimeModelCatalogItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    runtime_id: str
    model_id: str
    display_name: str
    is_default: bool
    sync_status: str
    last_seen_at: datetime | None = None
    last_synced_at: datetime | None = None


class RuntimeModelCatalogList(BaseModel):
    model_config = ConfigDict(frozen=True)

    count: int
    models: list[RuntimeModelCatalogItem]
    last_synced_at: datetime | None = None


class RuntimeToolCatalogItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    runtime_id: str
    tool_key: str
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
