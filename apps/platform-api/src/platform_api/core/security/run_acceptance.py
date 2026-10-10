"""Stable, opaque receipt identities; never bind retries to a JWT jti."""

import hashlib
import json
import re
from uuid import UUID


def binding_hash(values):
    return hashlib.sha256(
        json.dumps(values, separators=(",", ":")).encode()
    ).hexdigest()


def receipt_binding(tenant_id, project_id, subject, credential_id=None):
    scope = binding_hash(
        ["platform:run-receipt-scope:v1", tenant_id, project_id, subject]
    )
    credential = binding_hash(
        [
            "platform:run-receipt-credential:v1",
            "service-account" if credential_id else "user",
            credential_id or subject,
        ]
    )
    return scope, credential


def validate_grant(value, *, subject, tenant_id, project_id, credential_id, scope):
    names = {
        "scope_id",
        "credential_id",
        "operation",
        "thread_id",
        "key_sha256",
        "request_digest",
    }
    if not isinstance(value, dict) or set(value) != names:
        raise ValueError("Invalid run acceptance grant")
    expected_scope, expected_credential = receipt_binding(
        tenant_id, project_id, subject, credential_id
    )
    operation = (
        "create"
        if scope.get("operation") == "run-create"
        else "read"
        if scope.get("operation") == "run-acceptance-read"
        else None
    )
    try:
        thread = str(UUID(value["thread_id"]))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Invalid run acceptance thread") from exc
    if (
        value["scope_id"] != expected_scope
        or value["credential_id"] != expected_credential
        or value["operation"] != operation
        or value["thread_id"] != scope.get("thread_id")
        or thread != value["thread_id"]
        or not isinstance(value["key_sha256"], str)
        or not re.fullmatch("[0-9a-f]{64}", value["key_sha256"])
        or not isinstance(value["request_digest"], str)
        or not re.fullmatch("sha256:[0-9a-f]{64}", value["request_digest"])
    ):
        raise ValueError(
            "Run acceptance grant does not match original identity and target"
        )
    return dict(value)
