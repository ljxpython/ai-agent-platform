from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class StoredRuntimeModel:
    id: UUID
    display_name: str
    provider: str
    base_url: str
    protocol: str
    model_name: str
    api_key_ciphertext: str
    enabled: bool


@dataclass(frozen=True, slots=True)
class StoredRuntimeTool:
    id: UUID
    runtime_id: str
    tool_key: str
    name: str
    source: str | None
    description: str | None
    sync_status: str
    last_seen_at: datetime | None
    last_synced_at: datetime | None
    permissions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StoredRuntimeGraph:
    id: UUID
    runtime_id: str
    graph_key: str
    display_name: str | None
    description: str | None
    source_type: str
    sync_status: str
    last_seen_at: datetime | None
    last_synced_at: datetime | None
