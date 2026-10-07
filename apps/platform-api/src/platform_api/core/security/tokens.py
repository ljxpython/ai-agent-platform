from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from platform_api.config import Settings


class InvalidTokenError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _encode(
    payload: dict[str, Any], *, secret: str, kid: str, settings: Settings
) -> str:
    return jwt.encode(
        payload,
        secret,
        algorithm=settings.jwt_algorithm,
        headers={"kid": kid, "typ": "JWT"},
    )


def _decode(
    token: str,
    *,
    expected_type: str,
    active_kid: str,
    active_secret: str,
    verification_keys: dict[str, str],
    settings: Settings,
) -> dict[str, Any]:
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise InvalidTokenError("missing token kid")
        keys = {**verification_keys, active_kid: active_secret}
        secret = keys.get(kid)
        if not secret:
            raise InvalidTokenError("unknown token kid")
        payload = jwt.decode(
            token,
            secret,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["exp", "nbf", "sub", "jti", "type"]},
        )
    except InvalidTokenError:
        raise
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("token validation failed") from exc
    if payload.get("type") != expected_type:
        raise InvalidTokenError(f"invalid {expected_type} token type")
    if not isinstance(payload.get("sub"), str) or not payload["sub"]:
        raise InvalidTokenError("invalid token subject")
    if not isinstance(payload.get("jti"), str) or not payload["jti"]:
        raise InvalidTokenError("invalid token id")
    return payload


def create_access_token(*, user_id: str, username: str, settings: Settings) -> str:
    now = _now()
    payload: dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "type": "access",
        "jti": uuid.uuid4().hex,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(
            (now + timedelta(seconds=settings.jwt_access_ttl_seconds)).timestamp()
        ),
    }
    return _encode(
        payload,
        secret=settings.jwt_access_secret,
        kid=settings.jwt_access_kid,
        settings=settings,
    )


def create_refresh_token(
    *,
    user_id: str,
    username: str,
    settings: Settings,
) -> tuple[str, str]:
    now = _now()
    token_id = uuid.uuid4().hex
    payload: dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "type": "refresh",
        "jti": token_id,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(
            (now + timedelta(seconds=settings.jwt_refresh_ttl_seconds)).timestamp()
        ),
    }
    return (
        _encode(
            payload,
            secret=settings.jwt_refresh_secret,
            kid=settings.jwt_refresh_kid,
            settings=settings,
        ),
        token_id,
    )


