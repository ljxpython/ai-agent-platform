from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
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
        archived_at=record.archived_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _duration_ms_expression(session: Session):
    dialect_name = (getattr(session.bind, "dialect", None) and session.bind.dialect.name) or ""
    if dialect_name == "postgresql":
        return func.extract(
            "epoch",
            OperationRecord.finished_at - OperationRecord.started_at,
        ) * 1000

    return (
        (
            func.julianday(OperationRecord.finished_at)
            - func.julianday(OperationRecord.started_at)
        )
        * 24
        * 60
        * 60
        * 1000
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
        operation_uuid = self._parse_uuid(operation_id)
        if operation_uuid is None:
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
        kinds: tuple[str, ...],
        status: str | None,
        statuses: tuple[str, ...],
        requested_by: str | None,
        archive_scope: str,
        limit: int,
        offset: int,
    ) -> tuple[list[StoredOperation], int]:
        filters = []
        if project_id is not None:
            filters.append(OperationRecord.project_id == project_id)
        if kind is not None:
            filters.append(OperationRecord.kind == kind)
        elif kinds:
            filters.append(OperationRecord.kind.in_(kinds))
        if status is not None:
            filters.append(OperationRecord.status == status)
        elif statuses:
            filters.append(OperationRecord.status.in_(statuses))
        if requested_by is not None:
            filters.append(OperationRecord.requested_by == requested_by)
        if archive_scope == "exclude":
            filters.append(OperationRecord.archived_at.is_(None))
        elif archive_scope == "only":
            filters.append(OperationRecord.archived_at.is_not(None))

        stmt = (
            select(OperationRecord)
            .where(*filters)
            .order_by(OperationRecord.archived_at.asc().nullsfirst(), OperationRecord.created_at.desc())
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
        metadata: dict | None = None,
        cancel_requested_at: datetime | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> StoredOperation | None:
        operation_uuid = self._parse_uuid(operation_id)
        if operation_uuid is None:
            return None

        record = self.session.get(OperationRecord, operation_uuid)
        if record is None:
            return None

        record.status = status.value
        if result_payload is not None:
            record.result_payload = result_payload
        if error_payload is not None:
            record.error_payload = error_payload
        if metadata is not None:
            record.metadata_json = metadata
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
        stmt = stmt.order_by(OperationRecord.created_at.asc()).limit(8)

        records = list(self.session.scalars(stmt).all())
        for record in records:
            claimed_metadata = _mark_claimed_metadata(record.metadata_json or {}, started_at=started_at)
            claim_stmt = (
                update(OperationRecord)
                .where(
                    OperationRecord.id == record.id,
                    OperationRecord.status == OperationStatus.SUBMITTED.value,
                )
                .values(
                    status=OperationStatus.RUNNING.value,
                    started_at=started_at,
                    metadata_json=claimed_metadata,
                    updated_at=func.now(),
                )
            )
            result = self.session.execute(claim_stmt)
            if int(result.rowcount or 0) != 1:
                continue

            self.session.flush()
            refreshed = self.session.get(OperationRecord, record.id)
            if refreshed is not None:
                return _to_stored_operation(refreshed)
        return None

    def claim_submitted_by_id(
        self,
        *,
        operation_id: str,
        started_at: datetime,
    ) -> StoredOperation | None:
        operation_uuid = self._parse_uuid(operation_id)
        if operation_uuid is None:
            return None

        record = self.session.get(OperationRecord, operation_uuid)
        if record is None or record.status != OperationStatus.SUBMITTED.value:
            return None

        claimed_metadata = _mark_claimed_metadata(record.metadata_json or {}, started_at=started_at)
        claim_stmt = (
            update(OperationRecord)
            .where(
                OperationRecord.id == operation_uuid,
                OperationRecord.status == OperationStatus.SUBMITTED.value,
            )
            .values(
                status=OperationStatus.RUNNING.value,
                started_at=started_at,
                metadata_json=claimed_metadata,
                updated_at=func.now(),
            )
        )
        result = self.session.execute(claim_stmt)
        if int(result.rowcount or 0) != 1:
            return None

        self.session.flush()
        refreshed = self.session.get(OperationRecord, operation_uuid)
        return _to_stored_operation(refreshed) if refreshed is not None else None

    def requeue_operation(
        self,
        *,
        operation_id: str,
        error_payload: dict,
        metadata: dict,
    ) -> StoredOperation | None:
        operation_uuid = self._parse_uuid(operation_id)
        if operation_uuid is None:
            return None

        record = self.session.get(OperationRecord, operation_uuid)
        if record is None:
            return None

        record.status = OperationStatus.SUBMITTED.value
        record.error_payload = error_payload
        record.metadata_json = metadata
        record.started_at = None
        record.finished_at = None
        self.session.flush()
        self.session.refresh(record)
        return _to_stored_operation(record)

    def bulk_cancel_operations(
        self,
        *,
        operation_ids: tuple[str, ...],
        cancel_requested_at: datetime,
        terminal_statuses: tuple[str, ...],
    ) -> tuple[list[StoredOperation], list[str]]:
        updated: list[StoredOperation] = []
        skipped_ids: list[str] = []

        for operation_uuid, original_id in self._parse_operation_ids(operation_ids):
            record = self.session.get(OperationRecord, operation_uuid)
            if record is None or record.status in terminal_statuses:
                skipped_ids.append(original_id)
                continue
            record.status = OperationStatus.CANCELLED.value
            record.cancel_requested_at = cancel_requested_at
            record.finished_at = cancel_requested_at
            updated.append(_to_stored_operation(record))

        self.session.flush()
        return updated, skipped_ids

    def bulk_archive_operations(
        self,
        *,
        operation_ids: tuple[str, ...],
        archived_at: datetime,
        terminal_statuses: tuple[str, ...],
    ) -> tuple[list[StoredOperation], list[str]]:
        updated: list[StoredOperation] = []
        skipped_ids: list[str] = []

        for operation_uuid, original_id in self._parse_operation_ids(operation_ids):
            record = self.session.get(OperationRecord, operation_uuid)
            if (
                record is None
                or record.status not in terminal_statuses
                or record.archived_at is not None
            ):
                skipped_ids.append(original_id)
                continue
            record.archived_at = archived_at
            updated.append(_to_stored_operation(record))

        self.session.flush()
        return updated, skipped_ids

    def bulk_restore_operations(
        self,
        *,
        operation_ids: tuple[str, ...],
    ) -> tuple[list[StoredOperation], list[str]]:
        updated: list[StoredOperation] = []
        skipped_ids: list[str] = []

        for operation_uuid, original_id in self._parse_operation_ids(operation_ids):
            record = self.session.get(OperationRecord, operation_uuid)
            if record is None or record.archived_at is None:
                skipped_ids.append(original_id)
                continue
            record.archived_at = None
            updated.append(_to_stored_operation(record))

        self.session.flush()
        return updated, skipped_ids

    def summarize_operations(self) -> dict[str, object]:
        duration_ms_expr = _duration_ms_expression(self.session)
        status_rows = self.session.execute(
            select(OperationRecord.status, func.count()).group_by(OperationRecord.status)
        ).all()
        counts_by_status = {
            str(status): int(count or 0)
            for status, count in status_rows
        }
        archived_count = int(
            self.session.scalar(
                select(func.count())
                .select_from(OperationRecord)
                .where(OperationRecord.archived_at.is_not(None))
            )
            or 0
        )
        duration_stats = self.session.execute(
            select(
                func.avg(duration_ms_expr),
                func.max(duration_ms_expr),
            ).where(
                OperationRecord.started_at.is_not(None),
                OperationRecord.finished_at.is_not(None),
            )
        ).one()
        avg_duration_ms, max_duration_ms = duration_stats
        return {
            "counts_by_status": counts_by_status,
            "queued": counts_by_status.get(OperationStatus.SUBMITTED.value, 0),
            "running": counts_by_status.get(OperationStatus.RUNNING.value, 0),
            "succeeded": counts_by_status.get(OperationStatus.SUCCEEDED.value, 0),
            "failed": counts_by_status.get(OperationStatus.FAILED.value, 0),
            "cancelled": counts_by_status.get(OperationStatus.CANCELLED.value, 0),
            "archived": archived_count,
            "avg_duration_ms": round(float(avg_duration_ms or 0.0), 2),
            "max_duration_ms": round(float(max_duration_ms or 0.0), 2),
        }

    @staticmethod
    def _parse_uuid(value: str) -> UUID | None:
        try:
            return UUID(value)
        except ValueError:
            return None

    def _parse_operation_ids(self, operation_ids: tuple[str, ...]) -> list[tuple[UUID, str]]:
        parsed: list[tuple[UUID, str]] = []
        seen: set[UUID] = set()
        for operation_id in operation_ids:
            operation_uuid = self._parse_uuid(operation_id)
            if operation_uuid is None or operation_uuid in seen:
                continue
            seen.add(operation_uuid)
            parsed.append((operation_uuid, operation_id))
        return parsed


def _mark_claimed_metadata(metadata: dict, *, started_at: datetime) -> dict:
    next_metadata = dict(metadata)
    execution = next_metadata.get("_execution")
    if not isinstance(execution, dict):
        execution = {}

    attempts = execution.get("attempts")
    normalized_attempts = attempts if isinstance(attempts, int) and attempts >= 0 else 0
    execution["attempts"] = normalized_attempts + 1
    execution["last_claimed_at"] = started_at.isoformat()
    next_metadata["_execution"] = execution
    return next_metadata
