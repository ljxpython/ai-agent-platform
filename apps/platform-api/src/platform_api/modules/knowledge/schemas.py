"""Allowlisted projections for provider responses and project member views."""

from typing import Annotated, Literal

from pydantic import (
    AliasChoices,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    model_validator,
)

from platform_api.core.schemas import OffsetPage

JobId = Annotated[str, Field(pattern=r"^kj_[a-f0-9]{32}$")]
DocumentId = Annotated[str, Field(pattern=r"^kd_[a-f0-9]{32}$")]
FileName = Annotated[
    str, Field(min_length=1, max_length=200, pattern=r"^[^/\\\x00-\x1f\x7f]+$")
]
Size = Annotated[int, Field(strict=True, ge=1, le=20 * 1024 * 1024)]
Mime = Annotated[str, Field(pattern=r"^[a-z0-9.+-]+/[a-z0-9.+-]+$", max_length=150)]
ErrorCode = Literal[
    "knowledge_upload_disabled",
    "knowledge_not_configured",
    "knowledge_unavailable",
    "knowledge_not_found",
    "knowledge_upload_denied",
    "knowledge_invalid_file_ref",
    "knowledge_unsupported_file_type",
    "knowledge_file_too_large",
    "knowledge_queue_full",
    "knowledge_quota_exceeded",
    "knowledge_processing_timeout",
    "knowledge_processing_failed",
    "knowledge_content_conflict",
    "knowledge_processing_config_changed",
    "knowledge_submission_unconfirmed",
    "knowledge_authorization_unavailable",
    "knowledge_authorization_denied",
    "knowledge_unsupported_format",
    "invalid_file_ref",
    "knowledge_upload_expired",
    "knowledge_invalid_content",
    "knowledge_retry_limit",
    "knowledge_processing_interrupted",
    "knowledge_base_changed",
    "knowledge_snapshot_invalid",
    "knowledge_path_escape",
]


class Fields(BaseModel):
    model_config = ConfigDict(extra="ignore")


class KnowledgeCapabilities(Fields):
    version: Literal[1]
    read_enabled: StrictBool = Field(
        validation_alias=AliasChoices("read_enabled", "read")
    )
    upload_enabled: StrictBool
    supported_mime_types: Annotated[list[Mime], Field(max_length=32)]
    max_file_bytes: Annotated[int, Field(strict=True, ge=1, le=20 * 1024 * 1024)]
    disabled_reason: ErrorCode | None


class KnowledgeDocument(Fields):
    document_id: DocumentId
    file_name: FileName
    mime_type: Mime
    size_bytes: Size
    status: Literal["ready"]
    searchable: Literal[True]
    published_at: AwareDatetime


class KnowledgeJob(Fields):
    version: Literal[1]
    job_id: JobId
    document_id: DocumentId
    file_name: FileName
    status: Literal["queued", "parsing", "indexing", "publishing", "ready", "failed"]
    searchable: StrictBool
    error_code: ErrorCode | None
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @model_validator(mode="after")
    def consistent_failure(self):
        if (self.status == "failed") != (self.error_code is not None):
            raise ValueError("invalid_knowledge_job_error")
        if self.updated_at < self.created_at:
            raise ValueError("invalid_knowledge_job_time")
        return self


class KnowledgeDocumentPage(OffsetPage[KnowledgeDocument]):
    items: Annotated[list[KnowledgeDocument], Field(max_length=100)]
    total: Annotated[int, Field(strict=True, ge=0)]


class KnowledgeJobPage(OffsetPage[KnowledgeJob]):
    items: Annotated[list[KnowledgeJob], Field(max_length=100)]
    total: Annotated[int, Field(strict=True, ge=0)]
