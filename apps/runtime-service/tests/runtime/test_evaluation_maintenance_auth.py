import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langgraph_sdk import Auth

from runtime_service.auth import platform
from runtime_service.run_control.authorization import cancellation_context_hash


@pytest.mark.parametrize(
    "operation,action,value,allowed",
    [
        ("thread-delete", "delete", {"thread_id": "t"}, True),
        ("thread-delete", "read", {"thread_id": "t"}, False),
        ("thread-delete", "delete", {"thread_id": "other"}, False),
        ("thread-delete", "delete", {"thread_id": "t", "state": True}, False),
        ("thread-delete", "search", {}, False),
        ("run-create", "create", {"thread_id": "t"}, False),
        (
            "run-cancel",
            "update",
            {
                "thread_id": "t",
                "cancel_active": True,
                "cancellation_id": "11111111-1111-4111-8111-111111111111",
            },
            True,
        ),
        (
            "run-cancellation-read",
            "read",
            {
                "thread_id": "t",
                "cancellation_receipt": True,
                "cancellation_id": "11111111-1111-4111-8111-111111111111",
            },
            True,
        ),
        ("run-cancellation-read", "read", {"thread_id": "t"}, False),
    ],
)
@pytest.mark.parametrize("graph_id", ["evaluation_assistant", "dearflow_agent"])
def test_maintenance_never_reads_assistant_content(
    monkeypatch, operation, action, value, allowed, graph_id
):
    acl = AsyncMock()
    monkeypatch.setattr(platform, "authorize_thread_targets", acl)
    ctx = SimpleNamespace(
        resource="threads",
        action=action,
        user={
            "identity": "platform-evaluation-maintenance",
            "role": "platform_maintenance",
            "runtime_context_hash": cancellation_context_hash(
                "11111111-1111-4111-8111-111111111111"
            ),
            "runtime_scope": {
                "thread_id": "t",
                "project_id": "p",
                "assistant_id": graph_id,
                "operation": operation,
            },
        },
    )
    if allowed:
        assert asyncio.run(
            platform.deny_image_scope_on_server_resources(ctx, value)
        ) == {"project_id": "p"}
        acl.assert_awaited_once()
    else:
        with pytest.raises(Auth.exceptions.HTTPException) as error:
            asyncio.run(platform.deny_image_scope_on_server_resources(ctx, value))
        assert error.value.status_code == 403
        acl.assert_not_awaited()
