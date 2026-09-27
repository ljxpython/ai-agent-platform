from __future__ import annotations

import asyncio
import time
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from langgraph_sdk import Auth

from runtime_service import webapp
from runtime_service.auth.platform import authenticate
from runtime_service.runtime.resolver import runtime_context_hash

SECRET = "message-read-pair-test-secret-at-least-32-bytes"


def _authorization(
    operation: str,
    *,
    subject: str = "user-1",
    tenant_id: str = "tenant-1",
    project_id: str = "project-1",
    thread_id: str | None = None,
    credential_id: str | None = None,
    expired: bool = False,
) -> str:
    now = int(time.time())
    claims = {
        "type": "runtime_delegation",
        "delegation_version": 2,
        "sub": subject,
        "tenant_id": tenant_id,
        "project_id": project_id,
        "role": "project_editor",
        "permissions": [],
        "policy_version": "policy-1",
        "allowed_model_ids": ["model-1"],
        "tool_overrides": {},
        "tool_policy_version": "tools-1",
        "iat": now - 120 if expired else now,
        "exp": now - 60 if expired else now + 60,
        "iss": "runtime-test",
        "aud": "runtime-service",
        "scope": {
            "tenant_id": tenant_id,
            "project_id": project_id,
            "operation": operation,
            **({"assistant_id": "reference_agent"} if operation != "read" else {}),
            **({"thread_id": thread_id} if thread_id else {}),
        },
        "context_hash": runtime_context_hash(None),
    }
    if credential_id:
        claims["credential_id"] = credential_id
    return "Bearer " + jwt.encode(claims, SECRET, algorithm="HS256")


@pytest.fixture(autouse=True)
def _runtime_auth_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", "runtime-test")
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_AUDIENCE", "runtime-service")


def _check(message: str, read: str | None, *, thread_id: str = "thread-1") -> str:
    async def verify() -> str:
        facts = await authenticate(message)
        return await webapp._verified_run_read_authorization(facts, read, thread_id)

    return asyncio.run(verify())


def test_matching_read_delegation_is_forwarded_unchanged() -> None:
    read = _authorization("read", thread_id="thread-1")
    assert _check(_authorization("message-enqueue", thread_id="thread-1"), read) == read
    unbound_read = _authorization("read")
    assert (
        _check(_authorization("message-read", thread_id="thread-1"), unbound_read)
        == unbound_read
    )


@pytest.mark.parametrize(
    "read",
    [
        None,
        _authorization("read", expired=True),
        _authorization("message-read", thread_id="thread-1"),
        _authorization("read", subject="user-2"),
        _authorization("read", tenant_id="tenant-2"),
        _authorization("read", project_id="project-2"),
        _authorization("read", thread_id="other-thread"),
    ],
    ids=[
        "missing",
        "expired",
        "wrong-operation",
        "wrong-user",
        "wrong-tenant",
        "wrong-project",
        "wrong-thread",
    ],
)
def test_missing_or_mismatched_read_delegation_is_rejected(read: str | None) -> None:
    with pytest.raises((Auth.exceptions.HTTPException, HTTPException)) as error:
        _check(_authorization("message-enqueue", thread_id="thread-1"), read)
    assert error.value.status_code in {401, 403}


def test_service_account_read_delegation_requires_same_credential() -> None:
    subject = f"service-account:{uuid4()}"
    credential_id = str(uuid4())
    message = _authorization(
        "message-enqueue",
        subject=subject,
        thread_id="thread-1",
        credential_id=credential_id,
    )
    matching_read = _authorization("read", subject=subject, credential_id=credential_id)
    assert _check(message, matching_read) == matching_read
    read = _authorization(
        "read",
        subject=subject,
        thread_id="thread-1",
        credential_id=str(uuid4()),
    )
    with pytest.raises(HTTPException) as error:
        _check(message, read)
    assert error.value.status_code == 403