def create_runtime_delegation_token(
    *,
    subject: str,
    tenant_id: str,
    project_id: str,
    role: str,
    permissions: list[str] | tuple[str, ...],
    policy_version: str,
    allowed_model_ids: Sequence[str],
    tool_overrides: Mapping[str, bool],
    tool_policy_version: str,
    scope: Mapping[str, str | None],
    settings: Settings,
    context_hash: str | None = None,
    request_id: str | None = None,
    platform_trace_id: str | None = None,
    credential_id: str | None = None,
) -> str:
    secret = settings.runtime_delegation_secret
    if len(secret.encode("utf-8")) < 32:
        raise ValueError("runtime delegation secret must be at least 32 bytes")
    if (
        not isinstance(policy_version, str)
        or not policy_version.strip()
        or len(policy_version.strip()) > 100_000
    ):
        raise ValueError("runtime delegation policy_version must not be empty")
    model_ids = _runtime_names(allowed_model_ids, "allowed_model_ids")
    if not model_ids:
        raise ValueError("runtime delegation allowed_model_ids must not be empty")
    if (
        not isinstance(tool_overrides, dict)
        or len(tool_overrides) > 128
        or any(v is not False for v in tool_overrides.values())
    ):
        raise ValueError("tool_overrides must contain only false values")
    _runtime_names(list(tool_overrides), "tool_overrides")
    if len(json.dumps(tool_overrides, separators=(",", ":")).encode()) > 4096:
        raise ValueError("tool_overrides exceeds token budget")
    if (
        not isinstance(tool_policy_version, str)
        or not tool_policy_version.strip()
        or len(tool_policy_version) > 100_000
    ):
        raise ValueError("tool_policy_version is required")
    if not isinstance(scope, Mapping):
        raise ValueError("runtime delegation scope must be an object")
    scope_keys = {"tenant_id", "project_id", "assistant_id", "thread_id", "operation"}
    if (
        set(scope) - scope_keys
        or not scope.get("tenant_id")
        or not scope.get("project_id")
    ):
        raise ValueError(
            "runtime delegation scope must contain tenant_id and project_id"
        )
    normalized_scope = {}
    for key, value in scope.items():
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"runtime delegation scope {key} is invalid")
        normalized_scope[key] = value.strip()
    operation = normalized_scope.get("operation")
    if operation not in {
        "read",
        "cron-read",
        "cron-write",
        "thread-create",
        "thread-reconcile",
        "run-create",
        "thread-edit",
        "thread-delete",
        "run-cancel",
        "run-delete",
        "message-enqueue",
        "message-read",
        "image-upload",
        "image-read",
        "workspace-file-upload",
        "workspace-file-read",
        "workspace-fork",
        "terminal-read",
        "terminal-write",
        "dear-skills-read",
        "dear-skills-write",
        "dear-memory-read",
        "dear-memory-write",
        "dear-governance-read",
        "dear-governance-write",
        "suggestions-generate",
    }:
        raise ValueError("runtime delegation scope operation is unsupported")
    if operation not in {
        "read",
        "cron-read",
        "cron-write",
        "thread-create",
        "thread-reconcile",
        "thread-edit",
        "thread-delete",
    } and not normalized_scope.get("assistant_id"):
        raise ValueError("runtime delegation execution requires assistant_id")
    if (
        normalized_scope.get("tenant_id") != tenant_id
        or normalized_scope.get("project_id") != project_id
    ):
        raise ValueError("runtime delegation scope does not match token claims")
    if context_hash is None:
        context_hash = empty_runtime_context_hash()
    if (
        not isinstance(context_hash, str)
        or len(context_hash) != 71
        or not context_hash.startswith("sha256:")
        or any(char not in "0123456789abcdef" for char in context_hash[7:])
    ):
        raise ValueError("runtime delegation context_hash is invalid")

    required_values = {
        "subject": subject,
        "tenant_id": tenant_id,
        "project_id": project_id,
        "role": role,
        "kid": settings.runtime_delegation_kid,
        "issuer": settings.runtime_delegation_issuer,
        "audience": settings.runtime_delegation_audience,
    }
    missing = [
        name
        for name, value in required_values.items()
        if not isinstance(value, str) or not value.strip()
    ]
    if missing:
        raise ValueError(
            "runtime delegation fields must not be empty: " + ", ".join(missing)
        )
    for name in (subject, tenant_id, project_id, role):
        _runtime_names([name], "principal")
    if not isinstance(permissions, (list, tuple)) or any(
        not isinstance(item, str) for item in permissions
    ):
        raise ValueError("runtime delegation permissions must be an array of strings")
    normalized_permissions = sorted(
        {item.strip() for item in permissions if item.strip()}
    )
    _runtime_names(normalized_permissions, "permissions")
    if subject.startswith("service-account:") and credential_id is None:
        raise ValueError("runtime delegation service account requires credential_id")

    now = _now()
    payload: dict[str, Any] = {
        "sub": subject,
        "tenant_id": tenant_id,
        "project_id": project_id,
        "role": role,
        "permissions": normalized_permissions,
        "policy_version": policy_version.strip(),
        "allowed_model_ids": model_ids,
        "delegation_version": 2,
        "tool_overrides": dict(sorted(tool_overrides.items())),
        "tool_policy_version": tool_policy_version,
        "type": "runtime_delegation",
        "jti": uuid.uuid4().hex,
        "iss": settings.runtime_delegation_issuer,
        "aud": settings.runtime_delegation_audience,
        "scope": normalized_scope,
        "context_hash": context_hash,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int(
            (
                now + timedelta(seconds=settings.runtime_delegation_ttl_seconds)
            ).timestamp()
        ),
    }
    for name, value in (
        ("request_id", request_id),
        ("platform_trace_id", platform_trace_id),
    ):
        if value is not None:
            if not isinstance(value, str) or not value.strip() or len(value) > 256:
                raise ValueError(f"runtime delegation {name} is invalid")
            payload[name] = value.strip()
    if credential_id is not None:
        if not subject.startswith("service-account:"):
            raise ValueError(
                "runtime delegation credential_id requires a service account"
            )
        try:
            if not isinstance(credential_id, str):
                raise ValueError("invalid credential_id type")
            uuid.UUID(credential_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("runtime delegation credential_id is invalid") from exc
        payload["credential_id"] = credential_id
    return jwt.encode(
        payload,
        secret,
        algorithm="HS256",
        headers={"kid": settings.runtime_delegation_kid, "typ": "JWT"},
    )


def _runtime_names(values: Sequence[str], field: str) -> list[str]:
    if not isinstance(values, (list, tuple)):
        raise ValueError(f"runtime delegation {field} must be an array")
    normalized = []
    for value in values:
        if (
            not isinstance(value, str)
            or not value.strip()
            or value != value.strip()
            or len(value) > 128
        ):
            raise ValueError(f"runtime delegation {field} contains an invalid name")
        if not value.isascii() or any(
            char.isspace() or not char.isprintable() for char in value
        ):
            raise ValueError(f"runtime delegation {field} contains an invalid name")
        normalized.append(value)
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"runtime delegation {field} contains duplicate names")
    return sorted(normalized)


def empty_runtime_context_hash() -> str:
    payload = {
        "schema": "runtime-context/v5",
        "model_id": None,
        "temperature": None,
        "max_tokens": None,
        "top_p": None,
        "execution_mode": None,
        "access_policy": None,
        "offload_conversation": False,
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    return _decode(
        token,
        expected_type="access",
        active_kid=settings.jwt_access_kid,
        active_secret=settings.jwt_access_secret,
        verification_keys=settings.jwt_access_verification_keys,
        settings=settings,
    )


def decode_refresh_token(token: str, settings: Settings) -> dict[str, Any]:
    return _decode(
        token,
        expected_type="refresh",
        active_kid=settings.jwt_refresh_kid,
        active_secret=settings.jwt_refresh_secret,
        verification_keys=settings.jwt_refresh_verification_keys,
        settings=settings,
    )
