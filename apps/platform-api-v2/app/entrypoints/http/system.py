from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.core.context.models import ActorContext, RequestContext
from app.entrypoints.http.dependencies import get_actor_context, get_request_context
from app.modules.platform_config.application import PlatformConfigService, UpdateFeatureFlagsCommand

router = APIRouter(prefix="/_system", tags=["system"])


def get_platform_config_service(request: Request) -> PlatformConfigService:
    settings: Settings = request.app.state.settings
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is not None and not isinstance(session_factory, sessionmaker):
        session_factory = None
    return PlatformConfigService(
        session_factory=session_factory,
        settings=settings,
    )


@router.get("/health")
async def health(
    request: Request,
    context: RequestContext = Depends(get_request_context),
) -> dict[str, str]:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "env": settings.app_env,
        "request_id": context.request_id,
    }


@router.get("/platform-config")
async def platform_config(
    actor: ActorContext = Depends(get_actor_context),
    service: PlatformConfigService = Depends(get_platform_config_service),
) -> dict[str, object]:
    return await service.get_snapshot(actor=actor)


@router.patch("/platform-config/feature-flags")
async def update_platform_feature_flags(
    payload: UpdateFeatureFlagsCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: PlatformConfigService = Depends(get_platform_config_service),
) -> dict[str, object]:
    return await service.update_feature_flags(actor=actor, command=payload)
