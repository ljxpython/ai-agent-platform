from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.modules.audit.application.ports import AuditWriteCommand, StoredAuditEvent
from app.modules.audit.domain import AuditPlane, AuditResult
from app.modules.audit.infra.sqlalchemy.models import AuditLogRecord


def _to_event(record: AuditLogRecord) -> StoredAuditEvent:
    return StoredAuditEvent(
        id=str(record.id),
        request_id=record.request_id,
        plane=AuditPlane(record.plane),
        action=record.action,
        target_type=record.target_type,
        target_id=record.target_id,
        actor_user_id=record.actor_user_id,
        actor_subject=record.actor_subject,
        tenant_id=record.tenant_id,
        project_id=record.project_id,
        result=AuditResult(record.result),
        method=record.method,
        path=record.path,
        status_code=record.status_code,
        duration_ms=record.duration_ms,
        created_at=record.created_at,
        metadata=record.metadata_json or {},
    )


class SqlAlchemyAuditRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_event(self, command: AuditWriteCommand) -> None:
        record = AuditLogRecord(
            request_id=command.request_id,
            plane=command.plane.value,
            action=command.action,
            target_type=command.target_type,
            target_id=command.target_id,
            actor_user_id=command.actor_user_id,
            actor_subject=command.actor_subject,
            tenant_id=command.tenant_id,
            project_id=command.project_id,
            result=command.result.value,
            method=command.method,
            path=command.path,
            status_code=command.status_code,
            duration_ms=command.duration_ms,
            metadata_json=command.metadata,
        )
        self.session.add(record)
        self.session.flush()

    def list_events(
        self,
        *,
        project_id: str | None,
        plane: str | None,
        action: str | None,
        target_type: str | None,
        target_id: str | None,
        actor_user_id: str | None,
        method: str | None,
        result: str | None,
        status_code: int | None,
        created_from: datetime | None,
        created_to: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[StoredAuditEvent], int]:
        base_stmt = select(AuditLogRecord)
        if project_id:
            base_stmt = base_stmt.where(AuditLogRecord.project_id == project_id)
        if plane:
            base_stmt = base_stmt.where(AuditLogRecord.plane == plane)
        if action:
            base_stmt = base_stmt.where(AuditLogRecord.action.startswith(action))
        if target_type:
            base_stmt = base_stmt.where(AuditLogRecord.target_type == target_type)
        if target_id:
            base_stmt = base_stmt.where(AuditLogRecord.target_id == target_id)
        if actor_user_id:
            base_stmt = base_stmt.where(AuditLogRecord.actor_user_id == actor_user_id)
        if method:
            base_stmt = base_stmt.where(AuditLogRecord.method == method)
        if result:
            base_stmt = base_stmt.where(AuditLogRecord.result == result)
        if status_code is not None:
            base_stmt = base_stmt.where(AuditLogRecord.status_code == status_code)
        if created_from is not None:
            base_stmt = base_stmt.where(AuditLogRecord.created_at >= created_from)
        if created_to is not None:
            base_stmt = base_stmt.where(AuditLogRecord.created_at <= created_to)

        stmt = (
            base_stmt.order_by(desc(AuditLogRecord.created_at), desc(AuditLogRecord.id))
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        rows = list(self.session.scalars(stmt).all())
        total = int(self.session.scalar(count_stmt) or 0)
        return [_to_event(row) for row in rows], total
