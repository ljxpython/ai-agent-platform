import asyncio
from unittest.mock import AsyncMock

import pytest

from runtime_service.runtime.errors import RuntimeAuthError
from runtime_service.runtime.resolver import runtime_context_hash
from runtime_service.runtime.scheduled import (
    MARKER,
    _ScheduledGraph,
    scheduled_execution,
)


def config():
    return {
        "context": {},
        "metadata": {"run_id": "run"},
        "configurable": {
            MARKER: {"values": {}, "signature": "signed"},
            "cron_id": "cron",
            "thread_id": "thread",
            "langgraph_auth_user": {
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
                    "assistant_id": "probe",
                    "operation": "run-create",
                },
                "runtime_context_hash": runtime_context_hash({}),
            },
        },
    }


def test_guard_preserves_ordinary_runs_and_rejects_before_factory(monkeypatch):
    factory = AsyncMock(return_value=object())
    callback = AsyncMock(return_value={"allowed": False, "error_code": "revoked"})
    monkeypatch.setattr("runtime_service.runtime.scheduled._callback", callback)
    guard = scheduled_execution(factory, agent_key="probe")
    asyncio.run(guard({}))
    factory.assert_awaited_once()
    callback.assert_not_awaited()
    factory.reset_mock()
    for kind in ("marker", "scope", "hash", "revoked"):
        value = config()
        if kind == "marker":
            value["configurable"].pop(MARKER)
        elif kind == "scope":
            value["configurable"]["langgraph_auth_user"]["runtime_scope"][
                "assistant_id"
            ] = "other"
        elif kind == "hash":
            value["context"] = {"model_id": "tampered"}
        with pytest.raises(RuntimeAuthError):
            asyncio.run(guard(value))
        factory.assert_not_awaited()
    callback.assert_awaited_once()


def test_guard_refreshes_current_policy_before_factory(monkeypatch):
    factory = AsyncMock(return_value=object())
    callback = AsyncMock(
        return_value={
            "allowed": True,
            "configurable": {"platform_model_ref": "fresh"},
            "role": "project_executor",
            "policy": {"version": "new", "allowed_model_ids": ["model"]},
        }
    )
    monkeypatch.setattr("runtime_service.runtime.scheduled._callback", callback)
    value = config()
    asyncio.run(scheduled_execution(factory, agent_key="probe")(value))
    user = factory.call_args.args[0]["configurable"]["langgraph_auth_user"]
    assert user["role"] == "project_executor"
    assert user["runtime_policy"]["version"] == "new"
    assert value["configurable"]["platform_model_ref"] == "fresh"


@pytest.mark.parametrize(
    "result,code",
    [
        ({"messages": []}, None),
        ({"__interrupt__": ["approve"]}, "scheduled_task_approval_required"),
    ],
)
def test_nonstream_execution_reports_outcome(monkeypatch, result, code):
    report = AsyncMock()
    monkeypatch.setattr("runtime_service.runtime.scheduled._report", report)
    graph = _ScheduledGraph(
        type("Graph", (), {"ainvoke": AsyncMock(return_value=result)})(),
        {"run_id": "run"},
    )
    if code:
        with pytest.raises(RuntimeAuthError, match=code):
            asyncio.run(graph.ainvoke({}))
        report.assert_awaited_once_with({"run_id": "run"}, code)
    else:
        assert asyncio.run(graph.ainvoke({})) == result
        report.assert_awaited_once_with({"run_id": "run"})
