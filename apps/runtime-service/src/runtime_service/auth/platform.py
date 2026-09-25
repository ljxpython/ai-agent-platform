"""LangGraph Agent Server authentication adapter for Runtime Delegation JWTs."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx

from langgraph_sdk import Auth

from runtime_service.runtime.auth import _user_value, verify_delegation_claims
from runtime_service.runtime.errors import RuntimeAuthError

auth = Auth()


def _setting(name: str, *, required: bool = True) -> str:
    value = os.getenv(name, "")
    if required and not value:
        raise Auth.exceptions.HTTPException(
            status_code=500, detail="Runtime auth is misconfigured"
        )
    return value


def _bearer_token(authorization: str | None) -> str:
    if not isinstance(authorization, str):
        raise Auth.exceptions.HTTPException(status_code=401, detail="Unauthorized")
    scheme, separator, token = authorization.strip().partition(" ")
    if scheme.lower() != "bearer" or not separator or not token.strip():
        raise Auth.exceptions.HTTPException(status_code=401, detail="Unauthorized")
    return token.strip()


@auth.authenticate
async def authenticate(authorization: str | None = None) -> Auth.types.MinimalUserDict:
    """Validate the request token and expose only non-secret Runtime auth facts."""

    try:
        verified = verify_delegation_claims(
            _bearer_token(authorization),
            secret=_setting("PLATFORM_RUNTIME_DELEGATION_SECRET"),
            issuer=_setting("PLATFORM_RUNTIME_DELEGATION_ISSUER"),
            audience=_setting("PLATFORM_RUNTIME_DELEGATION_AUDIENCE"),
        )
    except Auth.exceptions.HTTPException:
        raise
    except (RuntimeAuthError, ValueError) as exc:
        raise Auth.exceptions.HTTPException(
            status_code=401, detail="Unauthorized"
        ) from exc

    principal = verified.principal
    policy = verified.policy
    return {
        "identity": principal.user_id,
        "is_authenticated": True,
        "tenant_id": principal.tenant_id,
        "project_id": principal.project_id,
        "role": principal.role,
        "permissions": list(principal.permissions),
        "policy_version": policy.version,
        "allowed_model_ids": list(policy.allowed_model_ids),
        "tool_overrides": dict.fromkeys(policy.denied_tool_names, False),
        "tool_policy_version": policy.tool_policy_version,
        "runtime_principal": {
            "user_id": principal.user_id,
            "tenant_id": principal.tenant_id,
            "project_id": principal.project_id,
            "role": principal.role,
            "permissions": list(principal.permissions),
        },
        "runtime_policy": {
            "version": policy.version,
            "allowed_model_ids": list(policy.allowed_model_ids),
            "tool_overrides": dict.fromkeys(policy.denied_tool_names, False),
            "tool_policy_version": policy.tool_policy_version,
        },
        "runtime_scope": {
            "tenant_id": verified.scope.tenant_id,
            "project_id": verified.scope.project_id,
            "assistant_id": verified.scope.assistant_id,
            "thread_id": verified.scope.thread_id,
            "operation": verified.scope.operation,
        },
        "runtime_context_hash": verified.context_hash,
        "request_id": verified.request_id,
        "platform_trace_id": verified.platform_trace_id,
    }


@auth.on
async def deny_image_scope_on_server_resources(
    ctx: Auth.types.AuthContext, value: dict
) -> None:
    """Enforce delegation scope and recheck platform ACL for thread resources."""
    scope = _user_value(ctx.user, "runtime_scope")
    if not isinstance(scope, dict) or scope.get("operation") not in {
        "read",
        "run-create",
        "thread-create",
        "thread-reconcile",
        "thread-edit",
        "thread-delete",
        "run-cancel",
        "run-delete",
    }:
        raise Auth.exceptions.HTTPException(
            status_code=403,
            detail="custom operation tokens cannot access native LangGraph server resources",
        )
    resource = str(ctx.resource)
    action = str(ctx.action)
    bound_thread = scope.get("thread_id")
    requested_thread = value.get("thread_id")
    if (
        bound_thread
        and requested_thread is not None
        and str(requested_thread) != bound_thread
    ):
        raise Auth.exceptions.HTTPException(
            status_code=403, detail="Thread scope mismatch"
        )
    if scope["operation"] == "thread-create":
        if (
            resource != "threads"
            or action != "create"
            or str(value.get("thread_id") or "") != str(scope.get("thread_id") or "")
        ):
            raise Auth.exceptions.HTTPException(
                status_code=403, detail="Thread creation scope mismatch"
            )
        acl_action = "create"
    elif scope["operation"] == "thread-reconcile":
        if (
            resource != "threads"
            or action != "read"
            or str(value.get("thread_id") or "") != str(scope.get("thread_id") or "")
        ):
            raise Auth.exceptions.HTTPException(
                status_code=403, detail="Thread reconciliation scope mismatch"
            )
        acl_action = "reconcile"
    elif resource == "threads" and action == "create":
        raise Auth.exceptions.HTTPException(
            status_code=403, detail="Thread creation requires a scoped delegation"
        )
    elif resource == "assistants":
        assistant_id = str(scope.get("assistant_id") or "")
        allowed_ids = (
            {assistant_id, str(uuid5(NAMESPACE_URL, assistant_id))}
            if assistant_id
            else set()
        )
        if action != "read" or str(value.get("assistant_id") or "") not in allowed_ids:
            raise Auth.exceptions.HTTPException(
                status_code=403, detail="Assistant scope mismatch"
            )
        return
    elif resource != "threads":
        raise Auth.exceptions.HTTPException(
            status_code=403, detail="Unsupported server resource"
        )
    else:
        if scope["operation"] == "run-create":
            assistant_id = str(value.get("assistant_id") or "")
            if assistant_id != str(scope.get("assistant_id") or ""):
                raise Auth.exceptions.HTTPException(
                    status_code=403, detail="Assistant scope mismatch"
                )
        allowed_actions = {
            "read": {"read", "search"},
            "run-create": {"create_run"},
            "thread-edit": {"update"},
            "thread-delete": {"delete"},
            "run-cancel": {"update"},
            "run-delete": {"delete"},
        }
        if action not in allowed_actions.get(scope["operation"], set()) or (
            scope["operation"] != "read" and not bound_thread
        ):
            raise Auth.exceptions.HTTPException(
                status_code=403, detail="Delegation operation mismatch"
            )
        if (
            scope["operation"] in {"run-cancel", "run-delete"}
            and value.get("run_id") is None
        ):
            raise Auth.exceptions.HTTPException(
                status_code=403, detail="Run target is required"
            )
        if (
            scope["operation"] in {"thread-edit", "thread-delete"}
            and value.get("run_id") is not None
        ):
            raise Auth.exceptions.HTTPException(
                status_code=403, detail="Thread operation cannot target runs"
            )
        acl_action = {
            "read": "read",
            "search": "read",
            "create_run": "approve"
            if "resume"
            in (value.get("command") if isinstance(value.get("command"), dict) else {})
            else "comment",
            "update": "edit",
            "delete": "delete",
            "approve": "approve",
        }.get(action)
        if acl_action is None:
            raise Auth.exceptions.HTTPException(
                status_code=403, detail="Unsupported thread operation"
            )
    project_id = _user_value(ctx.user, "project_id")
    identity = _user_value(ctx.user, "identity")
    if (
        not isinstance(project_id, str)
        or not project_id
        or not isinstance(identity, str)
        or not identity
    ):
        raise Auth.exceptions.HTTPException(
            status_code=403, detail="Thread identity is unavailable"
        )
    thread_id = value.get("thread_id")
    thread_ids = value.get("ids")
    if isinstance(thread_id, str) and thread_id:
        targets = [thread_id]
    elif isinstance(thread_id, UUID):
        targets = [str(thread_id)]
    elif (
        isinstance(thread_ids, list)
        and 0 < len(thread_ids) <= 100
        and all(isinstance(item, str) and item for item in thread_ids)
    ):
        targets = thread_ids
    else:
        raise Auth.exceptions.HTTPException(
            status_code=403, detail="Thread targets are required"
        )
    if bound_thread and any(target != bound_thread for target in targets):
        raise Auth.exceptions.HTTPException(
            status_code=403, detail="Thread scope mismatch"
        )

    endpoint = _setting("PLATFORM_THREAD_AUTHORIZATION_URL")
    secret = _setting("PLATFORM_RUNTIME_DELEGATION_SECRET")
    payload = {
        "action": acl_action,
        "project_id": project_id,
        "user_id": identity,
        "thread_ids": targets,
    }
    stamp = str(int(time.time()))
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    signature = hmac.new(
        secret.encode(),
        f"{stamp}\nthread-authorization\n{canonical}".encode(),
        hashlib.sha256,
    ).hexdigest()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.post(
                endpoint,
                json=payload,
                headers={
                    "x-runtime-acl-timestamp": stamp,
                    "x-runtime-acl-signature": signature,
                },
            )
            response.raise_for_status()
            result = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise Auth.exceptions.HTTPException(
            status_code=503, detail="Platform authorization unavailable"
        ) from exc
    allowed = result.get("allowed_thread_ids") if isinstance(result, dict) else None
    if not isinstance(allowed, list) or set(allowed) != set(targets):
        raise Auth.exceptions.HTTPException(
            status_code=403, detail="Thread access denied"
        )


__all__ = ["auth", "authenticate", "deny_image_scope_on_server_resources"]
