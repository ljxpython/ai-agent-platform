from __future__ import annotations

import socket
from datetime import datetime, timezone
from os import getpid
from time import monotonic

from sqlalchemy.orm import Session, sessionmaker

from app.core.db.session import session_scope
from app.modules.operations.infra import SqlAlchemyOperationWorkerHeartbeatRepository


class OperationWorkerHeartbeatReporter:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        queue_backend: str,
        heartbeat_interval_seconds: float,
    ) -> None:
        self._session_factory = session_factory
        self._queue_backend = queue_backend
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._hostname = socket.gethostname()
        self._pid = str(getpid())
        self._worker_id = f"{self._hostname}:{self._pid}:{queue_backend}"
        self._last_heartbeat_monotonic = 0.0
        self._last_started_at: datetime | None = None
        self._last_completed_at: datetime | None = None
        self._current_operation_id: str | None = None
        self._last_error: str | None = None

    @property
    def worker_id(self) -> str:
        return self._worker_id

    def beat_idle(self, *, force: bool = False) -> None:
        self._write(status="idle", force=force)

    def beat_running(self, *, operation_id: str) -> None:
        now = datetime.now(timezone.utc)
        self._current_operation_id = operation_id
        self._last_started_at = now
        self._last_error = None
        self._write(status="running", force=True)

    def beat_finished(self, *, operation_id: str | None, status: str, error: str | None = None) -> None:
        self._current_operation_id = None
        self._last_completed_at = datetime.now(timezone.utc)
        self._last_error = error
        self._write(
            status="idle" if status in {"succeeded", "cancelled", "retried", "missing"} else "error",
            force=True,
            metadata={
                "last_operation_id": operation_id,
                "last_result": status,
            },
        )

    def beat_error(self, *, error: str) -> None:
        self._last_error = error
        self._current_operation_id = None
        self._write(status="error", force=True)

    def _write(
        self,
        *,
        status: str,
        force: bool,
        metadata: dict[str, object] | None = None,
    ) -> None:
        now_monotonic = monotonic()
        if not force and (now_monotonic - self._last_heartbeat_monotonic) < self._heartbeat_interval_seconds:
            return

        now = datetime.now(timezone.utc)
        with session_scope(self._session_factory) as session:
            repository = SqlAlchemyOperationWorkerHeartbeatRepository(session)
            repository.upsert_heartbeat(
                worker_id=self._worker_id,
                queue_backend=self._queue_backend,
                hostname=self._hostname,
                pid=self._pid,
                status=status,
                current_operation_id=self._current_operation_id,
                last_error=self._last_error,
                last_started_at=self._last_started_at,
                last_completed_at=self._last_completed_at,
                last_heartbeat_at=now,
                metadata=metadata or {},
            )
        self._last_heartbeat_monotonic = now_monotonic
