from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

import httpx
import langgraph_sdk

from platform_api.core.errors import PlatformApiError, UpstreamServiceError
from platform_api.core.errors.payload import safe_error_headers, safe_validation_details
from platform_api.core.runtime_contract import is_runtime_history_file_path

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
        "image_scope_denied runtime_target_denied thread_project_denied stop_scope_denied"
    ),
    404: (
        "artifact_not_found artifact_source_unavailable file_not_found memory_not_found "
        "skill_not_found terminal_not_found workspace_directory_unavailable "
        "workspace_file_unavailable workspace_not_found image_not_found stop_request_not_found"
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
        "idempotency_key_conflict image_content_conflict image_capability_unavailable thread_stopping"
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
    422: "damaged_pdf encrypted_pdf invalid_document invalid_presentation invalid_stop_cursor invalid_stop_query",
    429: "terminal_input_busy terminal_session_limit queue_full",
    503: "memory_storage_unavailable stop_storage_unavailable",
}
_PUBLIC_CODES[400] += " file_hash_mismatch"
_PUBLIC_CODES[409] += " message_scope_required idempotency_conflict message_id_conflict"
_PUBLIC_CODES[403] += " background_task_denied"
_PUBLIC_CODES[404] += " background_task_not_found"
_PUBLIC_CODES[409] += (
    " background_task_not_supported background_task_disabled background_task_idempotency_conflict"
)
_PUBLIC_CODES[422] += " invalid_background_task_cursor invalid_background_task_query"
_PUBLIC_CODES[429] += (
    " background_task_limit_reached background_task_log_capacity_reached"
)
_PUBLIC_CODES[503] += (
    " background_task_storage_unavailable background_task_control_unavailable"
)
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
        "ModelCallLimitExceededError",
        "ToolCallLimitExceededError",
        "RunTimedOut",
    }
)

_BUDGET_EXECUTION_ERRORS = {
    "GraphRecursionError": (
        "runtime_graph_step_limit_reached",
        "Graph step limit reached",
    ),
    "ModelCallLimitExceededError": (
        "runtime_model_call_limit_reached",
        "Model call limit reached",
    ),
    "ToolCallLimitExceededError": (
        "runtime_tool_call_limit_reached",
        "Tool call limit reached",
    ),
    "RunTimedOut": ("runtime_run_timeout", "Run time limit reached"),
}

_WORKSPACE_EXECUTION_MESSAGES = {
    "runtime.workspace.unavailable": "工作区暂不可用，本次运行已停止。",
    "runtime.workspace.execution_unavailable": "执行环境暂不可用，本次运行已停止。",
    "runtime.workspace.backend_invalid": "工作区执行配置不可用。",
    "runtime.workspace.image_invalid": "工作区执行配置不可用。",
    "runtime.workspace.execution_outcome_unknown": (
        "命令执行结果尚不确定，本次运行已停止，请先核对工作区结果。"
    ),
}


def project_budget_notice(value: Any) -> dict[str, Any] | None:
    if (
        not isinstance(value, dict)
        or type(value.get("version")) is not int
        or value.get("version") != 1
        or value.get("type") != "runtime_budget_notice"
    ):
        return None
    for key, maximum in (("run_id", 128), ("notice_id", 256)):
        item = value.get(key)
        if (
            not isinstance(item, str)
            or not 0 < len(item) <= maximum
            or any(c in item for c in ("\n", "\r", "/", "\\"))
        ):
            return None
    if value.get("scope") not in ("primary", "subagent"):
        return None
    combinations = {
        "model_call_limit_approaching": ("model_calls", ("run", "thread")),
        "model_call_limit_reached": ("model_calls", ("run", "thread")),
        "graph_step_limit_approaching": ("graph_supersteps", ("graph",)),
        "wrapup_started": ("seconds", ("run",)),
    }
    combination = (
        combinations.get(value.get("code"))
        if isinstance(value.get("code"), str)
        else None
    )
    if (
        combination is None
        or value.get("unit") != combination[0]
        or value.get("budget_scope") not in combination[1]
    ):
        return None
    for key in ("limit", "used", "remaining"):
        item = value.get(key)
        if item is None:
            continue
        if (
            type(item) not in (int, float)
            or item < 0
            or item > 9007199254740991
            or not math.isfinite(item)
            or (combination[0] != "seconds" and type(item) is not int)
        ):
            return None
    return {
        key: value.get(key)
        for key in (
            "version",
            "type",
            "notice_id",
            "run_id",
            "scope",
            "budget_scope",
            "code",
            "limit",
            "used",
            "remaining",
            "unit",
        )
    }


