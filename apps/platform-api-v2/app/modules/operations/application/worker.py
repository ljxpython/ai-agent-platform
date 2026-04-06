from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.core.db.session import session_scope
from app.modules.audit.domain import AuditResult
from app.modules.operations.application.audit import write_operation_audit_event
from app.modules.operations.application.execution import OperationExecutorRegistry, actor_from_operation
from app.modules.operations.application.ports import StoredOperation
from app.modules.operations.domain import OperationStatus
from app.modules.operations.infra.sqlalchemy.repository import SqlAlchemyOperationsRepository

logger = logging.getLogger(__name__)


class OperationWorker:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        executor_registry: OperationExecutorRegistry,
        poll_interval_seconds: float = 1.0,
        idle_sleep_seconds: float = 2.0,
    ) -> None:
        self._session_factory = session_factory
        self._executor_registry = executor_registry
        self._poll_interval_seconds = poll_interval_seconds
        self._idle_sleep_seconds = idle_sleep_seconds

    async def run_once(self) -> bool:
        operation = self._claim_next_operation()
        if operation is None:
            return False

        actor = actor_from_operation(operation)
        write_operation_audit_event(
            session_factory=self._session_factory,
            action="operation.started",
            operation=operation,
            actor=actor,
            result=AuditResult.SUCCESS,
            status_code=202,
        )

        executor = self._executor_registry.get(operation.kind)
        if executor is None:
            error_payload = {
                "code": "unsupported_operation_kind",
                "message": f"Unsupported operation kind: {operation.kind}",
            }
            self._finish_failed(operation_id=operation.id, error_payload=error_payload)
            failed = self._get_operation(operation.id)
            if failed is not None:
                write_operation_audit_event(
                    session_factory=self._session_factory,
                    action="operation.failed",
                    operation=failed,
                    actor=actor,
                    result=AuditResult.FAILED,
                    status_code=500,
                    metadata={"error": error_payload},
                )
            return True

        try:
            result = await executor.execute(operation=operation, actor=actor)
        except Exception as exc:
            error_payload = {
                "code": "operation_execution_failed",
                "message": str(exc) or exc.__class__.__name__,
                "exception_type": exc.__class__.__name__,
            }
            self._finish_failed(operation_id=operation.id, error_payload=error_payload)
            failed = self._get_operation(operation.id)
            if failed is not None:
                write_operation_audit_event(
                    session_factory=self._session_factory,
                    action="operation.failed",
                    operation=failed,
                    actor=actor,
                    result=AuditResult.FAILED,
                    status_code=500,
                    metadata={"error": error_payload},
                )
            logger.exception("operation_execution_failed operation_id=%s kind=%s", operation.id, operation.kind)
            return True

        latest = self._get_operation(operation.id)
        if latest is None:
            return True

        if latest.status == OperationStatus.CANCELLED:
            return True

        succeeded = self._finish_succeeded(
            operation_id=operation.id,
            result_payload=result.result_payload,
            metadata=result.metadata,
        )
        if succeeded is not None:
            write_operation_audit_event(
                session_factory=self._session_factory,
                action="operation.succeeded",
                operation=succeeded,
                actor=actor,
                result=AuditResult.SUCCESS,
                status_code=200,
                metadata={"result": _safe_payload_summary(succeeded.result_payload)},
            )
        return True

    async def run_forever(self) -> None:
        while True:
            processed = await self.run_once()
            await asyncio.sleep(self._poll_interval_seconds if processed else self._idle_sleep_seconds)

    def _claim_next_operation(self) -> StoredOperation | None:
        with session_scope(self._session_factory) as session:
            repository = SqlAlchemyOperationsRepository(session)
            return repository.claim_next_submitted(
                supported_kinds=self._executor_registry.supported_kinds(),
                started_at=datetime.now(timezone.utc),
            )

    def _get_operation(self, operation_id: str) -> StoredOperation | None:
        with session_scope(self._session_factory) as session:
            repository = SqlAlchemyOperationsRepository(session)
            return repository.get_by_id(operation_id)

    def _finish_failed(self, *, operation_id: str, error_payload: Mapping[str, Any]) -> None:
        with session_scope(self._session_factory) as session:
            repository = SqlAlchemyOperationsRepository(session)
            repository.update_status(
                operation_id=operation_id,
                status=OperationStatus.FAILED,
                error_payload=dict(error_payload),
                finished_at=datetime.now(timezone.utc),
            )

    def _finish_succeeded(
        self,
        *,
        operation_id: str,
        result_payload: Mapping[str, Any],
        metadata: Mapping[str, Any],
    ) -> StoredOperation | None:
        with session_scope(self._session_factory) as session:
            repository = SqlAlchemyOperationsRepository(session)
            current = repository.get_by_id(operation_id)
            if current is None:
                return None
            if current.status == OperationStatus.CANCELLED:
                return current

            final_payload = dict(result_payload)
            if metadata:
                final_payload.setdefault("_meta", {}).update(dict(metadata))
            return repository.update_status(
                operation_id=operation_id,
                status=OperationStatus.SUCCEEDED,
                result_payload=final_payload,
                finished_at=datetime.now(timezone.utc),
            )


def _safe_payload_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in ("count", "last_synced_at", "assistant_id", "project_id"):
        if key in payload:
            summary[key] = payload[key]
    return summary
