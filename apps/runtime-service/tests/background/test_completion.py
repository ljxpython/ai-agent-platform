"""Signed completions must pass current authorization before graph construction."""

import asyncio
import hashlib
import hmac
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from langgraph_sdk import Auth

from runtime_service.background_tasks import authorization
from runtime_service.run_control.authorization import cancellation_context_hash
from runtime_service.runtime import background_completion as guard
from runtime_service.runtime.errors import RuntimeAuthError
from runtime_service.runtime.resolver import runtime_context_hash

SECRET = "synthetic-background-test-secret-at-least-32-bytes"


def config(monkeypatch):
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", SECRET)
    values = {
        "tenant_id": "tenant",
        "project_id": "project",
        "owner_id": "owner",
        "credential_id": None,
        "graph_id": "showcase_demo",
        "thread_id": str(uuid4()),
        "origin_run_id": str(uuid4()),
        "task_id": str(uuid4()),
        "event_id": str(uuid4()),
        "context_hash": runtime_context_hash({}),
    }
    signature = hmac.new(
        SECRET.encode(),
        (
            "background-completion\n"
            + json.dumps(
                values, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            )
        ).encode(),
        hashlib.sha256,
    ).hexdigest()
    user = {
        "runtime_principal": {
            "tenant_id": "tenant",
            "project_id": "project",
            "user_id": "owner",
            "role": "project_editor",
            "permissions": [],
        },
        "runtime_policy": {
            "version": "1",
            "allowed_model_ids": ["model"],
            "tool_overrides": {},
            "tool_policy_version": "1",
        },
        "runtime_scope": {
            "tenant_id": "tenant",
            "project_id": "project",
            "assistant_id": "showcase_demo",
            "thread_id": values["thread_id"],
            "operation": "run-create",
        },
        "runtime_context_hash": runtime_context_hash({}),
    }
    return {
        "context": {},
        "metadata": {"run_id": str(uuid4())},
        "configurable": {
            guard.MARKER: {"values": values, "signature": signature},
            "thread_id": values["thread_id"],
            "langgraph_auth_user": user,
        },
    }, values


@pytest.mark.parametrize(
    "kind",
    [
        "signature",
        "unicode",
        "context",
        "identity",
        "cron",
        "stop",
        "revoked",
        "late_stop",
        "malformed_config",
        "malformed_metadata",
    ],
)
def test_completion_refusal_precedes_factory(kind, monkeypatch):
    value, row = config(monkeypatch)
    factory = AsyncMock()
    bind = Mock(return_value=row)
    allowed = Mock(return_value=row)
    callback = AsyncMock(return_value={"allowed": False})
    monkeypatch.setattr(guard, "bind_completion_run", bind)
    monkeypatch.setattr(guard, "completion_allowed", allowed)
    monkeypatch.setattr(guard, "callback", callback)
    if kind in {"signature", "unicode"}:
        value["configurable"][guard.MARKER]["signature"] = (
            "wrong" if kind == "signature" else "非ASCII"
        )
    elif kind == "context":
        value["context"] = {"model_id": "tampered"}
    elif kind == "identity":
        value["configurable"]["langgraph_auth_user"]["runtime_principal"]["user_id"] = (
            "other"
        )
    elif kind == "cron":
        value["configurable"]["cron_id"] = "cron"
    elif kind == "stop":
        allowed.return_value = None
    elif kind == "late_stop":
        allowed.side_effect = [row, None]
        callback.return_value = {"allowed": True}
    elif kind == "malformed_config":
        value["configurable"] = [guard.MARKER]
    elif kind == "malformed_metadata":
        value["metadata"] = []
    with pytest.raises(RuntimeAuthError):
        asyncio.run(
            guard.background_completion_execution(factory, agent_key="showcase_demo")(
                value
            )
        )
    factory.assert_not_awaited()


def test_completion_refreshes_model_policy_and_latest_approval_policy(monkeypatch):
    value, row = config(monkeypatch)
    monkeypatch.setattr(guard, "bind_completion_run", Mock(return_value=row))
    monkeypatch.setattr(guard, "completion_allowed", Mock(return_value=row))
    monkeypatch.setattr(
        guard,
        "callback",
        AsyncMock(
            return_value={
                "allowed": True,
                "policy": {
                    "version": "current",
                    "allowed_model_ids": ["current-model"],
                    "tool_overrides": {"execute": False},
                    "tool_policy_version": "current",
                },
                "role": "project_editor",
                "access_policy": "review",
                "configurable": {"runtime_model_ref": "fresh"},
            }
        ),
    )
    factory = AsyncMock(return_value="compiled")
    assert (
        asyncio.run(
            guard.background_completion_execution(factory, agent_key="showcase_demo")(
                value
            )
        )
        == "compiled"
    )
    refreshed = factory.await_args.args[0]
    assert refreshed["context"]["access_policy"] == "review"
    user = refreshed["configurable"]["langgraph_auth_user"]
    assert user["runtime_context_hash"] == runtime_context_hash(refreshed["context"])
    assert user["runtime_policy"]["tool_overrides"]["execute"] is False
    assert refreshed["configurable"]["runtime_model_ref"] == "fresh"


def test_ordinary_run_uses_original_factory(monkeypatch):
    factory = AsyncMock(return_value="ordinary")
    callback = AsyncMock()
    monkeypatch.setattr(guard, "callback", callback)
    assert (
        asyncio.run(
            guard.background_completion_execution(factory, agent_key="showcase_demo")(
                {}
            )
        )
        == "ordinary"
    )
    callback.assert_not_awaited()


@pytest.mark.parametrize(
    "operation,action", [("read", "read"), ("run-cancel", "update")]
)
def test_cleanup_receipt_can_only_reach_fixed_stopped_completion(
    monkeypatch, operation, action
):
    value, row = config(monkeypatch)
    task_id = row["task_id"]
    user = value["configurable"]["langgraph_auth_user"]
    user["runtime_policy"]["version"] = "background-control-v1:" + task_id
    user["policy_version"] = user["runtime_policy"]["version"]
    user["runtime_scope"]["operation"] = operation
    user["runtime_context_hash"] = cancellation_context_hash(task_id)
    row.update(stop_id=str(uuid4()), delivery_run_id=str(uuid4()))
    monkeypatch.setattr(authorization, "_receipt", Mock(return_value=row))
    ctx = SimpleNamespace(user=user, resource="threads", action=action)
    payload = {"thread_id": row["thread_id"], "run_id": row["delivery_run_id"]}
    assert asyncio.run(authorization.authorize_completion_cleanup(ctx, payload)) == {
        "project_id": row["project_id"]
    }
    for changed in (
        {"run_id": row["origin_run_id"]},
        {"thread_id": str(uuid4())},
        {"action": "rollback"},
        {"run_id": None},
    ):
        with pytest.raises(Auth.exceptions.HTTPException):
            asyncio.run(
                authorization.authorize_completion_cleanup(ctx, {**payload, **changed})
            )
    row["stop_id"] = None
    with pytest.raises(Auth.exceptions.HTTPException):
        asyncio.run(authorization.authorize_completion_cleanup(ctx, payload))
