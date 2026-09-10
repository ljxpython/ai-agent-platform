from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True, slots=True)
class StoredUser:
    id: UUID
    username: str
    external_subject: str
    email: str | None
    status: str
    password_hash: str
    is_super_admin: bool
    platform_roles: tuple[str, ...]
    must_change_password: bool
    failed_login_attempts: int
    locked_until: datetime | None


@dataclass(frozen=True, slots=True)
class StoredRefreshToken:
    token_id: str
    user_id: UUID
    expires_at: datetime
    revoked_at: datetime | None
    family_id: str
    consumed_at: datetime | None
