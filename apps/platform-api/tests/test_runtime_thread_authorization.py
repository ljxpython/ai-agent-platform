from __future__ import annotations

import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from starlette.requests import Request

from platform_api.modules.runtime_catalog.presentation.http import authorize_runtime_threads


SECRET = "runtime-delegation-secret-at-least-32-bytes"


def _request(payload: dict, *, signature: str | None = None) -> Request:
    app = FastAPI()
    app.state.settings = SimpleNamespace(runtime_delegation_secret=SECRET)
    app.state.db_session_factory = object()
    stamp = str(int(time.time()))
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    signature = signature or hmac.new(
        SECRET.encode(), f"{stamp}\nthread-authorization\n{canonical}".encode(), hashlib.sha256
    ).hexdigest()
    return Request({
        "type": "http", "method": "POST", "path": "/api/runtime/internal/thread-authorization",
        "headers": [(b"x-runtime-acl-timestamp", stamp.encode()),
                    (b"x-runtime-acl-signature", signature.encode())], "app": app,
    })


def test_batch_endpoint_rebuilds_actor_and_checks_platform_acl() -> None:
    payload = {"action": "read", "project_id": "p1", "user_id": "u1", "thread_ids": ["t1", "t2"]}
    actor = object()
    request = _request(payload)
    with patch("platform_api.modules.runtime_catalog.presentation.http.load_user_actor", return_value=actor) as load_actor, \
         patch("platform_api.modules.runtime_catalog.presentation.http.thread_access.get", return_value={"project_id": "p1"}) as get_access, \
         patch("platform_api.modules.runtime_catalog.presentation.http.thread_access.allowed", side_effect=[True, False]) as allowed:
        result = authorize_runtime_threads(request, payload)

    assert result == {"allowed_thread_ids": ["t1"]}
    load_actor.assert_called_once_with(
        session_factory=request.app.state.db_session_factory, user_id="u1", project_id="p1"
    )
    assert get_access.call_count == 2
    assert [call.args[3] for call in allowed.call_args_list] == ["read", "read"]


def test_batch_endpoint_rejects_invalid_signature_and_unbounded_targets() -> None:
    payload = {"action": "read", "project_id": "p1", "user_id": "u1", "thread_ids": ["t1"]}
    bad = _request(payload, signature="invalid")
    try:
        authorize_runtime_threads(bad, payload)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
    else:
        raise AssertionError("invalid signature was accepted")

    oversized = {**payload, "thread_ids": [f"t{i}" for i in range(101)]}
    try:
        authorize_runtime_threads(_request(oversized), oversized)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
    else:
        raise AssertionError("oversized batch was accepted")

    invalid_action = {**payload, "action": "owner-can-do-anything"}
    try:
        authorize_runtime_threads(_request(invalid_action), invalid_action)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
    else:
        raise AssertionError("invalid action was accepted")


def test_create_authorization_requires_pending_owner() -> None:
    payload = {"action": "create", "project_id": "p1", "user_id": "u1", "thread_ids": ["pending", "ready"]}
    actor = SimpleNamespace(principal_type="user")
    with patch("platform_api.modules.runtime_catalog.presentation.http.load_user_actor", return_value=actor), \
         patch("platform_api.modules.runtime_catalog.presentation.http.thread_access.pending_owner", side_effect=[True, False]) as pending_owner:
        result = authorize_runtime_threads(_request(payload), payload)
    assert result == {"allowed_thread_ids": ["pending"]}
    assert pending_owner.call_count == 2
