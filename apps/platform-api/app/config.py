from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    langgraph_upstream_url: str
    langgraph_upstream_api_key: str | None
    interaction_data_service_url: str | None
    interaction_data_service_token: str | None
    interaction_data_service_timeout_seconds: float
    proxy_timeout_seconds: float
    proxy_cors_allow_origins: list[str]
    proxy_upstream_retries: int
    proxy_log_level: str
    platform_db_enabled: bool
    platform_db_auto_create: bool
    database_url: str | None
    auth_required: bool
    langgraph_auth_required: bool
    langgraph_scope_guard_enabled: bool
    jwt_access_secret: str
    jwt_refresh_secret: str
    jwt_access_ttl_seconds: int
    jwt_refresh_ttl_seconds: int
    bootstrap_admin_username: str
    bootstrap_admin_password: str
    logs_dir: str
    backend_log_file: str
    backend_log_max_bytes: int
    backend_log_backup_count: int
    api_docs_enabled: bool
    langgraph_graph_source_root: str | None


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    return Settings(
        langgraph_upstream_url=os.getenv(
            "LANGGRAPH_UPSTREAM_URL", "http://127.0.0.1:8123"
        ),
        langgraph_upstream_api_key=os.getenv("LANGGRAPH_UPSTREAM_API_KEY") or None,
        interaction_data_service_url=os.getenv("INTERACTION_DATA_SERVICE_URL")
        or "http://127.0.0.1:8081",
        interaction_data_service_token=os.getenv("INTERACTION_DATA_SERVICE_TOKEN")
        or None,
        interaction_data_service_timeout_seconds=float(
            os.getenv("INTERACTION_DATA_SERVICE_TIMEOUT_SECONDS", "30")
        ),
        proxy_timeout_seconds=float(os.getenv("PROXY_TIMEOUT_SECONDS", "300")),
        proxy_cors_allow_origins=os.getenv("PROXY_CORS_ALLOW_ORIGINS", "*").split(","),
        proxy_upstream_retries=max(0, int(os.getenv("PROXY_UPSTREAM_RETRIES", "1"))),
        proxy_log_level=os.getenv("PROXY_LOG_LEVEL", "INFO").upper(),
        platform_db_enabled=_as_bool(os.getenv("PLATFORM_DB_ENABLED", "false")),
        platform_db_auto_create=_as_bool(os.getenv("PLATFORM_DB_AUTO_CREATE", "false")),
        database_url=os.getenv("DATABASE_URL") or None,
        auth_required=_as_bool(os.getenv("AUTH_REQUIRED", "true"), True),
        langgraph_auth_required=_as_bool(
            os.getenv("LANGGRAPH_AUTH_REQUIRED", "false"), False
        ),
        langgraph_scope_guard_enabled=_as_bool(
            os.getenv("LANGGRAPH_SCOPE_GUARD_ENABLED", "false"), False
        ),
        jwt_access_secret=os.getenv("JWT_ACCESS_SECRET", "change-me-access-secret"),
        jwt_refresh_secret=os.getenv("JWT_REFRESH_SECRET", "change-me-refresh-secret"),
        jwt_access_ttl_seconds=max(
            60, int(os.getenv("JWT_ACCESS_TTL_SECONDS", "1800"))
        ),
        jwt_refresh_ttl_seconds=max(
            300, int(os.getenv("JWT_REFRESH_TTL_SECONDS", str(7 * 24 * 3600)))
        ),
        bootstrap_admin_username=os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin").strip()
        or "admin",
        bootstrap_admin_password=os.getenv(
            "BOOTSTRAP_ADMIN_PASSWORD", "admin123456"
        ).strip()
        or "admin123456",
        logs_dir=os.getenv("LOGS_DIR", "logs"),
        backend_log_file=os.getenv("BACKEND_LOG_FILE", "backend.log"),
        backend_log_max_bytes=max(
            1024 * 1024, int(os.getenv("BACKEND_LOG_MAX_BYTES", str(10 * 1024 * 1024)))
        ),
        backend_log_backup_count=max(
            1, int(os.getenv("BACKEND_LOG_BACKUP_COUNT", "5"))
        ),
        api_docs_enabled=_as_bool(os.getenv("API_DOCS_ENABLED", "false")),
        langgraph_graph_source_root=os.getenv("LANGGRAPH_GRAPH_SOURCE_ROOT") or None,
    )
