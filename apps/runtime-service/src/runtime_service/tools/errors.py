"""Approved tool failures only; Runtime policy and unknown defects must propagate."""

from __future__ import annotations

import json
from asyncio import CancelledError
from functools import partial
from importlib.resources import files

import anyio
import httpx
from langchain_core.exceptions import ContextOverflowError, ModelInvalidRequestError
from langchain_core.tools import ToolException
from langgraph.errors import GraphBubbleUp

from runtime_service.runtime.errors import (
    BackgroundTaskNotStarted,
    RuntimeErrorBase,
    RuntimeWorkspaceError,
)

_RESEARCH = {
    "invalid_research_query",
    "research_url_denied",
    "invalid_github_query",
    "invalid_github_operation",
    "invalid_github_path",
    "invalid_arxiv_query",
    "invalid_arxiv_date_range",
}
_RESEARCH_FAILURES = {
    "research_provider_failed",
    "jina_provider_failed",
    "research_extract_failed",
    "research_response_too_large",
    "research_empty_page",
    "research_rate_limited_or_forbidden",
    "research_not_found_or_private",
    "invalid_github_response",
    "github_private_repository_denied",
    "github_default_branch_unavailable",
    "github_file_unavailable",
    "github_file_not_text",
    "invalid_arxiv_response",
    "invalid_guidelines_encoding",
    "invalid_guidelines_response",
    "research_unavailable: TAVILY_API_KEY is not configured",
    "research_unavailable: No research provider configured",
}
_FILES = {
    "invalid_query",
    "invalid_page_range",
    "invalid_csv",
    "damaged_pdf",
    "encrypted_pdf",
    "invalid_pdf_magic",
    "empty_file",
    "file_too_large",
    "unsupported_file_type",
    "invalid_xls_magic",
    "invalid_xlsx",
    "macro_workbook_denied",
    "invalid_document",
    "invalid_file_ref",
    "file_not_found",
    "invalid_artifact_ref",
    "artifact_not_found",
    "artifact_source_denied",
    "artifact_source_unavailable",
    "unsupported_artifact_type",
    "invalid_artifact_image",
    "artifact_image_type_mismatch",
    "presentation_size_or_type",
    "invalid_presentation",
    "archive_size_limit",
    "unsafe_archive_entry",
    "archive_expansion_limit",
    "empty_archive",
    "invalid_archive",
}
_SKILLS = {
    "invalid_skill_query",
    "invalid_skill_source",
    "skill_source_truncated",
    "unsafe_skill_source",
    "skill_source_size",
    "skill_package_size",
    "skill_package_capacity",
    "unsafe_skill_package",
    "invalid_skill_package",
    "skill_frontmatter_required",
    "invalid_skill_frontmatter",
    "invalid_skill_metadata",
    "skill_not_found",
    "skill_revision_conflict",
    "skill_name_conflict",
    "skill_capacity",
    "reserved_public_skill_name",
    "skill_security_blocked",
    "skill_name_mismatch",
}
_IMAGE_INPUT = {
    "Prompt must contain 1 to 8000 characters.",
    "At most 4 images and 1 to 8000 prompt characters.",
    "At most three additional reference images are supported.",
    "Question must contain 1 to 8000 characters.",
    "Image must be between 1 byte and 20 MiB.",
    "Use a valid PNG, JPEG or WebP with at most 25 million pixels.",
    "Use an image path inside /workspace/.",
    "Image file is unavailable or unsafe.",
    "Workspace path is unavailable or unsafe.",
    "image_path_invalid",
    "image_not_found",
    "image_type_unsupported",
    "image_too_large",
}
_CHART_NAMES = {
    item["name"]
    for item in json.loads(
        files(__package__).joinpath("chart-schemas.json").read_text()
    )
}

