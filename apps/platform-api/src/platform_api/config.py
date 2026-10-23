from __future__ import annotations

import json
import re
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class KnowledgeConnection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_url: str
    token: str = Field(min_length=32, repr=False)
    scope: dict[str, str]
    knowledge_base_id: str | None = Field(default=None, pattern=r"^kb_[a-f0-9]{32}$")

    @model_validator(mode="after")
    def validate_connection(self):
        from urllib.parse import urlsplit

        parsed = urlsplit(self.base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("knowledge URL must be a managed HTTP origin")
        if set(self.scope) != {"tenant_id", "project_id"} or any(
            not v or v != v.strip() for v in self.scope.values()
        ):
            raise ValueError("invalid knowledge connection scope")
        if not self.token.isascii() or any(
            ord(c) < 33 or ord(c) == 127 for c in self.token
        ):
            raise ValueError("invalid knowledge token")
        self.base_url = self.base_url.rstrip("/")
        return self


class Settings(BaseSettings):
    app_name: str = "Platform API"
    app_version: str = "0.1.2"
    app_env: str = "local"
    api_docs_enabled: bool = True
    cors_allow_origins: tuple[str, ...] = ("*",)

    langgraph_upstream_url: str = "http://127.0.0.1:8123"
    langgraph_upstream_api_key: str | None = None
    langgraph_upstream_timeout_seconds: float = Field(default=30.0, gt=0, le=600)
    runtime_delegation_secret: str = ""
    runtime_delegation_kid: str = "runtime-delegation-v1"
    runtime_delegation_issuer: str = "platform-api"
    runtime_delegation_audience: str = "runtime-service"
    runtime_delegation_ttl_seconds: int = Field(default=60, ge=10, le=300)
    runtime_completion_key_id: str = ""
    runtime_completion_secret: str = ""
    runtime_completion_clock_skew_seconds: int = Field(default=30, ge=1, le=300)
    runtime_completion_enabled: bool = False
    runtime_completion_verification_keys: dict[str, str] = Field(default_factory=dict)
    model_config_master_key: str | None = None
    runtime_model_config_secret: str | None = None
    suggestions_enabled: bool = True
    suggestions_max: int = Field(default=3, ge=1, le=5)
    suggestions_timeout_seconds: float = Field(default=8.0, gt=0, le=30)
    title_timeout_seconds: float = Field(default=8.0, gt=0, le=30)
    title_auto_enabled: bool = False
    knowledge_mcp_bindings: dict[str, str] = Field(
        default_factory=dict, validation_alias="PLATFORM_KNOWLEDGE_MCP_BINDINGS_JSON"
    )
    knowledge_connections: dict[str, KnowledgeConnection] = Field(
        default_factory=dict, validation_alias="PLATFORM_API_KNOWLEDGE_CONNECTIONS_JSON"
    )
    knowledge_upload_enabled: bool = False
    knowledge_key_id: str = "knowledge-v1"
    knowledge_secret: str = Field(default="", repr=False)
    knowledge_gateway_base_url: str = Field(
        default="http://152.136.27.196:8000",
        validation_alias="PLATFORM_API_KNOWLEDGE_GATEWAY_BASE_URL",
    )

    platform_db_enabled: bool = False
    platform_db_auto_create: bool = False
    database_url: str | None = None
    observability_metrics_top_paths_limit: int = Field(default=10, ge=1, le=50)
    loki_url: str = Field(default="http://127.0.0.1:3100")
    loki_timeout_seconds: float = Field(default=3.0, gt=0, le=30)

    auth_required: bool = True
    jwt_access_secret: str = "change-me-access-secret-at-least-32-bytes"
    jwt_refresh_secret: str = "change-me-refresh-secret-at-least-32-bytes"
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "platform-api"
    jwt_audience: str = "platform-control-plane"
    jwt_access_kid: str = "access-v1"
    jwt_refresh_kid: str = "refresh-v1"
    jwt_access_verification_keys: dict[str, str] = Field(default_factory=dict)
    jwt_refresh_verification_keys: dict[str, str] = Field(default_factory=dict)
    jwt_access_ttl_seconds: int = Field(default=1800, ge=60)
    jwt_refresh_ttl_seconds: int = Field(default=7 * 24 * 3600, ge=300)
    oidc_enabled: bool = False
    oidc_issuer_url: str | None = None
    oidc_client_id: str | None = None
    service_accounts_enabled: bool = True
    service_account_api_key_header: str = "x-platform-api-key"
    service_account_token_default_ttl_days: int = Field(default=90, ge=1, le=3650)

    bootstrap_admin_enabled: bool = True
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = "admin123456"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PLATFORM_API_",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("knowledge_mcp_bindings")
    @classmethod
    def validate_knowledge_bindings(cls, value: dict[str, str]) -> dict[str, str]:
        if len(set(value.values())) != len(value):
            raise ValueError("knowledge resources must belong to exactly one project")
        for scope, resource in value.items():
            parts = scope.split(":")
            if (
                len(parts) != 2
                or (parts[0] != "__default" and str(UUID(parts[0])) != parts[0])
                or str(UUID(parts[-1])) != parts[-1]
            ):
                raise ValueError(
                    "knowledge scope must be tenant UUID (or __default):project UUID"
                )
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", resource):
                raise ValueError("invalid knowledge resource ID")
        return value

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
    def validate_security_guards(self) -> Settings:
        normalized_env = self.app_env.lower()
        if normalized_env not in {"local", "dev", "staging", "prod", "production"}:
            raise ValueError("app_env must be one of local/dev/staging/prod/production")

        is_production = normalized_env in {"prod", "production"}
        for resource, connection in self.knowledge_connections.items():
            scope = connection.scope
            if (
                self.knowledge_mcp_bindings.get(
                    f"{scope['tenant_id']}:{scope['project_id']}"
                )
                != resource
            ):
                raise ValueError("knowledge connections must match trusted bindings")
        if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", self.knowledge_key_id):
            raise ValueError("invalid knowledge key ID")
        if self.knowledge_secret and (
            len(self.knowledge_secret.encode()) < 32
            or self.knowledge_secret
            in {
                self.runtime_delegation_secret,
                self.runtime_completion_secret,
                self.jwt_access_secret,
                self.jwt_refresh_secret,
            }
        ):
            raise ValueError(
                "knowledge requires a separate secret of at least 32 bytes"
            )
        if self.knowledge_upload_enabled and not self.knowledge_secret:
            raise ValueError("knowledge upload requires its dedicated secret")
        if self.platform_db_enabled and not self.database_url:
            raise ValueError(
                "PLATFORM_API_DATABASE_URL is required when platform_db_enabled=true"
            )
        if self.oidc_enabled and (not self.oidc_issuer_url or not self.oidc_client_id):
            raise ValueError(
                "oidc_issuer_url and oidc_client_id are required when oidc_enabled=true"
            )
        if self.jwt_algorithm not in {"HS256", "HS384", "HS512"}:
            raise ValueError("jwt_algorithm must be one of HS256/HS384/HS512")
        if (
            self.runtime_delegation_secret
            and len(self.runtime_delegation_secret.encode("utf-8")) < 32
        ):
            raise ValueError("runtime_delegation_secret must be at least 32 bytes")
        completion_keys = {**self.runtime_completion_verification_keys}
        if self.runtime_completion_secret:
            completion_keys[self.runtime_completion_key_id] = (
                self.runtime_completion_secret
            )
        if any(
            not key
            or not key.isascii()
            or len(key) > 128
            or not all(c.isalnum() or c in "_.-" for c in key)
            or len(secret.encode()) < 32
            for key, secret in completion_keys.items()
        ):
            raise ValueError(
                "runtime completion keys require an ID and at least 32 secret bytes"
            )
        if self.runtime_completion_enabled and not completion_keys:
            raise ValueError(
                "runtime completion must have verification keys when enabled"
            )
        if is_production:
            if self.api_docs_enabled:
                raise ValueError("API docs must be disabled in production")
            if self.bootstrap_admin_enabled:
                raise ValueError("Bootstrap admin must be disabled in production")
            if self.jwt_access_secret == "change-me-access-secret-at-least-32-bytes":
                raise ValueError("JWT access secret must be overridden in production")
            if self.jwt_refresh_secret == "change-me-refresh-secret-at-least-32-bytes":
                raise ValueError("JWT refresh secret must be overridden in production")
            if not self.runtime_delegation_secret:
                raise ValueError(
                    "Runtime delegation secret must be configured in production"
                )
        return self


def load_settings() -> Settings:
    return Settings()
