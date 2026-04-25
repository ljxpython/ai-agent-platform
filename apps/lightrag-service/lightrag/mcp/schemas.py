from __future__ import annotations

from pydantic import BaseModel, Field


class CitationRecord(BaseModel):
    document_id: str | None = Field(default=None)
    file_path: str | None = Field(default=None)
    filename: str | None = Field(default=None)
    chunk_id: str | None = Field(default=None)
    page_index: int | None = Field(default=None)
    snippet: str | None = Field(default=None)


class QueryProjectKnowledgeResponse(BaseModel):
    project_id: str
    query: str
    mode: str
    answer: str
    matched_document_ids: list[str] = Field(default_factory=list)
    citations: list[CitationRecord] = Field(default_factory=list)
    timing_ms: int | None = None


class ProjectKnowledgeDocumentSummary(BaseModel):
    document_id: str
    file_path: str | None = None
    filename: str | None = None
    overall_status: str
    track_id: str | None = None
    chunks_count: int | None = None
    updated_at: str | None = None
    last_error: str | None = None


class ListProjectKnowledgeDocumentsResponse(BaseModel):
    project_id: str
    count: int
    documents: list[ProjectKnowledgeDocumentSummary] = Field(default_factory=list)


class ProjectKnowledgeDocumentStatusResponse(BaseModel):
    project_id: str
    document_id: str
    overall_status: str
    file_path: str | None = None
    filename: str | None = None
    track_id: str | None = None
    chunks_count: int | None = None
    updated_at: str | None = None
    last_error: str | None = None
