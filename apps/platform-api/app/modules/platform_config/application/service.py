from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.context.models import ActorContext
from app.core.db import SqlAlchemyUnitOfWork, session_scope
from app.core.errors import BadRequestError, ServiceUnavailableError
from app.core.observability import metrics_registry
from app.modules.iam.application import AuthorizationRequest, IamPolicyEngine, PermissionCode
from app.modules.operations.infra import (
    SqlAlchemyOperationsRepository,
    SqlAlchemyOperationWorkerHeartbeatRepository,
)
from app.modules.platform_config.application.contracts import UpdateFeatureFlagsCommand
from app.modules.platform_config.infra import SqlAlchemyPlatformConfigRepository
from app.modules.service_accounts.infra.sqlalchemy.repository import (
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
            "operations_enabled": True,
            "operations_center_enabled": True,
            "platform_config_enabled": True,
            "runtime_catalog_refresh_async_ready": True,
            "policy_overlay_registry_ready": True,
            "runtime_policy_overlay_enabled": True,
        }

    @staticmethod
    def _mask_secret(value: str | None) -> dict[str, object]:
        if not value:
            return {"configured": False, "masked_value": None}
        masked = value[:2] + "*" * max(0, len(value) - 6) + value[-4:]
        return {"configured": True, "masked_value": masked}

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _build_worker_snapshot(self) -> dict[str, object]:
        if self._session_factory is None:
            return {
                "heartbeat_interval_seconds": self._settings.operations_worker_heartbeat_interval_seconds,
                "stale_after_seconds": self._settings.operations_worker_stale_after_seconds,
                "healthy_count": 0,
                "stale_count": 0,
                "items": [],
            }

        now = datetime.now(timezone.utc)
        with session_scope(self._require_session_factory()) as session:
            repository = SqlAlchemyOperationWorkerHeartbeatRepository(session)
            heartbeats = repository.list_heartbeats()

        items: list[dict[str, object]] = []
        healthy_count = 0
        stale_count = 0
        for item in heartbeats:
            last_started_at = self._normalize_datetime(item.last_started_at)
            last_completed_at = self._normalize_datetime(item.last_completed_at)
            last_heartbeat_at = self._normalize_datetime(item.last_heartbeat_at)
            age_seconds = (
                max(0.0, (now - last_heartbeat_at).total_seconds())
                if last_heartbeat_at is not None
                else self._settings.operations_worker_stale_after_seconds + 1
            )
            is_healthy = age_seconds <= self._settings.operations_worker_stale_after_seconds
            if is_healthy:
                healthy_count += 1
            else:
                stale_count += 1
            items.append(
                {
                    "worker_id": item.worker_id,
                    "queue_backend": item.queue_backend,
                    "hostname": item.hostname,
                    "pid": item.pid,
                    "status": item.status,
                    "current_operation_id": item.current_operation_id,
                    "last_error": item.last_error,
                    "last_started_at": last_started_at,
                    "last_completed_at": last_completed_at,
                    "last_heartbeat_at": last_heartbeat_at,
                    "age_seconds": round(age_seconds, 2),
                    "healthy": is_healthy,
                    "metadata": item.metadata,
                }
            )

        return {
            "heartbeat_interval_seconds": self._settings.operations_worker_heartbeat_interval_seconds,
            "stale_after_seconds": self._settings.operations_worker_stale_after_seconds,
            "healthy_count": healthy_count,
            "stale_count": stale_count,
            "items": items,
        }

    def _build_operations_snapshot(self) -> dict[str, object]:
        base_snapshot = {
            "queue_backend": self._settings.operations_queue_backend,
            "worker_poll_interval_seconds": self._settings.operations_worker_poll_interval_seconds,
            "worker_idle_sleep_seconds": self._settings.operations_worker_idle_sleep_seconds,
            "worker_heartbeat_interval_seconds": self._settings.operations_worker_heartbeat_interval_seconds,
            "worker_stale_after_seconds": self._settings.operations_worker_stale_after_seconds,
            "artifact_storage_backend": self._settings.operations_artifact_storage_backend,
            "artifact_retention_hours": self._settings.operations_artifact_retention_hours,
            "artifact_cleanup_batch_size": self._settings.operations_artifact_cleanup_batch_size,
        }
        if self._session_factory is None:
            return {
                **base_snapshot,
                "queue_depth": 0,
                "running_count": 0,
                "succeeded_count": 0,
                "failed_count": 0,
                "cancelled_count": 0,
                "archived_count": 0,
                "avg_duration_ms": 0.0,
                "max_duration_ms": 0.0,
            }

        with session_scope(self._require_session_factory()) as session:
            repository = SqlAlchemyOperationsRepository(session)
            summary = repository.summarize_operations()
        return {
            **base_snapshot,
            "queue_depth": summary["queued"],
            "running_count": summary["running"],
            "succeeded_count": summary["succeeded"],
            "failed_count": summary["failed"],
            "cancelled_count": summary["cancelled"],
            "archived_count": summary["archived"],
            "avg_duration_ms": summary["avg_duration_ms"],
            "max_duration_ms": summary["max_duration_ms"],
        }

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
                "mode": "boundary_defined" if self._settings.oidc_enabled else "reserved",
            },
            "service_accounts": {
                "enabled": self._settings.service_accounts_enabled,
                "api_key_header": self._settings.service_account_api_key_header,
                "default_token_ttl_days": self._settings.service_account_token_default_ttl_days,
                **self._build_service_account_summary(),
            },
            "sensitive_config": {
                "langgraph_upstream_api_key": self._mask_secret(self._settings.langgraph_upstream_api_key),
                "interaction_data_service_token": self._mask_secret(self._settings.interaction_data_service_token),
                "jwt_access_secret": self._mask_secret(self._settings.jwt_access_secret),
                "jwt_refresh_secret": self._mask_secret(self._settings.jwt_refresh_secret),
            },
        }

    def _build_environment_snapshot(self) -> dict[str, object]:
        return {
            "current": self._settings.app_env,
            "supported": ["local", "dev", "staging", "prod"],
            "production_like": self._settings.app_env.lower() in {"staging", "prod", "production"},
            "auth_required": self._settings.auth_required,
            "docs_enabled": self._settings.api_docs_enabled,
            "bootstrap_admin_enabled": self._settings.bootstrap_admin_enabled,
        }

    def _build_data_governance_snapshot(self) -> dict[str, object]:
        return {
            "artifact_retention_hours": self._settings.operations_artifact_retention_hours,
            "artifact_cleanup_batch_size": self._settings.operations_artifact_cleanup_batch_size,
            "audit_storage": "platform_database",
            "export_mode": "operation_managed",
            "delete_mode": "governed_manual_or_api",
        }

    async def get_observability_snapshot(self) -> dict[str, object]:
        return {
            "requests": metrics_registry.snapshot_http_metrics(
                top_paths_limit=self._settings.observability_metrics_top_paths_limit
            ),
            "operations": self._build_operations_snapshot(),
            "workers": self._build_worker_snapshot(),
            "trace": {
                "request_id_header": "x-request-id",
                "trace_id_header": "x-trace-id",
                "operation_chain_source": "operation.metadata._request_chain",
            },
        }

    async def get_observability_snapshot_for_actor(
        self,
        *,
        actor: ActorContext,
    ) -> dict[str, object]:
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(permission=PermissionCode.PLATFORM_CONFIG_READ),
        )
        return await self.get_observability_snapshot()

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
                **self._build_operations_snapshot(),
            },
            "auth": {
                "required": self._settings.auth_required,
                "bootstrap_admin_enabled": self._settings.bootstrap_admin_enabled,
            },
            "runtime": {
                "langgraph_upstream_url": self._settings.langgraph_upstream_url,
                "interaction_data_service_configured": bool(self._settings.interaction_data_service_url),
            },
            "observability": await self.get_observability_snapshot(),
            "security": self._build_security_snapshot(),
            "environment": self._build_environment_snapshot(),
            "data_governance": self._build_data_governance_snapshot(),
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
