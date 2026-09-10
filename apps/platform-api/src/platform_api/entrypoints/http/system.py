from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from starlette.concurrency import run_in_threadpool

from platform_api.config import Settings
from platform_api.core.context.models import ActorContext, RequestContext
from platform_api.entrypoints.http.dependencies import (
    get_actor_context,
    get_request_context,
)
from platform_api.modules.platform_config.service import PlatformConfigService
from platform_api.modules.platform_config.contracts import UpdateFeatureFlagsCommand

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


def _database_ready(request: Request) -> bool:
    if not request.app.state.settings.platform_db_enabled:
        return True
    factory = getattr(request.app.state, "db_session_factory", None)
    if factory is None:
        return False
    try:
        with factory() as session:
            session.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError:
        return False


@router.get("/health")
async def health(
    request: Request,
    context: RequestContext = Depends(get_request_context),
    service: PlatformConfigService = Depends(get_platform_config_service),
) -> dict[str, str]:
    settings = request.app.state.settings
    database_ready = await run_in_threadpool(_database_ready, request)
    return {
        "status": "ok" if database_ready else "degraded",
        "service": settings.app_name,
        "version": settings.app_version,
        "env": settings.app_env,
        "request_id": context.request_id,
        "trace_id": context.trace_id,
        "database_ready": str(database_ready).lower(),
    }


@router.get("/probes/live")
async def live_probe(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    return {
        "status": "alive",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@router.get("/probes/ready")
async def ready_probe(
    request: Request,
    service: PlatformConfigService = Depends(get_platform_config_service),
) -> dict[str, object]:
    database_ready = await run_in_threadpool(_database_ready, request)
    ready = database_ready
    return {
        "status": "ready" if ready else "not_ready",
        "database_ready": database_ready,
    }


@router.get("/metrics")
def metrics(
    actor: ActorContext = Depends(get_actor_context),
    service: PlatformConfigService = Depends(get_platform_config_service),
) -> dict[str, object]:
    return service.get_observability_snapshot_for_actor(actor=actor)


@router.get("/platform-config")
def platform_config(
    actor: ActorContext = Depends(get_actor_context),
    service: PlatformConfigService = Depends(get_platform_config_service),
) -> dict[str, object]:
    return service.get_snapshot(actor=actor)


@router.patch("/platform-config/feature-flags")
def update_platform_feature_flags(
    payload: UpdateFeatureFlagsCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: PlatformConfigService = Depends(get_platform_config_service),
) -> dict[str, object]:
    return service.update_feature_flags(actor=actor, command=payload)
