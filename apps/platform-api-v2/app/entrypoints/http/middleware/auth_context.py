from __future__ import annotations

from dataclasses import replace

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.context import replace_current_request_context
from app.core.context.models import ActorContext, PlatformRequestContext
from app.core.security import InvalidTokenError, decode_access_token
from app.modules.iam.domain import PlatformRole
from app.modules.identity.infra.sqlalchemy.repository import SqlAlchemyIdentityRepository
from app.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository


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


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    payload = {
        "error": {
            "code": code,
            "message": message,
            "details": [],
        },
        "request_id": getattr(request.state, "request_id", None),
    }
    return JSONResponse(
        status_code=status_code,
        content=payload,
        headers=headers or {},
    )


def _load_actor(
    *,
    session_factory: sessionmaker[Session] | None,
    user_id: str,
) -> ActorContext | None:
    if session_factory is None:
        return None
    session = session_factory()
    try:
        repository = SqlAlchemyIdentityRepository(session)
        try:
            from uuid import UUID

            normalized_user_id = UUID(user_id)
        except ValueError:
            return None
        user = repository.get_user_by_id(normalized_user_id)
        if user is None or user.status != "active":
            return None
        projects_repository = SqlAlchemyProjectsRepository(session)
        platform_roles = (
            (PlatformRole.SUPER_ADMIN.value,) if user.is_super_admin else ()
        )
        return ActorContext(
            user_id=str(user.id),
            subject=user.external_subject,
            email=user.email,
            platform_roles=platform_roles,
            project_roles=projects_repository.list_user_project_roles(
                user_id=normalized_user_id
            ),
        )
    finally:
        session.close()


def _replace_context_actor(
    request: Request,
    *,
    actor: ActorContext,
) -> None:
    context: PlatformRequestContext = request.state.platform_context
    next_context = replace(context, actor=actor)
    request.state.platform_context = next_context
    replace_current_request_context(next_context)


def register_auth_context_middleware(app: FastAPI, settings: Settings) -> None:
    docs_paths = {"/docs", "/openapi.json", "/redoc"}
    public_paths = {
        "/_system/health",
        "/api/identity/session",
        "/api/identity/session/refresh",
    }
    public_path_methods = {
        ("DELETE", "/api/identity/session"),
    }

    @app.middleware("http")
    async def auth_context_middleware(request: Request, call_next):
        if (
            request.method.upper() == "OPTIONS"
            or request.url.path in public_paths
            or (request.method.upper(), request.url.path) in public_path_methods
            or (settings.api_docs_enabled and request.url.path in docs_paths)
        ):
            return await call_next(request)

        token = _extract_bearer_token(request.headers.get("authorization"))
        if not token:
            if settings.auth_required:
                return _error_response(
                    request,
                    status_code=401,
                    code="not_authenticated",
                    message="Missing bearer token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return await call_next(request)

        try:
            payload = decode_access_token(token, settings)
        except InvalidTokenError:
            return _error_response(
                request,
                status_code=401,
                code="invalid_token",
                message="Token validation failed",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user_id = str(payload.get("sub") or "")
        if not user_id:
            return _error_response(
                request,
                status_code=401,
                code="invalid_token",
                message="Token payload is incomplete",
                headers={"WWW-Authenticate": "Bearer"},
            )

        session_factory = getattr(request.app.state, "db_session_factory", None)
        if session_factory is None:
            return _error_response(
                request,
                status_code=503,
                code="platform_database_not_enabled",
                message="Platform database is not enabled",
            )

        actor = _load_actor(session_factory=session_factory, user_id=user_id)
        if actor is None:
            return _error_response(
                request,
                status_code=403,
                code="user_not_active",
                message="User is not active",
            )

        _replace_context_actor(request, actor=actor)
        response = await call_next(request)
        response.headers["x-user-id"] = actor.user_id or ""
        response.headers["x-user-subject"] = actor.subject or ""
        return response