_INPUT_BY_TOOL = {
    **dict.fromkeys(
        (
            "search_web",
            "fetch_page",
            "github_query",
            "arxiv_search",
            "fetch_web_guidelines",
        ),
        _RESEARCH,
    ),
    **dict.fromkeys(("parse_document", "present_artifacts"), _FILES),
    **dict.fromkeys(("upload_skill", "update_skill", "import_skill"), _SKILLS | _FILES),
    **dict.fromkeys(
        (
            "list_skills",
            "find_skills",
            "review_skill_package",
            "set_skill_enabled",
            "delete_skill",
        ),
        _SKILLS,
    ),
    "search_memory": {"memory_query_too_long"},
    "manage_memory": {
        "memory_capacity_exceeded",
        "memory_revision_conflict",
        "memory_not_found",
        "memory_expired",
        "memory_duplicate_fact",
        "memory_fact_required",
        "invalid_memory_fact",
    },
    "analyze_image": _IMAGE_INPUT,
    **dict.fromkeys(
        ("generate_image", "edit_image"), _IMAGE_INPUT | {"invalid_external_task"}
    ),
    **dict.fromkeys(
        _CHART_NAMES,
        {"chart_invalid_input", "chart_dimension_limit", "chart_data_limit"},
    ),
    "get_media_task": {"Invalid or inaccessible media task."},
    "deploy_preview": _FILES
    | {
        "unsafe_deployment_archive",
        "deployment_manifest_mismatch",
        "deployment_private_file",
        "deployment_file_type",
        "deployment_secret_detected",
        "deployment_digest_mismatch",
    },
    "fetch_documentation": {
        "Use an HTTPS URL on docs.python.org, docs.langchain.com or reference.langchain.com.",
    },
}
_FAILURE_BY_TOOL = {
    **dict.fromkeys(
        (
            "search_web",
            "fetch_page",
            "github_query",
            "arxiv_search",
            "fetch_web_guidelines",
        ),
        _RESEARCH_FAILURES,
    ),
    "fetch_documentation": {
        "Redirects are not followed; use the final official documentation URL.",
        "Only text documentation is supported.",
        "Documentation request failed; check the URL or retry later.",
    },
    "import_skill": {"skill_source_unavailable"},
    "analyze_image": {"image_analysis_unavailable"},
    **dict.fromkeys(_CHART_NAMES, {"chart_provider_failed", "chart_image_missing"}),
}
_MESSAGES = {
    "background_task_not_supported": "当前环境不支持后台执行，本次调用未登记任务。短任务可改用 execute（默认30秒、最大60秒）；长任务请拆分或选择支持后台执行的环境。",
    "background_task_disabled": "后台新任务已关闭，本次调用未登记任务。已有任务仍可查询或取消。短任务可改用 execute（默认30秒、最大60秒）；长任务请拆分或选择支持后台执行的环境。",
    "tool.invalid_input": "工具输入不符合要求，请修正参数后继续。",
    "tool.upstream_unavailable": "工具暂时无法完成请求，请选择其他方式。",
    "tool.operation_failed": "工具未返回可用结果，请选择其他方式。",
    "tool.outcome_unknown": "操作结果尚不确定，请先核对结果，不要重复提交。",
}


