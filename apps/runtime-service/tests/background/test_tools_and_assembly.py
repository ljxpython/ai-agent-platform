"""Tool identity and composition gates without external models or Docker."""

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from langchain_core.tools import ToolException

from runtime_service.runtime.access_policy import interrupts_for_access_policy
from runtime_service.runtime.capabilities import graph_capabilities
from runtime_service.runtime.resolver import runtime_context_hash
from runtime_service.tools import background
from runtime_service.workspace.background import BackgroundBinding


@pytest.fixture(autouse=True)
def supported_start(monkeypatch):
    monkeypatch.setenv("DATABASE_URI", "isolated-test-only")
    monkeypatch.setenv("RUNTIME_BACKEND", "docker")
    monkeypatch.setenv("RUNTIME_BACKGROUND_TASKS_ENABLED", "1")
    monkeypatch.setenv("RUNTIME_EXECUTION_HOST_ID", "test-host")


@pytest.mark.parametrize(
    "key,value,query,start",
    [
        ("RUNTIME_BACKEND", "docker", True, True),
        ("RUNTIME_BACKEND", "local", True, False),
        ("RUNTIME_BACKGROUND_TASKS_ENABLED", "0", True, False),
        ("RUNTIME_EXECUTION_HOST_ID", "", True, False),
        ("RUNTIME_EXECUTION_HOST_ID", "invalid host", True, False),
        ("DATABASE_URI", "", False, False),
    ],
)
@pytest.mark.parametrize("graph_id", ["showcase_demo", "dearflow_agent"])
def test_capabilities_and_receipt_routes_preserve_query_gate(
    key, value, query, start, graph_id, monkeypatch
):
    monkeypatch.setenv(key, value)
    binding = Mock(side_effect=AssertionError("probe must not resolve a Workspace"))
    names = {tool.name for tool in background.build_background_tools(binding)}
    caps = graph_capabilities(graph_id)
    assert caps["background_tasks"] is query
    assert caps["background_tasks_start_enabled"] is start
    assert (
        "background_execute" in names
    )  # Hidden at the model boundary, retained for replay.
    assert ("background_task" in names) is query
    assert ("cancel_background_task" in names) is query
    assert not graph_capabilities("reference_agent")["background_tasks"]
    binding.assert_not_called()


def invocation(tmp_path):
    thread, run = str(uuid4()), str(uuid4())
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
            "thread_id": thread,
            "operation": "run-create",
        },
        "runtime_context_hash": runtime_context_hash({}),
    }
    runtime = SimpleNamespace(
        server_info=SimpleNamespace(user=user),
        execution_info=SimpleNamespace(thread_id=thread, run_id=None),
        config={"metadata": {"run_id": run}, "configurable": {}},
        tool_call_id="call",
        context={},
    )
    binding = BackgroundBinding(
        tmp_path, "python:3.13-slim", ("tenant", "project", thread), "showcase_demo"
    )
    return runtime, binding, run


def test_metadata_identity_and_dynamic_skills_snapshot(monkeypatch, tmp_path):
    runtime, binding, run = invocation(tmp_path)
    current = [binding]
    start = AsyncMock(return_value={"receipt": True})
    monkeypatch.setattr(background, "start_task", start)
    monkeypatch.setattr(background, "task_view", lambda row: row)
    tools = background.build_background_tools(lambda: current[0])
    current[0] = replace(binding, skills=tmp_path / "skills-snapshot")
    result = asyncio.run(tools[0].coroutine("printf done", runtime, 30))
    assert result == {"receipt": True}
    assert start.await_args.args[0]["origin_run_id"] == run
    assert start.await_args.args[1].skills == tmp_path / "skills-snapshot"


@pytest.mark.parametrize(
    "kind",
    [
        "missing_run",
        "mismatch",
        "scope",
        "execute_denied",
        "background_denied",
        "missing_server",
        "maintenance",
        "completion",
        "probe",
    ],
)
def test_start_denials_have_zero_side_effects(kind, monkeypatch, tmp_path):
    runtime, binding, _ = invocation(tmp_path)
    if kind == "missing_run":
        runtime.config["metadata"].clear()
    elif kind == "mismatch":
        runtime.execution_info.run_id = str(uuid4())
    elif kind == "scope":
        binding = replace(binding, scope=("tenant", "other", binding.scope[2]))
    elif kind.endswith("denied"):
        name = "execute" if kind == "execute_denied" else "background_execute"
        runtime.server_info.user["runtime_policy"]["tool_overrides"] = {name: False}
    elif kind == "missing_server":
        runtime.server_info = None
    elif kind == "maintenance":
        monkeypatch.setattr(
            background, "is_conversation_maintenance", lambda runtime: True
        )
    elif kind == "completion":
        runtime.config["configurable"]["platform_background_completion"] = {}
    elif kind == "probe":
        binding = None
    start = AsyncMock()
    monkeypatch.setattr(background, "start_task", start)
    with pytest.raises(ToolException):
        asyncio.run(
            background.build_background_tools(binding)[0].coroutine(
                "printf done", runtime, 30
            )
        )
    start.assert_not_awaited()


def test_completion_surface_and_access_policies(tmp_path):
    _, binding, _ = invocation(tmp_path)
    assert [
        tool.name
        for tool in background.build_background_tools(binding, completion=True)
    ] == ["background_task", "cancel_background_task"]
    approvals = {
        name: {} for name in background.BACKGROUND_TOOLS if name != "background_task"
    }
    assert interrupts_for_access_policy("review", approvals) == approvals
    assert interrupts_for_access_policy("workspace_write", approvals) == {}
    assert interrupts_for_access_policy("full_access", approvals) == {}
