from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from app.core.db import session_scope
from app.modules.audit.application.http_resolution import AuditHttpRequest, resolve_http_audit
from app.modules.audit.application.ports import AuditWriteCommand
from app.modules.audit.domain import AuditResult
from app.modules.audit.infra import SqlAlchemyAuditRepository


@dataclass(frozen=True, slots=True)
class WriteHttpAuditCommand:
    request_id: str
    request: AuditHttpRequest
    actor_user_id: str | None
    actor_subject: str | None
    tenant_id: str | None
    fallback_project_id: str | None
    response_payload: dict[str, object] | None
    status_code: int
    result: AuditResult
    duration_ms: int


def write_http_audit_event(
    *,
    session_factory: sessionmaker[Session],
    command: WriteHttpAuditCommand,
) -> None:
    resolved = resolve_http_audit(
        request=command.request,
        response_payload=command.response_payload,
        actor_user_id=command.actor_user_id,
        status_code=command.status_code,
        result=command.result,
    )
    with session_scope(session_factory) as session:
        repository = SqlAlchemyAuditRepository(session)
        repository.create_event(
            AuditWriteCommand(
                request_id=command.request_id,
                plane=resolved.plane,
                action=resolved.action,
                target_type=resolved.target_type,
                target_id=resolved.target_id,
                actor_user_id=command.actor_user_id,
                actor_subject=command.actor_subject,
                tenant_id=command.tenant_id,
                project_id=resolved.project_id or command.fallback_project_id,
                result=command.result,
                method=command.request.method,
                path=command.request.path,
                status_code=command.status_code,
                duration_ms=command.duration_ms,
                metadata=resolved.metadata,
            )
        )
