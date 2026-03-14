from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateUseCaseRequest(BaseModel):
    project_id: str
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    status: str = Field(default="draft", min_length=1, max_length=64)
    workflow_id: str | None = None
    snapshot_id: str | None = None
    content_json: dict[str, Any] = Field(default_factory=dict)


class UpdateUseCaseRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = Field(default=None, min_length=1, max_length=64)
    content_json: dict[str, Any] | None = None


class UseCaseResponse(BaseModel):
    id: str
    project_id: str
    workflow_id: str | None
    snapshot_id: str | None
    title: str
    description: str
    status: str
    content_json: dict[str, Any]
    created_at: str
    updated_at: str


class UseCaseListResponse(BaseModel):
    items: list[UseCaseResponse]
    total: int
