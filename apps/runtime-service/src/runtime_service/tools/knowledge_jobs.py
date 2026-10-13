"""Project upload receipts are projected before MCP Adapter conversion."""

import json
from typing import Annotated, Literal

from mcp.types import CallToolResult, TextContent
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    model_validator,
)

from runtime_service.runtime.mcp_config import KNOWLEDGE_JOB_TOOL, KNOWLEDGE_SUBMIT_TOOL

JOB_TOOL = KNOWLEDGE_JOB_TOOL
SUBMIT_TOOL = KNOWLEDGE_SUBMIT_TOOL

ERROR_CODES = frozenset(
    {
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
    }
)


class JobReceipt(BaseModel):
    model_config = ConfigDict(extra="ignore")
    version: Literal[1]
    job_id: Annotated[str, Field(pattern=r"^kj_[a-f0-9]{32}$")] | None
    document_id: Annotated[str, Field(pattern=r"^kd_[a-f0-9]{32}$")]
    file_name: Annotated[
        str, Field(min_length=1, max_length=200, pattern=r"^[^/\\\x00-\x1f\x7f]+$")
    ]
    status: Literal["queued", "parsing", "indexing", "publishing", "ready", "failed"]
    searchable: StrictBool
    error_code: str | None
    created_at: AwareDatetime
    updated_at: AwareDatetime
    reused: StrictBool | None = None

    @model_validator(mode="after")
    def valid_receipt(self):
        if self.error_code is not None and self.error_code not in ERROR_CODES:
            raise ValueError("unsafe_knowledge_error")
        if (self.status == "failed") != (
            self.error_code is not None
        ) or self.updated_at < self.created_at:
            raise ValueError("invalid_knowledge_job")
        if self.job_id is None and not (self.status == "ready" and self.reused is True):
            raise ValueError("missing_knowledge_job")
        return self


def error_result(code):
    safe = code if code in ERROR_CODES else "knowledge_unavailable"
    return CallToolResult(
        isError=True,
        content=[TextContent(type="text", text=json.dumps({"code": safe}))],
    )


def receipt_result(payload, *, submit=False, job_id=None):
    parsed = JobReceipt.model_validate(payload)
    if (
        submit
        and parsed.reused is None
        or not submit
        and (parsed.job_id is None or job_id and parsed.job_id != job_id)
    ):
        raise ValueError("invalid_knowledge_receipt")
    safe = parsed.model_dump(mode="json")
    if not submit:
        safe.pop("reused")
    encoded = json.dumps(safe, ensure_ascii=False)
    if len(encoded.encode()) > 4096:
        raise ValueError("knowledge_receipt_too_large")
    return CallToolResult(
        content=[TextContent(type="text", text=encoded)], structuredContent=safe
    )


def project_job_result(result, *, submit=False, job_id=None):
    try:
        if (
            not isinstance(result, CallToolResult)
            or len(result.content) != 1
            or not isinstance(result.content[0], TextContent)
            or len(result.content[0].text.encode()) > 65536
        ):
            raise ValueError()
        payload = json.loads(result.content[0].text)
        if result.isError:
            return error_result(
                payload.get("code") if isinstance(payload, dict) else None
            )
        if result.structuredContent is not None and result.structuredContent != payload:
            raise ValueError()
        return receipt_result(payload, submit=submit, job_id=job_id)
    except (ValueError, TypeError, KeyError):
        return error_result("knowledge_unavailable")
