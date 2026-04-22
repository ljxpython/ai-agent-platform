from __future__ import annotations

from fastapi import Request

from app.core.context.models import (
    ActorContext,
    PlatformRequestContext,
    ProjectContext,
    RequestContext,
    TenantContext,
)


def get_platform_request_context(request: Request) -> PlatformRequestContext:
    return request.state.platform_context


def get_request_context(request: Request) -> RequestContext:
    return get_platform_request_context(request).request


def get_tenant_context(request: Request) -> TenantContext:
    return get_platform_request_context(request).tenant


def get_project_context(request: Request) -> ProjectContext:
    return get_platform_request_context(request).project


def get_actor_context(request: Request) -> ActorContext:
    return get_platform_request_context(request).actor
