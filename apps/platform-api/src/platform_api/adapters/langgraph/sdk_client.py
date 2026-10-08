from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx
import langgraph_sdk

from platform_api.core.errors import PlatformApiError, UpstreamServiceError
from platform_api.core.errors.payload import safe_error_headers, safe_validation_details

FORWARDED_HEADER_KEYS = ("x-request-id",)

# Public Runtime codes are exact matches; unknown upstream text never becomes a client message.
_PUBLIC_CODES = {
    400: (
        "artifact_source_denied invalid_artifact_ref invalid_file_ref invalid_memory_fact "
        "invalid_skill_frontmatter invalid_skill_metadata invalid_skill_package invalid_skill_path "
        "invalid_source_thread_id invalid_workspace_cursor invalid_workspace_limit "
        "invalid_workspace_path memory_fact_required memory_query_too_long "
        "memory_setting_required reserved_public_skill_name skill_frontmatter_required skill_name_mismatch "
        "skill_package_capacity skill_security_blocked terminal_input_invalid "
        "unsafe_skill_package image_digest_mismatch image_path_invalid"
    ),
    403: (
        "dear_governance_scope_denied dear_memory_scope_denied dear_skills_scope_denied "
        "file_scope_denied file_target_denied terminal_scope_denied runtime.tool.not_allowed "
        "image_scope_denied runtime_target_denied thread_project_denied"
    ),
    404: (
        "artifact_not_found artifact_source_unavailable file_not_found memory_not_found "
        "skill_not_found terminal_not_found workspace_directory_unavailable "
        "workspace_file_unavailable workspace_not_found image_not_found"
    ),
    409: (
        "artifact_hash_mismatch dear_governance_disabled dear_skills_disabled "
        "file_content_conflict file_hash_mismatch file_workspace_unavailable "
        "memory_capacity_exceeded memory_duplicate_fact memory_expired "
        "memory_extraction_cancelled memory_maintenance_required memory_revision_conflict "
        "skill_capacity skill_name_conflict skill_revision_conflict "
        "terminal_backend_invalid terminal_disabled terminal_exited terminal_input_conflict "
        "terminal_input_sequence terminal_instance_changed terminal_offset_ahead "
        "terminal_workspace_unavailable workspace_capability_unavailable "
        "workspace_directory_changed thread_active_run_conflict run_start_in_progress "
        "idempotency_key_conflict image_content_conflict image_capability_unavailable"
    ),
    410: "cursor_expired",
    413: (
        "file_too_large html_preview_too_large presentation_size_or_type skill_package_size "
        "terminal_input_too_large workspace_directory_too_large image_too_large payload_too_large"
    ),
    415: (
        "artifact_image_type_mismatch empty_file invalid_artifact_image invalid_pdf_magic "
        "invalid_xls_magic unsupported_artifact_type unsupported_file_type workspace_not_file "
        "workspace_preview_unsupported image_type_unsupported"
    ),
    422: "damaged_pdf encrypted_pdf invalid_document invalid_presentation",
    429: "terminal_input_busy terminal_session_limit queue_full",
    503: "memory_storage_unavailable",
}
_PUBLIC_CODES[400] += " file_hash_mismatch"
_PUBLIC_CODES[409] += " message_scope_required idempotency_conflict message_id_conflict"
_PUBLIC_CODES = {status: set(codes.split()) for status, codes in _PUBLIC_CODES.items()}
_PUBLIC_MESSAGES = {
    "workspace_directory_changed": "Directory changed",
    "cursor_expired": "Event cursor expired",
    "thread_active_run_conflict": "Thread already has an active run",
    "run_start_in_progress": "Run start is in progress",
    "idempotency_key_conflict": "Idempotency key conflict",
    "runtime.tool.not_allowed": "Tool access denied",
}


def build_forward_headers(
    headers: Mapping[str, str | None],
    *,
    request_id: str | None = None,
) -> dict[str, str]:
    return {"x-request-id": request_id} if request_id else {}


