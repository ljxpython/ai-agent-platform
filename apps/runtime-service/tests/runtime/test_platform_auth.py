from __future__ import annotations

import asyncio
import time

import jwt
import pytest
from langgraph_sdk import Auth

from runtime_service.auth.platform import authenticate
from runtime_service.runtime.resolver import runtime_context_hash

SECRET = "r1-test-secret-with-at-least-32-bytes"


def _token(*, request_id: str | None = None, platform_trace_id: str | None = None) -> str:
    now = int(time.time())
    claims = {
            "type": "runtime_delegation", "delegation_version": 2,
            "sub": "user-a",
            "tenant_id": "tenant-a",
            "project_id": "project-a",
            "role": "developer",
            "permissions": ["runtime.tool.read"],
            "policy_version": "policy-1",
            "allowed_model_ids": ["deepseek:deepseek-chat"],
            "tool_overrides": {}, "tool_policy_version": "test-tools-v2",
            "iat": now,
            "exp": now + 60,
            "iss": "runtime-test",
            "aud": "runtime-service",
            "scope": {"tenant_id": "tenant-a", "project_id": "project-a", "operation": "read"},
            "context_hash": runtime_context_hash(None),
    }
    if request_id is not None:
        claims["request_id"] = request_id
    if platform_trace_id is not None:
        claims["platform_trace_id"] = platform_trace_id
    return jwt.encode(claims, SECRET, algorithm="HS256")


def test_platform_auth_returns_runtime_facts_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-test")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")
    user = asyncio.run(authenticate(authorization=f"Bearer {_token()}"))

    assert user["identity"] == "user-a"
    assert user["tenant_id"] == "tenant-a"
    assert user["project_id"] == "project-a"
    assert user["role"] == "developer"
    assert user["policy_version"] == "policy-1"
    assert user["allowed_model_ids"] == ["deepseek:deepseek-chat"]
    assert user["tool_overrides"] == {}
    assert user["tool_policy_version"] == "test-tools-v2"
    assert user["runtime_principal"]["tenant_id"] == "tenant-a"
    assert user["runtime_policy"]["version"] == "policy-1"
    assert user["runtime_context_hash"].startswith("sha256:")
    assert "Bearer" not in str(user)


def test_platform_auth_rejects_missing_or_invalid_authorization(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-test")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")
    with pytest.raises(Auth.exceptions.HTTPException) as missing:
        asyncio.run(authenticate(authorization=None))
    assert missing.value.status_code == 401

    with pytest.raises(Auth.exceptions.HTTPException) as invalid:
        asyncio.run(authenticate(authorization="Bearer invalid"))
    assert invalid.value.status_code == 401


def test_platform_auth_preserves_signed_trace_correlation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-test")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")

    user = asyncio.run(
        authenticate(
            authorization=(
                "Bearer "
                + _token(request_id="request-1", platform_trace_id="platform-trace-1")
            )
        )
    )

    assert user["request_id"] == "request-1"
    assert user["platform_trace_id"] == "platform-trace-1"


def test_platform_auth_requires_audience_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-test")
    monkeypatch.delenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", raising=False)

    with pytest.raises(Auth.exceptions.HTTPException) as error:
        asyncio.run(authenticate(authorization=f"Bearer {_token()}"))

    assert error.value.status_code == 500


@pytest.mark.parametrize("operation", ["dear-skills-read", "dear-skills-write", "dear-memory-read", "dear-memory-write", "message-enqueue", "terminal-write", "unknown"])
def test_skill_tokens_cannot_use_server_resources(operation):
    from types import SimpleNamespace
    from runtime_service.auth.platform import deny_image_scope_on_server_resources
    with pytest.raises(Auth.exceptions.HTTPException) as error:
        asyncio.run(deny_image_scope_on_server_resources(SimpleNamespace(user={"runtime_scope": {"operation": operation}}), {}))
    assert error.value.status_code == 403


def test_custom_scope_is_rejected_for_attribute_user():
    from types import SimpleNamespace
    from runtime_service.auth.platform import deny_image_scope_on_server_resources

    user = SimpleNamespace(runtime_scope={"operation": "workspace-file-read"})
    with pytest.raises(Auth.exceptions.HTTPException) as error:
        asyncio.run(deny_image_scope_on_server_resources(SimpleNamespace(user=user), {}))
    assert error.value.status_code == 403


