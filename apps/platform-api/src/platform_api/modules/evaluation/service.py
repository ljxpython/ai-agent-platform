"""Authorized evaluation sources, historical projections and revocation."""

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from platform_api.core.context.models import ActorContext
from platform_api.core.db import session_scope
from platform_api.core.errors import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from platform_api.modules.audit.models import AuditLogRecord
from platform_api.modules.evaluation.models import EvaluationExport, FeedbackEvent
from platform_api.modules.identity.models import (
    UserRecord,
    normalize_user_platform_roles,
)
from platform_api.modules.projects.models import ProjectMemberRecord, ProjectRecord
from platform_api.modules.runtime_gateway.application import thread_access
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    ThreadAccessRecord,
)


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def authorize(session, actor, project_id, thread_id, action="comment"):
    record = session.scalar(
        select(ThreadAccessRecord)
        .where(ThreadAccessRecord.thread_id == thread_id)
        .with_for_update()
    )
    if record is None or record.project_id != project_id:
        raise ForbiddenError(code="thread_project_denied", message="无权访问该会话。")
    access = {
        key: getattr(record, key)
        for key in (
            "project_id",
            "owner_user_id",
            "visibility",
            "shared_actions",
            "project_actions",
            "takeovers",
        )
    }
    access["access_version"] = 1
    thread_access.require_action(actor, project_id, access, action)
    if actor.principal_type != "user" or not actor.user_id:
        raise ForbiddenError(
            code="evaluation_human_required", message="需要已认证用户。"
        )
    return record


def audit(session, actor, project_id, target_id, action, *, retention_policy=None):
    session.add(
        AuditLogRecord(
            request_id=target_id,
            plane="project",
            action=action,
            target_type="evaluation",
            target_id=target_id,
            actor_user_id=actor.user_id,
            project_id=project_id,
            result="success",
            method="POST",
            path="/api/evaluation",
            status_code=200,
            duration_ms=0,
            metadata_json={"retention_policy": retention_policy}
            if retention_policy
            else {},
        )
    )


def latest(session, actor_id, thread_id, message_id):
    return session.scalar(
        select(FeedbackEvent)
        .where(
            FeedbackEvent.actor_id == actor_id,
            FeedbackEvent.thread_id == thread_id,
            FeedbackEvent.message_id == message_id,
        )
        .order_by(FeedbackEvent.revision.desc())
        .limit(1)
    )


def authorized_package(factory, project_id, export_id):
    with session_scope(factory) as session:
        return _authorized_package(session, project_id, export_id)