def project_execution_error(value: Any) -> Any:
    """Preserve SDK error shapes while discarding exception bodies and stacks."""
    if value is None:
        return None
    if not isinstance(value, dict):
        if isinstance(value, str):
            if value in _WORKSPACE_EXECUTION_MESSAGES:
                return value
            if "CANARY" not in value:
                if "GraphRecursionError" in value or "Recursion limit of" in value:
                    code, message = _BUDGET_EXECUTION_ERRORS["GraphRecursionError"]
                    return {
                        "message": message,
                        "code": code,
                        "type": "GraphRecursionError",
                    }
                if (
                    "ModelCallLimitExceededError" in value
                    or "Model call limit" in value
                ):
                    code, message = _BUDGET_EXECUTION_ERRORS[
                        "ModelCallLimitExceededError"
                    ]
                    return {
                        "message": message,
                        "code": code,
                        "type": "ModelCallLimitExceededError",
                    }
                if "ToolCallLimitExceededError" in value or "Tool call limit" in value:
                    code, message = _BUDGET_EXECUTION_ERRORS[
                        "ToolCallLimitExceededError"
                    ]
                    return {
                        "message": message,
                        "code": code,
                        "type": "ToolCallLimitExceededError",
                    }
                if "RunTimedOut" in value or "Run time limit" in value:
                    code, message = _BUDGET_EXECUTION_ERRORS["RunTimedOut"]
                    return {"message": message, "code": code, "type": "RunTimedOut"}
        return "Runtime execution failed"

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
    known_workspace = isinstance(code, str) and code in _WORKSPACE_EXECUTION_MESSAGES
    if known_workspace:
        result = {
            "message": _WORKSPACE_EXECUTION_MESSAGES[code],
            "code": code,
        }
    else:
        result = {
            "message": "Runtime execution failed",
            "code": "runtime_execution_failed",
        }
        error_type = value.get("type") or value.get("error")
        if isinstance(error_type, str):
            if error_type in _BUDGET_EXECUTION_ERRORS:
                code, message = _BUDGET_EXECUTION_ERRORS[error_type]
                result = {"message": message, "code": code}
            elif (
                "GraphRecursionError" in error_type
                or "Recursion limit of" in error_type
            ):
                code, message = _BUDGET_EXECUTION_ERRORS["GraphRecursionError"]
                result = {"message": message, "code": code}
            elif (
                "ModelCallLimitExceededError" in error_type
                or "Model call limit" in error_type
            ):
                code, message = _BUDGET_EXECUTION_ERRORS["ModelCallLimitExceededError"]
                result = {"message": message, "code": code}
            elif (
                "ToolCallLimitExceededError" in error_type
                or "Tool call limit" in error_type
            ):
                code, message = _BUDGET_EXECUTION_ERRORS["ToolCallLimitExceededError"]
                result = {"message": message, "code": code}
            elif "RunTimedOut" in error_type:
                code, message = _BUDGET_EXECUTION_ERRORS["RunTimedOut"]
                result = {"message": message, "code": code}
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


