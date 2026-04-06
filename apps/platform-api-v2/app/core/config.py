from __future__ import annotations

import json
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Platform API V2"
    app_version: str = "0.1.0"
    app_env: str = "local"
    api_docs_enabled: bool = True
    cors_allow_origins: tuple[str, ...] = ("*",)

    langgraph_upstream_url: str = "http://127.0.0.1:8123"
    langgraph_upstream_api_key: str | None = None
    langgraph_upstream_timeout_seconds: float = Field(default=30.0, gt=0, le=600)
    langgraph_graph_source_root: str | None = None
    interaction_data_service_url: str | None = "http://127.0.0.1:8081"
    interaction_data_service_token: str | None = None
    interaction_data_service_timeout_seconds: float = Field(default=30.0, gt=0, le=600)

    platform_db_enabled: bool = False
    platform_db_auto_create: bool = False
    database_url: str | None = None
    operations_queue_backend: str = "db_polling"
    operations_worker_poll_interval_seconds: float = Field(default=1.0, gt=0, le=60)
    operations_worker_idle_sleep_seconds: float = Field(default=2.0, gt=0, le=120)
    operations_artifacts_dir: str = ".runtime/operations-artifacts"

    auth_required: bool = True
    jwt_access_secret: str = "change-me-access-secret"
    jwt_refresh_secret: str = "change-me-refresh-secret"
    jwt_access_ttl_seconds: int = Field(default=1800, ge=60)
    jwt_refresh_ttl_seconds: int = Field(default=7 * 24 * 3600, ge=300)

    bootstrap_admin_enabled: bool = True
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = "admin123456"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PLATFORM_API_V2_",
        extra="ignore",
    )

    @field_validator("cors_allow_origins", mode="before")
    @classmethod
    def parse_cors_allow_origins(cls, value: Any) -> tuple[str, ...]:
        if isinstance(value, str):
            normalized = value.strip()
            if normalized.startswith("["):
                try:
                    parsed = json.loads(normalized)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, list):
                    items = [str(item).strip() for item in parsed if str(item).strip()]
                    return tuple(items or ["*"])
            items = [item.strip() for item in value.split(",") if item.strip()]
            return tuple(items or ["*"])
        if isinstance(value, (list, tuple)):
            items = [str(item).strip() for item in value if str(item).strip()]
            return tuple(items or ["*"])
        return ("*",)

    @model_validator(mode="after")
    def validate_security_guards(self) -> "Settings":
        is_production = self.app_env.lower() in {"prod", "production"}
        if self.platform_db_enabled and not self.database_url:
            raise ValueError(
                "PLATFORM_API_V2_DATABASE_URL is required when platform_db_enabled=true"
            )
        if self.operations_queue_backend not in {"db_polling"}:
            raise ValueError("operations_queue_backend must be 'db_polling'")
        if is_production:
            if self.api_docs_enabled:
                raise ValueError("API docs must be disabled in production")
            if self.bootstrap_admin_enabled:
                raise ValueError("Bootstrap admin must be disabled in production")
            if self.jwt_access_secret == "change-me-access-secret":
                raise ValueError("JWT access secret must be overridden in production")
            if self.jwt_refresh_secret == "change-me-refresh-secret":
                raise ValueError("JWT refresh secret must be overridden in production")
        return self


def load_settings() -> Settings:
    return Settings()
