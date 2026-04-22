from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.core.context.models import ActorContext
from app.core.db.session import session_scope
from app.modules.audit.application.ports import AuditWriteCommand
from app.modules.audit.domain import AuditPlane, AuditResult
from app.modules.audit.infra.sqlalchemy.repository import SqlAlchemyAuditRepository
from app.modules.operations.application.ports import StoredOperation


def write_operation_audit_event(
    *,
    session_factory: sessionmaker[Session] | None,
    action: str,
    operation: StoredOperation,
    actor: ActorContext,
    result: AuditResult,
    status_code: int,
    metadata: dict[str, Any] | None = None,
) -> None:
    if session_factory is None:
        return

    with session_scope(session_factory) as session:
        repository = SqlAlchemyAuditRepository(session)
        repository.create_event(
            AuditWriteCommand(
                request_id=f"operation:{operation.id}",
                plane=AuditPlane.SYSTEM_INTERNAL,
                action=action,
                target_type="operation",
                target_id=operation.id,
                actor_user_id=actor.user_id,
                actor_subject=actor.subject,
                tenant_id=operation.tenant_id,
                project_id=operation.project_id,
                result=result,
                method="WORKER",
                path=f"/operations/{operation.id}",
                status_code=status_code,
                duration_ms=0,
                metadata={
                    "kind": operation.kind,
                    "status": operation.status.value,
                    **(metadata or {}),
                },
            )
        )
