from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from platform_api.core.context.models import ActorContext
from platform_api.core.db import session_scope
from platform_api.core.errors import NotFoundError, ServiceUnavailableError, BadRequestError, ConflictError
from platform_api.core.identifiers import parse_uuid
from platform_api.modules.iam.application import (
    AuthorizationRequest,
    IamPolicyEngine,
    PermissionCode,
)
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
from platform_api.modules.runtime_catalog.infra import (
    SqlAlchemyRuntimeCatalogRepository,
)
from platform_api.modules.runtime_policies.application.contracts import (
    RuntimeGraphPolicyList,
    RuntimeModelPolicyList,
    UpsertRuntimeGraphPolicyCommand,
    UpsertRuntimeModelPolicyCommand,
)
from platform_api.modules.runtime_policies.domain import (
    RuntimeGraphPolicyItem,
    RuntimeGraphPolicyValue,
    RuntimeModelPolicyItem,
    RuntimeModelPolicyValue,
)
from platform_api.modules.runtime_policies.infra import (
    SqlAlchemyRuntimePolicyRepository,
)

from platform_api.modules.runtime_policies.infra.sqlalchemy.models import RuntimeToolRestrictionRecord
from platform_api.modules.runtime_policies.application.contracts import CreateToolRestriction, ToolRestrictionItem, ToolRestrictionList

_NO_ENABLED_MODEL_SENTINEL = "platform:no-enabled-model"


