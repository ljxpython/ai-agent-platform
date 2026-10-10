import json

import pytest
from pydantic import ValidationError
from test_execution_budget_projection import notice
from test_run_diagnostics import summary

from platform_api.adapters.langgraph.sdk_client import (
    project_budget_notice,
    project_execution_error,
    redact_runtime_private_fields,
)
from platform_api.core.runtime_contract import reject_private_runtime_state
from platform_api.modules.runtime_gateway.application.diagnostics import (
    RuntimeDiagnostics,
)
from platform_api.modules.runtime_gateway.presentation.http import _redact_sse_frame

CODE = "runtime.loop.detected"


def loop_summary(**changes):
    return {
        "observation_id": "loop-1",
        "scope": "primary",
        "namespace": [],
        "code": "tool_loop_approaching",
        "repetitions": 3,
        "threshold": 3,
        **changes,
    }


@pytest.mark.parametrize("used", [3, 5])
def test_loop_notice_exact_combinations_and_whitelist(used):
    payload = notice(
        code="tool_loop_approaching" if used == 3 else "tool_loop_reached",
        unit="tool_rounds",
        limit=5,
        used=used,
        remaining=5 - used,
        signature="SECRET_CANARY",
    )
    assert "CANARY" not in json.dumps(project_budget_notice(payload))
    for changes in (
        {"limit": 6},
        {"used": 4},
        {"remaining": None},
        {"remaining": 1},
        {"used": True},
        {"budget_scope": "thread"},
        {"unit": "model_calls"},
    ):
        assert project_budget_notice({**payload, **changes}) is None


@pytest.mark.parametrize("field", ["type", "error"])
def test_exact_loop_error_is_idempotent_and_not_substring_matched(field):
    result = project_execution_error(
        {field: "RuntimeExecutionError", "message": CODE, "stack": "SECRET_CANARY"}
    )
    assert result["code"] == CODE and "CANARY" not in json.dumps(result)
    assert project_execution_error(result) == result
    assert project_execution_error(CODE) == CODE
    for kind in (
        "ForgedRuntimeExecutionError",
        "RuntimeExecutionErrorSuffix",
        "ValueError",
    ):
        assert project_execution_error({field: kind, "message": CODE})["code"] != CODE
    for text in ("prefix " + CODE, CODE + " suffix", "RuntimeExecutionError: " + CODE):
        assert project_execution_error(text) == "Runtime execution failed"
        assert (
            project_execution_error({field: "RuntimeExecutionError", "message": text})[
                "code"
            ]
            != CODE
        )


@pytest.mark.parametrize("protocol", [False, True])
@pytest.mark.parametrize(
    "channel",
    ["values", "updates", "tasks", "debug", "checkpoints", "lifecycle", "custom"],
)
def test_private_state_and_error_cleaned_in_sse(channel, protocol):
    values = {
        "runtime_loop_state": {"signature": "SECRET_CANARY"},
        "messages": [{"type": "tool", "content": "ordinary tool result"}],
    }
    error = {"type": "RuntimeExecutionError", "message": CODE, "stack": "SECRET_CANARY"}
    payload = (
        {
            "values": values,
            "tasks": [{"error": error, "state": values}],
        }
        if channel == "checkpoints"
        else {"values": values}
    )
    if channel == "tasks":
        payload = {
            "id": "task-1",
            "name": "loop",
            "interrupts": [],
            "error": error,
            "result": values,
        }
    elif channel == "debug":
        payload = {"type": "task_result", "payload": {"error": error, "result": values}}
    elif channel == "lifecycle":
        payload = {
            "event": "lifecycle",
            "status": "error",
            "error": error,
            "values": values,
        }
    if channel == "custom":
        payload = notice(
            code="tool_loop_reached",
            unit="tool_rounds",
            limit=5,
            used=5,
            remaining=0,
            runtime_loop_state=values,
        )
    if protocol:
        payload = {
            "method": channel,
            "params": {
                "namespace": ["tools:child"],
                "seq": 7,
                "run_id": "run-1",
                "data": payload,
            },
        }
    frame = f"event: {channel}\nid: 7\ndata: {json.dumps(payload)}".encode()
    cleaned = _redact_sse_frame(frame, protocol=protocol)
    assert b"SECRET_CANARY" not in cleaned and b"runtime_loop_state" not in cleaned
    if channel in {"tasks", "debug", "checkpoints", "lifecycle"}:
        assert CODE.encode() in cleaned
    assert (
        b"ordinary tool result" in cleaned
        if channel != "custom"
        else b"tool_loop_reached" in cleaned
    )


def test_private_write_denied_recursively_and_normal_content_preserved():
    for payload in (
        {"input": {"runtime_loop_state": {}}},
        {"command": {"resume": {"id": {"runtime_loop_state": {}}}}},
        {"values": [{"runtime_loop_state": {}}]},
    ):
        with pytest.raises(ValueError):
            reject_private_runtime_state(payload)
        assert "runtime_loop_state" not in json.dumps(
            redact_runtime_private_fields(payload)
        )
    assert redact_runtime_private_fields({"content": CODE}) == {"content": CODE}


def test_optional_v1_loop_summary_and_graph_error_remain_model_independent():
    assert RuntimeDiagnostics.model_validate(summary()).loop_detections == []
    dto = RuntimeDiagnostics.model_validate(
        {
            **summary(),
            "loop_detections": [loop_summary(signature="SECRET_CANARY")],
            "graph_executions": [
                {"observation_id": "graph-1", "outcome": "failed", "error_code": CODE}
            ],
        }
    )
    assert "CANARY" not in dto.model_dump_json()
    assert dto.graph_executions[0].error_code == CODE
    with pytest.raises(ValidationError):
        RuntimeDiagnostics.model_validate(
            {
                **summary(),
                "model_errors": [
                    {
                        "observation_id": "model-1",
                        "scope": "primary",
                        "namespace": [],
                        "code": CODE,
                    }
                ],
            }
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"repetitions": True},
        {"repetitions": 3.0},
        {"repetitions": 4},
        {"threshold": 5},
        {"scope": "unknown"},
        {"namespace": ["/host/path"]},
        {"namespace": ["x"] * 9},
        {"code": CODE},
    ],
)
def test_loop_summary_strict_dto(changes):
    with pytest.raises(ValidationError):
        RuntimeDiagnostics.model_validate(
            {**summary(), "loop_detections": [loop_summary(**changes)]}
        )
