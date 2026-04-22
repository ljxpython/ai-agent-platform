from __future__ import annotations

from dataclasses import asdict

from sqlalchemy.orm import Session, sessionmaker

from app.core.context.models import ActorContext
from app.core.db import SqlAlchemyUnitOfWork
from app.core.errors import ServiceUnavailableError
from app.modules.audit.application.contracts import AuditEventPage, ListAuditEventsQuery
from app.modules.audit.domain import AuditEvent
from app.modules.audit.infra.sqlalchemy.repository import SqlAlchemyAuditRepository
from app.modules.iam.application import AuthorizationRequest, IamPolicyEngine, PermissionCode


class AuditService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None,
        policy_engine: IamPolicyEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._policy_engine = policy_engine or IamPolicyEngine()

    def _require_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            raise ServiceUnavailableError(
                code="platform_database_not_enabled",
                message="Platform database is not enabled",
            )
        return self._session_factory

    async def list_events(
        self,
        *,
        actor: ActorContext,
        query: ListAuditEventsQuery,
    ) -> AuditEventPage:
        session_factory = self._require_session_factory()
        if query.project_id:
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PROJECT_AUDIT_READ,
                    project_id=query.project_id,
                ),
            )
        else:
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PLATFORM_AUDIT_READ,
                ),
            )

        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyAuditRepository(uow.session)
            items, total = repository.list_events(
                project_id=query.project_id,
                plane=query.plane.value if query.plane else None,
                action=query.action,
                target_type=query.target_type,
                target_id=query.target_id,
                actor_user_id=query.actor_user_id,
                method=query.method.upper() if query.method else None,
                result=query.result.value if query.result else None,
                status_code=query.status_code,
                created_from=query.created_from,
                created_to=query.created_to,
                limit=query.limit,
                offset=query.offset,
            )
            return AuditEventPage(
                items=[AuditEvent(**asdict(item)) for item in items],
                total=total,
            )
