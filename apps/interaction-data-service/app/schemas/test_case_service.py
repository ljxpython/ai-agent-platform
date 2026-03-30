from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateTestCaseDocumentRequest(BaseModel):
    project_id: str
    batch_id: str | None = None
    idempotency_key: str | None = Field(default=None, max_length=255)
    filename: str = Field(min_length=1, max_length=255)
    content_type: str = Field(min_length=1, max_length=128)
    storage_path: str | None = None
    source_kind: str = Field(default="upload", min_length=1, max_length=64)
    parse_status: str = Field(default="parsed", min_length=1, max_length=64)
    summary_for_model: str = ""
    parsed_text: str | None = None
    structured_data: dict[str, Any] | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None
    error: dict[str, Any] | None = None


class TestCaseDocumentResponse(BaseModel):
    id: str
    project_id: str
    batch_id: str | None
    idempotency_key: str | None
    filename: str
    content_type: str
    storage_path: str | None
    source_kind: str
    parse_status: str
    summary_for_model: str
    parsed_text: str | None
    structured_data: dict[str, Any] | None
    provenance: dict[str, Any]
    confidence: float | None
    error: dict[str, Any] | None
    created_at: str


class TestCaseDocumentListResponse(BaseModel):
    items: list[TestCaseDocumentResponse]
    total: int


class TestCaseOverviewResponse(BaseModel):
    project_id: str | None = None
    documents_total: int
    parsed_documents_total: int
    failed_documents_total: int
    test_cases_total: int
    latest_batch_id: str | None = None
    latest_activity_at: str | None = None


class TestCaseBatchSummary(BaseModel):
    batch_id: str
    documents_count: int
    test_cases_count: int
    latest_created_at: str | None = None
    parse_status_summary: dict[str, int] = Field(default_factory=dict)


class TestCaseBatchListResponse(BaseModel):
    items: list[TestCaseBatchSummary]
    total: int


class CreateTestCaseRequest(BaseModel):
    project_id: str
    batch_id: str | None = None
    case_id: str | None = None
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    status: str = Field(default="active", min_length=1, max_length=64)
    module_name: str | None = Field(default=None, max_length=255)
    priority: str | None = Field(default=None, max_length=32)
    source_document_ids: list[str] = Field(default_factory=list)
    content_json: dict[str, Any] = Field(default_factory=dict)


class UpdateTestCaseRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: str | None = Field(default=None, min_length=1, max_length=64)
    module_name: str | None = Field(default=None, max_length=255)
    priority: str | None = Field(default=None, max_length=32)
    source_document_ids: list[str] | None = None
    content_json: dict[str, Any] | None = None


class TestCaseResponse(BaseModel):
    id: str
    project_id: str
    batch_id: str | None
    case_id: str | None
    title: str
    description: str
    status: str
    module_name: str | None
    priority: str | None
    source_document_ids: list[str]
    content_json: dict[str, Any]
    created_at: str
    updated_at: str


class TestCaseListResponse(BaseModel):
    items: list[TestCaseResponse]
    total: int
