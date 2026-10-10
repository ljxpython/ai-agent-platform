"""Validate acceptance facts and reconstruct only the original fixed read grant."""

import hashlib
from datetime import datetime
from uuid import UUID

from platform_api.core.errors import UpstreamServiceError
from platform_api.core.security.run_acceptance import receipt_binding
from platform_api.core.security.tokens import create_runtime_delegation_token


def grant_for(record, operation="read"):
    if not all(
        (
            record.upstream_idempotency_key,
            record.upstream_body,
            record.upstream_request_digest,
            record.upstream_receipt_scope_id,
            record.upstream_receipt_credential_id,
            record.upstream_auth_snapshot,
        )
    ):
        raise ValueError("Original acceptance binding unavailable")
    snapshot = record.upstream_auth_snapshot
    scope, credential = receipt_binding(
        snapshot["tenant_id"],
        snapshot["project_id"],
        snapshot["subject"],
        snapshot.get("credential_id"),
    )
    if (
        scope != record.upstream_receipt_scope_id
        or credential != record.upstream_receipt_credential_id
        or snapshot["project_id"] != record.project_id
        or snapshot["scope"]["thread_id"] != record.thread_id
        or snapshot["scope"]["assistant_id"] != record.agent_key
        or record.requested_by != (snapshot.get("credential_id") or snapshot["subject"])
        or "sha256:" + hashlib.sha256(record.upstream_body).hexdigest()
        != record.upstream_request_digest
    ):
        raise ValueError("Original acceptance facts do not match")
    return {
        "scope_id": scope,
        "credential_id": credential,
        "operation": operation,
        "thread_id": str(UUID(record.thread_id)),
        "key_sha256": hashlib.sha256(
            record.upstream_idempotency_key.encode()
        ).hexdigest(),
        "request_digest": record.upstream_request_digest,
    }


def receipt_headers(record, settings):
    grant = grant_for(record)
    snapshot = {
        **record.upstream_auth_snapshot,
        "scope": {
            **record.upstream_auth_snapshot["scope"],
            "operation": "run-acceptance-read",
        },
    }
    token = create_runtime_delegation_token(
        **snapshot, settings=settings, run_acceptance=grant
    )
    return {"authorization": "Bearer " + token}


def validate_receipt(value, thread_id, key, digest):
    expected = hashlib.sha256(key.encode()).hexdigest()
    if (
        not isinstance(value, dict)
        or type(value.get("schema_version")) is not int
        or value["schema_version"] != 1
        or value.get("thread_id") != thread_id
        or value.get("key_sha256") != expected
        or value.get("request_digest") != digest
        or value.get("result")
        not in {"accepted", "definitively_not_accepted", "unknown"}
    ):
        raise UpstreamServiceError(
            upstream="langgraph",
            code="run_acceptance_invalid",
            message="Invalid Run acceptance receipt",
        )
    result = value["result"]
    try:
        for name in ("observed_at", "accepted_at", "details_expires_at"):
            stamp = value[name]
            if stamp is None and name != "observed_at":
                continue
            if (
                not isinstance(stamp, str)
                or datetime.fromisoformat(stamp).tzinfo is None
            ):
                raise ValueError()
        state = value["run_state"]
        if (
            not isinstance(state, dict)
            or set(state) != {"available", "status"}
            or type(state["available"]) is not bool
            or state["available"] != isinstance(state["status"], str)
            or state["available"]
            and state["status"]
            not in {"pending", "running", "success", "error", "timeout", "interrupted"}
        ):
            raise ValueError()
        if result == "accepted":
            if str(UUID(value["run_id"])) != value["run_id"]:
                raise ValueError()
            if value["accepted_at"] is None or value["reason"] is not None:
                raise ValueError()
        elif (
            value.get("run_id") is not None
            or value.get("accepted_at") is not None
            or state["available"]
        ):
            raise ValueError()
        if result == "definitively_not_accepted" and (
            value.get("reason") != "multitask_rejected"
            or value["details_expires_at"] is None
        ):
            raise ValueError()
        if result == "unknown" and (
            value["reason"] not in {"no_receipt", "receipt_expired"}
            or value["details_expires_at"] is not None
        ):
            raise ValueError()
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise UpstreamServiceError(
            upstream="langgraph",
            code="run_acceptance_invalid",
            message="Invalid Run acceptance receipt",
        ) from exc
    return result
