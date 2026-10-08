"""Small transactions for trusted stop audit callbacks."""

from uuid import uuid5

from sqlalchemy.exc import IntegrityError

from platform_api.core.context.runtime import DEFAULT_TENANT_ID
from platform_api.core.db import session_scope
from platform_api.core.errors import ForbiddenError
from platform_api.modules.audit.models import AuditLogRecord
from platform_api.modules.projects.models import ProjectRecord


def assert_project_scope(factory, payload):
    with session_scope(factory) as session:
        project = session.get(ProjectRecord, payload.project_id)
        if project is None or payload.tenant_id not in {
            DEFAULT_TENANT_ID,
            str(project.tenant_id),
        }:
            raise ForbiddenError(code="stop_scope_denied", message="Invalid stop scope")


def record_stop_phase(factory, payload):
    data = payload.model_dump(mode="json")
    action = {
        "stopped": "confirmed",
        "no_active_run": "confirmed",
        "confirmation_unavailable": "unknown",
    }.get(payload.phase, payload.phase)
    event_id = uuid5(payload.stop_id, payload.phase)
    with session_scope(factory) as session:
        if session.get(AuditLogRecord, event_id) is not None:
            return
        session.add(
            AuditLogRecord(
                id=event_id,
                request_id=(payload.request_id or data["stop_id"])[:64],
                plane="runtime_gateway",
                action="runtime.thread.stop." + action,
                target_type="stop_request",
                target_id=data["stop_id"],
                actor_subject=data["owner_id"],
                tenant_id=data["tenant_id"],
                project_id=data["project_id"],
                result="failed" if action in {"unknown", "rejected"} else "success",
                method="POST",
                path="/api/runtime/internal/stop-authorization",
                status_code=200,
                duration_ms=0,
                metadata_json={
                    "stop_id": data["stop_id"],
                    "thread_id": data["thread_id"],
                    "phase": payload.phase,
                    "target_count": payload.target_count,
                    "platform_trace_id": payload.platform_trace_id,
                },
            )
        )
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
