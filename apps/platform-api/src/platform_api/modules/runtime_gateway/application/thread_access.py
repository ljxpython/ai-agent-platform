"""Platform-owned Thread ACL, persisted independently from Runtime metadata."""
from __future__ import annotations

import time
from uuid import uuid4

from sqlalchemy import or_, select
from platform_api.core.db import session_scope
from platform_api.core.identifiers import parse_uuid
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import ThreadAccessRecord
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
from platform_api.modules.audit.models import AuditLogRecord

from platform_api.core.context.models import ActorContext
from platform_api.core.errors import BadRequestError, ForbiddenError

ACL_KEYS = frozenset({"access_version", "owner_user_id", "visibility", "shared_actions", "readable_by", "takeovers", "project_actions", "allowed_actions"})
SHARE_ACTIONS = frozenset({"read", "comment", "edit", "share", "delete"})


def is_manager(actor: ActorContext, project_id: str) -> bool:
    return actor.is_authenticated and actor.principal_type == "user" and (
        actor.has_platform_role("platform_super_admin") or actor.has_project_role(project_id, "project_admin")
    )


def is_owner(actor: ActorContext, metadata: dict) -> bool:
    return bool(actor.principal_type == "user" and actor.user_id and metadata.get("owner_user_id") == actor.user_id)


def private_owner(actor: ActorContext, metadata: dict) -> bool:
    return metadata.get("access_version") == 1 and metadata.get("visibility") == "private" and is_owner(actor, metadata)


def personal_memory_allowed(metadata: dict, *, project_id: str, user_id: str) -> bool:
    return (metadata.get("access_version") == 1 and metadata.get("project_id") == project_id
            and metadata.get("owner_user_id") == user_id and metadata.get("visibility") == "private"
            and not metadata.get("shared_actions") and not metadata.get("project_actions"))


def initial_metadata(actor: ActorContext, metadata: dict) -> dict:
    result = {key: value for key, value in metadata.items() if key not in ACL_KEYS and key not in {"sandbox_id", "workspace_id"}}
    personal = actor.principal_type == "user" and bool(actor.user_id)
    result.update(access_version=1, owner_user_id=actor.user_id if personal else None,
                  visibility="private" if personal else "project", shared_actions={}, takeovers={},
                  readable_by=[actor.user_id] if personal else [],
                  project_actions=[] if personal else ["read", "comment", "edit"])
    return result


def allowed(actor: ActorContext, project_id: str, metadata: dict, action: str) -> bool:
    if not actor.is_authenticated or metadata.get("project_id") != project_id:
        return False
    if action in {"delete", "approve"} and is_manager(actor, project_id):
        return True
    if metadata.get("access_version") != 1:
        return False  # Old unowned data is never implicitly assigned to a caller.
    if not actor.project_role_set(project_id) and not (action == "read" and is_manager(actor, project_id)):
        return False
    if action in {"terminal", "full_access"}:
        return private_owner(actor, metadata)
    if is_owner(actor, metadata):
        return True
    if action in {"delete", "approve"}:
        return False
    if action == "read" and is_manager(actor, project_id):
        takeover = metadata.get("takeovers", {}).get(actor.user_id, {})
        if isinstance(takeover, dict) and isinstance(takeover.get("expires_at"), (int, float)) and takeover["expires_at"] > time.time():
            return True
    if metadata.get("visibility") == "project":
        return bool(actor.project_role_set(project_id)) and (
            action in metadata.get("project_actions", []) or is_manager(actor, project_id)
        )
    if actor.principal_type != "user" or not actor.user_id:
        return False
    actions = metadata.get("shared_actions", {}).get(actor.user_id, [])
    return action in actions


def require_action(actor: ActorContext, project_id: str, metadata: dict, action: str) -> None:
    if not allowed(actor, project_id, metadata, action):
        raise ForbiddenError(code="thread_action_denied", message="Thread action is not permitted")


