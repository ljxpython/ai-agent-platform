from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class StoredServiceAccount:
    id: UUID
    name: str
    description: str | None
    status: str
    platform_roles: tuple[str, ...]
    created_by: str | None
    updated_by: str | None
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class StoredServiceAccountToken:
    id: UUID
    service_account_id: UUID
    name: str
    token_prefix: str
    status: str
    expires_at: datetime | None
    last_used_at: datetime | None
    revoked_at: datetime | None
    created_by: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class StoredServiceAccountProjectGrant:
    id: UUID
    service_account_id: UUID
    project_id: UUID
    role: str
    created_at: datetime
    updated_at: datetime
