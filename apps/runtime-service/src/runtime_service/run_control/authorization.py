"""Short native delegations minted only by the trusted Runtime reconciler."""

import hashlib
import hmac
import json
import os
import time
from uuid import UUID, uuid4

import jwt

from runtime_service.auth.acl_client import post_acl


def cancellation_context_hash(cancellation_id):
    value = str(UUID(str(cancellation_id)))
    return (
        "sha256:"
        + hashlib.sha256(("runtime-cancellation/v1:" + value).encode()).hexdigest()
    )


def _setting(name):
    value = os.getenv(name)
    if not value:
        raise ValueError("stop_authorization_unconfigured")
    return value


def native_headers(row, operation):
    facts = row["auth_facts"]
    stamp = int(time.time())
    payload = {
        "type": "runtime_delegation",
        "sub": facts["identity"],
        "tenant_id": facts["tenant_id"],
        "project_id": facts["project_id"],
        "role": facts["role"],
        "permissions": [],
        "policy_version": "stop-control-v1",
        "allowed_model_ids": ["platform:no-enabled-model"],
        "delegation_version": 2,
        "tool_overrides": {},
        "tool_policy_version": "stop-control-v1",
        "scope": {**facts["runtime_scope"], "operation": operation},
        "context_hash": cancellation_context_hash(row["stop_id"]),
        "iss": _setting("PLATFORM_RUNTIME_DELEGATION_ISSUER"),
        "aud": _setting("PLATFORM_RUNTIME_DELEGATION_AUDIENCE"),
        "iat": stamp,
        "nbf": stamp,
        "exp": stamp + 30,
        "jti": uuid4().hex,
    }
    if facts.get("runtime_credential_id"):
        payload["credential_id"] = facts["runtime_credential_id"]
    token = jwt.encode(
        payload, _setting("PLATFORM_RUNTIME_DELEGATION_SECRET"), algorithm="HS256"
    )
    return {"Authorization": "Bearer " + token}


async def stop_callback(row, *, authorize=False):
    facts = row["auth_facts"]
    payload = {
        "stop_id": str(row["stop_id"]),
        "tenant_id": row["tenant_id"],
        "project_id": row["project_id"],
        "thread_id": row["thread_id"],
        "owner_id": facts["identity"],
        "credential_id": facts.get("runtime_credential_id"),
        "authorize": authorize,
        "phase": row["phase"],
        "request_id": facts.get("request_id"),
        "platform_trace_id": facts.get("platform_trace_id"),
        "target_count": row["engine_receipt"]["target_count"]
        if row["engine_receipt"]
        else None,
    }
    endpoint = (
        _setting("PLATFORM_THREAD_AUTHORIZATION_URL").removesuffix(
            "/thread-authorization"
        )
        + "/stop-authorization"
    )
    stamp = str(int(time.time()))
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    signature = hmac.new(
        _setting("PLATFORM_RUNTIME_DELEGATION_SECRET").encode(),
        f"{stamp}\nstop-authorization\n{canonical}".encode(),
        hashlib.sha256,
    ).hexdigest()
    response = await post_acl(
        endpoint,
        payload,
        {"x-runtime-acl-timestamp": stamp, "x-runtime-acl-signature": signature},
    )
    response.raise_for_status()
    result = response.json()
    if not isinstance(result, dict) or type(result.get("allowed")) is not bool:
        raise ValueError("invalid_stop_authorization")
    return result["allowed"]
