from __future__ import annotations

from starlette.concurrency import run_in_threadpool

from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from platform_api.core.context.models import ActorContext
from platform_api.core.db import session_scope
from platform_api.core.errors import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
)
from platform_api.core.identifiers import parse_actor_user_id, parse_uuid
from platform_api.core.runtime_contract import (
    normalize_runtime_object,
    validate_runtime_option_values,
)
from platform_api.modules.agents.application.contracts import (
    CreateAssistantCommand,
    ListAssistantsQuery,
    UpdateAssistantCommand,
)
from platform_api.modules.agents.application.ports import (
    AssistantParameterSchemaProviderProtocol,
    StoredAssistantAggregate,
)
from platform_api.modules.agents.domain import (
    AssistantItem,
    AssistantPage,
    AssistantStatus,
)
from platform_api.modules.agents.infra.sqlalchemy.repository import (
    SqlAlchemyAssistantsRepository,
)
from platform_api.modules.iam.application import (
    AuthorizationRequest,
    IamPolicyEngine,
    PermissionCode,
)
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository


def _normalize_object(value: dict[str, Any] | None) -> dict[str, Any]:
    return normalize_runtime_object(value)


def _normalize_agent_context(
    context: dict[str, Any] | None, project_id: str
) -> dict[str, Any]:
    normalized = _normalize_object(context)
    allowed = {"model_id", "temperature", "max_tokens", "top_p", "tools"}
    if set(normalized) - allowed:
        raise BadRequestError(
            code="invalid_agent_context", message="Unsupported Agent default"
        )
    try:
        validate_runtime_option_values(normalized)
    except ValueError as exc:
        raise BadRequestError(code="invalid_agent_context", message=str(exc)) from exc
    return normalized


