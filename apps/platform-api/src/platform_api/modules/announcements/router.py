from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import sessionmaker

from platform_api.core.context.models import ActorContext
from platform_api.core.schemas import AckResponse
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.modules.announcements.contracts import (
    AnnouncementFeedQuery,
    CreateAnnouncementCommand,
    ListAnnouncementsQuery,
    UpdateAnnouncementCommand,
)
from platform_api.modules.announcements.service import AnnouncementsService
from platform_api.modules.announcements.schemas import (
    AnnouncementItem,
    AnnouncementPage,
    AnnouncementScopeType,
    AnnouncementStatus,
)

router = APIRouter(prefix="/api/announcements", tags=["announcements"])


def get_announcements_service(request: Request) -> AnnouncementsService:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is not None and not isinstance(session_factory, sessionmaker):
        session_factory = None
    return AnnouncementsService(session_factory=session_factory)


@router.get("", response_model=AnnouncementPage)
def list_announcements(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    query: str | None = Query(default=None),
    status: AnnouncementStatus | None = Query(default=None),
    scope_type: AnnouncementScopeType | None = Query(default=None),
    project_id: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: AnnouncementsService = Depends(get_announcements_service),
) -> AnnouncementPage:
    return service.list_admin_announcements(
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
def create_announcement(
    payload: CreateAnnouncementCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: AnnouncementsService = Depends(get_announcements_service),
) -> AnnouncementItem:
    return service.create_announcement(actor=actor, command=payload)


@router.patch("/{announcement_id}", response_model=AnnouncementItem)
def update_announcement(
    announcement_id: str,
    payload: UpdateAnnouncementCommand,
    actor: ActorContext = Depends(get_actor_context),
    service: AnnouncementsService = Depends(get_announcements_service),
) -> AnnouncementItem:
    return service.update_announcement(
        actor=actor,
        announcement_id=announcement_id,
        command=payload,
    )


@router.delete("/{announcement_id}", response_model=AckResponse)
def delete_announcement(
    announcement_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: AnnouncementsService = Depends(get_announcements_service),
) -> AckResponse:
    service.delete_announcement(actor=actor, announcement_id=announcement_id)
    return AckResponse()


@router.get("/feed", response_model=AnnouncementPage)
def announcement_feed(
    project_id: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: AnnouncementsService = Depends(get_announcements_service),
) -> AnnouncementPage:
    return service.feed(
        actor=actor,
        query=AnnouncementFeedQuery(project_id=project_id),
    )


@router.post("/{announcement_id}/read")
def mark_announcement_read(
    announcement_id: str,
    actor: ActorContext = Depends(get_actor_context),
    service: AnnouncementsService = Depends(get_announcements_service),
) -> dict[str, str | bool]:
    read_at = service.mark_read(actor=actor, announcement_id=announcement_id)
    return {"ok": True, "read_at": read_at.isoformat()}


@router.post("/read-all")
def mark_all_announcements_read(
    project_id: str | None = Query(default=None),
    actor: ActorContext = Depends(get_actor_context),
    service: AnnouncementsService = Depends(get_announcements_service),
) -> dict[str, int | bool]:
    count = service.mark_all_read(
        actor=actor,
        query=AnnouncementFeedQuery(project_id=project_id),
    )
    return {"ok": True, "count": count}
