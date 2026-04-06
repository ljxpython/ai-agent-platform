from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import sessionmaker

from app.core.context.models import ActorContext
from app.core.schemas import AckResponse
from app.entrypoints.http.dependencies import get_actor_context
from app.modules.announcements.application import (
    AnnouncementFeedQuery,
    AnnouncementsService,
    CreateAnnouncementCommand,
    ListAnnouncementsQuery,
    UpdateAnnouncementCommand,
)
from app.modules.announcements.domain import AnnouncementItem, AnnouncementPage, AnnouncementScopeType, AnnouncementStatus

router = APIRouter(prefix="/api/announcements", tags=["announcements"])


def get_announcements_service(request: Request) -> AnnouncementsService:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is not None and not isinstance(session_factory, sessionmaker):
        session_factory = None
    return AnnouncementsService(session_factory=session_factory)


@router.get("", response_model=AnnouncementPage)
async def list_announcements(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    query: str | None = Query(default=None),
    status: AnnouncementStatus | None = Query(default=None),
    scope_type: AnnouncementScopeType | None = Query(default=None),
    project_id: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: AnnouncementsService = Depends(get_announcements_service),
) -> AnnouncementPage:
    return await service.list_admin_announcements(
        actor=actor,
        query=ListAnnouncementsQuery(
            limit=limit,
            offset=offset,
            query=query,
            status=status,
            scope_type=scope_type,
            project_id=project_id,
        ),
    )


@router.post("", response_model=AnnouncementItem)
async def create_announcement(
    payload: CreateAnnouncementCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: AnnouncementsService = Depends(get_announcements_service),
) -> AnnouncementItem:
    return await service.create_announcement(actor=actor, command=payload)


@router.patch("/{announcement_id}", response_model=AnnouncementItem)
async def update_announcement(
    announcement_id: str,
    payload: UpdateAnnouncementCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: AnnouncementsService = Depends(get_announcements_service),
) -> AnnouncementItem:
    return await service.update_announcement(
        actor=actor,
        announcement_id=announcement_id,
        command=payload,
    )


@router.delete("/{announcement_id}", response_model=AckResponse)
async def delete_announcement(
    announcement_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: AnnouncementsService = Depends(get_announcements_service),
) -> AckResponse:
    await service.delete_announcement(actor=actor, announcement_id=announcement_id)
    return AckResponse()


@router.get("/feed", response_model=AnnouncementPage)
async def announcement_feed(
    project_id: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: AnnouncementsService = Depends(get_announcements_service),
) -> AnnouncementPage:
    return await service.feed(
        actor=actor,
        query=AnnouncementFeedQuery(project_id=project_id),
    )


@router.post("/{announcement_id}/read")
async def mark_announcement_read(
    announcement_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: AnnouncementsService = Depends(get_announcements_service),
) -> dict[str, str | bool]:
    read_at = await service.mark_read(actor=actor, announcement_id=announcement_id)
    return {"ok": True, "read_at": read_at.isoformat()}


@router.post("/read-all")
async def mark_all_announcements_read(
    project_id: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: AnnouncementsService = Depends(get_announcements_service),
) -> dict[str, int | bool]:
    count = await service.mark_all_read(
        actor=actor,
        query=AnnouncementFeedQuery(project_id=project_id),
    )
    return {"ok": True, "count": count}
