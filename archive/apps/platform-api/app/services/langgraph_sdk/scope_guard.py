from __future__ import annotations

import uuid
from typing import Any

from app.db.access import get_agent_by_project_and_langgraph_assistant_id, parse_uuid
from app.db.session import session_scope
from app.services.langgraph_sdk.client import get_langgraph_client
from fastapi import HTTPException, Request

_PROJECT_ID_HEADER = "x-project-id"
_THREAD_PROJECT_ID_KEYS = ("project_id", "x-project-id", "projectId")
_RUNTIME_CONTEXT_BUSINESS_KEYS = (
    "model_id",
    "system_prompt",
    "temperature",
    "max_tokens",
    "top_p",
    "enable_tools",
    "tools",
)
_TRUSTED_CONTEXT_KEYS = (
    "user_id",
    "tenant_id",
    "role",
    "permissions",
    "project_id",
    "projectId",
    "x-project-id",
)


def _scope_guard_enabled(request: Request) -> bool:
    settings = getattr(request.app.state, "settings", None)
    return bool(getattr(settings, "langgraph_scope_guard_enabled", False))


def _require_db_session_factory(request: Request) -> Any:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is None:
        raise HTTPException(status_code=503, detail="Database is not enabled")
    return session_factory


def _normalize_project_id(raw_project_id: Any) -> str | None:
    if isinstance(raw_project_id, uuid.UUID):
        return str(raw_project_id)
    if not isinstance(raw_project_id, str) or not raw_project_id:
        return None
    parsed = parse_uuid(raw_project_id)
    if parsed is None:
        return None
    return str(parsed)


def _thread_project_id_from_metadata(thread: Any) -> str | None:
    if isinstance(thread, dict):
        metadata = thread.get("metadata")
    else:
        metadata = getattr(thread, "metadata", None)

    if not isinstance(metadata, dict):
        return None

    for key in _THREAD_PROJECT_ID_KEYS:
        normalized = _normalize_project_id(metadata.get(key))
        if normalized is not None:
            return normalized
    return None


def get_optional_project_id(request: Request) -> str | None:
    raw_project_id = request.headers.get(_PROJECT_ID_HEADER)
    if raw_project_id is None or not raw_project_id.strip():
        return None
    normalized = _normalize_project_id(raw_project_id)
    if normalized is None:
        raise HTTPException(
            status_code=400,
            detail="x-project-id header is required and must be a valid UUID",
        )
    return normalized


def require_project_id(request: Request) -> str:
    normalized = get_optional_project_id(request)
    if normalized is None:
        raise HTTPException(
            status_code=400,
            detail="x-project-id header is required and must be a valid UUID",
        )
    return normalized


async def assert_assistant_belongs_project(request: Request, assistant_id: str) -> None:
    if not _scope_guard_enabled(request):
        return

    project_uuid = uuid.UUID(require_project_id(request))
    session_factory = _require_db_session_factory(request)
    with session_scope(session_factory) as session:
        agent = get_agent_by_project_and_langgraph_assistant_id(
            session,
            project_id=project_uuid,
            langgraph_assistant_id=assistant_id,
        )
    if agent is None:
        raise HTTPException(status_code=403, detail="assistant_project_denied")


async def assert_thread_belongs_project(request: Request, thread_id: str) -> None:
    if not _scope_guard_enabled(request):
        return

    project_id = require_project_id(request)
    client = get_langgraph_client(request)
    try:
        thread = await client.threads.get(thread_id)
    except Exception as exc:
        # 上游 LangGraph 不可用时，统一转换为可控网关错误，避免直接抛 500。
        raise HTTPException(
            status_code=502, detail="langgraph_upstream_unavailable"
        ) from exc
    thread_project_id = _thread_project_id_from_metadata(thread)
    # 无 project 元数据也按越权处理，避免 thread 在项目边界外被探测。
    if thread_project_id is None or thread_project_id != project_id:
        raise HTTPException(status_code=403, detail="thread_project_denied")


def inject_project_metadata(
    request: Request, payload: dict[str, Any]
) -> dict[str, Any]:
    next_payload = dict(payload) if isinstance(payload, dict) else {}
    project_id = get_optional_project_id(request)
    if project_id is None:
        return next_payload
    metadata = next_payload.get("metadata")
    metadata_dict = _without_project_scope_aliases(dict(metadata)) if isinstance(metadata, dict) else {}
    metadata_dict["project_id"] = project_id
    next_payload["metadata"] = metadata_dict
    return next_payload


def _without_project_scope_aliases(payload: dict[str, Any]) -> dict[str, Any]:
    next_payload = dict(payload)
    for key in _THREAD_PROJECT_ID_KEYS:
        next_payload.pop(key, None)
    return next_payload


def _without_trusted_context_keys(payload: dict[str, Any]) -> dict[str, Any]:
    next_payload = dict(payload)
    for key in _TRUSTED_CONTEXT_KEYS:
        next_payload.pop(key, None)
    return next_payload


def _move_runtime_business_fields_into_context(
    *,
    source: dict[str, Any],
    context: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    next_source = dict(source)
    next_context = dict(context)
    for key in _RUNTIME_CONTEXT_BUSINESS_KEYS:
        if key not in next_source:
            continue
        value = next_source.pop(key)
        if value is None or key in next_context:
            continue
        next_context[key] = value
    return next_source, next_context


def inject_project_scope(
    request: Request,
    payload: dict[str, Any],
) -> dict[str, Any]:
    next_payload = inject_project_metadata(request, payload)
    project_id = get_optional_project_id(request)
    if project_id is None:
        return next_payload

    config = next_payload.get("config")
    config_dict = dict(config) if isinstance(config, dict) else {}
    context = next_payload.get("context")
    context_dict = (
        _without_trusted_context_keys(dict(context))
        if isinstance(context, dict)
        else {}
    )

    config_dict = _without_project_scope_aliases(config_dict)
    config_dict, context_dict = _move_runtime_business_fields_into_context(
        source=config_dict,
        context=context_dict,
    )

    configurable = config_dict.get("configurable")
    if isinstance(configurable, dict):
        configurable_dict = _without_trusted_context_keys(
            _without_project_scope_aliases(dict(configurable))
        )
        configurable_dict, context_dict = _move_runtime_business_fields_into_context(
            source=configurable_dict,
            context=context_dict,
        )
        if configurable_dict:
            config_dict["configurable"] = configurable_dict
        else:
            config_dict.pop("configurable", None)
    else:
        config_dict.pop("configurable", None)

    context_dict["project_id"] = project_id
    next_payload["context"] = context_dict

    config_metadata = config_dict.get("metadata")
    if isinstance(config_metadata, dict):
        config_metadata_dict = _without_project_scope_aliases(dict(config_metadata))
        if config_metadata_dict:
            config_dict["metadata"] = config_metadata_dict
        else:
            config_dict.pop("metadata", None)
    else:
        config_dict.pop("metadata", None)

    if config_dict:
        next_payload["config"] = config_dict
    else:
        next_payload.pop("config", None)
    return next_payload
