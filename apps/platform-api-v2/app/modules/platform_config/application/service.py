from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.context.models import ActorContext
from app.core.db import SqlAlchemyUnitOfWork
from app.core.errors import BadRequestError, ServiceUnavailableError
from app.modules.iam.application import AuthorizationRequest, IamPolicyEngine, PermissionCode
from app.modules.platform_config.application.contracts import UpdateFeatureFlagsCommand
from app.modules.platform_config.infra import SqlAlchemyPlatformConfigRepository

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
            "operations_enabled": True,
            "operations_center_enabled": True,
            "platform_config_enabled": True,
            "runtime_catalog_refresh_async_ready": True,
            "policy_overlay_registry_ready": True,
            "runtime_policy_overlay_enabled": True,
        }

    async def get_snapshot(self, *, actor: ActorContext) -> dict[str, object]:
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(permission=PermissionCode.PLATFORM_CONFIG_READ),
        )
        feature_flags = dict(self._default_feature_flags())
        if self._session_factory is not None:
            session_factory = self._require_session_factory()
            async with SqlAlchemyUnitOfWork(session_factory) as uow:
                repository = SqlAlchemyPlatformConfigRepository(uow.session)
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
            "operations": {
                "queue_backend": self._settings.operations_queue_backend,
                "worker_poll_interval_seconds": self._settings.operations_worker_poll_interval_seconds,
                "worker_idle_sleep_seconds": self._settings.operations_worker_idle_sleep_seconds,
            },
            "auth": {
                "required": self._settings.auth_required,
                "bootstrap_admin_enabled": self._settings.bootstrap_admin_enabled,
            },
            "runtime": {
                "langgraph_upstream_url": self._settings.langgraph_upstream_url,
                "interaction_data_service_configured": bool(self._settings.interaction_data_service_url),
            },
            "feature_flags": feature_flags,
        }

    async def update_feature_flags(
        self,
        *,
        actor: ActorContext,
        command: UpdateFeatureFlagsCommand,
    ) -> dict[str, object]:
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(permission=PermissionCode.PLATFORM_CONFIG_WRITE),
        )
        session_factory = self._require_session_factory()
        current_flags = dict(self._default_feature_flags())
        unknown_keys = sorted(set(command.feature_flags) - set(current_flags))
        if unknown_keys:
            raise BadRequestError(
                code="unknown_feature_flags",
                message=f"unknown_feature_flags:{','.join(unknown_keys)}",
            )

        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            repository = SqlAlchemyPlatformConfigRepository(uow.session)
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

        return await self.get_snapshot(actor=actor)
