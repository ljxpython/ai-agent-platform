from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from app.core.context.models import ActorContext

from app.modules.operations.domain import OperationStatus


@dataclass(frozen=True, slots=True)
class StoredOperation:
    id: str
    kind: str
    status: OperationStatus
    requested_by: str
    tenant_id: str | None
    project_id: str | None
    idempotency_key: str | None
    input_payload: dict[str, Any]
    result_payload: dict[str, Any]
    error_payload: dict[str, Any]
    metadata: dict[str, Any]
    cancel_requested_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class OperationExecutionResult:
    result_payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class OperationRepositoryProtocol(Protocol):
    def create_operation(
        self,
        *,
        kind: str,
        status: OperationStatus,
        requested_by: str,
        tenant_id: str | None,
        project_id: str | None,
        idempotency_key: str | None,
        input_payload: dict[str, Any],
        metadata: dict[str, Any],
    ) -> StoredOperation: ...

    def get_by_id(self, operation_id: str) -> StoredOperation | None: ...

    def get_by_idempotency_key(
        self,
        *,
        requested_by: str,
        idempotency_key: str,
    ) -> StoredOperation | None: ...

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
    ) -> tuple[list[StoredOperation], int]: ...

    def update_status(
        self,
        *,
        operation_id: str,
        status: OperationStatus,
        result_payload: dict[str, Any] | None = None,
        error_payload: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        cancel_requested_at: datetime | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> StoredOperation | None: ...

    def claim_next_submitted(
        self,
        *,
        supported_kinds: tuple[str, ...] | None,
        started_at: datetime,
    ) -> StoredOperation | None: ...

    def claim_submitted_by_id(
        self,
        *,
        operation_id: str,
        started_at: datetime,
    ) -> StoredOperation | None: ...

    def requeue_operation(
        self,
        *,
        operation_id: str,
        error_payload: dict[str, Any],
        metadata: dict[str, Any],
    ) -> StoredOperation | None: ...

    def bulk_cancel_operations(
        self,
        *,
        operation_ids: tuple[str, ...],
        cancel_requested_at: datetime,
        terminal_statuses: tuple[str, ...],
    ) -> tuple[list[StoredOperation], list[str]]: ...

    def bulk_archive_operations(
        self,
        *,
        operation_ids: tuple[str, ...],
        archived_at: datetime,
        terminal_statuses: tuple[str, ...],
    ) -> tuple[list[StoredOperation], list[str]]: ...

    def bulk_restore_operations(
        self,
        *,
        operation_ids: tuple[str, ...],
    ) -> tuple[list[StoredOperation], list[str]]: ...


class OperationDispatcherProtocol(Protocol):
    async def dispatch(self, *, operation: StoredOperation) -> None: ...


class OperationQueueConsumerProtocol(Protocol):
    async def dequeue(self, *, timeout_seconds: float) -> str | None: ...


class OperationExecutorProtocol(Protocol):
    kind: str

    async def execute(
        self,
        *,
        operation: StoredOperation,
        actor: ActorContext,
    ) -> OperationExecutionResult: ...
