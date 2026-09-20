from __future__ import annotations

import time

import jwt
import pytest

from runtime_service.runtime.auth import verify_delegation_claims, verify_delegation_token
from runtime_service.runtime import RuntimeContext
from runtime_service.runtime.resolver import runtime_context_hash
from runtime_service.runtime.errors import RuntimeAuthError

SECRET = "r1-test-secret-with-at-least-32-bytes"


def _token(**overrides: object) -> str:
    now = int(time.time())
    claims: dict[str, object] = {
        "type": "runtime_delegation", "delegation_version": 2,
        "sub": "user-a",
        "tenant_id": "tenant-a",
        "project_id": "project-a",
        "role": "developer",
        "permissions": ["runtime.read"],
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
    claims.update(overrides)
    return jwt.encode(claims, SECRET, algorithm="HS256")


def _verify(token: str, *, secret: str = SECRET) -> tuple[object, object]:
    return verify_delegation_token(
        token,
        secret=secret,
        issuer="runtime-test",
        audience="runtime-service",
    )


def test_valid_delegation_token_maps_principal_and_policy() -> None:
    principal, policy = _verify(_token())
    assert principal.user_id == "user-a"
    assert principal.tenant_id == "tenant-a"
    assert policy.version == "policy-1"
    assert policy.allowed_model_ids == ("deepseek:deepseek-chat",)


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"type": "other"}, "runtime.auth.invalid_claim"),
        ({"policy_tenant_id": "tenant-b"}, "runtime.auth.invalid_principal"),
        ({"allowed_model_ids": []}, "runtime.auth.invalid_claim"),
    ],
)
def test_invalid_claims_fail_closed(overrides: dict[str, object], expected: str) -> None:
    with pytest.raises(RuntimeAuthError) as error:
        _verify(_token(**overrides))
    assert error.value.code == expected


def test_bad_signature_and_expiry_are_not_retried_or_leaked() -> None:
    with pytest.raises(RuntimeAuthError) as signature:
        _verify(_token(), secret="wrong-secret-with-at-least-32-bytes")
    assert signature.value.code == "runtime.auth.invalid_token"
    assert "wrong-secret" not in str(signature.value)

    now = int(time.time())
    with pytest.raises(RuntimeAuthError) as expired:
        _verify(_token(iat=now - 120, exp=now - 1))
    assert expired.value.code == "runtime.auth.invalid_token"


def test_unknown_claim_is_rejected() -> None:
    with pytest.raises(RuntimeAuthError) as error:
        _verify(_token(unexpected="value"))
    assert error.value.code == "runtime.auth.invalid_claim"


def test_old_or_incomplete_tool_delegations_are_rejected():
    claims = jwt.decode(_token(), options={"verify_signature": False})
    for field in ("delegation_version", "tool_overrides", "tool_policy_version"):
        missing = {key: value for key, value in claims.items() if key != field}
        with pytest.raises(RuntimeAuthError):
            _verify(jwt.encode(missing, SECRET, algorithm="HS256"))
    for override in ({"delegation_version": 1}, {"delegation_version": True},
                     {"allowed_tool_names": ["read_reference"]}, {"tool_overrides": {"read_reference": 0}}):
        with pytest.raises(RuntimeAuthError):
            _verify(_token(**override))


@pytest.mark.parametrize(
    "overrides",
    [
        {"scope": {"operation": "read", "tenant_id": "tenant-b", "project_id": "project-a"}},
        {"scope": {"operation": "read", "tenant_id": "tenant-a", "project_id": "project-a", "thread_id": 1}},
        {"context_hash": "sha256:wrong"},
        {"scope": {"tenant_id": "tenant-a", "project_id": "project-a"}},
        {"scope": {"tenant_id": "tenant-a", "project_id": "project-a", "operation": "admin"}},
    ],
)
def test_scope_and_context_hash_claims_fail_closed(overrides: dict[str, object]) -> None:
    with pytest.raises(RuntimeAuthError):
        _verify(_token(**overrides))


def test_scope_and_context_are_checked_against_execution_inputs() -> None:
    token = _token(
        scope={
            "operation": "run-create",
            "tenant_id": "tenant-a",
            "project_id": "project-a",
            "assistant_id": "assistant-a",
            "thread_id": "thread-a",
        }
    )
    verified = verify_delegation_claims(
        token,
        secret=SECRET,
        issuer="runtime-test",
        audience="runtime-service",
        context=RuntimeContext(),
        expected_scope={
            "operation": "run-create",
            "tenant_id": "tenant-a",
            "project_id": "project-a",
            "assistant_id": "assistant-a",
            "thread_id": "thread-a",
        },
    )
    assert verified.scope.thread_id == "thread-a"

    with pytest.raises(RuntimeAuthError) as scope_error:
        verify_delegation_claims(
            token,
            secret=SECRET,
            issuer="runtime-test",
            audience="runtime-service",
            expected_scope={"thread_id": "other-thread"},
        )
    assert scope_error.value.code == "runtime.auth.invalid_principal"

    with pytest.raises(RuntimeAuthError) as context_error:
        verify_delegation_claims(
            token,
            secret=SECRET,
            issuer="runtime-test",
            audience="runtime-service",
            context=RuntimeContext(temperature=1),
        )
    assert context_error.value.code == "runtime.auth.context_hash_mismatch"


def test_scope_operation_is_preserved() -> None:
    token = _token(
        scope={
            "tenant_id": "tenant-a",
            "project_id": "project-a",
            "operation": "run-create",
            "assistant_id": "reference_agent",
        }
    )
    verified = verify_delegation_claims(
        token,
        secret=SECRET,
        issuer="runtime-test",
        audience="runtime-service",
    )
    assert verified.scope.operation == "run-create"