class RuntimePolicyOverlayService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None,
        runtime_base_url: str,
        policy_engine: IamPolicyEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._runtime_id = "default"
        self._policy_engine = policy_engine or IamPolicyEngine()

    def _require_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            raise ServiceUnavailableError(
                code="platform_database_not_enabled",
                message="Platform database is not enabled",
            )
        return self._session_factory

    def build_delegation_policy(self, *, project_id: str) -> dict[str, object]:
        session_factory = self._require_session_factory()
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        with session_factory() as session:
            catalog_repository = SqlAlchemyRuntimeCatalogRepository(session)
            policy_repository = SqlAlchemyRuntimePolicyRepository(session)
            models = catalog_repository.list_models()
            model_policies = {
                str(item.model_catalog_id): item
                for item in policy_repository.list_model_policies(
                    project_id=project_uuid
                )
            }
            allowed_model_ids = sorted(
                str(item.id)
                for item in models
                if item.enabled
                and (
                    str(item.id) not in model_policies
                    or model_policies[str(item.id)].is_enabled
                )
            )
            # Keep the delegation structurally valid when every model is disabled;
            # the Gateway still rejects any run before contacting the upstream.
            if not allowed_model_ids:
                allowed_model_ids = [_NO_ENABLED_MODEL_SENTINEL]
        revision_payload = {
            "runtime_id": self._runtime_id,
            "models": allowed_model_ids,
        }
        revision = (
            "platform-policy-"
            + hashlib.sha256(
                json.dumps(
                    revision_payload, sort_keys=True, separators=(",", ":")
                ).encode()
            ).hexdigest()[:32]
        )
        return {
            "version": revision,
            "allowed_model_ids": allowed_model_ids,
        }

    def resolve_tool_overrides(self, *, project_id: str, user_id: str | None, graph_id: str) -> dict:
        project = parse_uuid(project_id, code="invalid_project_id")
        user = parse_uuid(user_id, code="invalid_user_id") if user_id is not None else None
        with self._require_session_factory()() as session:
            self._ensure_project_exists(session, project)
            names = session.scalars(select(RuntimeToolRestrictionRecord.tool_name).where(
                RuntimeToolRestrictionRecord.project_id == project,
                RuntimeToolRestrictionRecord.graph_id == graph_id,
                or_(
                    (RuntimeToolRestrictionRecord.subject_type == "project") & (RuntimeToolRestrictionRecord.subject_id == project),
                    (RuntimeToolRestrictionRecord.subject_type == "user") & (RuntimeToolRestrictionRecord.subject_id == user),
                ),
            )).all()
        overrides = dict.fromkeys(sorted(set(names)), False)
        payload = json.dumps([project_id, user_id, graph_id, overrides], separators=(",", ":"))
        if len(overrides) > 128 or len(json.dumps(overrides, separators=(",", ":")).encode()) > 4096:
            raise ServiceUnavailableError(code="tool_policy_too_large", message="Tool restrictions exceed delegation budget")
        return {"tool_overrides": overrides,
                "tool_policy_version": "sha256:" + hashlib.sha256(payload.encode()).hexdigest()}

    def list_tool_restrictions(self, *, actor: ActorContext, project_id: str) -> ToolRestrictionList:
        project = self._require_project_access(actor=actor, project_id=project_id, write=True)
        with self._require_session_factory()() as session:
            self._ensure_project_exists(session, project)
            rows = session.scalars(select(RuntimeToolRestrictionRecord).where(
                RuntimeToolRestrictionRecord.project_id == project
            ).order_by(RuntimeToolRestrictionRecord.created_at, RuntimeToolRestrictionRecord.id)).all()
            return ToolRestrictionList(items=[ToolRestrictionItem.model_validate(row) for row in rows], total=len(rows))

    def validate_restriction_subject(self, *, actor: ActorContext, project_id: str, command: CreateToolRestriction) -> None:
        project = self._require_project_access(actor=actor, project_id=project_id, write=True)
        with self._require_session_factory()() as session:
            self._ensure_project_exists(session, project)
            repository = SqlAlchemyProjectsRepository(session)
            if command.subject_type == "project":
                valid = command.subject_id == project
            else:
                valid = repository.user_exists(user_id=command.subject_id) and repository.get_project_member_role(
                    project_id=project, user_id=command.subject_id) is not None
            if not valid:
                raise BadRequestError(code="invalid_restriction_subject", message="Restriction subject must belong to the project")

    def create_tool_restriction(self, *, actor: ActorContext, project_id: str,
                                command: CreateToolRestriction) -> ToolRestrictionItem:
        self.validate_restriction_subject(actor=actor, project_id=project_id, command=command)
        try:
            with session_scope(self._require_session_factory()) as session:
                row = RuntimeToolRestrictionRecord(project_id=parse_uuid(project_id, code="invalid_project_id"),
                    **command.model_dump(), created_by=actor.user_id or actor.subject)
                session.add(row)
                session.flush()
                return ToolRestrictionItem.model_validate(row)
        except IntegrityError as exc:
            raise ConflictError(code="tool_restriction_exists", message="Restriction already exists") from exc

    def delete_tool_restriction(self, *, actor: ActorContext, project_id: str, restriction_id: str) -> ToolRestrictionItem:
        project = self._require_project_access(actor=actor, project_id=project_id, write=True)
        with session_scope(self._require_session_factory()) as session:
            self._ensure_project_exists(session, project)
            row = session.get(RuntimeToolRestrictionRecord, parse_uuid(restriction_id, code="invalid_restriction_id"))
            if row is None or row.project_id != project:
                raise NotFoundError(code="tool_restriction_not_found", message="Restriction not found")
            deleted = ToolRestrictionItem.model_validate(row)
            session.delete(row)
            return deleted

    def _require_project_access(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        write: bool,
    ) -> UUID:
        permission = (
            PermissionCode.PROJECT_RUNTIME_WRITE
            if write
            else PermissionCode.PROJECT_RUNTIME_READ
        )
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=permission, project_id=project_id
            ),
        )
        return parse_uuid(project_id, code="invalid_project_id")

    @staticmethod
    def _ensure_project_exists(session: Session, project_uuid: UUID) -> None:
        repository = SqlAlchemyProjectsRepository(session)
        project = repository.get_project_by_id(project_uuid)
        if project is None or project.status == "deleted":
            raise NotFoundError(message="Project not found", code="project_not_found")

    def list_graph_policies(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> RuntimeGraphPolicyList:
        session_factory = self._require_session_factory()
        project_uuid = self._require_project_access(
            actor=actor, project_id=project_id, write=False
        )
        with session_scope(session_factory) as session:
            self._ensure_project_exists(session, project_uuid)
            catalog_repository = SqlAlchemyRuntimeCatalogRepository(session)
            policy_repository = SqlAlchemyRuntimePolicyRepository(session)
            catalog_rows = catalog_repository.list_graphs(runtime_id=self._runtime_id)
            policy_rows = {
                str(item.graph_catalog_id): item
                for item in policy_repository.list_graph_policies(
                    project_id=project_uuid
                )
            }
            items = [
                RuntimeGraphPolicyItem(
                    catalog_id=str(row.id),
                    graph_id=row.graph_key,
                    display_name=row.display_name or row.graph_key,
                    description=row.description or "",
                    source_type=row.source_type,
                    sync_status=row.sync_status,
                    last_synced_at=row.last_synced_at,
                    policy=RuntimeGraphPolicyValue(
                        is_enabled=policy_rows.get(str(row.id)).is_enabled
                        if policy_rows.get(str(row.id))
                        else True,
                        display_order=policy_rows.get(str(row.id)).display_order
                        if policy_rows.get(str(row.id))
                        else None,
                        note=policy_rows.get(str(row.id)).note
                        if policy_rows.get(str(row.id))
                        else None,
                    ),
                )
                for row in catalog_rows
            ]
            return RuntimeGraphPolicyList(items=items, total=len(items))

    def upsert_graph_policy(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        catalog_id: str,
        command: UpsertRuntimeGraphPolicyCommand,
    ) -> RuntimeGraphPolicyValue:
        session_factory = self._require_session_factory()
        project_uuid = self._require_project_access(
            actor=actor, project_id=project_id, write=True
        )
        catalog_uuid = parse_uuid(catalog_id, code="invalid_catalog_id")
        with session_scope(session_factory) as session:
            self._ensure_project_exists(session, project_uuid)
            catalog_repository = SqlAlchemyRuntimeCatalogRepository(session)
            if catalog_repository.get_graph_by_id(catalog_uuid) is None:
                raise NotFoundError(
                    message="Graph catalog not found", code="graph_catalog_not_found"
                )
            policy_repository = SqlAlchemyRuntimePolicyRepository(session)
            row = policy_repository.upsert_graph_policy(
                project_id=project_uuid,
                graph_catalog_id=catalog_uuid,
                is_enabled=command.is_enabled,
                display_order=command.display_order,
                note=command.note,
                updated_by=actor.user_id,
            )
            return RuntimeGraphPolicyValue(
                is_enabled=row.is_enabled,
                display_order=row.display_order,
                note=row.note,
                updated_at=row.updated_at,
            )


    def list_model_policies(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> RuntimeModelPolicyList:
        session_factory = self._require_session_factory()
        project_uuid = self._require_project_access(
            actor=actor, project_id=project_id, write=False
        )
        with session_scope(session_factory) as session:
            self._ensure_project_exists(session, project_uuid)
            catalog_repository = SqlAlchemyRuntimeCatalogRepository(session)
            policy_repository = SqlAlchemyRuntimePolicyRepository(session)
            catalog_rows = catalog_repository.list_models()
            policy_rows = {
                str(item.model_catalog_id): item
                for item in policy_repository.list_model_policies(
                    project_id=project_uuid
                )
            }
            items = [
                RuntimeModelPolicyItem(
                    catalog_id=str(row.id),
                    model_id=str(row.id),
                    display_name=row.display_name or str(row.id),
                    policy=RuntimeModelPolicyValue(
                        is_enabled=policy_rows.get(str(row.id)).is_enabled
                        if policy_rows.get(str(row.id))
                        else True,
                        is_default_for_project=policy_rows.get(
                            str(row.id)
                        ).is_default_for_project
                        if policy_rows.get(str(row.id))
                        else False,
                        temperature_default=float(
                            policy_rows.get(str(row.id)).temperature_default
                        )
                        if policy_rows.get(str(row.id))
                        and policy_rows.get(str(row.id)).temperature_default is not None
                        else None,
                        note=policy_rows.get(str(row.id)).note
                        if policy_rows.get(str(row.id))
                        else None,
                    ),
                )
                for row in catalog_rows
            ]
            return RuntimeModelPolicyList(items=items, total=len(items))

    def upsert_model_policy(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        catalog_id: str,
        command: UpsertRuntimeModelPolicyCommand,
    ) -> RuntimeModelPolicyValue:
        session_factory = self._require_session_factory()
        project_uuid = self._require_project_access(
            actor=actor, project_id=project_id, write=True
        )
        catalog_uuid = parse_uuid(catalog_id, code="invalid_catalog_id")
        with session_scope(session_factory) as session:
            self._ensure_project_exists(session, project_uuid)
            catalog_repository = SqlAlchemyRuntimeCatalogRepository(session)
            if catalog_repository.get_model_by_id(catalog_uuid) is None:
                raise NotFoundError(
                    message="Model catalog not found", code="model_catalog_not_found"
                )
            policy_repository = SqlAlchemyRuntimePolicyRepository(session)
            row = policy_repository.upsert_model_policy(
                project_id=project_uuid,
                model_catalog_id=catalog_uuid,
                is_enabled=command.is_enabled,
                is_default_for_project=command.is_default_for_project,
                temperature_default=Decimal(str(command.temperature_default))
                if command.temperature_default is not None
                else None,
                note=command.note,
                updated_by=actor.user_id,
            )
            return RuntimeModelPolicyValue(
                is_enabled=row.is_enabled,
                is_default_for_project=row.is_default_for_project,
                temperature_default=float(row.temperature_default)
                if row.temperature_default is not None
                else None,
                note=row.note,
                updated_at=row.updated_at,
            )