def record_metadata(row: ThreadAccessRecord) -> dict:
    return {"project_id": row.project_id, "access_version": 1, "owner_user_id": row.owner_user_id,
            "visibility": row.visibility, "shared_actions": row.shared_actions,
            "project_actions": row.project_actions, "takeovers": row.takeovers}


def register(factory, *, thread_id: str, project_id: str, actor: ActorContext) -> dict:
    metadata = initial_metadata(actor, {"project_id": project_id})
    with session_scope(factory) as session:
        row = ThreadAccessRecord(thread_id=thread_id, **{key: metadata[key] for key in (
            "project_id", "owner_user_id", "visibility", "shared_actions", "project_actions", "takeovers",
        )})
        session.add(row)
        session.flush()
        return record_metadata(row)


def get(factory, thread_id: str) -> dict:
    with session_scope(factory) as session:
        row = session.get(ThreadAccessRecord, thread_id)
        return record_metadata(row) if row else {}


def remove(factory, *, actor: ActorContext, project_id: str, thread_id: str) -> None:
    with session_scope(factory) as session:
        row = session.get(ThreadAccessRecord, thread_id, with_for_update=True)
        if row is not None:
            if row.project_id != project_id:
                raise ForbiddenError(code="thread_action_denied", message="Thread is unavailable")
            session.delete(row)
        _audit(session, actor=actor, project_id=project_id, thread_id=thread_id,
               action="thread.deleted", reason="Authorized Thread deletion")


def visible_records(factory, *, actor: ActorContext, project_id: str) -> dict[str, dict]:
    with session_scope(factory) as session:
        # Filter candidates in SQL; allowed() still checks membership, actions and expiry.
        candidates = [ThreadAccessRecord.visibility == "project"]
        if actor.principal_type == "user" and actor.user_id:
            candidates.extend([
                ThreadAccessRecord.owner_user_id == actor.user_id,
                ThreadAccessRecord.shared_actions[actor.user_id].as_string().is_not(None),
            ])
            if is_manager(actor, project_id):
                candidates.append(ThreadAccessRecord.takeovers[actor.user_id].as_string().is_not(None))
        # ponytail: JSON predicates scan project rows; normalize shares if large-project query latency requires indexes.
        rows = session.scalars(select(ThreadAccessRecord).where(
            ThreadAccessRecord.project_id == project_id, or_(*candidates)))
        return {row.thread_id: record_metadata(row) for row in rows if allowed(actor, project_id, record_metadata(row), "read")}


def _audit(session, *, actor: ActorContext, project_id: str, thread_id: str, action: str, reason: str) -> None:
    session.add(AuditLogRecord(
        request_id=str(uuid4()), plane="runtime_gateway", action=action, target_type="thread", target_id=thread_id,
        actor_user_id=actor.user_id, actor_subject=actor.subject, project_id=project_id, result="success",
        method="POST", path=f"/api/langgraph/threads/{thread_id}/access", status_code=200, duration_ms=0,
        metadata_json={"reason": reason},
    ))


def audit_takeover_access(factory, *, actor: ActorContext, project_id: str, thread_id: str) -> None:
    with session_scope(factory) as session:
        _audit(session, actor=actor, project_id=project_id, thread_id=thread_id,
               action="thread.takeover.accessed", reason="time-limited private Thread access")


