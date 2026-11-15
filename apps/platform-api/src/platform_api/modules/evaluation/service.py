"""Append-only user feedback, with ACL rechecked in the write transaction."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import func, select

from platform_api.core.context.models import ActorContext
from platform_api.core.db import session_scope
from platform_api.core.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
)
from platform_api.modules.audit.models import AuditLogRecord
from platform_api.modules.evaluation.models import EvaluationExport, FeedbackEvent
from platform_api.modules.evaluation.privacy import clean_synthetic
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


def public_event(event):
    return {"event_id": event.event_id, "revision": event.revision, **event.payload}


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


def read_feedback(factory, actor, scope):
    project_id, thread_id, message_id = scope
    with session_scope(factory) as session:
        authorize(session, actor, project_id, thread_id, "read")
        event = latest(session, actor.user_id, thread_id, message_id)
        result = public_event(event) if event else {"revision": 0, "rating": None}
        if event:
            export = session.scalar(
                select(EvaluationExport)
                .where(
                    EvaluationExport.event_id == event.event_id,
                    EvaluationExport.actor_id == actor.user_id,
                )
                .order_by(
                    EvaluationExport.created_at.desc(),
                    EvaluationExport.export_id.desc(),
                )
                .limit(1)
            )
            if export:
                expiry = (
                    export.expires_at.replace(tzinfo=UTC)
                    if export.expires_at.tzinfo is None
                    else export.expires_at
                )
                result["export"] = {
                    "export_id": export.export_id,
                    "status": "expired"
                    if export.status != "revoked" and expiry <= datetime.now(UTC)
                    else export.status,
                    "expires_at": export.expires_at.isoformat(),
                    "receipt": export.receipt,
                    "scenario": export.payload.get("scenario", ""),
                    "expected": export.payload.get("expected", ""),
                }
                projection = export.receipt.get("projection")
                if projection:
                    result["link_status"] = projection["status"]
                    result["mlflow_trace_ids"] = list(projection["links"])
                    result["assessment_ids"] = list(projection["links"].values())
                    result["link_reason"] = projection["reason"]
                elif datetime.now(UTC) >= export.created_at.replace(
                    tzinfo=UTC
                ) + timedelta(minutes=15):
                    result["link_status"] = "unavailable"
                    result["link_reason"] = "projection_deadline_exceeded"
                if export.status == "revoked" or expiry <= datetime.now(UTC):
                    result["link_status"] = "unavailable"
                    result["link_reason"] = "source_revoked_or_expired"
            else:
                result["link_status"] = "unavailable"
                result["link_reason"] = "export_authorization_required"
        return result


def save_feedback(factory, actor, scope, body, *, run_ids):
    project_id, thread_id, message_id = scope
    payload = body.model_dump(mode="json")
    request_hash = digest({"scope": scope, "actor": actor.user_id, "body": payload})
    with session_scope(factory) as session:
        authorize(session, actor, project_id, thread_id)
        prior = session.get(FeedbackEvent, str(body.event_id))
        if prior:
            if prior.digest != request_hash:
                raise ConflictError(
                    code="evaluation_idempotency_conflict",
                    message="请求标识已用于其他内容。",
                )
            return public_event(prior)
        current = latest(session, actor.user_id, thread_id, message_id)
        revision = current.revision if current else 0
        if body.expected_revision != revision:
            raise ConflictError(
                code="evaluation_revision_conflict",
                message="反馈已更新，请刷新后重试。",
            )
        count = session.scalar(
            select(func.count())
            .select_from(FeedbackEvent)
            .where(
                FeedbackEvent.actor_id == actor.user_id,
                FeedbackEvent.created_at > datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        if count >= 30:
            raise BadRequestError(
                code="evaluation_rate_limit", message="反馈过于频繁，请稍后重试。"
            )
        project = session.get(ProjectRecord, UUID(project_id))
        event = FeedbackEvent(
            event_id=str(body.event_id),
            tenant_id=str(project.tenant_id),
            project_id=project_id,
            thread_id=thread_id,
            message_id=message_id,
            actor_id=actor.user_id,
            revision=revision + 1,
            digest=request_hash,
            payload={
                "rating": body.rating,
                "reason": body.reason,
                "comment": body.comment,
                "run_ids": run_ids,
                "mlflow_trace_ids": [],
                "link_status": "pending",
                "schema_version": "1",
                "confirmation_status": "suspected",
                "signal_source": "human",
            },
        )
        session.add(event)
        audit(session, actor, project_id, event.event_id, "evaluation.feedback.saved")
        return public_event(event)


def create_export(factory, actor, project_id, body):
    with session_scope(factory) as session:
        event = session.get(FeedbackEvent, str(body.event_id))
        if not event or event.project_id != project_id:
            raise NotFoundError(code="evaluation_event_missing", message="反馈不存在。")
        access = authorize(session, actor, project_id, event.thread_id)
        if access.owner_user_id != actor.user_id or not thread_access.is_manager(
            actor, project_id
        ):
            raise ForbiddenError(
                code="evaluation_export_denied",
                message="仅项目管理员可授权导出自己会话的合成复现。",
            )
        current = latest(session, event.actor_id, event.thread_id, event.message_id)
        if (
            current.event_id != event.event_id
            or current.payload["rating"] == "withdrawn"
        ):
            raise ConflictError(
                code="evaluation_source_changed", message="源反馈已修改或撤回。"
            )
        request_hash = digest(body.model_dump(mode="json"))
        prior = session.get(EvaluationExport, str(body.export_id))
        if prior:
            if prior.digest != request_hash:
                raise ConflictError(
                    code="evaluation_export_conflict",
                    message="同一导出标识不能用于不同内容。",
                )
            return {"export_id": prior.export_id, "status": prior.status}
        # One pass keeps substitutions consistent across scenario and expected answer.
        cleaned = clean_synthetic(
            json.dumps(
                {"scenario": body.scenario, "expected": body.expected},
                ensure_ascii=False,
            )
        )
        export = EvaluationExport(
            export_id=str(body.export_id),
            event_id=event.event_id,
            project_id=project_id,
            actor_id=actor.user_id,
            digest=request_hash,
            status="ready",
            expires_at=datetime.now(UTC) + timedelta(hours=body.expires_in_hours),
            payload={
                **json.loads(cleaned),
                "data_class": "synthetic",
                "purpose": body.purpose,
                "policy_version": "synthetic-local-v1",
                "retention_policy": "local-synthetic-20261114",
                "source_event": event.event_id,
                "feedback": {
                    "event_id": event.event_id,
                    "revision": event.revision,
                    "rating": event.payload["rating"],
                    "actor_id": event.actor_id,
                    "thread_id": event.thread_id,
                    "message_id": event.message_id,
                    "run_ids": event.payload["run_ids"],
                },
                "snapshot_timing": "human_reconstruction",
                "content_hash": digest(json.loads(cleaned)),
            },
        )
        session.add(export)
        audit(
            session,
            actor,
            project_id,
            export.export_id,
            "evaluation.export.authorized",
            retention_policy=export.payload.get("retention_policy"),
        )
        return {"export_id": export.export_id, "status": export.status}


def inspection_agent(factory, actor, project_id, thread_id, run_id, run):
    from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord

    if (
        not isinstance(run, dict)
        or run.get("thread_id") != thread_id
        or run.get("run_id") != run_id
        or run.get("status") != "success"
    ):
        raise ForbiddenError(
            code="inspection_run_denied", message="巡检仅接受当前会话已完成的运行。"
        )
    with session_scope(factory) as session:
        access = authorize(session, actor, project_id, thread_id, "read")
        if (
            not thread_access.is_manager(actor, project_id)
            or access.owner_user_id != actor.user_id
        ):
            raise ForbiddenError(
                code="inspection_scope_denied", message="巡检授权范围无效。"
            )
        agents = session.scalars(
            select(AgentRecord).where(
                AgentRecord.project_id == UUID(project_id),
                AgentRecord.status == "active",
            )
        ).all()
        # Runtime uses the graph key or its deterministic UUID, not the platform Agent ID.
        matches = [
            agent
            for agent in agents
            if run.get("assistant_id")
            in {agent.graph_id, str(uuid5(NAMESPACE_URL, agent.graph_id))}
        ]
        if len(matches) != 1:
            raise ForbiddenError(
                code="inspection_agent_denied",
                message="运行未关联当前项目的有效 Agent。",
            )
        return {"agent_id": str(matches[0].id), "graph_id": matches[0].graph_id}


def create_inspection_export(factory, actor, project_id, body):
    from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord

    with session_scope(factory) as session:
        access = authorize(session, actor, project_id, str(body.thread_id), "read")
        agent = session.get(AgentRecord, body.agent_id)
        if (
            not thread_access.is_manager(actor, project_id)
            or access.owner_user_id != actor.user_id
            or agent is None
            or str(agent.project_id) != project_id
            or agent.status != "active"
        ):
            raise ForbiddenError(
                code="inspection_scope_denied", message="巡检授权范围无效。"
            )
        request_hash = digest(body.model_dump(mode="json"))
        prior = session.get(EvaluationExport, str(body.export_id))
        if prior:
            if prior.digest != request_hash or prior.actor_id != actor.user_id:
                raise ConflictError(
                    code="inspection_conflict", message="巡检授权标识已使用。"
                )
            return {"export_id": prior.export_id, "status": prior.status}
        content = json.loads(
            clean_synthetic(
                json.dumps(
                    {"input": body.input, "output": body.output}, ensure_ascii=False
                )
            )
        )
        payload = {
            **content,
            "purpose": body.purpose,
            "data_class": body.data_class,
            "thread_id": str(body.thread_id),
            "run_id": str(body.run_id),
            "agent_id": str(body.agent_id),
            "allowed_fields": list(body.allowed_fields),
            "judge_route": body.judge_route,
            "budget_policy_version": body.budget_policy_version,
            "policy_version": "inspection-synthetic-v1",
            "retention_policy": "local-synthetic-20261114",
            "snapshot_timing": "human_reconstruction",
            "run_outcome": "completed",
        }
        payload["content_hash"] = digest(payload)
        export = EvaluationExport(
            export_id=str(body.export_id),
            event_id=str(body.export_id),
            project_id=project_id,
            actor_id=actor.user_id,
            digest=request_hash,
            status="ready",
            payload=payload,
            receipt={},
            expires_at=datetime.now(UTC) + timedelta(hours=body.expires_in_hours),
        )
        session.add(export)
        audit(
            session,
            actor,
            project_id,
            export.export_id,
            "evaluation.inspection.authorized",
            retention_policy=export.payload.get("retention_policy"),
        )
        return {"export_id": export.export_id, "status": export.status}


def read_inspection_exports(factory, actor, project_id, thread_id, run_id):
    with session_scope(factory) as session:
        authorize(session, actor, project_id, thread_id, "read")
        rows = session.scalars(
            select(EvaluationExport)
            .where(
                EvaluationExport.project_id == project_id,
                EvaluationExport.actor_id == actor.user_id,
                EvaluationExport.payload["purpose"].as_string() == "quality_inspection",
                EvaluationExport.payload["thread_id"].as_string() == thread_id,
                EvaluationExport.payload["run_id"].as_string() == run_id,
            )
            .order_by(EvaluationExport.created_at.desc())
            .limit(20)
        ).all()
        return [
            {
                "export_id": row.export_id,
                "status": "expired"
                if row.status != "revoked"
                and row.expires_at.replace(tzinfo=UTC) <= datetime.now(UTC)
                else row.status,
                "expires_at": row.expires_at.isoformat(),
                "receipt": row.receipt,
            }
            for row in rows
        ]


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


def save_receipt(factory, export_id, receipt):
    with session_scope(factory) as session:
        export = lock_packages(session, [export_id])[str(export_id)]
        if not export:
            raise NotFoundError(
                code="evaluation_export_missing", message="导出记录不存在。"
            )
        _authorized_package(session, export.project_id, export_id)
        if (
            receipt.get("export_id") != export.export_id
            or receipt.get("content_hash") != export.payload["content_hash"]
        ):
            raise ConflictError(
                code="evaluation_receipt_mismatch", message="接收回执不匹配。"
            )
        export.receipt = {
            **receipt,
            **(
                {"projection": export.receipt["projection"]}
                if "projection" in export.receipt
                else {}
            ),
        }
        export.status = "exported"
        return {
            "export_id": export.export_id,
            "status": export.status,
            "receipt": receipt,
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
