from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.api.management.common import (
    current_user_id_from_request,
    require_db_session_factory,
    require_project_role,
)
from app.api.management.schemas import CreateAssistantRequest, UpdateAssistantRequest
from app.db.access import (
    create_agent,
    delete_agent,
    get_agent_by_id,
    get_assistant_profile_by_agent_id,
    list_project_agents,
    parse_uuid,
    update_agent_runtime_fields,
    update_agent_sync_state,
    upsert_assistant_profile,
)
from app.db.session import session_scope
from app.services.graph_parameter_schema import GraphParameterSchemaService
from app.services.langgraph_sdk.assistants_service import LangGraphAssistantsService
from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError

router = APIRouter(tags=["management-assistants"])

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

_PROJECT_SCOPE_ALIAS_KEYS = (
    "project_id",
    "projectId",
    "x-project-id",
)


def _extract_upstream_assistant_id(item: Any) -> str | None:
    if isinstance(item, dict):
        assistant_id = item.get("assistant_id")
        if isinstance(assistant_id, str) and assistant_id:
            return assistant_id
    return None


def _serialize_assistant(row: Any, profile: Any) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "name": row.name,
        "description": row.description,
        "graph_id": row.graph_id,
        "langgraph_assistant_id": row.langgraph_assistant_id,
        "runtime_base_url": row.runtime_base_url,
        "sync_status": row.sync_status,
        "last_sync_error": row.last_sync_error,
        "last_synced_at": row.last_synced_at,
        "status": profile.status if profile is not None else "active",
        "config": profile.config if profile is not None else {},
        "context": profile.context if profile is not None else {},
        "metadata": profile.metadata_json if profile is not None else {},
        "created_by": str(profile.created_by) if profile is not None else None,
        "updated_by": str(profile.updated_by) if profile is not None else None,
        "created_at": row.created_at,
        "updated_at": profile.updated_at if profile is not None else None,
    }


