from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from app.core.db.session import session_scope
from app.core.observability import log_event
from app.modules.audit.domain import AuditResult
from app.modules.operations.application.audit import write_operation_audit_event
from app.modules.operations.application.execution import OperationExecutorRegistry, actor_from_operation
from app.modules.operations.application.heartbeat import OperationWorkerHeartbeatReporter
from app.modules.operations.application.ports import (
    OperationDispatcherProtocol,
    OperationQueueConsumerProtocol,
    StoredOperation,
)
from app.modules.operations.domain import OperationStatus
from app.modules.operations.infra.sqlalchemy.repository import SqlAlchemyOperationsRepository

logger = logging.getLogger(__name__)

_EXECUTION_META_KEY = "_execution"
_RETRY_POLICY_META_KEY = "_retry_policy"


class OperationWorker:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        executor_registry: OperationExecutorRegistry,
        dispatcher: OperationDispatcherProtocol | None = None,
        queue_consumer: OperationQueueConsumerProtocol | None = None,
        poll_interval_seconds: float = 1.0,
        idle_sleep_seconds: float = 2.0,
        heartbeat_reporter: OperationWorkerHeartbeatReporter | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._executor_registry = executor_registry
        self._dispatcher = dispatcher
        self._queue_consumer = queue_consumer
        self._poll_interval_seconds = poll_interval_seconds
        self._idle_sleep_seconds = idle_sleep_seconds
        self._heartbeat_reporter = heartbeat_reporter

    async def run_once(self) -> bool:
        operation = await self._claim_next_operation()
        if operation is None:
            if self._heartbeat_reporter is not None:
                self._heartbeat_reporter.beat_idle()
            return False

        if self._heartbeat_reporter is not None:
            self._heartbeat_reporter.beat_running(operation_id=operation.id)
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
            if self._heartbeat_reporter is not None:
                self._heartbeat_reporter.beat_finished(
                    operation_id=operation.id,
                    status=OperationStatus.FAILED.value,
                    error=error_payload["message"],
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
            latest = self._get_operation(operation.id)
            if latest is not None and latest.status == OperationStatus.CANCELLED:
                return True

            retry_source = latest or operation
            retried = await self._retry_failed_operation(operation=retry_source, error_payload=error_payload)
            if retried is not None:
                write_operation_audit_event(
                    session_factory=self._session_factory,
                    action="operation.retried",
                    operation=retried,
                    actor=actor,
                    result=AuditResult.SUCCESS,
                    status_code=202,
                    metadata={
                        "error": error_payload,
                        "attempts": _execution_attempts(retried.metadata),
                    },
                )
                log_event(
                    logger,
                    "operation.execution.retried",
                    operation_id=operation.id,
                    kind=operation.kind,
                    attempts=_execution_attempts(retried.metadata),
                    error=error_payload["message"],
                )
                if self._heartbeat_reporter is not None:
                    self._heartbeat_reporter.beat_finished(
                        operation_id=operation.id,
                        status="retried",
                        error=error_payload["message"],
                    )
                return True

            failed_metadata = _mark_execution_error(
                retry_source.metadata,
                error_payload=error_payload,
                retried=False,
            )
            self._finish_failed(
                operation_id=operation.id,
                error_payload=error_payload,
                metadata=failed_metadata,
            )
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
            log_event(
                logger,
                "operation.execution.failed",
                level=logging.ERROR,
                operation_id=operation.id,
                kind=operation.kind,
                error=error_payload["message"],
            )
            logger.exception("operation_execution_failed operation_id=%s kind=%s", operation.id, operation.kind)
            if self._heartbeat_reporter is not None:
                self._heartbeat_reporter.beat_finished(
                    operation_id=operation.id,
                    status=OperationStatus.FAILED.value,
                    error=error_payload["message"],
                )
            return True

        latest = self._get_operation(operation.id)
        if latest is None:
            if self._heartbeat_reporter is not None:
                self._heartbeat_reporter.beat_finished(
                    operation_id=operation.id,
                    status="missing",
                )
            return True

        if latest.status == OperationStatus.CANCELLED:
            if self._heartbeat_reporter is not None:
                self._heartbeat_reporter.beat_finished(
                    operation_id=operation.id,
                    status=OperationStatus.CANCELLED.value,
                )
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
            log_event(
                logger,
                "operation.execution.succeeded",
                operation_id=operation.id,
                kind=operation.kind,
            )
        if self._heartbeat_reporter is not None:
            self._heartbeat_reporter.beat_finished(
                operation_id=operation.id,
                status=OperationStatus.SUCCEEDED.value,
            )
        return True

    async def run_forever(self) -> None:
        while True:
            try:
                processed = await self.run_once()
            except Exception as exc:
                if self._heartbeat_reporter is not None:
                    self._heartbeat_reporter.beat_error(error=str(exc) or exc.__class__.__name__)
                log_event(
                    logger,
                    "operation.worker.loop_failed",
                    level=logging.ERROR,
                    error=str(exc) or exc.__class__.__name__,
                )
                logger.exception("operation_worker_loop_failed")
                await asyncio.sleep(self._idle_sleep_seconds)
                continue
            if self._queue_consumer is not None:
                if not processed:
                    await asyncio.sleep(0.1)
                continue
            await asyncio.sleep(self._poll_interval_seconds if processed else self._idle_sleep_seconds)

    async def _claim_next_operation(self) -> StoredOperation | None:
        if self._queue_consumer is not None:
            operation_id = await self._queue_consumer.dequeue(timeout_seconds=self._idle_sleep_seconds)
            if not operation_id:
                return None
            return self._claim_operation_by_id(operation_id)
        with session_scope(self._session_factory) as session:
            repository = SqlAlchemyOperationsRepository(session)
            return repository.claim_next_submitted(
                supported_kinds=self._executor_registry.supported_kinds(),
                started_at=datetime.now(timezone.utc),
            )

    def _claim_operation_by_id(self, operation_id: str) -> StoredOperation | None:
        with session_scope(self._session_factory) as session:
            repository = SqlAlchemyOperationsRepository(session)
            return repository.claim_submitted_by_id(
                operation_id=operation_id,
                started_at=datetime.now(timezone.utc),
            )

    def _get_operation(self, operation_id: str) -> StoredOperation | None:
        with session_scope(self._session_factory) as session:
            repository = SqlAlchemyOperationsRepository(session)
            return repository.get_by_id(operation_id)

    def _finish_failed(
        self,
        *,
        operation_id: str,
        error_payload: Mapping[str, Any],
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        with session_scope(self._session_factory) as session:
            repository = SqlAlchemyOperationsRepository(session)
            repository.update_status(
                operation_id=operation_id,
                status=OperationStatus.FAILED,
                error_payload=dict(error_payload),
                metadata=dict(metadata) if metadata is not None else None,
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

    async def _retry_failed_operation(
        self,
        *,
        operation: StoredOperation,
        error_payload: Mapping[str, Any],
    ) -> StoredOperation | None:
        max_attempts = _configured_max_attempts(operation.metadata)
        attempts = _execution_attempts(operation.metadata)
        if max_attempts <= 1 or attempts >= max_attempts:
            return None

        retry_metadata = _mark_execution_error(
            operation.metadata,
            error_payload=error_payload,
            retried=True,
        )
        with session_scope(self._session_factory) as session:
            repository = SqlAlchemyOperationsRepository(session)
            retried = repository.requeue_operation(
                operation_id=operation.id,
                error_payload=dict(error_payload),
                metadata=retry_metadata,
            )
        if retried is not None and self._dispatcher is not None:
            await self._dispatcher.dispatch(operation=retried)
        return retried


def _safe_payload_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in ("count", "last_synced_at", "assistant_id", "project_id"):
        if key in payload:
            summary[key] = payload[key]
    return summary


def _configured_max_attempts(metadata: Mapping[str, Any]) -> int:
    retry_policy = metadata.get(_RETRY_POLICY_META_KEY)
    if not isinstance(retry_policy, Mapping):
        return 1

    raw_value = retry_policy.get("max_attempts")
    if isinstance(raw_value, int) and raw_value >= 1:
        return raw_value
    return 1


def _execution_attempts(metadata: Mapping[str, Any]) -> int:
    execution = metadata.get(_EXECUTION_META_KEY)
    if not isinstance(execution, Mapping):
        return 0
    attempts = execution.get("attempts")
    if isinstance(attempts, int) and attempts >= 0:
        return attempts
    return 0


def _mark_execution_error(
    metadata: Mapping[str, Any],
    *,
    error_payload: Mapping[str, Any],
    retried: bool,
) -> dict[str, Any]:
    next_metadata = dict(metadata)
    execution = next_metadata.get(_EXECUTION_META_KEY)
    if not isinstance(execution, Mapping):
        execution = {}

    next_execution = dict(execution)
    next_execution["last_error"] = dict(error_payload)
    next_execution["last_error_at"] = datetime.now(timezone.utc).isoformat()
    next_execution["last_error_was_retried"] = retried
    retry_count = next_execution.get("retry_count")
    normalized_retry_count = retry_count if isinstance(retry_count, int) and retry_count >= 0 else 0
    if retried:
        next_execution["retry_count"] = normalized_retry_count + 1
    next_metadata[_EXECUTION_META_KEY] = next_execution
    return next_metadata
