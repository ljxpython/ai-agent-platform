from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    service_name: str
    service_version: str
    service_cors_allow_origins: list[str]
    api_docs_enabled: bool
    interaction_db_enabled: bool
    interaction_db_auto_create: bool
    database_url: str | None


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_settings() -> Settings:
    return Settings(
        service_name=os.getenv("SERVICE_NAME", "interaction-data-service").strip()
        or "interaction-data-service",
        service_version=os.getenv("SERVICE_VERSION", "0.1.0").strip() or "0.1.0",
        service_cors_allow_origins=os.getenv("SERVICE_CORS_ALLOW_ORIGINS", "*").split(","),
        api_docs_enabled=_as_bool(os.getenv("API_DOCS_ENABLED", "false")),
        interaction_db_enabled=_as_bool(os.getenv("INTERACTION_DB_ENABLED", "false")),
        interaction_db_auto_create=_as_bool(
            os.getenv("INTERACTION_DB_AUTO_CREATE", "false")
        ),
        database_url=os.getenv("DATABASE_URL") or None,
    )
