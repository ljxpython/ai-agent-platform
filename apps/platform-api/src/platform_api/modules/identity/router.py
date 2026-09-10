from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import sessionmaker

from platform_api.config import Settings
from platform_api.core.context.models import ActorContext
from platform_api.core.errors import ServiceUnavailableError
from platform_api.core.schemas import AckResponse
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.modules.identity.contracts import (
    ChangePasswordCommand,
    LoginCommand,
    LogoutCommand,
    RefreshSessionCommand,
    UpdateCurrentUserProfileCommand,
)
from platform_api.modules.identity.service import IdentityService
from platform_api.modules.identity.schemas import (
    AuthenticatedSession,
    SessionTokens,
    UserProfile,
)

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
def login(
    payload: LoginCommand,
    request: Request,
    service: IdentityService = Depends(get_identity_service),
) -> AuthenticatedSession:
    session, actor = service.login(payload)
    request.state.audit_actor = actor
    return session


@router.post("/session/refresh", response_model=SessionTokens)
def refresh_session(
    payload: RefreshSessionCommand,
    service: IdentityService = Depends(get_identity_service),
) -> SessionTokens:
    return service.refresh(payload)


@router.delete("/session", response_model=AckResponse)
def logout(
    payload: LogoutCommand,
    service: IdentityService = Depends(get_identity_service),
) -> AckResponse:
    service.logout(payload)
    return AckResponse()


@router.get("/me", response_model=UserProfile)
def get_me(
    actor: ActorContext = Depends(get_actor_context),
    service: IdentityService = Depends(get_identity_service),
) -> UserProfile:
    return service.get_current_user(actor)


@router.patch("/me", response_model=UserProfile)
def update_me(
    payload: UpdateCurrentUserProfileCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: IdentityService = Depends(get_identity_service),
) -> UserProfile:
    return service.update_current_user(actor=actor, command=payload)


@router.post("/password/change", response_model=SessionTokens)
def change_password(
    payload: ChangePasswordCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: IdentityService = Depends(get_identity_service),
) -> SessionTokens:
    return service.change_password(actor=actor, command=payload)
