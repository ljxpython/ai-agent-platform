from __future__ import annotations

from typing import Any, Literal
from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class CreateUserRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1)
    is_super_admin: bool = False


class UpdateUserRequest(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=64)
    status: Literal["active", "disabled"] | None = None
    is_super_admin: bool | None = None
    password: str | None = Field(default=None, min_length=1)


class UpdateMeRequest(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=64)
    email: str | None = Field(default=None, max_length=255)


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="")


class UpsertMemberRequest(BaseModel):
    user_id: str
    role: str


class CreateAnnouncementRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(default="", max_length=512)
    body: str = Field(default="")
    tone: Literal["info", "warning", "success"] = "info"
    scope_type: Literal["global", "project"] = "global"
    scope_project_id: str | None = None
    status: Literal["draft", "published", "archived"] = "published"
    publish_at: datetime | None = None
    expire_at: datetime | None = None


class UpdateAnnouncementRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = Field(default=None, max_length=512)
    body: str | None = None
    tone: Literal["info", "warning", "success"] | None = None
    scope_type: Literal["global", "project"] | None = None
    scope_project_id: str | None = None
    status: Literal["draft", "published", "archived"] | None = None
    publish_at: datetime | None = None
    expire_at: datetime | None = None


class CreateAssistantRequest(BaseModel):
    graph_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="")
    assistant_id: str | None = Field(default=None, min_length=1, max_length=128)
    config: dict[str, Any] | None = None
    context: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class UpdateAssistantRequest(BaseModel):
    graph_id: str | None = Field(default=None, min_length=1, max_length=128)
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = None
    status: Literal["active", "disabled"] | None = None
    config: dict[str, Any] | None = None
    context: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class UpsertProjectGraphPolicyRequest(BaseModel):
    is_enabled: bool = True
    display_order: int | None = None
    note: str | None = None


class UpsertProjectModelPolicyRequest(BaseModel):
    is_enabled: bool = True
    is_default_for_project: bool = False
    temperature_default: float | None = None
    note: str | None = None


class UpsertProjectToolPolicyRequest(BaseModel):
    is_enabled: bool = True
    display_order: int | None = None
    note: str | None = None


class CreateTestCaseRecordRequest(BaseModel):
    batch_id: str | None = Field(default=None, max_length=255)
    case_id: str | None = Field(default=None, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    status: str = Field(default="active", min_length=1, max_length=64)
    module_name: str | None = Field(default=None, max_length=255)
    priority: str | None = Field(default=None, max_length=32)
    source_document_ids: list[str] = Field(default_factory=list)
    content_json: dict[str, Any] = Field(default_factory=dict)


class UpdateTestCaseRecordRequest(BaseModel):
    batch_id: str | None = Field(default=None, max_length=255)
    case_id: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = Field(default=None, min_length=1, max_length=64)
    module_name: str | None = Field(default=None, max_length=255)
    priority: str | None = Field(default=None, max_length=32)
    source_document_ids: list[str] | None = None
    content_json: dict[str, Any] | None = None
