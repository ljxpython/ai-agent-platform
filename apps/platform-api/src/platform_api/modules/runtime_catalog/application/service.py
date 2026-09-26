from __future__ import annotations

from starlette.concurrency import run_in_threadpool

import ipaddress
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlparse
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from platform_api.config import Settings
from platform_api.core.context.models import ActorContext
from platform_api.core.db import session_scope
from platform_api.core.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotAuthenticatedError,
    NotFoundError,
    ServiceUnavailableError,
)
from platform_api.core.identifiers import parse_uuid
from platform_api.core.security import (
    create_runtime_delegation_token,
    empty_runtime_context_hash,
)
from platform_api.modules.iam.application import (
    AuthorizationRequest,
    IamPolicyEngine,
    PermissionCode,
)
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
from platform_api.modules.runtime_catalog.application.credentials import (
    ModelCredentialError,
    decrypt_api_key,
    encrypt_api_key,
)
from platform_api.modules.runtime_catalog.application.model_connection import (
    ModelReferenceError,
    parse_model_reference,
)
from platform_api.modules.runtime_catalog.domain import (
    RuntimeCatalogRefreshResult,
    RuntimeGraphCatalogItem,
    RuntimeGraphCatalogList,
    RuntimeModelCatalogItem,
    RuntimeModelCatalogList,
    RuntimeModelCreate,
    RuntimeModelUpdate,
    RuntimeToolCatalogItem,
    RuntimeToolCatalogList,
)
from platform_api.modules.runtime_catalog.infra import (
    SqlAlchemyRuntimeCatalogRepository,
)
from platform_api.modules.runtime_policies.application import (
    RuntimePolicyOverlayService,
)


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _runtime_id(value: str) -> str:
    # Deployment identity is logical; its network address is configuration.
    return "default"


_SUPPORTED_PROTOCOLS = {"openai", "openai-compatible", "deepseek", "anthropic"}


