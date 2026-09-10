from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from platform_api.modules.iam.domain import ProjectRole


@dataclass(frozen=True, slots=True)
class StoredTenant:
    id: UUID
    slug: str
    name: str
    status: str


@dataclass(frozen=True, slots=True)
class StoredProject:
    id: UUID
    tenant_id: UUID
    name: str
    description: str
    status: str
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class StoredProjectMemberView:
    project_id: UUID
    user_id: UUID
    username: str
    role: ProjectRole


@dataclass(frozen=True, slots=True)
class StoredProjectMemberCandidate:
    user_id: UUID
    username: str
    email: str | None
