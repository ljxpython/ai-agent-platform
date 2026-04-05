from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.db.access import (
    create_announcement,
    delete_announcement,
    get_announcement_by_id,
    get_user_by_id,
    list_announcements_admin,
    list_visible_announcements,
    mark_all_announcements_read,
    mark_announcement_read,
    parse_uuid,
    update_announcement,
)
from app.db.session import session_scope
from fastapi import APIRouter, HTTPException, Query, Request

from .common import (
    current_user_id_from_request,
    require_db_session_factory,
    require_project_role,
)
from .schemas import CreateAnnouncementRequest, UpdateAnnouncementRequest

router = APIRouter(prefix="/announcements", tags=["management-announcements"])


def _serialize_announcement(row: Any, *, is_read: bool) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "title": row.title,
        "summary": row.summary,
        "body": row.body,
        "tone": row.tone,
        "scope_type": row.scope_type,
        "scope_project_id": str(row.scope_project_id) if row.scope_project_id else None,
        "status": row.status,
        "publish_at": row.publish_at.isoformat() if row.publish_at else None,
        "expire_at": row.expire_at.isoformat() if row.expire_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "is_read": is_read,
    }


def _serialize_admin_announcement(row: Any) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "title": row.title,
        "summary": row.summary,
        "body": row.body,
        "tone": row.tone,
        "scope_type": row.scope_type,
        "scope_project_id": str(row.scope_project_id) if row.scope_project_id else None,
        "status": row.status,
        "publish_at": row.publish_at.isoformat() if row.publish_at else None,
        "expire_at": row.expire_at.isoformat() if row.expire_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _resolve_project_scope(request: Request, project_id: str | None) -> str | None:
    normalized = (
        project_id.strip()
        if isinstance(project_id, str) and project_id.strip()
        else None
    )
    if normalized is None:
        return None

    project_uuid = parse_uuid(normalized)
    if project_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_project_id")

    require_project_role(
        request, project_uuid, allowed_roles={"admin", "editor", "executor"}
    )
    return normalized


def _ensure_manage_access(
    request: Request,
    *,
    actor_user_id,
    scope_type: str,
    scope_project_id,
):
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        actor = get_user_by_id(session, actor_user_id)
        is_super_admin = bool(actor.is_super_admin) if actor is not None else False

    if scope_type == "global":
        if not is_super_admin:
            raise HTTPException(status_code=403, detail="super_admin_required")
        return None

    if scope_project_id is None:
        raise HTTPException(status_code=400, detail="scope_project_id_required")

    require_project_role(
        request, scope_project_id, allowed_roles={"admin", "editor"}
    )
    return None


def _normalize_scope_project_id(raw_value: str | None):
    normalized = raw_value.strip() if isinstance(raw_value, str) and raw_value.strip() else None
    if normalized is None:
        return None

    project_uuid = parse_uuid(normalized)
    if project_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_project_id")
    return project_uuid


def _payload_to_dict(payload: Any) -> dict[str, Any]:
    if hasattr(payload, "model_dump"):
        return payload.model_dump(exclude_unset=True)
    return dict(payload)


@router.get("")
async def list_announcements(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    query: str | None = Query(default=None),
    status: str | None = Query(default=None),
    scope_type: str | None = Query(default=None),
    project_id: str | None = Query(default=None),
) -> dict[str, Any]:
    actor_user_id = current_user_id_from_request(request)
    normalized_scope_project_id = _normalize_scope_project_id(project_id)

    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        actor = get_user_by_id(session, actor_user_id)
        is_super_admin = bool(actor.is_super_admin) if actor is not None else False
        if not is_super_admin:
            if normalized_scope_project_id is None:
                raise HTTPException(status_code=403, detail="project_scope_required")
            require_project_role(
                request,
                normalized_scope_project_id,
                allowed_roles={"admin", "editor"},
            )

        rows, total = list_announcements_admin(
            session,
            limit=limit,
            offset=offset,
            query=query,
            status=status,
            scope_type=scope_type,
            scope_project_id=normalized_scope_project_id,
        )
        return {
            "items": [_serialize_admin_announcement(row) for row in rows],
            "total": total,
        }


@router.post("")
async def create_announcement_item(
    request: Request,
    payload: CreateAnnouncementRequest,
) -> dict[str, Any]:
    actor_user_id = current_user_id_from_request(request)
    scope_project_id = _normalize_scope_project_id(payload.scope_project_id)
    _ensure_manage_access(
        request,
        actor_user_id=actor_user_id,
        scope_type=payload.scope_type,
        scope_project_id=scope_project_id,
    )

    publish_at = payload.publish_at or datetime.now(timezone.utc)
    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        row = create_announcement(
            session,
            title=payload.title.strip(),
            summary=payload.summary.strip(),
            body=payload.body.strip(),
            tone=payload.tone,
            scope_type=payload.scope_type,
            scope_project_id=scope_project_id,
            status=payload.status,
            publish_at=publish_at,
            expire_at=payload.expire_at,
            created_by=actor_user_id,
            updated_by=actor_user_id,
        )
        return _serialize_admin_announcement(row)


