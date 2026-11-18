import asyncio
import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from test_evaluation_feedback import setup as setup_fixture

from platform_api.config import Settings
from platform_api.core.errors import (
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
)
from platform_api.modules.platform_assistant.contracts import ReadRequest
from platform_api.modules.platform_assistant.diagnostics import checkpoint_summary
from platform_api.modules.platform_assistant.logs import authorized_logs
from platform_api.modules.platform_assistant.service import read

setup = setup_fixture
SECRET = "SYNTHETIC-DO-NOT-RETURN"


def failed_state(run_id):
    return {
        "metadata": {"run_id": run_id, "graph_id": "dearflow_agent"},
        "checkpoint": {"checkpoint_id": str(uuid4())},
        "tasks": [
            {
                "name": "ExecutionSkillsMiddleware.before_agent",
                "error": "runtime.execution_failed",
                "interrupts": [],
                "state": SECRET,
            }
        ],
        "interrupts": [],
        "values": {"messages": [{"type": "human", "content": SECRET}]},
    }


def environment(setup, tmp_path):
    factory, actor, scope = setup
    run_id = str(uuid4())
    snapshot = {
        "thread_id": scope[1],
        "run_id": run_id,
        "status": "error",
        "created_at": "2026-11-13T06:56:59+00:00",
        "updated_at": "2026-11-13T06:57:11+00:00",
        "kwargs": {"context": {"access_policy": "review", "api_key": SECRET}},
    }
    gateway = NS(
        get_thread_run=AsyncMock(return_value=snapshot),
        get_thread_run_diagnostics=AsyncMock(
            return_value={
                "availability": "disabled",
                "unavailable_reason": "not_configured",
                "request_id": "this-is-the-query-not-execution",
                "graph_executions": [
                    {"observation_id": "graph-1", "outcome": "failed"}
                ],
                "correlation": {
                    "platform_trace_id": None,
                    "execution_request_id": None,
                },
            }
        ),
        get_thread_history=AsyncMock(return_value=[failed_state(run_id)]),
    )
    log = tmp_path / "runtime.log"
    log.write_text("")
    settings = Settings(
        _env_file=None,
        platform_assistant_enabled=True,
        assistant_log_files={"runtime-service": str(log)},
    )
    request = NS(app=NS(state=NS(settings=settings, db_session_factory=factory)))
    return request, actor, scope, run_id, gateway, log


def invoke(env, operation="diagnostics"):
    request, actor, scope, run_id, gateway, _ = env
    return asyncio.run(
        read(
            request,
            actor,
            scope[0],
            ReadRequest(
                operation=operation,
                target_thread_id=scope[1],
                target_run_id=run_id,
            ),
            gateway,
        )
    )["data"]


def test_real_failure_shape_survives_unconfigured_tracing(setup, tmp_path):
    env = environment(setup, tmp_path)
    result = invoke(env)
    state = result["persistent_state"]
    assert result["availability"] == "disabled"
    assert result["run_status"] == "error"
    assert result["request_id_scope"] == "diagnostic_query_not_execution"
    assert result["availability_scope"] == "current_trace_query_client"
    assert result["historical_collection"] == "unknown"
    assert "observation_id" not in result["graph_executions"][0]
    assert "graph-1" not in json.dumps(result)
    assert state["failed_tasks"] == [
        {
            "node": "ExecutionSkillsMiddleware.before_agent",
            "error_code": "runtime.execution_failed",
        }
    ]
    assert state["approval_pending"] is False
    assert state["interrupts_observed"] is False
    assert state["messages"]["counts"] == {"human": 1, "ai": 0, "tool": 0, "other": 0}
    assert state["side_effects"] == "unknown"
    assert SECRET not in json.dumps(result)
    assert env[4].get_thread_history.call_args.kwargs["payload"] == {
        "limit": 1,
        "metadata": {"run_id": env[3]},
    }