def get_langgraph_client(
    *,
    base_url: str,
    api_key: str | None = None,
    forwarded_headers: Mapping[str, str] | None = None,
    timeout_seconds: float | None = None,
) -> Any:
    return langgraph_sdk.get_client(
        url=base_url,
        api_key=api_key if api_key else None,
        headers=dict(forwarded_headers or {}),
        timeout=timeout_seconds,
    )


_EXECUTION_ERROR_TYPES = frozenset(
    {
        "Exception",
        "RuntimeError",
        "RuntimeWorkspaceError",
        "ValueError",
        "TimeoutError",
        "ConnectionError",
        "RateLimitError",
        "APIStatusError",
        "APIConnectionError",
        "APITimeoutError",
        "AuthenticationError",
        "PermissionDeniedError",
        "BadRequestError",
        "NotFoundError",
        "GraphRecursionError",
        "InvalidUpdateError",
    }
)

_WORKSPACE_EXECUTION_MESSAGES = {
    "runtime.workspace.unavailable": "工作区暂不可用，本次运行已停止。",
    "runtime.workspace.execution_unavailable": "执行环境暂不可用，本次运行已停止。",
    "runtime.workspace.backend_invalid": "工作区执行配置不可用。",
    "runtime.workspace.image_invalid": "工作区执行配置不可用。",
    "runtime.workspace.execution_outcome_unknown": (
        "命令执行结果尚不确定，本次运行已停止，请先核对工作区结果。"
    ),
}


def project_execution_error(value: Any) -> Any:
    """Preserve SDK error shapes while discarding exception bodies and stacks."""
    if value is None:
        return None
    if not isinstance(value, dict):
        return (
            value
            if isinstance(value, str) and value in _WORKSPACE_EXECUTION_MESSAGES
            else "runtime.execution_failed"
        )
    code = value.get("code")
    if value.get("type") == "RuntimeWorkspaceError":
        code = code if isinstance(code, str) else value.get("message")
    elif (
        isinstance(code, str)
        and code in _WORKSPACE_EXECUTION_MESSAGES
        and value.get("message") == _WORKSPACE_EXECUTION_MESSAGES[code]
        and set(value) <= {"code", "message"}
    ):
        pass
    else:
        code = None
    known = isinstance(code, str) and code in _WORKSPACE_EXECUTION_MESSAGES
    result = {
        "message": _WORKSPACE_EXECUTION_MESSAGES[code]
        if known
        else "Runtime execution failed",
        "code": code if known else "runtime.execution_failed",
    }
    for key in ("type", "error"):
        if key in value:
            result[key] = (
                value[key]
                if isinstance(value[key], str) and value[key] in _EXECUTION_ERROR_TYPES
                else "RuntimeError"
            )
    return result


def redact_execution_fields(value: Any) -> Any:
    if not isinstance(value, dict):
        return value
    return {
        key: project_execution_error(item) if key == "error" else item
        for key, item in value.items()
        if key not in {"stack", "traceback", "body", "provider_response"}
    }


def redact_runtime_private_fields(value: Any, *, _resource: bool = True) -> Any:
    if isinstance(value, dict):
        result = dict(value)
        if _resource and "thread_id" in result and "error" in result:
            result["error"] = project_execution_error(result["error"])
        if (
            _resource
            and isinstance(result.get("tasks"), list)
            and any(key in result for key in ("values", "checkpoint", "next"))
        ):
            result["tasks"] = [
                redact_execution_fields(task) for task in result["tasks"]
            ]
        return {
            key: redact_runtime_private_fields(
                item,
                _resource=_resource
                and key
                not in {
                    "values",
                    "messages",
                    "input",
                    "output",
                    "metadata",
                    "args",
                    "content",
                    "artifact",
                    "result",
                },
            )
            for key, item in result.items()
            if not (
                str(key).startswith("_runtime_")
                or key
                in {
                    "runtime_model_ref",
                    "runtime_message_claim",
                    "authorization_ref",
                    "dear_skill_snapshot",
                    "dear_memory_source",
                }
            )
        }
    if isinstance(value, list):
        return [
            redact_runtime_private_fields(item, _resource=_resource) for item in value
        ]
    return value