def _content(
    tool_name: str, error_type: str, code: str, recovery: str, outcome: str
) -> str:
    return json.dumps(
        {
            "status": "error",
            "code": code,
            "error": _MESSAGES[code],
            "error_type": error_type,
            "name": tool_name,
            "recovery": recovery,
            "outcome": outcome,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def tool_error_content(exc: BaseException, tool_name: str) -> str | None:
    if (
        isinstance(exc, BackgroundTaskNotStarted)
        and tool_name == "background_execute"
        and exc.code in {"background_task_not_supported", "background_task_disabled"}
    ):
        return _content(
            tool_name,
            type(exc).__name__,
            exc.code,
            "use_execute_for_short_task",
            "not_started",
        )
    if isinstance(
        exc, (RuntimeErrorBase, RuntimeWorkspaceError, GraphBubbleUp, CancelledError)
    ):
        return None
    if (
        not isinstance(tool_name, str)
        or len(tool_name.encode()) > 128
        or len(type(exc).__name__.encode()) > 128
    ):
        return None
    # Preserve the reference service's explicit read-only policy, not generic ValueError handling.
    if tool_name == "read_reference" and type(exc) in (ValueError, ConnectionError):
        code = (
            "tool.invalid_input"
            if type(exc) is ValueError
            else "tool.upstream_unavailable"
        )
        return _content(
            tool_name,
            type(exc).__name__,
            code,
            "correct_input" if type(exc) is ValueError else "choose_alternative",
            "not_started" if type(exc) is ValueError else "failed",
        )
    if not isinstance(exc, ToolException):
        return None
    native_code = getattr(exc, "code", None) or (
        exc.args[0] if len(exc.args) == 1 else None
    )
    if not isinstance(native_code, str):
        return None
    if tool_name.startswith("mcp_") and native_code == "mcp_transport_unavailable":
        return _content(
            tool_name,
            type(exc).__name__,
            "tool.upstream_unavailable",
            "choose_alternative",
            "failed",
        )
    if native_code in _INPUT_BY_TOOL.get(tool_name, ()):
        return _content(
            tool_name,
            type(exc).__name__,
            "tool.invalid_input",
            "correct_input",
            "not_started",
        )
    if tool_name in {"generate_image", "edit_image"} and native_code in {
        "Image provider is not configured; no submission.",
        "external_task_capacity",
    }:
        return _content(
            tool_name,
            type(exc).__name__,
            "tool.operation_failed",
            "choose_alternative",
            "not_started",
        )
    if native_code in _FAILURE_BY_TOOL.get(tool_name, ()):
        return _content(
            tool_name,
            type(exc).__name__,
            "tool.upstream_unavailable",
            "choose_alternative",
            "failed",
        )
    if tool_name in {"generate_image", "edit_image"} and native_code in {
        "image_submission_unknown",
        "image_content_policy_violation",
    }:
        return _content(
            tool_name,
            type(exc).__name__,
            "tool.outcome_unknown",
            "do_not_repeat",
            "unknown",
        )
    if (
        tool_name in {"generate_image", "edit_image", "deploy_preview"}
        and native_code == "external_task_idempotency_conflict"
    ):
        return _content(
            tool_name,
            type(exc).__name__,
            "tool.outcome_unknown",
            "do_not_repeat",
            "unknown",
        )
    return None


def task_failure_content(exc: BaseException) -> str:
    return _content(
        "task",
        type(exc).__name__,
        "tool.upstream_unavailable",
        "choose_alternative",
        "failed",
    )


def on_tool_error(exc: Exception, request, *, readonly_roles=frozenset()) -> str | None:
    args = request.tool_call.get("args") or {}
    role = args.get("subagent_type") if isinstance(args, dict) else None
    if (
        request.tool_call["name"] == "task"
        and isinstance(role, str)
        and role in readonly_roles
    ):
        body = getattr(exc, "body", None)
        body = body.get("error", body) if isinstance(body, dict) else {}
        code = body.get("code") or body.get("type") if isinstance(body, dict) else None
        if isinstance(exc, ContextOverflowError) or (
            isinstance(exc, ModelInvalidRequestError)
            and code
            in {
                "context_length_exceeded",
                "context_window_exceeded",
                "invalid_prompt",
                "invalid_prompt_input",
            }
        ):
            return _content(
                "task",
                type(exc).__name__,
                "tool.invalid_input",
                "correct_input",
                "failed",
            )
    return tool_error_content(exc, request.tool_call["name"])


def handle_expected_tool_error(exc: ToolException, *, tool_name: str) -> str:
    content = tool_error_content(exc, tool_name)
    if content is None:
        raise exc
    return content


def tool_error_handler(tool_name: str):
    return partial(handle_expected_tool_error, tool_name=tool_name)


def is_transport_error(exc: BaseException) -> bool:
    if isinstance(exc, BaseExceptionGroup):
        return all(is_transport_error(item) for item in exc.exceptions)
    if isinstance(exc, httpx.HTTPStatusError):
        return 500 <= exc.response.status_code < 600
    return isinstance(
        exc,
        (
            httpx.TransportError,
            ConnectionError,
            TimeoutError,
            anyio.BrokenResourceError,
            anyio.ClosedResourceError,
            anyio.EndOfStream,
        ),
    )