def share(factory, *, actor: ActorContext, project_id: str, thread_id: str, user_id: str | None, actions: list[str]) -> dict:
    if len(actions) != len(set(actions)) or set(actions) - SHARE_ACTIONS or (actions and "read" not in actions):
        raise BadRequestError(code="invalid_share_actions", message="Shared actions must be distinct known actions and include read")
    with session_scope(factory) as session:
        row = session.get(ThreadAccessRecord, thread_id, with_for_update=True)
        metadata = record_metadata(row) if row else {}
        require_action(actor, project_id, metadata, "share")
        if not is_owner(actor, metadata) and not (row.visibility == "project" and is_manager(actor, project_id)):
            current = set(metadata.get("shared_actions", {}).get(actor.user_id, []))
            if user_id is None or set(actions) - current:
                raise ForbiddenError(code="share_delegation_denied", message="Cannot delegate more actions than granted")
        if user_id is None:
            if set(actions) - {"read", "comment", "edit"}:
                raise BadRequestError(code="invalid_project_share", message="Project sharing supports read, comment and edit only")
            row.visibility = "project" if actions else "private"
            row.project_actions = actions
        else:
            member = SqlAlchemyProjectsRepository(session).get_project_member_role(
                project_id=parse_uuid(project_id, code="invalid_project_id"),
                user_id=parse_uuid(user_id, code="invalid_user_id"),
            )
            if member is None and actions:
                raise ForbiddenError(code="share_project_member_required", message="Share target must be a current project member")
            if "delete" in actions and (member is None or member.value != "project_admin"):
                raise ForbiddenError(code="share_delete_denied", message="Only the owner or a project/platform administrator may delete")
            grants = dict(row.shared_actions)
            if actions:
                if user_id not in grants and len(grants) >= 100:
                    raise BadRequestError(code="share_limit_reached", message="A Thread supports at most 100 individual shares")
                grants[user_id] = actions
            else:
                grants.pop(user_id, None)
            row.shared_actions = grants
        _audit(session, actor=actor, project_id=project_id, thread_id=thread_id,
               action="thread.share.updated", reason=f"target={user_id or 'project'}; actions={','.join(actions)}")
        session.flush()
        return record_metadata(row)


def takeover(factory, *, actor: ActorContext, project_id: str, thread_id: str, category: str,
             reason: str, reference: str, duration_minutes: int) -> dict:
    if not is_manager(actor, project_id):
        raise ForbiddenError(code="thread_takeover_denied", message="Administrator permission required")
    if category not in {"security_incident", "compliance", "user_support", "handover"} or not 1 <= duration_minutes <= 60 or len(reason.strip()) < 10 or len(reference.strip()) < 3:
        raise BadRequestError(code="invalid_takeover", message="Provide a supported category, reason, case reference and a 1–60 minute duration")
    with session_scope(factory) as session:
        row = session.get(ThreadAccessRecord, thread_id, with_for_update=True)
        if row is None or row.project_id != project_id:
            raise ForbiddenError(code="thread_action_denied", message="Thread is unavailable")
        grants = {key: value for key, value in row.takeovers.items() if value.get("expires_at", 0) > time.time()}
        grant = {"expires_at": time.time() + duration_minutes * 60, "category": category,
                 "reason": reason.strip(), "reference": reference.strip()}
        grants[actor.user_id] = grant
        row.takeovers = grants
        _audit(session, actor=actor, project_id=project_id, thread_id=thread_id,
               action="thread.takeover.granted", reason=f"{category}; {reference}; {reason}; expires_at={grant['expires_at']}")
        return {"thread_id": thread_id, "actions": ["read"], **grant}


def end_takeover(factory, *, actor: ActorContext, project_id: str, thread_id: str) -> dict:
    if not is_manager(actor, project_id):
        raise ForbiddenError(code="thread_takeover_denied", message="Administrator permission required")
    with session_scope(factory) as session:
        row = session.get(ThreadAccessRecord, thread_id, with_for_update=True)
        if row is None or row.project_id != project_id:
            raise ForbiddenError(code="thread_action_denied", message="Thread is unavailable")
        grants = dict(row.takeovers)
        grants.pop(actor.user_id, None)
        row.takeovers = grants
        _audit(session, actor=actor, project_id=project_id, thread_id=thread_id,
               action="thread.takeover.ended", reason="Administrator ended temporary access")
        return {"thread_id": thread_id, "ended": True}