def create_runtime_upstream_error(
    *,
    status_code: int,
    detail: Any,
    fallback_code: str,
    upstream_path: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> UpstreamServiceError:
    selected: Mapping[str, Any] | None = None
    if isinstance(detail, Mapping):
        for candidate in (detail.get("error"), detail.get("detail"), detail):
            if not isinstance(candidate, Mapping):
                continue
            candidate_code = candidate.get("code")
            candidate_message = candidate.get("message")
            known_code = isinstance(
                candidate_code, str
            ) and candidate_code in _PUBLIC_CODES.get(status_code, set())
            has_message = isinstance(candidate_message, str) and bool(
                candidate_message.strip()
            )
            if known_code or has_message:
                selected = candidate
                break
    raw_code = (
        selected.get("code")
        if selected is not None
        else detail
        if isinstance(detail, str)
        else None
    )
    registered = isinstance(raw_code, str) and raw_code in _PUBLIC_CODES.get(
        status_code, set()
    )
    if status_code == 401:
        public_status, code, message = (
            502,
            "runtime_delegation_rejected",
            "Runtime authentication failed",
        )
    elif status_code >= 500:
        public_status = 502
        code = (
            "memory_storage_unavailable"
            if registered and raw_code == "memory_storage_unavailable"
            else "langgraph_upstream_request_failed"
        )
        message = (
            "Memory storage unavailable"
            if code == "memory_storage_unavailable"
            else "Runtime request failed"
        )
    elif registered:
        public_status, code = status_code, raw_code
        message = _PUBLIC_MESSAGES.get(code, code.replace("_", " ").capitalize())
    else:
        public_status = status_code
        code, message = {
            403: ("forbidden", "Permission denied"),
            422: ("validation_failed", "Validation failed"),
            429: ("langgraph_upstream_rate_limited", "Runtime request rate limited"),
        }.get(status_code, (fallback_code, "Runtime request failed"))
    extra: dict[str, Any] = {}
    if code == "cursor_expired" and isinstance(detail, Mapping):
        candidates = (selected.get("extra") if selected else None, selected, detail)
        recovery = None
        for candidate in candidates:
            if isinstance(candidate, Mapping):
                nested = candidate.get("upstream_detail")
                value = (
                    nested.get("recovery")
                    if isinstance(nested, Mapping)
                    else candidate.get("recovery")
                )
                if value == "thread_snapshot":
                    recovery = value
                    break
        if recovery:
            extra["upstream_detail"] = {"recovery": recovery}
    raw_details = (
        detail
        if isinstance(detail, list)
        else (detail.get("detail") if isinstance(detail, Mapping) else None)
    )
    details = (
        safe_validation_details(raw_details)
        if status_code == 422 and isinstance(raw_details, list)
        else []
    )
    return UpstreamServiceError(
        upstream="langgraph",
        upstream_status_code=status_code,
        code=code,
        status_code=public_status,
        message=message,
        details=details,
        extra=extra,
        headers=safe_error_headers(public_status, headers, platform=False),
    )


def raise_runtime_upstream_error(exc: Exception, *, fallback_detail: str) -> None:
    if isinstance(exc, (PlatformApiError, UpstreamServiceError)):
        raise exc

    if isinstance(exc, httpx.TimeoutException):
        raise UpstreamServiceError(
            upstream="langgraph",
            status_code=504,
            code="langgraph_upstream_timeout",
            message="LangGraph upstream timed out",
        ) from exc

    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        try:
            detail: Any = response.json()
        except (ValueError, TypeError):
            detail = getattr(response, "text", None) or fallback_detail
        raise create_runtime_upstream_error(
            status_code=status_code,
            detail=detail,
            fallback_code=fallback_detail,
            headers=getattr(response, "headers", None),
        ) from exc

    if isinstance(exc, httpx.HTTPError):
        raise UpstreamServiceError(
            upstream="langgraph",
            status_code=502,
            code="langgraph_upstream_unavailable",
            message="LangGraph upstream is unavailable",
        ) from exc

    raise UpstreamServiceError(
        upstream="langgraph",
        status_code=502,
        code="langgraph_upstream_unavailable",
        message="LangGraph upstream is unavailable",
    ) from exc
