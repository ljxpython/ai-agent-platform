from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    username: str
    status: str
    is_super_admin: bool
    email: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UserProjectItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    project_name: str
    project_description: str
    project_status: str
    role: str
    joined_at: datetime | None = None


class UserPage(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[UserItem]
    total: int


class UserProjectPage(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[UserProjectItem]
    total: int
