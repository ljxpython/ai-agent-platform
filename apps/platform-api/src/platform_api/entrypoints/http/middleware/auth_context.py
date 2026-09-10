from __future__ import annotations

from dataclasses import replace

from fastapi import FastAPI, Request
from starlette.concurrency import run_in_threadpool

from platform_api.config import Settings
from platform_api.core.context import replace_current_request_context
from platform_api.core.context.models import ActorContext, PlatformRequestContext
from platform_api.core.errors.payload import build_error_response
from platform_api.core.security import InvalidTokenError, decode_access_token
from platform_api.modules.identity.actors import load_user_actor as _load_actor
from platform_api.modules.service_accounts.service import ServiceAccountsService


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2:
        return None
    scheme, token = parts
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def _replace_context_actor(
    request: Request,
    *,
    actor: ActorContext,
) -> None:
    context: PlatformRequestContext = request.state.platform_context
    next_context = replace(context, actor=actor)
    request.state.platform_context = next_context
    replace_current_request_context(next_context)


def _extract_api_key(request: Request, settings: Settings) -> str | None:
    header_name = settings.service_account_api_key_header.lower()
    api_key = request.headers.get(header_name)
    if api_key and api_key.strip():
        return api_key.strip()
    fallback = request.headers.get("x-api-key")
    if fallback and fallback.strip():
        return fallback.strip()
    return None


def register_auth_context_middleware(app: FastAPI, settings: Settings) -> None:
    docs_paths = {"/docs", "/openapi.json", "/redoc"}
    public_paths = {
        "/_system/health",
        "/_system/probes/live",
        "/_system/probes/ready",
        "/api/identity/session",
        "/api/identity/session/refresh",
        "/api/runtime/internal/model-config",
    }
    public_path_methods = {
        ("DELETE", "/api/identity/session"),
    }

    @app.middleware("http")
    async def auth_context_middleware(request: Request, call_next):
        header_project_id = request.headers.get("x-project-id")
        context_project_id = request.state.platform_context.project.project_id
        path_segments = [
            segment for segment in request.url.path.strip("/").split("/") if segment
        ]
        route_project_id = (
            path_segments[2]
            if len(path_segments) >= 3 and path_segments[:2] == ["api", "projects"]
            else None
        )
        if (
            header_project_id
            and route_project_id
            and header_project_id.strip() != route_project_id
        ):
            return build_error_response(
                status_code=400,
                code="project_scope_mismatch",
                message="Route and header project scopes do not match",
                request_id=getattr(request.state, "request_id", None),
            )
        if (
            request.method.upper() == "OPTIONS"
            or request.url.path in public_paths
            or (request.method.upper(), request.url.path) in public_path_methods
            or (settings.api_docs_enabled and request.url.path in docs_paths)
        ):
            return await call_next(request)

        token = _extract_bearer_token(request.headers.get("authorization"))
        api_key = (
            _extract_api_key(request, settings)
            if settings.service_accounts_enabled
            else None
        )
        if not token and not api_key:
            if settings.auth_required:
                return build_error_response(
                    status_code=401,
                    code="not_authenticated",
                    message="Missing authentication credential",
                    request_id=getattr(request.state, "request_id", None),
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return await call_next(request)

        session_factory = getattr(request.app.state, "db_session_factory", None)
        if session_factory is None:
            return build_error_response(
                status_code=503,
                code="platform_database_not_enabled",
                message="Platform database is not enabled",
                request_id=getattr(request.state, "request_id", None),
            )

        actor: ActorContext | None = None
        if token:
            try:
                payload = decode_access_token(token, settings)
            except InvalidTokenError:
                return build_error_response(
                    status_code=401,
                    code="invalid_token",
                    message="Token validation failed",
                    request_id=getattr(request.state, "request_id", None),
                    headers={"WWW-Authenticate": "Bearer"},
                )

            user_id = str(payload.get("sub") or "")
            if not user_id:
                return build_error_response(
                    status_code=401,
                    code="invalid_token",
                    message="Token payload is incomplete",
                    request_id=getattr(request.state, "request_id", None),
                    headers={"WWW-Authenticate": "Bearer"},
                )
            project_id = context_project_id
            actor = await run_in_threadpool(
                _load_actor,
                session_factory=session_factory,
                user_id=user_id,
                project_id=project_id,
            )
            if actor is None:
                return build_error_response(
                    status_code=403,
                    code="user_not_active",
                    message="User is not active",
                    request_id=getattr(request.state, "request_id", None),
                )
        elif api_key:
            actor = await run_in_threadpool(
                ServiceAccountsService(
                    session_factory=session_factory
                ).authenticate_api_key,
                api_key,
                project_id=request.state.platform_context.project.project_id,
            )
            if actor is None:
                return build_error_response(
                    status_code=401,
                    code="invalid_api_key",
                    message="API key validation failed",
                    request_id=getattr(request.state, "request_id", None),
                )

        _replace_context_actor(request, actor=actor)
        response = await call_next(request)
        response.headers["x-user-id"] = actor.user_id or ""
        response.headers["x-user-subject"] = actor.subject or ""
        response.headers["x-principal-type"] = actor.principal_type
        response.headers["x-authentication-type"] = actor.authentication_type
        return response