def redact_runtime_private_fields(
    value: Any, *, _resource: bool = True, _execution_errors: bool = True
) -> Any:
    if isinstance(value, dict):
        if value.get("type") == "runtime_budget_notice":
            return project_budget_notice(value)
        if value.get("type") == "conversation_offloading":
            return _offloading_status(value)
        if (
            _execution_errors
            and value.get("error") is not None
            and (
                value.get("event") in ("lifecycle", "failed")
                or "thread_id" in value
                and "status" in value
                or {"id", "name", "result", "interrupts"}.issubset(value)
            )
        ):
            error = value["error"]
            safe_error: Any = "runtime.execution_failed"
            if isinstance(error, dict):
                safe_error = {"message": "runtime.execution_failed"}
                category = error.get("type")
                if (
                    isinstance(category, str)
                    and len(category) <= 128
                    and category.isidentifier()
                ):
                    safe_error["type"] = category
            value = {**value, "error": safe_error}

        # CompositeBackend removes route prefixes from checkpoint file keys.
        result = {
            key: {
                path: data
                for path, data in item.items()
                if not is_runtime_history_file_path(path)
            }
            if key == "files" and isinstance(item, dict)
            else item
            for key, item in value.items()
        }
        if "runtime_budget_notice" in result:
            notice = project_budget_notice(result["runtime_budget_notice"])
            if notice is not None and notice["code"] == "model_call_limit_reached":
                result["runtime_budget_notice"] = notice
            else:
                result.pop("runtime_budget_notice")
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
            key: _offloading_status(item)
            if key == "conversation_offloading" and type(item) is not bool
            else redact_runtime_private_fields(
                item,
                _resource=_resource
                and result.get("type") != "tool"
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
                _execution_errors=_execution_errors
                and key not in {"content", "artifact", "metadata", "values", "result"},
            )
            for key, item in result.items()
            if not (
                str(key).startswith("_runtime_")
                or key
                in {
                    "__graphharbor_run_budget",
                    "runtime_model_ref",
                    "runtime_message_claim",
                    "authorization_ref",
                    "dear_skill_snapshot",
                    "dear_memory_source",
                    "_summarization_event",
                    "_summarization_session_id",
                    "remaining_steps",
                    "runtime_budget_latches",
                    "runtime_budget_wrapup",
                    "runtime_wrapup_start",
                    "runtime_wrapup_started",
                    "thread_model_call_count",
                    "run_model_call_count",
                    "thread_tool_call_count",
                    "run_tool_call_count",
                    "_platform_model_resilience",
                    "model_resilience",
                    "fallback_model_id",
                    "fallback_connection",
                    "resilience_version",
                    "runtime_prepare",
                    "platform_background_completion",
                }
            )
        }
    if isinstance(value, list):
        return [
            redact_runtime_private_fields(
                item, _resource=_resource, _execution_errors=_execution_errors
            )
            for item in value
        ]
    return value


def _offloading_status(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("type") != "conversation_offloading":
        return {}
    if value.get("status") not in (
        "started",
        "completed",
        "skipped",
        "failed",
    ) or value.get("trigger") not in ("automatic", "manual"):
        return {}
    result = {
        "type": "conversation_offloading",
        "status": value["status"],
        "trigger": value["trigger"],
    }
    for key in ("operation_id", "run_id"):
        item = value.get(key)
        if isinstance(item, str) and 0 < len(item) <= 128:
            result[key] = item
    if type(value.get("history_saved")) is bool:
        result["history_saved"] = value["history_saved"]
    if value.get("reason_code") in (
        "nothing_to_offload",
        "cancelled",
        "summary_timeout",
        "run_failed",
        "history_save_failed",
        "media_save_failed",
        "input_budget_exceeded",
        "summary_input_budget_exceeded",
    ):
        result["reason_code"] = value["reason_code"]
    return result


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
            raw_code
            if registered
            and raw_code
            in {
                "memory_storage_unavailable",
                "stop_storage_unavailable",
                "background_task_storage_unavailable",
                "background_task_control_unavailable",
            }
            else "langgraph_upstream_request_failed"
        )
        message = (
            "Memory storage unavailable"
            if code == "memory_storage_unavailable"
            else "Stop storage unavailable"
            if code == "stop_storage_unavailable"
            else "Background task unavailable"
            if code
            in {
                "background_task_storage_unavailable",
                "background_task_control_unavailable",
            }
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
