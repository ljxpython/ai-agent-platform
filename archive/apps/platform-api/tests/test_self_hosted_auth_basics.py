from __future__ import annotations

from app.config import Settings
from app.security.password import hash_password, verify_password
from app.security.token import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
)


def _settings() -> Settings:
    return Settings(
        langgraph_upstream_url="http://127.0.0.1:8123",
        langgraph_upstream_api_key=None,
        interaction_data_service_url="http://127.0.0.1:8081",
        interaction_data_service_token=None,
        interaction_data_service_timeout_seconds=30,
        proxy_timeout_seconds=30,
        proxy_cors_allow_origins=["*"],
        proxy_upstream_retries=0,
        proxy_log_level="INFO",
        platform_db_enabled=True,
        platform_db_auto_create=False,
        database_url="postgresql+psycopg://x:y@localhost:5432/z",
        auth_required=True,
        langgraph_auth_required=False,
        langgraph_scope_guard_enabled=False,
        jwt_access_secret="test-access",
        jwt_refresh_secret="test-refresh",
        jwt_access_ttl_seconds=60,
        jwt_refresh_ttl_seconds=3600,
        bootstrap_admin_username="admin",
        bootstrap_admin_password="admin123456",
        logs_dir="logs",
        backend_log_file="backend.log",
        backend_log_max_bytes=1024,
        backend_log_backup_count=1,
        api_docs_enabled=False,
        langgraph_graph_source_root=None,
    )


def test_password_hash_and_verify() -> None:
    raw = "my-secret-password"
    digest = hash_password(raw)
    assert digest != raw
    assert verify_password(raw, digest)
    assert not verify_password("wrong-password", digest)


def test_access_token_roundtrip() -> None:
    settings = _settings()
    token = create_access_token(user_id="u-1", username="alice", settings=settings)
    payload = decode_access_token(token, settings)
    assert payload["sub"] == "u-1"
    assert payload["username"] == "alice"
    assert payload["type"] == "access"


def test_refresh_token_roundtrip() -> None:
    settings = _settings()
    token, token_id = create_refresh_token(
        user_id="u-2", username="bob", settings=settings
    )
    payload = decode_refresh_token(token, settings)
    assert payload["sub"] == "u-2"
    assert payload["username"] == "bob"
    assert payload["type"] == "refresh"
    assert payload["jti"] == token_id


def test_access_decode_rejects_refresh_token() -> None:
    settings = _settings()
    refresh_token, _ = create_refresh_token(
        user_id="u-3", username="charlie", settings=settings
    )
    try:
        decode_access_token(refresh_token, settings)
    except InvalidTokenError:
        return
    raise AssertionError("refresh token should not decode as access token")