def test_truncated_tasks_do_not_claim_no_approval():
    run_id = str(uuid4())
    state = failed_state(run_id)
    state["tasks"] += [{"name": "task", "interrupts": []}] * 20
    summary = checkpoint_summary(state, run_id)
    assert summary["tasks_truncated"] is True
    assert summary["interrupts_truncated"] is True
    assert summary["approval_pending"] is None
    assert summary["interrupts_observed"] is None


def test_checkpoint_does_not_confuse_other_run_or_raw_errors():
    run_id = str(uuid4())
    state = failed_state(str(uuid4()))
    assert checkpoint_summary(state, run_id)["reason"] == "run_mismatch"
    state = failed_state(run_id)
    state["tasks"][0]["error"] = f"ValueError: password={SECRET}"
    state["tasks"].append({"name": "secret_node", "error": {"key": SECRET}})
    state["tasks"][0]["interrupts"] = [
        {
            "value": {
                "action_requests": [{"name": "write_file", "args": {"key": SECRET}}],
                "review_configs": [{"allowed_decisions": ["approve", "reject"]}],
            }
        }
    ]
    state["values"]["messages"] += [{"type": "ai", "content": SECRET}] * 205
    result = checkpoint_summary(state, run_id)
    assert result["approval_pending"] is True
    assert result["failed_tasks"][0]["error_code"] == "unclassified_error"
    assert result["failed_tasks"][1]["node"] is None
    assert result["messages"]["scope"] == "checkpoint_state_not_run_delta"
    assert result["messages"]["truncated"] is True
    assert SECRET not in json.dumps(result)


@pytest.mark.parametrize(
    "failure",
    ["trace_backend", "state_backend", "state_timeout", "empty", "denied", "wrong_run"],
)
def test_state_source_failure_is_separate_and_acl_denial_still_stops(
    setup, tmp_path, failure
):
    env = environment(setup, tmp_path)
    gateway = env[4]
    if failure == "trace_backend":
        gateway.get_thread_run_diagnostics.side_effect = ServiceUnavailableError(
            code="backend", message=SECRET
        )
        result = invoke(env)
        assert result["availability"] == "unavailable"
        assert result["persistent_state"]["availability"] == "available"
    elif failure == "denied":
        gateway.get_thread_history.side_effect = ForbiddenError(
            code="thread_action_denied", message="denied"
        )
        with pytest.raises(ForbiddenError):
            invoke(env)
        return
    elif failure == "wrong_run":
        gateway.get_thread_run.return_value["run_id"] = str(uuid4())
        with pytest.raises(NotFoundError):
            invoke(env)
        gateway.get_thread_history.assert_not_called()
        return
    else:
        if failure == "state_backend":
            gateway.get_thread_history.side_effect = ServiceUnavailableError(
                code="backend", message=SECRET
            )
        elif failure == "state_timeout":
            gateway.get_thread_history.side_effect = TimeoutError()
        else:
            gateway.get_thread_history.return_value = []
        result = invoke(env)
        assert result["persistent_state"]["availability"] == (
            "empty" if failure == "empty" else "unavailable"
        )
        assert result["run_status"] == "error"
        if failure == "state_timeout":
            assert result["persistent_state"]["reason"] == "state_query_timeout"
    assert SECRET not in json.dumps(result)