def lock_packages(session, export_ids):
    """Lock source threads before grants, including the whole batch and its parents."""
    pending = {str(identifier) for identifier in export_ids}
    exports = {}
    threads = set()
    while pending:
        identifier = pending.pop()
        if identifier in exports:
            continue
        export = session.get(EvaluationExport, identifier)
        exports[identifier] = export
        if export is None:
            continue
        payload = export.payload
        threads.update(payload.get("source_threads", []))
        if payload.get("thread_id"):
            threads.add(payload["thread_id"])
        if payload.get("source_export_id"):
            pending.add(payload["source_export_id"])
        if (
            payload.get("source_kind") != "work_item"
            and payload.get("purpose") != "quality_inspection"
        ):
            event = session.get(FeedbackEvent, export.event_id)
            if event:
                threads.add(event.thread_id)
    if threads:
        session.scalars(
            select(ThreadAccessRecord)
            .where(ThreadAccessRecord.thread_id.in_(threads))
            .order_by(ThreadAccessRecord.thread_id)
            .with_for_update()
        ).all()
    if exports:
        # Refresh after waiting: a concurrent revocation must never validate stale status.
        session.scalars(
            select(EvaluationExport)
            .where(EvaluationExport.export_id.in_(exports))
            .order_by(EvaluationExport.export_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).all()
    return exports


def _authorized_package(session, project_id, export_id):
    export = lock_packages(session, [export_id])[str(export_id)]
    if not export or export.project_id != project_id:
        raise NotFoundError(
            code="evaluation_export_missing", message="导出记录不存在。"
        )
    expiry = (
        export.expires_at.replace(tzinfo=UTC)
        if export.expires_at.tzinfo is None
        else export.expires_at
    )
    if expiry <= datetime.now(UTC) or export.status in {"revoked", "expired"}:
        raise ForbiddenError(
            code="evaluation_export_expired", message="导出授权已撤销或过期。"
        )
    user = session.get(UserRecord, UUID(export.actor_id))
    project = session.get(ProjectRecord, UUID(project_id))
    member = session.scalar(
        select(ProjectMemberRecord).where(
            ProjectMemberRecord.project_id == UUID(project_id),
            ProjectMemberRecord.user_id == UUID(export.actor_id),
        )
    )
    if not user or user.status != "active" or not project or project.status != "active":
        raise ForbiddenError(
            code="evaluation_source_unavailable", message="源身份或项目不可用。"
        )
    actor = ActorContext(
        user_id=export.actor_id,
        platform_roles=normalize_user_platform_roles(
            user.platform_roles_json, is_super_admin=user.is_super_admin
        ),
        project_roles={project_id: (member.role,)} if member else {},
    )
    if export.payload.get("source_kind") == "work_item":
        from platform_api.modules.evaluation.workbench_grants import validate_scope

        validate_scope(session, export, actor, project_id)
        return {
            "export_id": export.export_id,
            "project_id": project_id,
            "expires_at": expiry.isoformat(),
            "authorized_by": export.actor_id,
            **export.payload,
        }
    if export.payload.get("purpose") == "quality_inspection":
        from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord

        access = authorize(
            session, actor, project_id, export.payload["thread_id"], "read"
        )
        agent = session.get(AgentRecord, UUID(export.payload["agent_id"]))
        if (
            not thread_access.is_manager(actor, project_id)
            or access.owner_user_id != actor.user_id
            or not agent
            or agent.status != "active"
            or str(agent.project_id) != project_id
        ):
            raise ForbiddenError(
                code="inspection_scope_denied", message="巡检授权范围已失效。"
            )
        return {
            "export_id": export.export_id,
            "project_id": project_id,
            "expires_at": expiry.isoformat(),
            "authorized_by": export.actor_id,
            **export.payload,
        }
    event = session.get(FeedbackEvent, export.event_id)
    if not event:
        raise ForbiddenError(
            code="evaluation_source_unavailable", message="源反馈已不存在。"
        )
    authorize(session, actor, project_id, event.thread_id)
    current = latest(session, event.actor_id, event.thread_id, event.message_id)
    if (
        not thread_access.is_manager(actor, project_id)
        or current.event_id != event.event_id
        or current.payload["rating"] == "withdrawn"
    ):
        raise ForbiddenError(
            code="evaluation_source_revoked", message="源反馈或授权已变更。"
        )
    return {
        "export_id": export.export_id,
        "project_id": project_id,
        "expires_at": expiry.isoformat(),
        "authorized_by": export.actor_id,
        **export.payload,
    }


def save_projection(factory, project_id, body):
    with session_scope(factory) as session:
        package = _authorized_package(session, project_id, body.export_id)
        if (
            package["source_event"] != str(body.event_id)
            or (body.status == "linked" and (not body.links or body.reason is not None))
            or (body.status == "unavailable" and (body.links or body.reason is None))
        ):
            raise ConflictError(
                code="evaluation_projection_mismatch", message="反馈投影回执不匹配。"
            )
        export = session.get(EvaluationExport, str(body.export_id))
        value = body.model_dump(mode="json")
        prior = export.receipt.get("projection")
        if prior and prior != value:
            raise ConflictError(
                code="evaluation_projection_conflict",
                message="投影回执已确认，不能覆盖。",
            )
        export.receipt = {**export.receipt, "projection": value}
        return value


def revoke_export(factory, actor, project_id, export_id):
    with session_scope(factory) as session:
        export = lock_packages(session, [export_id])[str(export_id)]
        if not export or export.project_id != project_id:
            raise NotFoundError(
                code="evaluation_export_missing", message="导出记录不存在。"
            )
        if export.payload.get("purpose") == "quality_inspection":
            authorize(session, actor, project_id, export.payload["thread_id"], "read")
        elif export.status != "revoked":
            event = session.get(FeedbackEvent, export.event_id)
            if not event:
                raise NotFoundError(
                    code="evaluation_source_missing", message="源记录不存在。"
                )
            authorize(session, actor, project_id, event.thread_id)
        if actor.user_id != export.actor_id:
            raise ForbiddenError(
                code="evaluation_export_denied", message="只能撤销自己的导出授权。"
            )
        export.status = "revoked"
        from platform_api.modules.evaluation.retention import scrub_payload

        export.payload = scrub_payload(
            {**export.payload, "source_event": export.event_id}, datetime.now(UTC)
        )
        audit(
            session,
            actor,
            project_id,
            str(export_id),
            "evaluation.export.revoked",
            retention_policy=export.payload.get("retention_policy"),
        )
        return {"export_id": str(export_id), "status": "revoked"}
