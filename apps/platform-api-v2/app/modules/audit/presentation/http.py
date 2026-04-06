from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import sessionmaker

from app.core.context.models import ActorContext
from app.entrypoints.http.dependencies import get_actor_context
from app.modules.audit.application import AuditEventPage, AuditService, ListAuditEventsQuery
from app.modules.audit.domain import AuditPlane, AuditResult

router = APIRouter(prefix="/api/audit", tags=["audit"])


def get_audit_service(request: Request) -> AuditService:
    session_factory = getattr(request.app.state, "db_session_factory", None)
    if session_factory is not None and not isinstance(session_factory, sessionmaker):
        session_factory = None
    return AuditService(session_factory=session_factory)


@router.get("", response_model=AuditEventPage)
async def list_audit_events(
    project_id: str | None = Query(default=None),
    plane: AuditPlane | None = Query(default=None),
    action: str | None = Query(default=None),
    target_type: str | None = Query(default=None),
    target_id: str | None = Query(default=None),
    actor_user_id: str | None = Query(default=None),
    method: str | None = Query(default=None),
    result: AuditResult | None = Query(default=None),
    status_code: int | None = Query(default=None, ge=100, le=599),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    actor: ActorContext = Depends(get_actor_context),
    service: AuditService = Depends(get_audit_service),
) -> AuditEventPage:
    return await service.list_events(
        actor=actor,
        query=ListAuditEventsQuery(
            project_id=project_id,
            plane=plane,
            action=action,
            target_type=target_type,
            target_id=target_id,
            actor_user_id=actor_user_id,
            method=method,
            result=result,
            status_code=status_code,
            created_from=created_from,
            created_to=created_to,
            limit=limit,
            offset=offset,
        ),
    )
