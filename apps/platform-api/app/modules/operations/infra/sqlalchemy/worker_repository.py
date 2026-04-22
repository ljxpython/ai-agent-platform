from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.operations.infra.sqlalchemy.models import OperationWorkerHeartbeatRecord


@dataclass(frozen=True, slots=True)
class StoredOperationWorkerHeartbeat:
    worker_id: str
    queue_backend: str
    hostname: str
    pid: str
    status: str
    current_operation_id: str | None
    last_error: str | None
    last_started_at: datetime | None
    last_completed_at: datetime | None
    last_heartbeat_at: datetime
    metadata: dict
    created_at: datetime
    updated_at: datetime


def _to_stored_heartbeat(record: OperationWorkerHeartbeatRecord) -> StoredOperationWorkerHeartbeat:
    return StoredOperationWorkerHeartbeat(
        worker_id=record.worker_id,
        queue_backend=record.queue_backend,
        hostname=record.hostname,
        pid=record.pid,
        status=record.status,
        current_operation_id=record.current_operation_id,
        last_error=record.last_error,
        last_started_at=record.last_started_at,
        last_completed_at=record.last_completed_at,
        last_heartbeat_at=record.last_heartbeat_at,
        metadata=dict(record.metadata_json or {}),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


class SqlAlchemyOperationWorkerHeartbeatRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert_heartbeat(
        self,
        *,
        worker_id: str,
        queue_backend: str,
        hostname: str,
        pid: str,
        status: str,
        current_operation_id: str | None,
        last_error: str | None,
        last_started_at: datetime | None,
        last_completed_at: datetime | None,
        last_heartbeat_at: datetime,
        metadata: dict,
    ) -> StoredOperationWorkerHeartbeat:
        record = self.session.get(OperationWorkerHeartbeatRecord, worker_id)
        if record is None:
            record = OperationWorkerHeartbeatRecord(
                worker_id=worker_id,
                queue_backend=queue_backend,
                hostname=hostname,
                pid=pid,
                status=status,
                current_operation_id=current_operation_id,
                last_error=last_error,
                last_started_at=last_started_at,
                last_completed_at=last_completed_at,
                last_heartbeat_at=last_heartbeat_at,
                metadata_json=metadata,
            )
            self.session.add(record)
        else:
            record.queue_backend = queue_backend
            record.hostname = hostname
            record.pid = pid
            record.status = status
            record.current_operation_id = current_operation_id
            record.last_error = last_error
            record.last_started_at = last_started_at
            record.last_completed_at = last_completed_at
            record.last_heartbeat_at = last_heartbeat_at
            record.metadata_json = metadata
        self.session.flush()
        self.session.refresh(record)
        return _to_stored_heartbeat(record)

    def list_heartbeats(self) -> list[StoredOperationWorkerHeartbeat]:
        stmt = select(OperationWorkerHeartbeatRecord).order_by(
            OperationWorkerHeartbeatRecord.last_heartbeat_at.desc()
        )
        return [_to_stored_heartbeat(row) for row in self.session.scalars(stmt).all()]
