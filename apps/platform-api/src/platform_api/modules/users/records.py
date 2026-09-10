from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class StoredPlatformUser:
    id: UUID
    username: str
    email: str | None
    status: str
    is_super_admin: bool
    platform_roles: tuple[str, ...]
    created_at: datetime | None
    updated_at: datetime | None
    must_change_password: bool


@dataclass(frozen=True, slots=True)
class StoredUserProjectMembership:
    project_id: UUID
    project_name: str
    project_description: str
    project_status: str
    role: str
    joined_at: datetime | None
