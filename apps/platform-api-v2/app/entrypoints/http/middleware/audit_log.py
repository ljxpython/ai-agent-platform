from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import FastAPI, Request, Response
from sqlalchemy.orm import Session, sessionmaker

from app.core.context.models import PlatformRequestContext
from app.core.db import session_scope
from app.modules.audit.application import AuditWriteCommand
from app.modules.audit.domain import AuditPlane, AuditResult
from app.modules.audit.infra import SqlAlchemyAuditRepository

logger = logging.getLogger(__name__)

_SKIP_PATHS = {"/docs", "/openapi.json", "/redoc", "/favicon.ico"}


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _route_segments(path: str) -> list[str]:
    return [segment for segment in path.strip("/").split("/") if segment]


def _response_size(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None

def _parse_json_bytes(value: bytes | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        payload = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _nested_value(payload: dict[str, Any] | None, *keys: str) -> str | None:
    current: Any = payload
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return _clean(current)


def _resolve_plane(path: str) -> AuditPlane:
    if path.startswith("/_system/"):
        return AuditPlane.SYSTEM_INTERNAL
    if path.startswith("/_runtime/"):
        return AuditPlane.RUNTIME_GATEWAY
    if path == "/api/langgraph" or path.startswith("/api/langgraph/"):
        return AuditPlane.RUNTIME_GATEWAY
    return AuditPlane.CONTROL_PLANE


def _resolve_project_id(request: Request) -> str | None:
    state_project_id = _clean(getattr(request.state, "audit_project_id", None))
    if state_project_id:
        return state_project_id
    query_project_id = _clean(request.query_params.get("project_id"))
    path_segments = _route_segments(request.url.path)
    if len(path_segments) >= 3 and path_segments[:2] == ["api", "projects"]:
        return _clean(path_segments[2])
    return query_project_id


def _resolve_action(
    *,
    request: Request,
    path: str,
    method: str,
) -> tuple[str, str | None, str | None]:
    segments = _route_segments(path)
    if segments == ["_system", "health"] and method == "GET":
        return "system.health.read", "system", "health"

    if len(segments) >= 2 and segments[:2] == ["api", "identity"]:
        if segments[2:] == ["session"] and method == "POST":
            return "identity.session.created", "session", None
        if segments[2:] == ["session", "refresh"] and method == "POST":
            return "identity.session.refreshed", "session", None
        if segments[2:] == ["session"] and method == "DELETE":
            return "identity.session.deleted", "session", None
        if segments[2:] == ["me"] and method == "GET":
            return "identity.profile.read", "user", None
        if segments[2:] == ["password", "change"] and method == "POST":
            return "identity.password.changed", "user", None

    if len(segments) >= 2 and segments[:2] == ["api", "projects"]:
        if len(segments) == 2 and method == "GET":
            return "project.collection.listed", "project", None
        if len(segments) == 2 and method == "POST":
            return "project.project.created", "project", None
        if len(segments) == 3 and method == "DELETE":
            return "project.project.deleted", "project", _clean(segments[2])
        if len(segments) >= 4 and segments[3] == "members":
            project_id = _clean(segments[2])
            if len(segments) == 4 and method == "GET":
                return "project.member.listed", "project_member", project_id
            if len(segments) == 5 and method == "PUT":
                return "project.member.upserted", "project_member", _clean(segments[4])
            if len(segments) == 5 and method == "DELETE":
                return "project.member.removed", "project_member", _clean(segments[4])

    if len(segments) >= 2 and segments[:2] == ["api", "announcements"]:
        if len(segments) == 2 and method == "GET":
            return "announcement.collection.listed", "announcement", None
        if len(segments) == 2 and method == "POST":
            return "announcement.item.created", "announcement", None
        if len(segments) == 3 and segments[2] == "feed" and method == "GET":
            return "announcement.feed.read", "announcement_feed", _resolve_project_id(request)
        if len(segments) == 3 and segments[2] == "read-all" and method == "POST":
            return "announcement.feed.read_all_marked", "announcement_feed", _resolve_project_id(
                request
            )
        if len(segments) == 3 and method == "PATCH":
            return "announcement.item.updated", "announcement", _clean(segments[2])
        if len(segments) == 3 and method == "DELETE":
            return "announcement.item.deleted", "announcement", _clean(segments[2])
        if len(segments) == 4 and segments[3] == "read" and method == "POST":
            return "announcement.item.read_marked", "announcement", _clean(segments[2])

    if segments == ["api", "audit"] and method == "GET":
        return "audit.collection.listed", "audit_event", None

    if segments == ["_system", "platform-config"] and method == "GET":
        return "system.config.read", "platform_config", "platform-config"
    if segments == ["_system", "platform-config", "feature-flags"] and method == "PATCH":
        return "system.config.feature_flags.updated", "platform_config", "platform-config"

    if len(segments) >= 2 and segments[:2] == ["api", "operations"]:
        if len(segments) == 2 and method == "POST":
            return "operation.item.submitted", "operation", None
        if len(segments) == 2 and method == "GET":
            return "operation.collection.listed", "operation", _resolve_project_id(request)
        if len(segments) == 3 and method == "GET":
            return "operation.item.read", "operation", _clean(segments[2])
        if len(segments) == 4 and segments[3] == "artifact" and method == "GET":
            return "operation.item.artifact_read", "operation_artifact", _clean(segments[2])
        if len(segments) == 4 and segments[3] == "cancel" and method == "POST":
            return "operation.item.cancelled", "operation", _clean(segments[2])

    if len(segments) >= 2 and segments[:2] == ["api", "assistants"]:
        if len(segments) == 3 and method == "GET":
            return "assistant.item.read", "assistant", _clean(segments[2])
        if len(segments) == 3 and method == "PATCH":
            return "assistant.item.updated", "assistant", _clean(segments[2])
        if len(segments) == 3 and method == "DELETE":
            return "assistant.item.deleted", "assistant", _clean(segments[2])
        if len(segments) == 4 and segments[3] == "resync" and method == "POST":
            return "assistant.item.resynced", "assistant", _clean(segments[2])

    if len(segments) >= 4 and segments[:2] == ["api", "projects"]:
        if len(segments) == 4 and segments[3] == "assistants" and method == "GET":
            return "assistant.collection.listed", "assistant", None
        if len(segments) == 4 and segments[3] == "assistants" and method == "POST":
            return "assistant.item.created", "assistant", None

    if len(segments) >= 4 and segments[:2] == ["api", "graphs"] and segments[3] == "assistant-parameter-schema":
        if method == "GET":
            return "assistant.schema.read", "graph", _clean(segments[2])

    if len(segments) >= 2 and segments[:2] == ["api", "runtime"]:
        if segments[2:] == ["models"] and method == "GET":
            return "runtime.model.collection.listed", "runtime_model", _resolve_project_id(request)
        if segments[2:] == ["models", "refresh"] and method == "POST":
            return "runtime.model.collection.refreshed", "runtime_model", _resolve_project_id(request)
        if segments[2:] == ["tools"] and method == "GET":
            return "runtime.tool.collection.listed", "runtime_tool", _resolve_project_id(request)
        if segments[2:] == ["tools", "refresh"] and method == "POST":
            return "runtime.tool.collection.refreshed", "runtime_tool", _resolve_project_id(request)
        if segments[2:] == ["graphs"] and method == "GET":
            return "runtime.graph.collection.listed", "runtime_graph", _resolve_project_id(request)
        if segments[2:] == ["graphs", "refresh"] and method == "POST":
            return "runtime.graph.collection.refreshed", "runtime_graph", _resolve_project_id(request)

    if len(segments) >= 5 and segments[:2] == ["api", "projects"] and segments[3] == "runtime-policies":
        project_id = _clean(segments[2])
        if len(segments) == 5 and segments[4] == "models" and method == "GET":
            return "runtime.policy.model.listed", "runtime_policy_model", project_id
        if len(segments) == 5 and segments[4] == "tools" and method == "GET":
            return "runtime.policy.tool.listed", "runtime_policy_tool", project_id
        if len(segments) == 5 and segments[4] == "graphs" and method == "GET":
            return "runtime.policy.graph.listed", "runtime_policy_graph", project_id
        if len(segments) == 6 and segments[4] == "models" and method == "PUT":
            return "runtime.policy.model.updated", "runtime_policy_model", _clean(segments[5])
        if len(segments) == 6 and segments[4] == "tools" and method == "PUT":
            return "runtime.policy.tool.updated", "runtime_policy_tool", _clean(segments[5])
        if len(segments) == 6 and segments[4] == "graphs" and method == "PUT":
            return "runtime.policy.graph.updated", "runtime_policy_graph", _clean(segments[5])

    if len(segments) >= 2 and segments[:2] == ["api", "langgraph"]:
        if segments[2:] == ["info"] and method == "GET":
            return "runtime.info.read", "runtime", "info"
        if segments[2:] == ["graphs", "search"] and method == "POST":
            return "runtime.graph.collection.searched", "graph", None
        if segments[2:] == ["graphs", "count"] and method == "POST":
            return "runtime.graph.collection.counted", "graph", None
        if segments[2:] == ["threads"] and method == "POST":
            return "runtime.thread.item.created", "thread", None
        if segments[2:] == ["threads", "search"] and method == "POST":
            return "runtime.thread.collection.searched", "thread", None
        if segments[2:] == ["threads", "count"] and method == "POST":
            return "runtime.thread.collection.counted", "thread", None
        if segments[2:] == ["threads", "prune"] and method == "POST":
            return "runtime.thread.collection.pruned", "thread", None
        if len(segments) == 4 and segments[2] == "threads" and method == "GET":
            return "runtime.thread.item.read", "thread", _clean(segments[3])
        if len(segments) == 4 and segments[2] == "threads" and method == "PATCH":
            return "runtime.thread.item.updated", "thread", _clean(segments[3])
        if len(segments) == 4 and segments[2] == "threads" and method == "DELETE":
            return "runtime.thread.item.deleted", "thread", _clean(segments[3])
        if len(segments) == 5 and segments[2] == "threads" and segments[4] == "copy" and method == "POST":
            return "runtime.thread.item.copied", "thread", _clean(segments[3])
        if len(segments) == 5 and segments[2] == "threads" and segments[4] == "state" and method == "GET":
            return "runtime.thread.state.read", "thread", _clean(segments[3])
        if len(segments) == 5 and segments[2] == "threads" and segments[4] == "state" and method == "POST":
            return "runtime.thread.state.updated", "thread", _clean(segments[3])
        if len(segments) == 6 and segments[2] == "threads" and segments[4] == "state" and method == "GET":
            return "runtime.thread.state.read", "thread", _clean(segments[3])
        if len(segments) == 5 and segments[2] == "threads" and segments[4] == "history" and method in {"GET", "POST"}:
            return "runtime.thread.history.read", "thread", _clean(segments[3])
        if segments[2:] == ["runs"] and method == "POST":
            return "runtime.run.item.created", "run", None
        if segments[2:] == ["runs", "stream"] and method == "POST":
            return "runtime.run.stream.opened", "run", None
        if segments[2:] == ["runs", "wait"] and method == "POST":
            return "runtime.run.wait.requested", "run", None
        if segments[2:] == ["runs", "batch"] and method == "POST":
            return "runtime.run.collection.created", "run", None
        if segments[2:] == ["runs", "cancel"] and method == "POST":
            return "runtime.run.collection.cancelled", "run", None
        if segments[2:] == ["runs", "crons"] and method == "POST":
            return "runtime.cron.item.created", "cron", None
        if segments[2:] == ["runs", "crons", "search"] and method == "POST":
            return "runtime.cron.collection.searched", "cron", None
        if segments[2:] == ["runs", "crons", "count"] and method == "POST":
            return "runtime.cron.collection.counted", "cron", None
        if len(segments) == 5 and segments[2] == "runs" and segments[3] == "crons" and method == "PATCH":
            return "runtime.cron.item.updated", "cron", _clean(segments[4])
        if len(segments) == 5 and segments[2] == "runs" and segments[3] == "crons" and method == "DELETE":
            return "runtime.cron.item.deleted", "cron", _clean(segments[4])
        if len(segments) == 5 and segments[2] == "threads" and segments[4] == "runs" and method == "POST":
            return "runtime.run.item.created", "thread", _clean(segments[3])
        if len(segments) == 6 and segments[2] == "threads" and segments[4] == "runs" and segments[5] == "stream" and method == "POST":
            return "runtime.run.stream.opened", "thread", _clean(segments[3])
        if len(segments) == 6 and segments[2] == "threads" and segments[4] == "runs" and segments[5] == "wait" and method == "POST":
            return "runtime.run.wait.requested", "thread", _clean(segments[3])
        if len(segments) == 5 and segments[2] == "threads" and segments[4] == "runs" and method == "GET":
            return "runtime.run.collection.listed", "thread", _clean(segments[3])
        if len(segments) == 6 and segments[2] == "threads" and segments[4] == "runs" and method == "GET":
            return "runtime.run.item.read", "run", _clean(segments[5])
        if len(segments) == 6 and segments[2] == "threads" and segments[4] == "runs" and method == "DELETE":
            return "runtime.run.item.deleted", "run", _clean(segments[5])
        if len(segments) == 7 and segments[2] == "threads" and segments[4] == "runs" and segments[6] == "join" and method == "GET":
            return "runtime.run.item.joined", "run", _clean(segments[5])
        if len(segments) == 7 and segments[2] == "threads" and segments[4] == "runs" and segments[6] == "stream" and method == "GET":
            return "runtime.run.stream.joined", "run", _clean(segments[5])
        if len(segments) == 6 and segments[2] == "threads" and segments[4] == "runs" and segments[5] == "crons" and method == "POST":
            return "runtime.cron.item.created", "thread", _clean(segments[3])
        if len(segments) == 8 and segments[2] == "threads" and segments[4] == "runs" and segments[6] == "cancel" and method == "POST":
            return "runtime.run.item.cancelled", "run", _clean(segments[5])

    return "system.route.requested", "route", path


def _resolve_metadata(
    *,
    request: Request,
    route_kind: AuditPlane,
    target_type: str | None,
    target_id: str | None,
    status_code: int,
    result: AuditResult,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "route_kind": route_kind.value,
        "query": request.url.query or None,
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent") or None,
        "target_type": target_type,
        "target_id": target_id,
        "result": result.value,
        "response_size": _response_size(getattr(request.state, "response_content_length", None)),
    }
    if status_code >= 400:
        metadata["is_error"] = True
    return {key: value for key, value in metadata.items() if value is not None}


def _resolve_context(request: Request) -> PlatformRequestContext | None:
    context = getattr(request.state, "platform_context", None)
    if isinstance(context, PlatformRequestContext):
        return context
    return None


def _resolve_response_payload(request: Request) -> dict[str, Any] | None:
    payload = getattr(request.state, "audit_response_payload", None)
    if isinstance(payload, dict):
        return payload
    return None


async def _capture_response(response: Response) -> tuple[Response, bytes]:
    body = getattr(response, "body", None)
    if body is None:
        chunks = [chunk async for chunk in response.body_iterator]
        body = b"".join(chunks)
    rebuilt = Response(
        content=body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
        background=response.background,
    )
    return rebuilt, body


def _resolve_project_id_from_payload(
    *,
    path: str,
    payload: dict[str, Any] | None,
) -> str | None:
    segments = _route_segments(path)
    if segments == ["api", "projects"]:
        return _nested_value(payload, "id")
    if len(segments) >= 2 and segments[:2] == ["api", "announcements"]:
        return _nested_value(payload, "scope_project_id")
    return None


def _resolve_target_id_from_payload(
    *,
    path: str,
    method: str,
    payload: dict[str, Any] | None,
    actor_user_id: str | None,
) -> str | None:
    segments = _route_segments(path)
    if len(segments) >= 2 and segments[:2] == ["api", "identity"]:
        if segments[2:] == ["session"] and method == "POST":
            return _nested_value(payload, "user", "id")
        if segments[2:] == ["me"] and method == "GET":
            return actor_user_id or _nested_value(payload, "id")
        if segments[2:] == ["password", "change"] and method == "POST":
            return actor_user_id
    if segments == ["api", "projects"] and method == "POST":
        return _nested_value(payload, "id")
    if len(segments) >= 2 and segments[:2] == ["api", "announcements"]:
        return _nested_value(payload, "id")
    if len(segments) >= 4 and segments[:2] == ["api", "projects"]:
        if segments[3] == "assistants" and method == "POST":
            return _nested_value(payload, "id")
    if len(segments) >= 2 and segments[:2] == ["api", "assistants"]:
        if method in {"GET", "PATCH", "POST"}:
            return _nested_value(payload, "id")
    if len(segments) >= 2 and segments[:2] == ["api", "langgraph"]:
        if segments[2:] == ["threads"] and method == "POST":
            return _nested_value(payload, "thread_id")
        if segments[2:] in (["runs"], ["runs", "wait"]) and method == "POST":
            return _nested_value(payload, "run_id")
        if len(segments) == 5 and segments[2] == "threads" and segments[4] == "runs" and method == "POST":
            return _nested_value(payload, "run_id")
    return None


def _write_audit_event(
    *,
    request: Request,
    session_factory: sessionmaker[Session],
    status_code: int,
    result: AuditResult,
    duration_ms: int,
) -> None:
    context = _resolve_context(request)
    plane = _resolve_plane(request.url.path)
    response_payload = _resolve_response_payload(request)
    action, target_type, target_id = _resolve_action(
        request=request,
        path=request.url.path,
        method=request.method.upper(),
    )
    actor = context.actor if context is not None else None
    tenant_id = context.tenant.tenant_id if context is not None else None
    target_id = target_id or _resolve_target_id_from_payload(
        path=request.url.path,
        method=request.method.upper(),
        payload=response_payload,
        actor_user_id=actor.user_id if actor is not None else None,
    )
    project_id = _resolve_project_id(request) or _resolve_project_id_from_payload(
        path=request.url.path,
        payload=response_payload,
    ) or (
        context.project.project_id if context is not None else None
    )

    metadata = _resolve_metadata(
        request=request,
        route_kind=plane,
        target_type=target_type,
        target_id=target_id,
        status_code=status_code,
        result=result,
    )
    with session_scope(session_factory) as session:
        repository = SqlAlchemyAuditRepository(session)
        repository.create_event(
            AuditWriteCommand(
                request_id=getattr(request.state, "request_id", "") or "unknown",
                plane=plane,
                action=action,
                target_type=target_type,
                target_id=target_id,
                actor_user_id=actor.user_id if actor is not None else None,
                actor_subject=actor.subject if actor is not None else None,
                tenant_id=tenant_id,
                project_id=project_id,
                result=result,
                method=request.method.upper(),
                path=request.url.path,
                status_code=status_code,
                duration_ms=duration_ms,
                metadata=metadata,
            )
        )


def register_audit_log_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def audit_log_middleware(request: Request, call_next):
        if request.url.path in _SKIP_PATHS:
            return await call_next(request)

        started_at = time.perf_counter()
        session_factory = getattr(request.app.state, "db_session_factory", None)
        if session_factory is None or not isinstance(session_factory, sessionmaker):
            return await call_next(request)

        try:
            response = await call_next(request)
        except asyncio.CancelledError:
            duration_ms = max(0, int(round((time.perf_counter() - started_at) * 1000)))
            try:
                _write_audit_event(
                    request=request,
                    session_factory=session_factory,
                    status_code=499,
                    result=AuditResult.CANCELLED,
                    duration_ms=duration_ms,
                )
            except Exception:
                logger.exception(
                    "audit_write_failed request_id=%s",
                    getattr(request.state, "request_id", "unknown"),
                )
            raise
        except Exception:
            duration_ms = max(0, int(round((time.perf_counter() - started_at) * 1000)))
            try:
                _write_audit_event(
                    request=request,
                    session_factory=session_factory,
                    status_code=500,
                    result=AuditResult.FAILED,
                    duration_ms=duration_ms,
                )
            except Exception:
                logger.exception(
                    "audit_write_failed request_id=%s",
                    getattr(request.state, "request_id", "unknown"),
                )
            raise

        response, response_body = await _capture_response(response)
        request.state.response_content_length = str(len(response_body))
        request.state.audit_response_payload = _parse_json_bytes(response_body)
        duration_ms = max(0, int(round((time.perf_counter() - started_at) * 1000)))
        try:
            _write_audit_event(
                request=request,
                session_factory=session_factory,
                status_code=response.status_code,
                result=(
                    AuditResult.SUCCESS
                    if response.status_code < 400
                    else AuditResult.FAILED
                ),
                duration_ms=duration_ms,
            )
        except Exception:
            logger.exception(
                "audit_write_failed request_id=%s",
                getattr(request.state, "request_id", "unknown"),
            )
        return response
