from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TestcaseOverview(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    documents_total: int = 0
    parsed_documents_total: int = 0
    failed_documents_total: int = 0
    test_cases_total: int = 0
    latest_batch_id: str | None = None
    latest_activity_at: datetime | None = None


class TestcaseRoleView(BaseModel):
    model_config = ConfigDict(frozen=True)

    project_id: str
    role: str
    can_write_testcase: bool


class TestcaseBatchSummary(BaseModel):
    model_config = ConfigDict(frozen=True)

    batch_id: str
    documents_count: int = 0
    test_cases_count: int = 0
    latest_created_at: datetime | None = None
    parse_status_summary: dict[str, int] = Field(default_factory=dict)


class TestcaseBatchPage(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[TestcaseBatchSummary] = Field(default_factory=list)
    total: int = 0


class TestcaseBatchDetailCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    case_id: str | None = None
    title: str
    status: str
    batch_id: str | None = None
    module_name: str | None = None
    priority: str | None = None
    updated_at: datetime | None = None


class TestcaseBatchDetailCasePage(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[TestcaseBatchDetailCase] = Field(default_factory=list)
    total: int = 0


class TestcaseDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    project_id: str
    batch_id: str | None = None
    filename: str
    content_type: str
    storage_path: str | None = None
    source_kind: str
    parse_status: str
    summary_for_model: str = ""
    parsed_text: str | None = None
    structured_data: dict[str, Any] | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None
    error: dict[str, Any] | None = None
    created_at: datetime


class TestcaseDocumentPage(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[TestcaseDocument] = Field(default_factory=list)
    total: int = 0


class TestcaseDocumentRelationCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    case_id: str | None = None
    title: str
    status: str
    batch_id: str | None = None


class TestcaseDocumentRelations(BaseModel):
    model_config = ConfigDict(frozen=True)

    document: TestcaseDocument
    runtime_meta: dict[str, Any] = Field(default_factory=dict)
    related_cases: list[TestcaseDocumentRelationCase] = Field(default_factory=list)
    related_cases_count: int = 0


class TestcaseCase(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    project_id: str
    batch_id: str | None = None
    case_id: str | None = None
    title: str
    description: str = ""
    status: str
    module_name: str | None = None
    priority: str | None = None
    source_document_ids: list[str] = Field(default_factory=list)
    source_documents: list[TestcaseDocument] | None = None
    missing_source_document_ids: list[str] | None = None
    content_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class TestcaseCasePage(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: list[TestcaseCase] = Field(default_factory=list)
    total: int = 0


class TestcaseBatchDetail(BaseModel):
    model_config = ConfigDict(frozen=True)

    batch: TestcaseBatchSummary
    documents: TestcaseDocumentPage
    test_cases: TestcaseBatchDetailCasePage