class AssistantsService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None,
        schema_provider: AssistantParameterSchemaProviderProtocol,
        policy_engine: IamPolicyEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._schema_provider = schema_provider
        self._policy_engine = policy_engine or IamPolicyEngine()

    def _require_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            raise ServiceUnavailableError(
                code="platform_database_not_enabled",
                message="Platform database is not enabled",
            )
        return self._session_factory

    def _assistant_item(self, item: StoredAssistantAggregate) -> AssistantItem:
        try:
            status = AssistantStatus(item.status)
        except ValueError:
            status = AssistantStatus.ACTIVE
        return AssistantItem(
            id=str(item.id),
            project_id=str(item.project_id),
            name=item.name,
            description=item.description,
            graph_id=item.graph_id,
            status=status,
            context=dict(item.context),
            created_by=str(item.created_by) if item.created_by else None,
            updated_by=str(item.updated_by) if item.updated_by else None,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    def _require_project_exists(
        self,
        *,
        session: Session,
        project_id: str,
    ) -> None:
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        projects_repository = SqlAlchemyProjectsRepository(session)
        project = projects_repository.get_project_by_id(project_uuid)
        if project is None or project.status == "deleted":
            raise NotFoundError(message="Project not found", code="project_not_found")

    def list_assistants(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        query: ListAssistantsQuery,
    ) -> AssistantPage:
        session_factory = self._require_session_factory()
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PROJECT_ASSISTANT_READ,
                project_id=project_id,
            ),
        )
        with session_scope(session_factory) as session:
            self._require_project_exists(session=session, project_id=project_id)
            repository = SqlAlchemyAssistantsRepository(session)
            items, total = repository.list_project_assistants(
                project_id=parse_uuid(project_id, code="invalid_project_id"),
                limit=query.limit,
                offset=query.offset,
                query=query.query,
                graph_id=query.graph_id,
            )
            return AssistantPage(
                items=[self._assistant_item(item) for item in items],
                total=total,
            )

    async def create_assistant(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        command: CreateAssistantCommand,
    ) -> AssistantItem:
        session_factory = self._require_session_factory()
        actor_user_id = parse_actor_user_id(actor)
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PROJECT_ASSISTANT_WRITE,
                project_id=project_id,
            ),
        )
        user_context = _normalize_agent_context(command.context, project_id)
        await self.get_parameter_schema(
            actor=actor, graph_id=command.graph_id, project_id=project_id
        )

        try:

            def persist():
                with session_scope(session_factory) as session:
                    self._require_project_exists(session=session, project_id=project_id)
                    repository = SqlAlchemyAssistantsRepository(session)
                    item = repository.create_assistant(
                        project_id=parse_uuid(project_id, code="invalid_project_id"),
                        name=command.name.strip(),
                        description=command.description.strip(),
                        graph_id=command.graph_id.strip(),
                        context=user_context,
                        actor_user_id=actor_user_id,
                    )
                    return self._assistant_item(item)

            return await run_in_threadpool(persist)
        except IntegrityError as exc:
            raise ConflictError(
                code="assistant_name_conflict",
                message="Assistant name already exists in this project",
            ) from exc

    def get_assistant(
        self,
        *,
        actor: ActorContext,
        assistant_id: str,
    ) -> AssistantItem:
        session_factory = self._require_session_factory()
        assistant_uuid = parse_uuid(assistant_id, code="invalid_assistant_id")
        with session_scope(session_factory) as session:
            repository = SqlAlchemyAssistantsRepository(session)
            item = repository.get_assistant_by_id(assistant_uuid)
            if item is None:
                raise NotFoundError(
                    message="Assistant not found",
                    code="assistant_not_found",
                )
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PROJECT_ASSISTANT_READ,
                    project_id=str(item.project_id),
                ),
            )
            return self._assistant_item(item)

    def update_assistant(
        self,
        *,
        actor: ActorContext,
        assistant_id: str,
        command: UpdateAssistantCommand,
    ) -> AssistantItem:
        session_factory = self._require_session_factory()
        actor_user_id = parse_actor_user_id(actor)
        assistant_uuid = parse_uuid(assistant_id, code="invalid_assistant_id")
        with session_scope(session_factory) as session:
            repository = SqlAlchemyAssistantsRepository(session)
            current = repository.get_assistant_by_id(assistant_uuid)
            if current is None:
                raise NotFoundError(
                    message="Assistant not found",
                    code="assistant_not_found",
                )
            project_id = str(current.project_id)
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PROJECT_ASSISTANT_WRITE,
                    project_id=project_id,
                ),
            )

            fields_set = command.model_fields_set
            next_graph_id = current.graph_id
            next_name = (
                command.name.strip()
                if "name" in fields_set and isinstance(command.name, str)
                else current.name
            )
            next_description = (
                command.description.strip()
                if "description" in fields_set and isinstance(command.description, str)
                else current.description
            )
            next_status = (
                command.status.value
                if "status" in fields_set and command.status is not None
                else current.status
            )
            next_context = _normalize_agent_context(
                command.context if "context" in fields_set else current.context,
                project_id,
            )

            repository.update_assistant_runtime_fields(
                assistant_id=assistant_uuid,
                graph_id=next_graph_id,
                name=next_name,
                description=next_description,
            )
            item = repository.update_assistant_configuration(
                assistant_id=assistant_uuid,
                status=next_status,
                context=next_context,
                actor_user_id=actor_user_id,
            )
            return self._assistant_item(item)

    def delete_assistant(
        self,
        *,
        actor: ActorContext,
        assistant_id: str,
    ) -> str:
        session_factory = self._require_session_factory()
        assistant_uuid = parse_uuid(assistant_id, code="invalid_assistant_id")
        with session_scope(session_factory) as session:
            repository = SqlAlchemyAssistantsRepository(session)
            current = repository.get_assistant_by_id(assistant_uuid)
            if current is None:
                raise NotFoundError(
                    message="Assistant not found",
                    code="assistant_not_found",
                )
            project_id = str(current.project_id)
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PROJECT_ASSISTANT_WRITE,
                    project_id=project_id,
                ),
            )
            repository.delete_assistant(assistant_id=assistant_uuid)
            return project_id

    async def get_parameter_schema(
        self,
        *,
        actor: ActorContext,
        graph_id: str,
        project_id: str | None,
    ) -> dict[str, Any]:
        normalized_graph_id = graph_id.strip()
        if not normalized_graph_id:
            raise BadRequestError(
                code="invalid_graph_id",
                message="Graph id is invalid",
            )

        if project_id:
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PROJECT_ASSISTANT_READ,
                    project_id=project_id,
                ),
            )
        else:
            raise BadRequestError(
                code="project_scope_required",
                message="project_id is required for assistant schema access",
            )

        return await self._schema_provider.build_schema(
            normalized_graph_id,
            actor=actor,
            project_id=project_id,
        )
