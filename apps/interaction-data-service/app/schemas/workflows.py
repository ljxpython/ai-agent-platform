from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateRequirementDocumentRequest(BaseModel):
    project_id: str
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=128)
    storage_path: str | None = None


class CreateWorkflowRequest(BaseModel):
    project_id: str
    title: str = Field(min_length=1, max_length=255)
    summary: str = ""
    requirement_document_id: str | None = None
    workflow_type: str = Field(default="usecase_generation", min_length=1, max_length=128)
    agent_key: str = Field(default="usecase_workflow_agent", min_length=1, max_length=128)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class CreateWorkflowSnapshotRequest(BaseModel):
    status: str = Field(min_length=1, max_length=64)
    review_summary: str = ""
    deficiency_count: int = Field(default=0, ge=0)
    persistable: bool = False
    payload_json: dict[str, Any] = Field(default_factory=dict)


class CreateWorkflowReviewRequest(BaseModel):
    snapshot_id: str
    summary: str = ""
    payload_json: dict[str, Any] = Field(default_factory=dict)


class WorkflowSummaryResponse(BaseModel):
    id: str
    project_id: str
    title: str
    summary: str
    status: str
    latest_snapshot_id: str | None
    persistable: bool
    created_at: str
    updated_at: str


class WorkflowSnapshotResponse(BaseModel):
    id: str
    workflow_id: str
    version: int
    status: str
    review_summary: str
    deficiency_count: int
    payload_json: dict[str, Any]
    created_at: str


class WorkflowListResponse(BaseModel):
    items: list[WorkflowSummaryResponse]
    total: int