@router.patch("/{announcement_id}")
async def update_announcement_item(
    request: Request,
    announcement_id: str,
    payload: UpdateAnnouncementRequest,
) -> dict[str, Any]:
    actor_user_id = current_user_id_from_request(request)
    announcement_uuid = parse_uuid(announcement_id)
    if announcement_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_announcement_id")

    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        row = get_announcement_by_id(session, announcement_uuid)
        if row is None:
            raise HTTPException(status_code=404, detail="announcement_not_found")

        patch = _payload_to_dict(payload)

        next_scope_type = patch.get("scope_type", row.scope_type)
        next_scope_project_id = (
            _normalize_scope_project_id(patch.get("scope_project_id"))
            if "scope_project_id" in patch
            else row.scope_project_id
        )
        if next_scope_type == "global":
            next_scope_project_id = None
        _ensure_manage_access(
            request,
            actor_user_id=actor_user_id,
            scope_type=next_scope_type,
            scope_project_id=next_scope_project_id,
        )

        updated = update_announcement(
            session,
            row,
            title=patch["title"].strip() if isinstance(patch.get("title"), str) else row.title,
            summary=patch["summary"].strip() if isinstance(patch.get("summary"), str) else row.summary,
            body=patch["body"].strip() if isinstance(patch.get("body"), str) else row.body,
            tone=patch.get("tone", row.tone),
            scope_type=next_scope_type,
            scope_project_id=next_scope_project_id,
            status=patch.get("status", row.status),
            publish_at=patch.get("publish_at", row.publish_at),
            expire_at=patch["expire_at"] if "expire_at" in patch else row.expire_at,
            updated_by=actor_user_id,
        )
        return _serialize_admin_announcement(updated)


@router.delete("/{announcement_id}")
async def delete_announcement_item(
    request: Request,
    announcement_id: str,
) -> dict[str, Any]:
    actor_user_id = current_user_id_from_request(request)
    announcement_uuid = parse_uuid(announcement_id)
    if announcement_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_announcement_id")

    session_factory = require_db_session_factory(request)
    with session_scope(session_factory) as session:
        row = get_announcement_by_id(session, announcement_uuid)
        if row is None:
            raise HTTPException(status_code=404, detail="announcement_not_found")

        _ensure_manage_access(
            request,
            actor_user_id=actor_user_id,
            scope_type=row.scope_type,
            scope_project_id=row.scope_project_id,
        )
        delete_announcement(session, row)
        return {"ok": True}


@router.get("/feed")
async def get_announcements_feed(
    request: Request,
    project_id: str | None = Query(default=None),
) -> dict[str, Any]:
    user_id = current_user_id_from_request(request)
    session_factory = require_db_session_factory(request)
    normalized_project_id = _resolve_project_scope(request, project_id)
    project_uuid = parse_uuid(normalized_project_id) if normalized_project_id else None

    with session_scope(session_factory) as session:
        items = list_visible_announcements(
            session,
            user_id=user_id,
            project_id=project_uuid,
            now=datetime.now(timezone.utc),
        )
        return {
            "items": [
                _serialize_announcement(row, is_read=is_read) for row, is_read in items
            ],
            "total": len(items),
        }


@router.post("/{announcement_id}/read")
async def mark_announcement_as_read(
    request: Request,
    announcement_id: str,
) -> dict[str, Any]:
    user_id = current_user_id_from_request(request)
    session_factory = require_db_session_factory(request)

    announcement_uuid = parse_uuid(announcement_id)
    if announcement_uuid is None:
        raise HTTPException(status_code=400, detail="invalid_announcement_id")

    with session_scope(session_factory) as session:
        row = get_announcement_by_id(session, announcement_uuid)
        if row is None or row.status != "published":
            raise HTTPException(status_code=404, detail="announcement_not_found")

        if row.scope_type == "project":
            if row.scope_project_id is None:
                raise HTTPException(status_code=400, detail="announcement_scope_invalid")
            require_project_role(
                request,
                row.scope_project_id,
                allowed_roles={"admin", "editor", "executor"},
            )

        read_row = mark_announcement_read(
            session, announcement_id=announcement_uuid, user_id=user_id
        )
        return {"ok": True, "read_at": read_row.read_at.isoformat()}


@router.post("/read-all")
async def mark_all_announcements_as_read(
    request: Request,
    project_id: str | None = Query(default=None),
) -> dict[str, Any]:
    user_id = current_user_id_from_request(request)
    session_factory = require_db_session_factory(request)
    normalized_project_id = _resolve_project_scope(request, project_id)
    project_uuid = parse_uuid(normalized_project_id) if normalized_project_id else None

    with session_scope(session_factory) as session:
        changed = mark_all_announcements_read(
            session,
            user_id=user_id,
            project_id=project_uuid,
            now=datetime.now(timezone.utc),
        )
        return {"ok": True, "count": changed}
