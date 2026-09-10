from __future__ import annotations


from sqlalchemy.orm import Session, sessionmaker

from platform_api.config import Settings
from platform_api.core.context.models import ActorContext
from platform_api.core.db import session_scope
from platform_api.core.errors import BadRequestError, ServiceUnavailableError
from platform_api.core.observability import metrics_registry
from platform_api.modules.iam.application import (
    AuthorizationRequest,
    IamPolicyEngine,
    PermissionCode,
)
from platform_api.modules.platform_config.contracts import UpdateFeatureFlagsCommand
from platform_api.modules.platform_config.repository import (
    SqlAlchemyPlatformConfigRepository,
)
from platform_api.modules.service_accounts.repository import (
    SqlAlchemyServiceAccountsRepository,
)

_FEATURE_FLAG_ENTRY_KEY = "feature_flags"


class PlatformConfigService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None,
        settings: Settings,
        policy_engine: IamPolicyEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._policy_engine = policy_engine or IamPolicyEngine()

    def _require_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            raise ServiceUnavailableError(
                code="platform_database_not_enabled",
                message="Platform database is not enabled",
            )
        return self._session_factory

    @staticmethod
    def _default_feature_flags() -> dict[str, bool]:
        return {
            "platform_config_enabled": True,
            "policy_overlay_registry_ready": True,
            "runtime_policy_overlay_enabled": True,
        }

    @staticmethod
    def _mask_secret(value: str | None) -> dict[str, object]:
        if not value:
            return {"configured": False, "masked_value": None}
        masked = value[:2] + "*" * max(0, len(value) - 6) + value[-4:]
        return {"configured": True, "masked_value": masked}

    def _build_service_account_summary(self) -> dict[str, int]:
        if self._session_factory is None:
            return {
                "total_accounts": 0,
                "active_accounts": 0,
                "active_tokens": 0,
                "revoked_tokens": 0,
            }
        with session_scope(self._require_session_factory()) as session:
            repository = SqlAlchemyServiceAccountsRepository(session)
            return repository.summarize()

    def _build_security_snapshot(self) -> dict[str, object]:
        return {
            "oidc": {
                "enabled": self._settings.oidc_enabled,
                "issuer_url": self._settings.oidc_issuer_url,
                "client_id": self._settings.oidc_client_id,
                "mode": "boundary_defined"
                if self._settings.oidc_enabled
                else "reserved",
            },
            "service_accounts": {
                "enabled": self._settings.service_accounts_enabled,
                "api_key_header": self._settings.service_account_api_key_header,
                "default_token_ttl_days": self._settings.service_account_token_default_ttl_days,
                **self._build_service_account_summary(),
            },
            "sensitive_config": {
                "langgraph_upstream_api_key": self._mask_secret(
                    self._settings.langgraph_upstream_api_key
                ),
                "jwt_access_secret": self._mask_secret(
                    self._settings.jwt_access_secret
                ),
                "jwt_refresh_secret": self._mask_secret(
                    self._settings.jwt_refresh_secret
                ),
            },
        }

    def _build_environment_snapshot(self) -> dict[str, object]:
        return {
            "current": self._settings.app_env,
            "supported": ["local", "dev", "staging", "prod"],
            "production_like": self._settings.app_env.lower()
            in {"staging", "prod", "production"},
            "auth_required": self._settings.auth_required,
            "docs_enabled": self._settings.api_docs_enabled,
            "bootstrap_admin_enabled": self._settings.bootstrap_admin_enabled,
        }

    def _build_data_governance_snapshot(self) -> dict[str, object]:
        return {
            "audit_storage": "platform_database",
            "delete_mode": "governed_manual_or_api",
        }

    def get_observability_snapshot(self) -> dict[str, object]:
        return {
            "requests": metrics_registry.snapshot_http_metrics(
                top_paths_limit=self._settings.observability_metrics_top_paths_limit
            ),
            "trace": {
                "request_id_header": "x-request-id",
                "trace_id_header": "x-trace-id",
            },
        }

    def get_observability_snapshot_for_actor(
        self,
        *,
        actor: ActorContext,
    ) -> dict[str, object]:
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PLATFORM_CONFIG_READ
            ),
        )
        return self.get_observability_snapshot()

    def get_snapshot(self, *, actor: ActorContext) -> dict[str, object]:
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PLATFORM_CONFIG_READ
            ),
        )
        feature_flags = dict(self._default_feature_flags())
        if self._session_factory is not None:
            session_factory = self._require_session_factory()
            with session_scope(session_factory) as session:
                repository = SqlAlchemyPlatformConfigRepository(session)
                payload = repository.get_json(_FEATURE_FLAG_ENTRY_KEY)
                if isinstance(payload, dict):
                    for key, value in payload.items():
                        if key in feature_flags and isinstance(value, bool):
                            feature_flags[key] = value

        return {
            "service": {
                "name": self._settings.app_name,
                "version": self._settings.app_version,
                "env": self._settings.app_env,
                "docs_enabled": self._settings.api_docs_enabled,
            },
            "database": {
                "enabled": self._settings.platform_db_enabled,
                "auto_create": self._settings.platform_db_auto_create,
                "migration_strategy": "alembic",
            },
            "auth": {
                "required": self._settings.auth_required,
                "bootstrap_admin_enabled": self._settings.bootstrap_admin_enabled,
            },
            "runtime": {
                "langgraph_upstream_url": self._settings.langgraph_upstream_url,
            },
            "observability": self.get_observability_snapshot(),
            "security": self._build_security_snapshot(),
            "environment": self._build_environment_snapshot(),
            "data_governance": self._build_data_governance_snapshot(),
            "feature_flags": feature_flags,
        }

    def update_feature_flags(
        self,
        *,
        actor: ActorContext,
        command: UpdateFeatureFlagsCommand,
    ) -> dict[str, object]:
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=PermissionCode.PLATFORM_CONFIG_WRITE
            ),
        )
        session_factory = self._require_session_factory()
        current_flags = dict(self._default_feature_flags())
        unknown_keys = sorted(set(command.feature_flags) - set(current_flags))
        if unknown_keys:
            raise BadRequestError(
                code="unknown_feature_flags",
                message=f"unknown_feature_flags:{','.join(unknown_keys)}",
            )

        with session_scope(session_factory) as session:
            repository = SqlAlchemyPlatformConfigRepository(session)
            payload = repository.get_json(_FEATURE_FLAG_ENTRY_KEY)
            if isinstance(payload, dict):
                for key, value in payload.items():
                    if key in current_flags and isinstance(value, bool):
                        current_flags[key] = value
            current_flags.update(command.feature_flags)
            repository.upsert_json(
                key=_FEATURE_FLAG_ENTRY_KEY,
                value=current_flags,
                updated_by=actor.user_id or actor.subject,
            )

        return self.get_snapshot(actor=actor)
