from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.operations.application.ports import StoredOperation
from app.modules.operations.domain import OperationStatus
from app.modules.operations.infra.sqlalchemy.models import OperationRecord


def _to_stored_operation(record: OperationRecord) -> StoredOperation:
    return StoredOperation(
        id=str(record.id),
        kind=record.kind,
        status=OperationStatus(record.status),
        requested_by=record.requested_by,
        tenant_id=record.tenant_id,
        project_id=record.project_id,
        idempotency_key=record.idempotency_key,
        input_payload=dict(record.input_payload or {}),
        result_payload=dict(record.result_payload or {}),
        error_payload=dict(record.error_payload or {}),
        metadata=dict(record.metadata_json or {}),
        cancel_requested_at=record.cancel_requested_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


class SqlAlchemyOperationsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_operation(
        self,
        *,
        kind: str,
        status: OperationStatus,
        requested_by: str,
        tenant_id: str | None,
        project_id: str | None,
        idempotency_key: str | None,
        input_payload: dict,
        metadata: dict,
    ) -> StoredOperation:
        record = OperationRecord(
            kind=kind,
            status=status.value,
            requested_by=requested_by,
            tenant_id=tenant_id,
            project_id=project_id,
            idempotency_key=idempotency_key,
            input_payload=input_payload,
            metadata_json=metadata,
            result_payload={},
            error_payload={},
        )
        self.session.add(record)
        self.session.flush()
        self.session.refresh(record)
        return _to_stored_operation(record)

    def get_by_id(self, operation_id: str) -> StoredOperation | None:
        try:
            from uuid import UUID

            operation_uuid = UUID(operation_id)
        except ValueError:
            return None

        record = self.session.get(OperationRecord, operation_uuid)
        return _to_stored_operation(record) if record is not None else None

    def get_by_idempotency_key(
        self,
        *,
        requested_by: str,
        idempotency_key: str,
    ) -> StoredOperation | None:
        stmt = (
            select(OperationRecord)
            .where(
                OperationRecord.requested_by == requested_by,
                OperationRecord.idempotency_key == idempotency_key,
            )
            .order_by(OperationRecord.created_at.desc())
            .limit(1)
        )
        record = self.session.scalar(stmt)
        return _to_stored_operation(record) if record is not None else None

    def list_operations(
        self,
        *,
        project_id: str | None,
        kind: str | None,
        status: str | None,
        requested_by: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[StoredOperation], int]:
        filters = []
        if project_id is not None:
            filters.append(OperationRecord.project_id == project_id)
        if kind is not None:
            filters.append(OperationRecord.kind == kind)
        if status is not None:
            filters.append(OperationRecord.status == status)
        if requested_by is not None:
            filters.append(OperationRecord.requested_by == requested_by)

        stmt = (
            select(OperationRecord)
            .where(*filters)
            .order_by(OperationRecord.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = list(self.session.scalars(stmt).all())

        total_stmt = select(func.count()).select_from(OperationRecord).where(*filters)
        total = int(self.session.scalar(total_stmt) or 0)
        return [_to_stored_operation(row) for row in rows], total

    def update_status(
        self,
        *,
        operation_id: str,
        status: OperationStatus,
        result_payload: dict | None = None,
        error_payload: dict | None = None,
        cancel_requested_at: datetime | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> StoredOperation | None:
        try:
            from uuid import UUID

            operation_uuid = UUID(operation_id)
        except ValueError:
            return None

        record = self.session.get(OperationRecord, operation_uuid)
        if record is None:
            return None

        record.status = status.value
        if result_payload is not None:
            record.result_payload = result_payload
        if error_payload is not None:
            record.error_payload = error_payload
        if cancel_requested_at is not None:
            record.cancel_requested_at = cancel_requested_at
        if started_at is not None:
            record.started_at = started_at
        if finished_at is not None:
            record.finished_at = finished_at
        self.session.flush()
        self.session.refresh(record)
        return _to_stored_operation(record)

    def claim_next_submitted(
        self,
        *,
        supported_kinds: tuple[str, ...] | None,
        started_at: datetime,
    ) -> StoredOperation | None:
        stmt = select(OperationRecord).where(OperationRecord.status == OperationStatus.SUBMITTED.value)
        if supported_kinds:
            stmt = stmt.where(OperationRecord.kind.in_(supported_kinds))
        stmt = stmt.order_by(OperationRecord.created_at.asc()).limit(1)

        record = self.session.scalar(stmt)
        if record is None:
            return None

        record.status = OperationStatus.RUNNING.value
        record.started_at = started_at
        self.session.flush()
        self.session.refresh(record)
        return _to_stored_operation(record)
