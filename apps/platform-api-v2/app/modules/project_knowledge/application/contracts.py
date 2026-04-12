from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UpdateProjectKnowledgeSpaceCommand(BaseModel):
    model_config = ConfigDict(frozen=True)

    display_name: str | None = Field(default=None, max_length=128)
    runtime_profile_json: dict[str, Any] | None = None


class DocumentsPageQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)
    status_filter: str | None = Field(default=None, max_length=32)
    sort_field: str = Field(default='updated_at', max_length=64)
    sort_direction: str = Field(default='desc', pattern='^(asc|desc)$')


class ProjectKnowledgeQueryRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    query: str = Field(min_length=1)
    mode: str | None = Field(default='mix', max_length=32)
    only_need_context: bool | None = None
    only_need_prompt: bool | None = None
    response_type: str | None = None
    top_k: int | None = Field(default=None, ge=1)
    chunk_top_k: int | None = Field(default=None, ge=1)
    max_entity_tokens: int | None = Field(default=None, ge=1)
    max_relation_tokens: int | None = Field(default=None, ge=1)
    max_total_tokens: int | None = Field(default=None, ge=1)
    hl_keywords: list[str] = Field(default_factory=list)
    ll_keywords: list[str] = Field(default_factory=list)
    conversation_history: list[dict[str, Any]] | None = None
    user_prompt: str | None = None
    enable_rerank: bool | None = None
    include_references: bool | None = True
    include_chunk_content: bool | None = False
    stream: bool | None = False
