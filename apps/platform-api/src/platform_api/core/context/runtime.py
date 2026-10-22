from __future__ import annotations

import re
import time
import uuid
from contextvars import ContextVar, Token

from fastapi import Request

from platform_api.core.context.models import (
    ActorContext,
    PlatformRequestContext,
    ProjectContext,
    RequestContext,
    TenantContext,
)

DEFAULT_TENANT_ID = "__default"
_TRACEPARENT_RE = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}$")

_REQUEST_CONTEXT: ContextVar[PlatformRequestContext | None] = ContextVar(
    "platform_api_request_context",
    default=None,
)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _request_id(request: Request) -> str:
    return uuid.uuid4().hex


def _span_id() -> str:
    return uuid.uuid4().hex[:16]


def _resolve_trace_and_span(
    request: Request, default_request_id: str
) -> tuple[str, str, str]:
    raw_traceparent = request.headers.get("traceparent")
    if raw_traceparent:
        match = _TRACEPARENT_RE.match(raw_traceparent.strip().lower())
        if match:
            trace_id = match.group(1)
            span_id = _span_id()
            return trace_id, span_id, f"00-{trace_id}-{span_id}-01"
    trace_id = default_request_id
    span_id = _span_id()
    return trace_id, span_id, f"00-{trace_id}-{span_id}-01"


def _route_project_id(path: str) -> str | None:
    segments = [segment for segment in path.strip("/").split("/") if segment]
    if len(segments) >= 3 and segments[:2] == ["api", "projects"]:
        return _clean(segments[2])
    return None


def build_request_context(request: Request) -> PlatformRequestContext:
    request_id = _request_id(request)
    trace_id, span_id, traceparent = _resolve_trace_and_span(request, request_id)
    started_at = time.perf_counter()
    header_project_id = _clean(request.headers.get("x-project-id"))
    query_project_id = _clean(request.query_params.get("project_id"))
    project_id = (
        _route_project_id(request.url.path) or header_project_id or query_project_id
    )
    return PlatformRequestContext(
        request=RequestContext(
            request_id=request_id,
            trace_id=trace_id,
            span_id=span_id,
            traceparent=traceparent,
            method=request.method,
            path=request.url.path,
            query=request.url.query or None,
            started_at=started_at,
            client_ip=request.client.host if request.client else None,
            user_agent=_clean(request.headers.get("user-agent")),
        ),
        tenant=TenantContext(tenant_id=DEFAULT_TENANT_ID),
        project=ProjectContext(
            project_id=project_id,
            requested_by_header=header_project_id is not None,
        ),
        actor=ActorContext(),
    )


def set_current_request_context(
    context: PlatformRequestContext,
) -> Token[PlatformRequestContext | None]:
    return _REQUEST_CONTEXT.set(context)


def replace_current_request_context(context: PlatformRequestContext) -> None:
    _REQUEST_CONTEXT.set(context)


def reset_current_request_context(token: Token[PlatformRequestContext | None]) -> None:
    _REQUEST_CONTEXT.reset(token)


def get_current_request_context() -> PlatformRequestContext:
    context = _REQUEST_CONTEXT.get()
    if context is None:
        raise RuntimeError("request_context_not_bound")
    return context