def test_thread_auth_rechecks_signed_platform_acl(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from runtime_service.auth import platform

    monkeypatch.setenv("PLATFORM_THREAD_AUTHORIZATION_URL", "http://platform.test/api/runtime/internal/thread-authorization")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"allowed_thread_ids": ["thread-1"]})
    post = AsyncMock(return_value=response)

    class Client:
        def __init__(self, **kwargs):
            assert kwargs == {"timeout": 3.0}

        async def __aenter__(self):
            return SimpleNamespace(post=post)

        async def __aexit__(self, *args):
            return None

    monkeypatch.setattr(platform.httpx, "AsyncClient", Client)
    ctx = SimpleNamespace(
        user={"identity": "user-a", "project_id": "project-a", "runtime_scope": {"operation": "read"}},
        resource="threads", action="read",
    )
    asyncio.run(platform.deny_image_scope_on_server_resources(ctx, {"thread_id": "thread-1"}))

    kwargs = post.await_args.kwargs
    assert kwargs["json"] == {
        "action": "read", "project_id": "project-a", "user_id": "user-a", "thread_ids": ["thread-1"]
    }
    assert kwargs["headers"]["x-runtime-acl-signature"]


def test_thread_create_accepts_graphharbor_uuid_target(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    from uuid import uuid4
    from unittest.mock import AsyncMock
    from runtime_service.auth import platform

    thread_id = uuid4()
    monkeypatch.setenv("PLATFORM_THREAD_AUTHORIZATION_URL", "http://platform.test/acl")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"allowed_thread_ids": [str(thread_id)]})

    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return SimpleNamespace(post=AsyncMock(return_value=response))
        async def __aexit__(self, *args): return None

    monkeypatch.setattr(platform.httpx, "AsyncClient", Client)
    ctx = SimpleNamespace(
        user={"identity": "user-a", "project_id": "project-a", "runtime_scope": {"operation": "thread-create", "thread_id": str(thread_id)}},
        resource="threads", action="create",
    )
    asyncio.run(platform.deny_image_scope_on_server_resources(ctx, {"thread_id": thread_id}))


def test_only_the_delegated_assistant_is_readable() -> None:
    from types import SimpleNamespace
    from uuid import NAMESPACE_URL, uuid5
    from runtime_service.auth.platform import deny_image_scope_on_server_resources

    ctx = SimpleNamespace(
        user={"runtime_scope": {"operation": "read", "assistant_id": "assistant-a"}},
        resource="assistants", action="read",
    )
    asyncio.run(deny_image_scope_on_server_resources(ctx, {"assistant_id": "assistant-a"}))
    asyncio.run(deny_image_scope_on_server_resources(ctx, {"assistant_id": uuid5(NAMESPACE_URL, "assistant-a")}))
    with pytest.raises(Auth.exceptions.HTTPException) as error:
        asyncio.run(deny_image_scope_on_server_resources(ctx, {"assistant_id": "assistant-b"}))
    assert error.value.status_code == 403


@pytest.mark.parametrize("resource", ["crons", "store", "runs"])
def test_unsupported_server_resources_are_denied(resource: str) -> None:
    from types import SimpleNamespace
    from runtime_service.auth.platform import deny_image_scope_on_server_resources

    ctx = SimpleNamespace(
        user={"runtime_scope": {"operation": "read"}}, resource=resource, action="read"
    )
    with pytest.raises(Auth.exceptions.HTTPException) as error:
        asyncio.run(deny_image_scope_on_server_resources(ctx, {}))
    assert error.value.status_code == 403


@pytest.mark.parametrize("action", ["create_run", "update", "delete", "approve"])
def test_read_delegation_cannot_mutate_threads(action: str) -> None:
    from types import SimpleNamespace
    from runtime_service.auth.platform import deny_image_scope_on_server_resources

    ctx = SimpleNamespace(
        user={"runtime_scope": {"operation": "read"}}, resource="threads", action=action
    )
    with pytest.raises(Auth.exceptions.HTTPException) as error:
        asyncio.run(deny_image_scope_on_server_resources(ctx, {"thread_id": "thread-1"}))
    assert error.value.status_code == 403


def test_thread_auth_fails_closed_for_unbounded_or_denied_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from runtime_service.auth import platform

    monkeypatch.setenv("PLATFORM_THREAD_AUTHORIZATION_URL", "http://platform.test/acl")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    ctx = SimpleNamespace(
        user={"identity": "user-a", "project_id": "project-a", "runtime_scope": {"operation": "read"}},
        resource="threads", action="search",
    )
    with pytest.raises(Auth.exceptions.HTTPException) as missing:
        asyncio.run(platform.deny_image_scope_on_server_resources(ctx, {}))
    assert missing.value.status_code == 403

    response = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {"allowed_thread_ids": []})

    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return SimpleNamespace(post=AsyncMock(return_value=response))
        async def __aexit__(self, *args): return None

    monkeypatch.setattr(platform.httpx, "AsyncClient", Client)
    with pytest.raises(Auth.exceptions.HTTPException) as denied:
        asyncio.run(platform.deny_image_scope_on_server_resources(ctx, {"ids": ["thread-1"]}))
    assert denied.value.status_code == 403