def _normalize_object(value: dict[str, Any] | None) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _strip_keys(payload: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    next_payload = dict(payload)
    for key in keys:
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


def _normalize_assistant_runtime_contract(
    *,
    config: dict[str, Any],
    context: dict[str, Any],
    metadata: dict[str, Any],
    project_id: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    next_context = _strip_keys(context, _TRUSTED_CONTEXT_KEYS)
    next_config = _strip_keys(config, _PROJECT_SCOPE_ALIAS_KEYS)
    next_metadata = _strip_keys(metadata, _PROJECT_SCOPE_ALIAS_KEYS)
    next_metadata["project_id"] = project_id

    next_config, next_context = _move_runtime_business_fields_into_context(
        source=next_config,
        context=next_context,
    )

    configurable = next_config.get("configurable")
    configurable_dict = (
        _strip_keys(dict(configurable), _TRUSTED_CONTEXT_KEYS)
        if isinstance(configurable, dict)
        else {}
    )
    configurable_dict, next_context = _move_runtime_business_fields_into_context(
        source=configurable_dict,
        context=next_context,
    )
    if configurable_dict:
        next_config["configurable"] = configurable_dict
    else:
        next_config.pop("configurable", None)

    config_metadata = next_config.get("metadata")
    config_metadata_dict = (
        _strip_keys(dict(config_metadata), _PROJECT_SCOPE_ALIAS_KEYS)
        if isinstance(config_metadata, dict)
        else {}
    )
    if config_metadata_dict:
        next_config["metadata"] = config_metadata_dict
    else:
        next_config.pop("metadata", None)

    return next_config, next_context, next_metadata


@router.get("/projects/{project_id}/assistants")
async def list_assistants(
    request: Request,
    project_id: str,
    graph_id: str | None = Query(default=None),
    query: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    project_uuid = parse_uuid(project_id)
    if project_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_project_id")

    require_project_role(
        request, project_uuid, allowed_roles={"admin", "editor", "executor"}
    )
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        rows, total = list_project_agents(
            session,
            project_id=project_uuid,
            limit=limit,
            offset=offset,
            query=query,
            graph_id=graph_id,
        )
        items = []
        for row in rows:
            profile = get_assistant_profile_by_agent_id(session, row.id)
            items.append(_serialize_assistant(row, profile))
        return {"items": items, "total": total}


@router.post("/projects/{project_id}/assistants")
async def create_assistant_for_project(
    request: Request,
    project_id: str,
    payload: CreateAssistantRequest,
) -> dict[str, Any]:
    project_uuid = parse_uuid(project_id)
    if project_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_project_id")

    actor_user_id, _ = require_project_role(
        request, project_uuid, allowed_roles={"admin", "editor"}
    )

    upstream_payload: dict[str, Any] = {
        "graph_id": payload.graph_id,
        "name": payload.name,
    }
    if payload.description:
        upstream_payload["description"] = payload.description
    if isinstance(payload.assistant_id, str) and payload.assistant_id.strip():
        upstream_payload["assistant_id"] = payload.assistant_id.strip()
    user_config = _normalize_object(payload.config)
    user_context = _normalize_object(payload.context)
    user_metadata = _normalize_object(payload.metadata)
    user_config, user_context, user_metadata = _normalize_assistant_runtime_contract(
        config=user_config,
        context=user_context,
        metadata=user_metadata,
        project_id=project_id,
    )
    if user_config:
        upstream_payload["config"] = user_config
    if user_context:
        upstream_payload["context"] = user_context
    if user_metadata:
        upstream_payload["metadata"] = user_metadata

    service = LangGraphAssistantsService(request)
    try:
        upstream_item = await service.create(upstream_payload)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="assistant_upstream_create_failed"
        ) from exc

    langgraph_assistant_id = _extract_upstream_assistant_id(upstream_item)
    if langgraph_assistant_id is None:
        raise HTTPException(
            status_code=502, detail="assistant_upstream_invalid_response"
        )

    settings = request.app.state.settings
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        try:
            row = create_agent(
                session,
                project_id=project_uuid,
                name=payload.name,
                graph_id=payload.graph_id,
                runtime_base_url=settings.langgraph_upstream_url,
                langgraph_assistant_id=langgraph_assistant_id,
                description=payload.description,
            )
            profile = upsert_assistant_profile(
                session,
                agent_id=row.id,
                status="active",
                config=user_config,
                context=user_context,
                metadata_json=user_metadata,
                actor_user_id=actor_user_id,
            )
        except IntegrityError as exc:
            raise HTTPException(
                status_code=409, detail="assistant_name_conflict"
            ) from exc

        return _serialize_assistant(row, profile)


@router.get("/assistants/{assistant_id}")
async def get_assistant(request: Request, assistant_id: str) -> dict[str, Any]:
    assistant_uuid = parse_uuid(assistant_id)
    if assistant_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_assistant_id")

    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        row = get_agent_by_id(session, assistant_uuid)
        if row is None:
            raise HTTPException(status_code=404, detail="assistant_not_found")
        require_project_role(
            request, row.project_id, allowed_roles={"admin", "editor", "executor"}
        )
        profile = get_assistant_profile_by_agent_id(session, row.id)
        return _serialize_assistant(row, profile)


@router.patch("/assistants/{assistant_id}")
async def update_assistant(
    request: Request,
    assistant_id: str,
    payload: UpdateAssistantRequest,
) -> dict[str, Any]:
    assistant_uuid = parse_uuid(assistant_id)
    if assistant_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_assistant_id")

    session_factory = require_db_session_factory(request)
    actor_user_id = current_user_id_from_request(request)
    with session_scope(session_factory) as session:
        row = get_agent_by_id(session, assistant_uuid)
        if row is None:
            raise HTTPException(status_code=404, detail="assistant_not_found")
        require_project_role(request, row.project_id, allowed_roles={"admin", "editor"})
        profile = get_assistant_profile_by_agent_id(session, row.id)

        next_graph_id = (
            payload.graph_id if isinstance(payload.graph_id, str) else row.graph_id
        )
        next_name = payload.name if isinstance(payload.name, str) else row.name
        next_description = (
            payload.description
            if isinstance(payload.description, str)
            else row.description
        )
        next_status = (
            payload.status
            if isinstance(payload.status, str)
            else (profile.status if profile is not None else "active")
        )
        next_config = (
            _normalize_object(payload.config)
            if isinstance(payload.config, dict)
            else (dict(profile.config) if profile is not None else {})
        )
        next_context = (
            _normalize_object(payload.context)
            if isinstance(payload.context, dict)
            else (dict(profile.context) if profile is not None else {})
        )
        next_metadata = (
            _normalize_object(payload.metadata)
            if isinstance(payload.metadata, dict)
            else (dict(profile.metadata_json) if profile is not None else {})
        )
        next_config, next_context, next_metadata = _normalize_assistant_runtime_contract(
            config=next_config,
            context=next_context,
            metadata=next_metadata,
            project_id=str(row.project_id),
        )

        update_payload: dict[str, Any] = {}
        if next_graph_id != row.graph_id:
            update_payload["graph_id"] = next_graph_id
        if next_name != row.name:
            update_payload["name"] = next_name
        if next_description != row.description:
            update_payload["description"] = next_description
        if profile is None or next_config != profile.config:
            update_payload["config"] = next_config
        if profile is None or next_context != profile.context:
            update_payload["context"] = next_context
        if profile is None or next_metadata != profile.metadata_json:
            update_payload["metadata"] = next_metadata

        if update_payload:
            service = LangGraphAssistantsService(request)
            try:
                await service.update(row.langgraph_assistant_id, update_payload)
                update_agent_sync_state(
                    session,
                    row,
                    sync_status="ready",
                    last_sync_error=None,
                    last_synced_at=datetime.now(timezone.utc),
                )
            except HTTPException:
                update_agent_sync_state(
                    session,
                    row,
                    sync_status="error",
                    last_sync_error="assistant_upstream_update_failed",
                    last_synced_at=datetime.now(timezone.utc),
                )
                raise
            except Exception as exc:
                update_agent_sync_state(
                    session,
                    row,
                    sync_status="error",
                    last_sync_error=str(exc),
                    last_synced_at=datetime.now(timezone.utc),
                )
                raise HTTPException(
                    status_code=502, detail="assistant_upstream_update_failed"
                ) from exc

        row.graph_id = next_graph_id
        row.name = next_name
        row.description = next_description
        profile = upsert_assistant_profile(
            session,
            agent_id=row.id,
            status=next_status,
            config=next_config,
            context=next_context,
            metadata_json=next_metadata,
            actor_user_id=actor_user_id,
        )
        return _serialize_assistant(row, profile)


@router.delete("/assistants/{assistant_id}")
async def delete_assistant_item(
    request: Request,
    assistant_id: str,
    delete_runtime: bool = Query(default=False),
    delete_threads: bool = Query(default=False),
) -> dict[str, Any]:
    assistant_uuid = parse_uuid(assistant_id)
    if assistant_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_assistant_id")

    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        row = get_agent_by_id(session, assistant_uuid)
        if row is None:
            raise HTTPException(status_code=404, detail="assistant_not_found")
        require_project_role(request, row.project_id, allowed_roles={"admin", "editor"})

        if delete_runtime:
            service = LangGraphAssistantsService(request)
            try:
                await service.delete(
                    row.langgraph_assistant_id, delete_threads=delete_threads
                )
                update_agent_sync_state(
                    session,
                    row,
                    sync_status="ready",
                    last_sync_error=None,
                    last_synced_at=datetime.now(timezone.utc),
                )
            except HTTPException:
                update_agent_sync_state(
                    session,
                    row,
                    sync_status="error",
                    last_sync_error="assistant_upstream_delete_failed",
                    last_synced_at=datetime.now(timezone.utc),
                )
                raise
            except Exception as exc:
                update_agent_sync_state(
                    session,
                    row,
                    sync_status="error",
                    last_sync_error=str(exc),
                    last_synced_at=datetime.now(timezone.utc),
                )
                raise HTTPException(
                    status_code=502, detail="assistant_upstream_delete_failed"
                ) from exc

        delete_agent(session, row)
        return {"ok": True}


@router.post("/assistants/{assistant_id}/resync")
async def resync_assistant_item(request: Request, assistant_id: str) -> dict[str, Any]:
    assistant_uuid = parse_uuid(assistant_id)
    if assistant_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_assistant_id")

    session_factory = require_db_session_factory(request)
    actor_user_id = current_user_id_from_request(request)
    with session_scope(session_factory) as session:
        row = get_agent_by_id(session, assistant_uuid)
        if row is None:
            raise HTTPException(status_code=404, detail="assistant_not_found")
        require_project_role(request, row.project_id, allowed_roles={"admin", "editor"})
        profile = get_assistant_profile_by_agent_id(session, row.id)

        service = LangGraphAssistantsService(request)
        try:
            upstream_item = await service.get(row.langgraph_assistant_id)
        except HTTPException:
            update_agent_sync_state(
                session,
                row,
                sync_status="error",
                last_sync_error="assistant_upstream_resync_failed",
                last_synced_at=datetime.now(timezone.utc),
            )
            raise
        except Exception as exc:
            update_agent_sync_state(
                session,
                row,
                sync_status="error",
                last_sync_error=str(exc),
                last_synced_at=datetime.now(timezone.utc),
            )
            raise HTTPException(
                status_code=502, detail="assistant_upstream_resync_failed"
            ) from exc

        if not isinstance(upstream_item, dict):
            update_agent_sync_state(
                session,
                row,
                sync_status="error",
                last_sync_error="assistant_upstream_invalid_response",
                last_synced_at=datetime.now(timezone.utc),
            )
            raise HTTPException(
                status_code=502, detail="assistant_upstream_invalid_response"
            )

        next_graph_id = str(upstream_item.get("graph_id") or row.graph_id)
        next_name = str(upstream_item.get("name") or row.name)
        next_description = str(upstream_item.get("description") or row.description)
        next_config = (
            dict(upstream_item.get("config"))
            if isinstance(upstream_item.get("config"), dict)
            else (dict(profile.config) if profile is not None else {})
        )
        next_context = (
            dict(upstream_item.get("context"))
            if isinstance(upstream_item.get("context"), dict)
            else (dict(profile.context) if profile is not None else {})
        )
        next_metadata = (
            dict(upstream_item.get("metadata"))
            if isinstance(upstream_item.get("metadata"), dict)
            else (dict(profile.metadata_json) if profile is not None else {})
        )
        next_config, next_context, next_metadata = _normalize_assistant_runtime_contract(
            config=next_config,
            context=next_context,
            metadata=next_metadata,
            project_id=str(row.project_id),
        )

        update_agent_runtime_fields(
            session,
            row,
            graph_id=next_graph_id,
            name=next_name,
            description=next_description,
            runtime_base_url=request.app.state.settings.langgraph_upstream_url,
        )
        update_agent_sync_state(
            session,
            row,
            sync_status="ready",
            last_sync_error=None,
            last_synced_at=datetime.now(timezone.utc),
        )
        profile = upsert_assistant_profile(
            session,
            agent_id=row.id,
            status=profile.status if profile is not None else "active",
            config=next_config,
            context=next_context,
            metadata_json=next_metadata,
            actor_user_id=actor_user_id,
        )
        return _serialize_assistant(row, profile)


@router.get("/graphs/{graph_id}/assistant-parameter-schema")
async def get_assistant_parameter_schema(
    request: Request, graph_id: str
) -> dict[str, Any]:
    project_raw = request.headers.get("x-project-id")
    project_uuid = parse_uuid(project_raw or "")
    if project_uuid is not None:
        require_project_role(
            request, project_uuid, allowed_roles={"admin", "editor", "executor"}
        )
    if not graph_id.strip():
        raise HTTPException(status_code=400, detail="invalid_graph_id")

    settings = request.app.state.settings
    service = GraphParameterSchemaService(settings)
    return service.build_schema(graph_id.strip())
