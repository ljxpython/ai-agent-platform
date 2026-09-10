from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from platform_api.config import Settings
from platform_api.core.context.models import ActorContext
from platform_api.core.errors import ServiceUnavailableError
from platform_api.core.schemas import AckResponse
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.modules.identity.application.contracts import (
    ChangePasswordCommand,
    LoginCommand,
    LogoutCommand,
    RefreshSessionCommand,
    UpdateCurrentUserProfileCommand,
)
from platform_api.modules.identity.application.service import IdentityService
from platform_api.modules.identity.domain import AuthenticatedSession, SessionTokens, UserProfile

router = APIRouter(prefix="/api/identity", tags=["identity"])


def get_identity_service(request: Request) -> IdentityService:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    settings: Settings = request.app.state.settings
    if session_factory is not None and not isinstance(session_factory, sessionmaker):
        raise ServiceUnavailableError(
            code="invalid_session_factory",
            message="Database session factory is invalid",
        )
    return IdentityService(
        settings=settings,
        session_factory=session_factory,
    )


@router.post("/session", response_model=AuthenticatedSession)
async def login(
    payload: LoginCommand,
    request: Request,
    service: IdentityService = Depends(get_identity_service),
) -> AuthenticatedSession:
    session, actor = await service.login(payload)
    request.state.audit_actor = actor
    return session


@router.post("/session/refresh", response_model=SessionTokens)
async def refresh_session(
    payload: RefreshSessionCommand,
    service: IdentityService = Depends(get_identity_service),
) -> SessionTokens:
    return await service.refresh(payload)


@router.delete("/session", response_model=AckResponse)
async def logout(
    payload: LogoutCommand,
    service: IdentityService = Depends(get_identity_service),
) -> AckResponse:
    await service.logout(payload)
    return AckResponse()


@router.get("/me", response_model=UserProfile)
async def get_me(
    actor: ActorContext = Depends(get_actor_context),
    service: IdentityService = Depends(get_identity_service),
) -> UserProfile:
    return await service.get_current_user(actor)


@router.patch("/me", response_model=UserProfile)
async def update_me(
    payload: UpdateCurrentUserProfileCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: IdentityService = Depends(get_identity_service),
) -> UserProfile:
    return await service.update_current_user(actor=actor, command=payload)


@router.post("/password/change", response_model=SessionTokens)
async def change_password(
    payload: ChangePasswordCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: IdentityService = Depends(get_identity_service),
) -> SessionTokens:
    return await service.change_password(actor=actor, command=payload)