class RuntimeCatalogService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None,
        upstream: Any,
        runtime_base_url: str,
        settings: Settings,
        tenant_id: str = "__default",
        policy_engine: IamPolicyEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._upstream = upstream
        self._runtime_id = _runtime_id(runtime_base_url)
        self._settings = settings
        self._tenant_id = tenant_id or "__default"
        self._policy_engine = policy_engine or IamPolicyEngine()

    def _require_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            raise ServiceUnavailableError(
                code="platform_database_not_enabled",
                message="Platform database is not enabled",
            )
        return self._session_factory

    def _require_project_exists(
        self,
        *,
        session: Session,
        project_id: str,
    ) -> UUID:
        project_uuid = parse_uuid(project_id, code="invalid_project_id")
        repository = SqlAlchemyProjectsRepository(session)
        project = repository.get_project_by_id(project_uuid)
        if project is None or project.status == "deleted":
            raise NotFoundError(message="Project not found", code="project_not_found")
        return project_uuid

    def _prepare_project_scope(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        permission: PermissionCode,
    ) -> UUID:
        session_factory = self._require_session_factory()
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=permission,
                project_id=project_id,
            ),
        )
        with session_scope(session_factory) as session:
            return self._require_project_exists(session=session, project_id=project_id)

    def _require_refresh_access(self, *, actor: ActorContext, project_id: str) -> None:
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PLATFORM_CATALOG_REFRESH
            ),
        )

    def _runtime_headers(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        catalog_refresh: bool = False,
        assistant_id: str | None = None,
    ) -> dict[str, str]:
        subject = actor.user_id or actor.subject
        if not subject:
            raise NotAuthenticatedError()
        project_roles = actor.project_role_set(project_id)
        if catalog_refresh:
            self._require_refresh_access(actor=actor, project_id=project_id)
            role = (
                "platform_super_admin"
                if actor.has_platform_role("platform_super_admin")
                else "platform_operator"
            )
        elif not project_roles:
            raise ForbiddenError(
                code="project_role_missing",
                message="Project role missing",
            )
        else:
            role = project_roles[0]
        try:
            policy = RuntimePolicyOverlayService(
                session_factory=self._session_factory,
                runtime_base_url=self._runtime_id,
            ).build_delegation_policy(project_id=project_id)
            delegation = create_runtime_delegation_token(
                subject=subject,
                tenant_id=self._tenant_id,
                project_id=project_id,
                role=role,
                permissions=[],
                policy_version=str(policy["version"]),
                allowed_model_ids=policy["allowed_model_ids"],
                tool_overrides={},
                tool_policy_version="unscoped-read-v2",
                scope={
                    "tenant_id": self._tenant_id,
                    "project_id": project_id,
                    "operation": "read",
                    **({"assistant_id": assistant_id} if assistant_id else {}),
                },
                context_hash=empty_runtime_context_hash(),
                settings=self._settings,
            )
        except ValueError as exc:
            raise ServiceUnavailableError(
                code="runtime_delegation_not_configured",
                message="Runtime delegation is not configured",
            ) from exc
        return {"authorization": f"Bearer {delegation}"}

    def _model_item(self, item: Any) -> RuntimeModelCatalogItem:
        scope_type = getattr(item, "scope_type", "platform") or "platform"
        project_id = getattr(item, "project_id", None)
        return RuntimeModelCatalogItem(
            id=str(item.id),
            display_name=item.display_name,
            provider=item.provider,
            base_url=item.base_url,
            protocol=item.protocol,
            model=item.model_name,
            enabled=item.enabled,
            credential_configured=bool(item.api_key_ciphertext),
            scope_type=scope_type,
            project_id=str(project_id) if project_id else None,
        )

    def _authorize_model_reference(self, values: dict, project_id: str) -> None:
        from datetime import UTC, datetime

        from platform_api.modules.agents.infra.sqlalchemy.repository import (
            SqlAlchemyAssistantsRepository,
        )
        from platform_api.modules.identity.actors import load_user_actor
        from platform_api.modules.runtime_policies.infra.sqlalchemy.repository import (
            SqlAlchemyRuntimePolicyRepository,
        )
        from platform_api.modules.service_accounts.models import (
            ServiceAccountTokenRecord,
        )
        from platform_api.modules.service_accounts.repository import (
            SqlAlchemyServiceAccountsRepository,
        )

        factory = self._require_session_factory()
        identity = values.get("actor")
        if not isinstance(identity, dict):
            raise ForbiddenError(
                code="runtime_model_reference_denied",
                message="Model reference has no principal",
            )

        with factory() as session:
            projects = SqlAlchemyProjectsRepository(session)
            project_uuid = parse_uuid(project_id, code="invalid_project_id")
            project = projects.get_project_by_id(project_uuid)
            if project is None or project.status == "deleted":
                raise ForbiddenError(
                    code="runtime_model_reference_denied",
                    message="Project is unavailable",
                )
            if identity.get("principal_type") == "user":
                actor = load_user_actor(
                    session_factory=factory,
                    user_id=identity.get("user_id") or "",
                    project_id=project_id,
                )
            elif identity.get("principal_type") == "service_account":
                token = session.get(
                    ServiceAccountTokenRecord,
                    parse_uuid(
                        identity.get("credential_id") or "",
                        code="invalid_credential_id",
                    ),
                )
                if (
                    token is None
                    or token.status != "active"
                    or token.revoked_at is not None
                    or (
                        token.expires_at is not None
                        and token.expires_at.replace(tzinfo=UTC) <= datetime.now(UTC)
                    )
                ):
                    raise ForbiddenError(
                        code="runtime_model_reference_denied",
                        message="Credential revoked",
                    )
                repo = SqlAlchemyServiceAccountsRepository(session)
                account = repo.get_service_account_by_id(token.service_account_id)
                role = repo.get_project_grant_role(
                    credential_id=str(token.id), project_id=project_uuid
                )
                actor = (
                    ActorContext(
                        subject=f"service-account:{account.id}",
                        principal_type="service_account",
                        platform_roles=account.platform_roles,
                        project_roles={project_id: (role.value,)} if role else {},
                    )
                    if account and account.status == "active"
                    else None
                )
            else:
                actor = None
            if actor is None:
                raise ForbiddenError(
                    code="runtime_model_reference_denied", message="Principal revoked"
                )
            from platform_api.modules.runtime_gateway.application import thread_access

            action = values.get("thread_action", "comment")
            if action not in {"comment", "approve"}:
                raise ForbiddenError(
                    code="thread_action_denied", message="Invalid execution action"
                )
            access = thread_access.get(factory, values.get("thread_id") or "")
            thread_access.require_action(actor, project_id, access, action)
            if action != "approve":
                self._policy_engine.require(
                    actor=actor,
                    authorization=AuthorizationRequest(
                        permission=PermissionCode.PROJECT_RUNTIME_EXECUTE,
                        project_id=project_id,
                    ),
                )
            agent = SqlAlchemyAssistantsRepository(session).get_by_project_and_graph_id(
                project_id=project_uuid, graph_id=values.get("agent_key") or ""
            )
            if agent is None or agent.status != "active":
                raise ForbiddenError(
                    code="runtime_target_denied", message="Agent is unavailable"
                )
            graph_ids = {
                str(graph.id)
                for graph in SqlAlchemyRuntimeCatalogRepository(session).list_graphs(
                    runtime_id=self._runtime_id
                )
                if graph.graph_key == agent.graph_id
            }
            if any(
                str(policy.graph_catalog_id) in graph_ids and not policy.is_enabled
                for policy in SqlAlchemyRuntimePolicyRepository(
                    session
                ).list_graph_policies(project_id=project_uuid)
            ):
                raise ForbiddenError(
                    code="runtime_target_denied", message="Graph permission revoked"
                )
            policies = SqlAlchemyRuntimePolicyRepository(session).list_model_policies(
                project_id=project_uuid
            )
            if any(
                str(policy.model_catalog_id) == values.get("model_id")
                and not policy.is_enabled
                for policy in policies
            ):
                raise ForbiddenError(
                    code="runtime_model_denied",
                    message="Project model permission revoked",
                )

    def authorize_message(self, reference: str, *, thread_id: str, run_id: str) -> dict:
        import jwt

        secret = (
            self._settings.runtime_model_config_secret
            or self._settings.runtime_delegation_secret
        )
        if not secret:
            raise ForbiddenError(
                code="message_authorization_unavailable",
                message="Message authorization is not configured",
            )
        try:
            values = jwt.decode(
                reference,
                secret,
                algorithms=["HS256"],
                audience="runtime-message",
                options={
                    "require": ["exp", "project_id", "thread_id", "run_id", "actor"]
                },
            )
        except jwt.InvalidTokenError as exc:
            raise ForbiddenError(
                code="message_authorization_invalid",
                message="Invalid message authorization",
            ) from exc
        if values["thread_id"] != thread_id or values["run_id"] != run_id:
            raise ForbiddenError(
                code="message_scope_denied", message="Message scope mismatch"
            )
        self._authorize_model_reference(values, values["project_id"])
        return {"allowed": True, "project_id": values["project_id"]}

    def resolve_model_connection(
        self,
        *,
        reference: str,
        project_id: str,
        trusted_runtime: bool = False,
    ) -> dict[str, str]:
        """Resolve one short-lived internal reference without exposing it publicly."""
        secret = (
            self._settings.runtime_model_config_secret
            or self._settings.runtime_delegation_secret
        )
        try:
            values = parse_model_reference(
                reference, secret=secret, allow_expired=trusted_runtime
            )
        except ModelReferenceError as exc:
            raise ForbiddenError(
                code="runtime_model_reference_invalid",
                message="Invalid model reference",
            ) from exc
        if values["project_id"] != project_id:
            raise ForbiddenError(
                code="runtime_model_reference_denied",
                message="Model reference project mismatch",
            )

        self._authorize_model_reference(values, project_id)
        session_factory = self._require_session_factory()
        with session_scope(session_factory) as session:
            repository = SqlAlchemyRuntimeCatalogRepository(session)
            item = repository.get_model_by_id(
                parse_uuid(values["model_id"], code="invalid_model_id")
            )
            if item is None or not item.enabled:
                raise NotFoundError(
                    code="runtime_model_not_found", message="Runtime model not found"
                )
            if item.scope_type == "project" and str(item.project_id) != project_id:
                raise ForbiddenError(
                    code="runtime_model_reference_denied",
                    message="Model reference project mismatch",
                )
            try:
                api_key = decrypt_api_key(
                    item.api_key_ciphertext,
                    master_key=self._settings.model_config_master_key,
                )
            except ModelCredentialError as exc:
                raise ServiceUnavailableError(
                    code="model_credential_unavailable",
                    message="Model credential storage is not configured",
                ) from exc
            required = (
                item.provider,
                item.base_url,
                item.protocol,
                item.model_name,
                api_key,
            )
            if any(not value for value in required):
                raise ServiceUnavailableError(
                    code="runtime_model_connection_incomplete",
                    message="Runtime model connection is incomplete",
                )
            return {
                "model_id": str(item.id),
                "provider": item.provider,
                "base_url": item.base_url,
                "protocol": item.protocol,
                "model": item.model_name,
                "api_key": api_key,
            }

    @staticmethod
    def _validated_model_values(
        payload: RuntimeModelCreate | RuntimeModelUpdate, *, partial: bool
    ) -> dict[str, Any]:
        values = payload.model_dump(exclude_unset=partial)
        if "enabled" in values and not isinstance(values["enabled"], bool):
            raise BadRequestError(
                code="invalid_model_enabled", message="enabled must be a boolean"
            )
        required = ("provider", "display_name", "base_url", "protocol", "model")
        if not partial:
            missing = [
                key for key in (*required, "api_key") if not _clean(values.get(key))
            ]
            if missing:
                raise BadRequestError(
                    message="model fields are required",
                    code="model_fields_required",
                )
        for key in required:
            if key in values and not _clean(values[key]):
                raise BadRequestError(
                    message=f"{key} is required", code="model_field_required"
                )
        if "base_url" in values:
            parsed = urlparse(str(values["base_url"]).strip())
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise BadRequestError(
                    message="base_url must be a valid http or https URL",
                    code="invalid_model_base_url",
                )
            if parsed.username or parsed.password:
                raise BadRequestError(
                    message="base_url must not contain embedded credentials",
                    code="invalid_model_base_url",
                )
            hostname = (parsed.hostname or "").lower().rstrip(".")
            if hostname in {"localhost", "localhost.localdomain"}:
                raise BadRequestError(
                    message="base_url must not target localhost",
                    code="invalid_model_base_url",
                )
            try:
                address = ipaddress.ip_address(hostname)
            except ValueError:
                address = None
            if address is not None and (
                address.is_private
                or address.is_loopback
                or address.is_link_local
                or address.is_unspecified
            ):
                raise BadRequestError(
                    message="base_url must not target a private or local address",
                    code="invalid_model_base_url",
                )
            values["base_url"] = str(values["base_url"]).strip().rstrip("/")
        if "protocol" in values:
            values["protocol"] = str(values["protocol"]).strip().lower()
            if values["protocol"] not in _SUPPORTED_PROTOCOLS:
                raise BadRequestError(
                    message="unsupported model protocol",
                    code="unsupported_model_protocol",
                )
        for key in ("provider", "display_name", "model"):
            if key in values:
                values[key] = str(values[key]).strip()
        if "api_key" in values and not _clean(values["api_key"]):
            raise BadRequestError(
                message="api_key is required", code="model_field_required"
            )
        return values

    def create_model(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        payload: RuntimeModelCreate,
    ) -> RuntimeModelCatalogItem:
        scope_type = payload.scope_type or "platform"
        target_project_uuid: UUID | None = None
        if scope_type == "project":
            effective_project_id = _clean(project_id or payload.project_id)
            if not effective_project_id:
                raise BadRequestError(
                    code="project_id_required",
                    message="project_id is required for project scoped models",
                )
            self._prepare_project_scope(
                actor=actor,
                project_id=effective_project_id,
                permission=PermissionCode.PROJECT_RUNTIME_WRITE,
            )
            target_project_uuid = parse_uuid(
                effective_project_id, code="invalid_project_id"
            )
        else:
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PLATFORM_MODEL_WRITE
                ),
            )

        values = self._validated_model_values(payload, partial=False)
        values["scope_type"] = scope_type
        values["project_id"] = target_project_uuid
        try:
            values["api_key_ciphertext"] = encrypt_api_key(
                payload.api_key,
                master_key=self._settings.model_config_master_key,
            )
        except ModelCredentialError as exc:
            raise ServiceUnavailableError(
                code="model_credential_unavailable",
                message="Model credential storage is not configured",
            ) from exc
        session_factory = self._require_session_factory()
        with session_scope(session_factory) as session:
            repository = SqlAlchemyRuntimeCatalogRepository(session)
            existing = repository.find_model_by_endpoint_and_name(
                provider=values["provider"],
                base_url=values["base_url"],
                model_name=values["model"],
                scope_type=scope_type,
                project_id=target_project_uuid,
            )
            if existing is not None:
                raise ConflictError(
                    code="duplicate_model",
                    message=f"Model '{values['model']}' already exists for provider '{values['provider']}' at endpoint '{values['base_url']}'",
                )
            item = repository.create_configured_model(
                values=values,
            )
            return self._model_item(item)

    def update_model(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        model_id: str,
        payload: RuntimeModelUpdate,
    ) -> RuntimeModelCatalogItem:
        model_uuid = parse_uuid(model_id, code="invalid_model_id")
        session_factory = self._require_session_factory()
        with session_scope(session_factory) as session:
            repository = SqlAlchemyRuntimeCatalogRepository(session)
            current = repository.get_model_by_id(model_uuid)
            if current is None:
                raise NotFoundError(message="Model not found", code="model_not_found")

            if current.scope_type == "project":
                current_project_str = str(current.project_id)
                req_project_id = _clean(project_id)
                if req_project_id and req_project_id != current_project_str:
                    raise ForbiddenError(
                        code="project_mismatch",
                        message="Cannot modify a model belonging to another project",
                    )
                self._prepare_project_scope(
                    actor=actor,
                    project_id=current_project_str,
                    permission=PermissionCode.PROJECT_RUNTIME_WRITE,
                )
            else:
                self._policy_engine.require(
                    actor=actor,
                    authorization=AuthorizationRequest(
                        permission=PermissionCode.PLATFORM_MODEL_WRITE
                    ),
                )

            values = self._validated_model_values(payload, partial=True)
            if "api_key" in values:
                try:
                    values["api_key_ciphertext"] = encrypt_api_key(
                        values.pop("api_key"),
                        master_key=self._settings.model_config_master_key,
                    )
                except ModelCredentialError as exc:
                    raise ServiceUnavailableError(
                        code="model_credential_unavailable",
                        message="Model credential storage is not configured",
                    ) from exc
            if "model" in values:
                model_name = values.pop("model")
                values["model_name"] = model_name
            if "enabled" not in values:
                values.pop("enabled", None)

            # Prevent mutating scope_type or project_id via update
            values.pop("scope_type", None)
            values.pop("project_id", None)

            target_provider = values.get("provider", current.provider)
            target_base_url = values.get("base_url", current.base_url)
            target_model_name = values.get("model_name", current.model_name)
            existing = repository.find_model_by_endpoint_and_name(
                provider=target_provider,
                base_url=target_base_url,
                model_name=target_model_name,
                scope_type=current.scope_type,
                project_id=current.project_id,
            )
            if existing is not None and existing.id != model_uuid:
                raise ConflictError(
                    code="duplicate_model",
                    message=f"Model '{target_model_name}' already exists for provider '{target_provider}' at endpoint '{target_base_url}'",
                )
            item = repository.update_configured_model(
                model_uuid,
                values=values,
            )
            if item is None:
                raise NotFoundError(message="Model not found", code="model_not_found")
            return self._model_item(item)

    def delete_model(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        model_id: str,
    ) -> None:
        model_uuid = parse_uuid(model_id, code="invalid_model_id")
        session_factory = self._require_session_factory()
        with session_scope(session_factory) as session:
            repository = SqlAlchemyRuntimeCatalogRepository(session)
            current = repository.get_model_by_id(model_uuid)
            if current is None:
                raise NotFoundError(message="Model not found", code="model_not_found")

            if current.scope_type == "project":
                current_project_str = str(current.project_id)
                req_project_id = _clean(project_id)
                if req_project_id and req_project_id != current_project_str:
                    raise ForbiddenError(
                        code="project_mismatch",
                        message="Cannot delete a model belonging to another project",
                    )
                self._prepare_project_scope(
                    actor=actor,
                    project_id=current_project_str,
                    permission=PermissionCode.PROJECT_RUNTIME_WRITE,
                )
            else:
                self._policy_engine.require(
                    actor=actor,
                    authorization=AuthorizationRequest(
                        permission=PermissionCode.PLATFORM_MODEL_WRITE
                    ),
                )

            repository.delete_configured_model(model_uuid)

    def _tool_item(self, item: Any) -> RuntimeToolCatalogItem:
        return RuntimeToolCatalogItem(
            id=str(item.id),
            runtime_id=item.runtime_id,
            tool_key=item.tool_key,
            graph_ids=list(item.graph_ids),
            name=item.name,
            source=item.source or "",
            description=item.description or "",
            sync_status=item.sync_status,
            last_seen_at=item.last_seen_at,
            last_synced_at=item.last_synced_at,
        )

    def _graph_item(self, item: Any) -> RuntimeGraphCatalogItem:
        return RuntimeGraphCatalogItem(
            id=str(item.id),
            runtime_id=item.runtime_id,
            graph_id=item.graph_key,
            display_name=item.display_name or item.graph_key,
            description=item.description or "",
            source_type=item.source_type,
            sync_status=item.sync_status,
            last_seen_at=item.last_seen_at,
            last_synced_at=item.last_synced_at,
        )

    @staticmethod
    def _normalize_tool_items(payload: Any) -> list[dict[str, Any]]:
        def invalid():
            return ServiceUnavailableError(
                code="runtime_tool_catalog_invalid",
                message="Invalid Runtime tool declarations",
            )

        if not isinstance(payload, dict) or not isinstance(payload.get("tools"), list):
            raise invalid()
        seen = set()
        for item in payload["tools"]:
            if not isinstance(item, dict):
                raise invalid()
            for key in ("tool_key", "name"):
                value = item.get(key)
                if (
                    not isinstance(value, str)
                    or not value
                    or len(value) > 128
                    or value != value.strip()
                ):
                    raise invalid()
            graphs = item.get("graph_ids")
            if (
                item["tool_key"] != item["name"]
                or item["tool_key"] in seen
                or not isinstance(graphs, list)
                or not graphs
                or any(not isinstance(g, str) or not g or len(g) > 128 for g in graphs)
            ):
                raise invalid()
            seen.add(item["tool_key"])
        return payload["tools"]

    async def read_tool_declarations(
        self, *, actor: ActorContext, project_id: str
    ) -> list[dict]:
        await run_in_threadpool(
            self._prepare_project_scope,
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_RUNTIME_READ,
        )
        payload = await self._upstream.require_json(
            "GET",
            "/internal/capabilities/tools",
            forwarded_headers=await run_in_threadpool(
                self._runtime_headers, actor=actor, project_id=project_id
            ),
        )
        return self._normalize_tool_items(payload)

    @staticmethod
    def _normalize_graph_items(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict) and isinstance(payload.get("items"), list):
            return [item for item in payload["items"] if isinstance(item, dict)]
        return []

    @staticmethod
    def _latest_synced_at(items: list[Any]) -> datetime | None:
        return max(
            (item.last_synced_at for item in items if item.last_synced_at is not None),
            default=None,
        )

    def list_models(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        platform: bool = False,
    ) -> RuntimeModelCatalogList:
        target_project_uuid: UUID | None = None
        scope_filter: str | None = None
        if platform:
            self._policy_engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PLATFORM_MODEL_READ
                ),
            )
            scope_filter = "platform"
        else:
            self._prepare_project_scope(
                actor=actor,
                project_id=project_id,
                permission=PermissionCode.PROJECT_RUNTIME_READ,
            )
            target_project_uuid = parse_uuid(project_id, code="invalid_project_id")

        session_factory = self._require_session_factory()
        with session_scope(session_factory) as session:
            repository = SqlAlchemyRuntimeCatalogRepository(session)
            rows = repository.list_models(
                scope_type=scope_filter,
                project_id=target_project_uuid,
            )
            items = [self._model_item(item) for item in rows]
            if not platform:
                result_items = []
                for item in items:
                    if item.scope_type == "platform":
                        result_items.append(
                            item.model_copy(
                                update={
                                    "base_url": "",
                                    "credential_configured": item.credential_configured,
                                }
                            )
                        )
                    else:
                        result_items.append(item)
                items = result_items
            return RuntimeModelCatalogList(
                count=len(items),
                models=items,
            )

    def list_tools(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> RuntimeToolCatalogList:
        self._prepare_project_scope(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_RUNTIME_READ,
        )
        session_factory = self._require_session_factory()
        with session_scope(session_factory) as session:
            repository = SqlAlchemyRuntimeCatalogRepository(session)
            rows = repository.list_tools(runtime_id=self._runtime_id)
            items = [self._tool_item(item) for item in rows]
            return RuntimeToolCatalogList(
                count=len(items),
                tools=items,
                last_synced_at=self._latest_synced_at(items),
            )

    async def refresh_tools(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> RuntimeCatalogRefreshResult:
        await run_in_threadpool(
            self._prepare_project_scope,
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PLATFORM_CATALOG_REFRESH,
        )
        self._require_refresh_access(actor=actor, project_id=project_id)

        payload = await self._upstream.require_json(
            "GET",
            "/internal/capabilities/tools",
            forwarded_headers=await run_in_threadpool(
                self._runtime_headers,
                actor=actor,
                project_id=project_id,
                catalog_refresh=True,
            ),
        )
        items = self._normalize_tool_items(payload)
        synced_at = datetime.now(UTC)
        active_keys = {item["tool_key"] for item in items}

        session_factory = self._require_session_factory()

        def persist():
            with session_scope(session_factory) as session:
                repository = SqlAlchemyRuntimeCatalogRepository(session)
                repository.upsert_tool_items(
                    runtime_id=self._runtime_id,
                    items=items,
                    synced_at=synced_at,
                )
                repository.mark_missing_tools_deleted(
                    runtime_id=self._runtime_id,
                    active_keys=active_keys,
                    synced_at=synced_at,
                )

        await run_in_threadpool(persist)

        return RuntimeCatalogRefreshResult(
            ok=True,
            count=len(items),
            last_synced_at=synced_at,
        )

    async def get_graph_schema(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        graph_id: str,
    ) -> dict[str, Any]:
        await run_in_threadpool(
            self._prepare_project_scope,
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_RUNTIME_READ,
        )
        return await self._upstream.require_json(
            "GET",
            f"/assistants/{quote(graph_id, safe='')}/schemas",
            forwarded_headers=await run_in_threadpool(
                self._runtime_headers,
                actor=actor,
                project_id=project_id,
                assistant_id=graph_id,
            ),
        )

    def list_graphs(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> RuntimeGraphCatalogList:
        self._prepare_project_scope(
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PROJECT_RUNTIME_READ,
        )
        session_factory = self._require_session_factory()
        with session_scope(session_factory) as session:
            repository = SqlAlchemyRuntimeCatalogRepository(session)
            rows = repository.list_graphs(runtime_id=self._runtime_id)

            items = [self._graph_item(item) for item in rows]
            return RuntimeGraphCatalogList(
                count=len(items),
                graphs=items,
                last_synced_at=self._latest_synced_at(items),
            )

    async def refresh_graphs(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> RuntimeCatalogRefreshResult:
        await run_in_threadpool(
            self._prepare_project_scope,
            actor=actor,
            project_id=project_id,
            permission=PermissionCode.PLATFORM_CATALOG_REFRESH,
        )
        self._require_refresh_access(actor=actor, project_id=project_id)

        rows = await self._upstream.list_deployed_graphs(
            forwarded_headers=await run_in_threadpool(
                self._runtime_headers,
                actor=actor,
                project_id=project_id,
                catalog_refresh=True,
            ),
        )
        items = [{**row, "display_name": row["graph_id"]} for row in rows]
        synced_at = datetime.now(UTC)
        active_keys = {
            graph_id
            for graph_id in (_clean(item.get("graph_id")) for item in items)
            if graph_id
        }

        session_factory = self._require_session_factory()

        def persist():
            with session_scope(session_factory) as session:
                repository = SqlAlchemyRuntimeCatalogRepository(session)
                repository.upsert_graph_items(
                    runtime_id=self._runtime_id,
                    items=items,
                    synced_at=synced_at,
                    source_type="default_assistant",
                )
                repository.mark_missing_graphs_deleted(
                    runtime_id=self._runtime_id,
                    active_keys=active_keys,
                    synced_at=synced_at,
                )

        await run_in_threadpool(persist)

        return RuntimeCatalogRefreshResult(
            ok=True,
            count=len(items),
            last_synced_at=synced_at,
        )
