from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.core.context.models import ActorContext
from app.core.db import SqlAlchemyUnitOfWork
from app.core.errors import BadRequestError, ConflictError, NotAuthenticatedError, NotFoundError, ServiceUnavailableError
from app.modules.audit.domain import AuditResult
from app.modules.iam.application import AuthorizationRequest, IamPolicyEngine, PermissionCode
from app.modules.operations.application.audit import write_operation_audit_event
from app.modules.operations.application.artifacts import LocalOperationArtifactStore, OperationArtifact
from app.modules.operations.application.contracts import CreateOperationCommand, ListOperationsQuery
from app.modules.operations.application.execution import with_actor_snapshot
from app.modules.operations.application.ports import OperationDispatcherProtocol, StoredOperation
from app.modules.operations.domain import OperationPage, OperationStatus, OperationView
from app.modules.operations.infra.sqlalchemy.repository import SqlAlchemyOperationsRepository
from app.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository

_TERMINAL_OPERATION_STATUSES = {
    OperationStatus.SUCCEEDED,
    OperationStatus.FAILED,
    OperationStatus.CANCELLED,
}


def _parse_uuid(value: str, *, code: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise BadRequestError(message=code.replace("_", " "), code=code) from exc


def _normalize_str(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _require_actor_identity(actor: ActorContext) -> str:
    requested_by = _normalize_str(actor.user_id) or _normalize_str(actor.subject)
    if requested_by:
        return requested_by
    raise NotAuthenticatedError()


class OperationsService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None,
        dispatcher: OperationDispatcherProtocol | None = None,
        artifact_store: LocalOperationArtifactStore | None = None,
        policy_engine: IamPolicyEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._dispatcher = dispatcher
        self._artifact_store = artifact_store
        self._policy_engine = policy_engine or IamPolicyEngine()

    def _require_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            raise ServiceUnavailableError(
                code="platform_database_not_enabled",
                message="Platform database is not enabled",
            )
        return self._session_factory

    def _require_read_access(self, *, actor: ActorContext, project_id: str | None) -> None:
        if project_id:
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PROJECT_OPERATION_READ,
                    project_id=project_id,
                ),
            )
            return

        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PLATFORM_OPERATION_READ,
            ),
        )

    def _require_write_access(self, *, actor: ActorContext, project_id: str | None) -> None:
        if project_id:
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PROJECT_OPERATION_WRITE,
                    project_id=project_id,
                ),
            )
            return

        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PLATFORM_OPERATION_WRITE,
            ),
        )

    def _operation_view(self, item: StoredOperation) -> OperationView:
        return OperationView(
            id=item.id,
            kind=item.kind,
            status=item.status,
            requested_by=item.requested_by,
            tenant_id=item.tenant_id,
            project_id=item.project_id,
            idempotency_key=item.idempotency_key,
            input_payload=dict(item.input_payload),
            result_payload=dict(item.result_payload),
            error_payload=dict(item.error_payload),
            metadata=dict(item.metadata),
            cancel_requested_at=item.cancel_requested_at,
            started_at=item.started_at,
            finished_at=item.finished_at,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    def _require_project_exists(
        self,
        *,
        uow: SqlAlchemyUnitOfWork,
        project_id: str,
    ) -> None:
        project_uuid = _parse_uuid(project_id, code="invalid_project_id")
        repository = SqlAlchemyProjectsRepository(uow.session)
        project = repository.get_project_by_id(project_uuid)
        if project is None or project.status == "deleted":
            raise NotFoundError(message="Project not found", code="project_not_found")

    async def submit_operation(
        self,
        *,
        actor: ActorContext,
        command: CreateOperationCommand,
    ) -> OperationView:
        session_factory = self._require_session_factory()
        requested_by = _require_actor_identity(actor)
        project_id = _normalize_str(command.project_id)
        idempotency_key = _normalize_str(command.idempotency_key)
        kind = command.kind.strip()
        metadata = with_actor_snapshot(metadata=command.metadata, actor=actor)

        self._require_write_access(actor=actor, project_id=project_id)

        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            if project_id:
                self._require_project_exists(uow=uow, project_id=project_id)

            repository = SqlAlchemyOperationsRepository(uow.session)
            if idempotency_key:
                existing = repository.get_by_idempotency_key(
                    requested_by=requested_by,
                    idempotency_key=idempotency_key,
                )
                if existing is not None:
                    return self._operation_view(existing)

            operation = repository.create_operation(
                kind=kind,
                status=OperationStatus.SUBMITTED,
                requested_by=requested_by,
                tenant_id=None,
                project_id=project_id,
                idempotency_key=idempotency_key,
                input_payload=dict(command.input_payload),
                metadata=metadata,
            )
            if self._dispatcher is not None:
                await self._dispatcher.dispatch(operation=operation)

        write_operation_audit_event(
            session_factory=session_factory,
            action="operation.submitted",
            operation=operation,
            actor=actor,
            result=AuditResult.SUCCESS,
            status_code=202,
        )
        return self._operation_view(operation)

    async def get_operation(
        self,
        *,
        actor: ActorContext,
        operation_id: str,
    ) -> OperationView:
        session_factory = self._require_session_factory()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyOperationsRepository(uow.session)
            operation = repository.get_by_id(operation_id)
            if operation is None:
                raise NotFoundError(message="Operation not found", code="operation_not_found")
            self._require_read_access(actor=actor, project_id=operation.project_id)
            return self._operation_view(operation)

    async def list_operations(
        self,
        *,
        actor: ActorContext,
        query: ListOperationsQuery,
    ) -> OperationPage:
        session_factory = self._require_session_factory()
        project_id = _normalize_str(query.project_id)
        self._require_read_access(actor=actor, project_id=project_id)

        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            if project_id:
                self._require_project_exists(uow=uow, project_id=project_id)

            repository = SqlAlchemyOperationsRepository(uow.session)
            items, total = repository.list_operations(
                project_id=project_id,
                kind=_normalize_str(query.kind),
                status=query.status.value if query.status else None,
                requested_by=_normalize_str(query.requested_by),
                limit=query.limit,
                offset=query.offset,
            )
            return OperationPage(
                items=[self._operation_view(item) for item in items],
                total=total,
            )

    async def cancel_operation(
        self,
        *,
        actor: ActorContext,
        operation_id: str,
    ) -> OperationView:
        session_factory = self._require_session_factory()
        cancelled_at = datetime.now(timezone.utc)

        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyOperationsRepository(uow.session)
            operation = repository.get_by_id(operation_id)
            if operation is None:
                raise NotFoundError(message="Operation not found", code="operation_not_found")

            self._require_write_access(actor=actor, project_id=operation.project_id)
            if operation.status in _TERMINAL_OPERATION_STATUSES:
                raise ConflictError(
                    code="operation_already_finished",
                    message=f"Operation already {operation.status.value}",
                )

            updated = repository.update_status(
                operation_id=operation_id,
                status=OperationStatus.CANCELLED,
                cancel_requested_at=cancelled_at,
                finished_at=cancelled_at,
            )
            if updated is None:
                raise NotFoundError(message="Operation not found", code="operation_not_found")

        write_operation_audit_event(
            session_factory=session_factory,
            action="operation.cancelled",
            operation=updated,
            actor=actor,
            result=AuditResult.CANCELLED,
            status_code=200,
        )
        return self._operation_view(updated)

    async def get_operation_artifact(
        self,
        *,
        actor: ActorContext,
        operation_id: str,
    ) -> OperationArtifact:
        session_factory = self._require_session_factory()
        if self._artifact_store is None:
            raise NotFoundError(message="Operation artifact not found", code="operation_artifact_not_found")

        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyOperationsRepository(uow.session)
            operation = repository.get_by_id(operation_id)
            if operation is None:
                raise NotFoundError(message="Operation not found", code="operation_not_found")
            self._require_read_access(actor=actor, project_id=operation.project_id)

            artifact_payload = operation.result_payload.get("_artifact")
            if not isinstance(artifact_payload, dict):
                raise NotFoundError(message="Operation artifact not found", code="operation_artifact_not_found")
            return self._artifact_store.resolve(artifact_payload)