@pytest.mark.parametrize(
    "correlation", ["run_id", "execution_request_id", "platform_trace_id"]
)
def test_logs_use_verified_fallback_and_reject_collisions(setup, tmp_path, correlation):
    env = environment(setup, tmp_path)
    _, _, scope, run_id, gateway, log = env
    identifiers = {"platform_trace_id": "a" * 32, "execution_request_id": "b" * 32}
    if correlation != "run_id":
        gateway.get_thread_run_diagnostics.return_value["correlation"][correlation] = (
            identifiers[correlation]
        )
    row = {
        "ts": "2026-11-13T06:57:00+00:00",
        "project_id": scope[0],
        "thread_id": scope[1],
        "run_id": run_id,
        "request_id": "b" * 32,
        "platform_trace_id": "a" * 32,
        "event": "runtime.execution.failed",
        "error_code": "runtime.execution_failed",
        "password": SECRET,
    }
    rows = [
        row,
        {**row, "project_id": str(uuid4())},
        {**row, "thread_id": str(uuid4())},
        {**row, "run_id": str(uuid4())},
        {**row, "ts": "2026-11-17T06:57:00+00:00"},
        {**row, "run_id": str(uuid4()), "message": run_id},
    ]
    if correlation == "execution_request_id":
        rows.append({**row, "request_id": "wrong-request", "message": "b" * 32})
    log.write_text("\n".join(json.dumps(r) for r in rows))
    result = invoke(env, "logs")
    assert result["total"] == 1
    assert result["correlation_type"] == correlation
    assert result["availability"] == "available"
    assert result["source"] == "fixed_files"
    assert result["partial"] is True
    assert result["query_start"] == "2026-11-13T06:51:59+00:00"
    assert SECRET not in json.dumps(result)


def test_logs_distinguish_empty_missing_source_and_unverified_requests(setup, tmp_path):
    env = environment(setup, tmp_path)
    assert invoke(env, "logs")["availability"] == "empty"
    env[-1].unlink()
    result = invoke(env, "logs")
    assert result["availability"] == "unavailable"
    assert result["error"] == "assistant_log_source_unavailable"
    request, actor, scope, run_id, _, _ = env
    with pytest.raises(ForbiddenError):
        asyncio.run(
            authorized_logs(
                request,
                actor,
                scope[0],
                "",
                target_thread_id=scope[1],
                target_run_id=run_id,
                execution_request_id="b" * 32,
            )
        )


def test_run_log_fallback_stops_after_target_membership_is_revoked(setup, tmp_path):
    from sqlalchemy import select

    from platform_api.modules.projects.models import ProjectMemberRecord

    env = environment(setup, tmp_path)
    factory, actor, scope = setup
    with factory.begin() as session:
        member = session.scalar(
            select(ProjectMemberRecord).where(
                ProjectMemberRecord.project_id == UUID(scope[0]),
                ProjectMemberRecord.user_id == UUID(actor.user_id),
            )
        )
        assert member is not None
        session.delete(member)
    with pytest.raises(ForbiddenError):
        invoke(env, "logs")
    env[4].get_thread_run.assert_not_called()


def test_capabilities_are_current_scoped_and_do_not_expose_paths(
    setup, tmp_path, monkeypatch
):
    from platform_api.modules.runtime_policies.application.service import (
        RuntimePolicyOverlayService,
    )

    env = environment(setup, tmp_path)
    request, actor, scope, _, gateway, log = env
    result = asyncio.run(
        read(request, actor, scope[0], ReadRequest(operation="authorize"), gateway)
    )["data"]
    caps = result["capabilities"]
    assert caps["databases"]["availability"] == "empty"
    assert caps["databases"]["reason"] == "no_readable_sources"
    assert caps["logs"]["services"] == ["runtime-service"]
    assert caps["logs"]["availability"] == "not_checked"
    assert caps["run_diagnostics"] == "on_request"
    assert str(log) not in json.dumps(result) and caps["shell"] is False
    monkeypatch.setattr(
        RuntimePolicyOverlayService,
        "resolve_tool_overrides",
        lambda *a, **k: {
            "tool_overrides": {
                "read_run_logs": False,
                "read_run_diagnostics": False,
                "list_databases": False,
            }
        },
    )
    denied = asyncio.run(
        read(request, actor, scope[0], ReadRequest(operation="authorize"), gateway)
    )["data"]["capabilities"]
    assert (
        denied["logs"]["availability"] == "denied" and denied["logs"]["services"] == []
    )
    assert denied["databases"]["availability"] == "denied"
    assert denied["run_diagnostics"] == "denied"
