from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api", tags=["interaction-data"])


@router.get("/meta")
async def service_meta(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "status": "ready",
        "db_enabled": "true" if settings.interaction_db_enabled else "false",
    }
