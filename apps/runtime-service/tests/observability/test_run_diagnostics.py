from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from langfuse.api.client import AsyncLangfuseAPI

from runtime_service.observability import langfuse, query, startup
from runtime_service.runtime.errors import RuntimeWorkspaceError
from runtime_service.services.reference_agent.agent import _local_test_facts

SCOPE = {
    "tenant_id": "tenant",
    "project_id": "project",
    "graph_id": "reference_agent",
    "thread_id": str(uuid4()),
    "run_id": str(uuid4()),
}


def observation(event, **fields):
    return {
        "id": str(uuid4()),
        "trace_id": "a" * 32,
        "name": event,
        "metadata": {
            **SCOPE,
            "schema_version": 1,
            "event": event,
            "request_id": "execution-request",
            **fields,
        },
    }


def workspace_summary(**fields):
    return {
        "backend": "docker",
        "phase": "execute",
        "outcome": "failed",
        "command_state": "unknown",
        "attempts": 1,
        "retry_wait_ms": 0.0,
        "code": "runtime.workspace.execution_outcome_unknown",
        "duration_ms": 3,
        **fields,
    }


def test_workspace_projection_limits_scope_and_execution_codes():
    code = workspace_summary()["code"]
    events = [
        observation(
            "runtime.workspace.execution_completed",
            **workspace_summary(),
            command="CANARY",
        ),
        observation("runtime.graph.completed", outcome="failed", error_code=code),
        observation("runtime.startup.completed", factory_id="one"),
        observation(
            "runtime.startup.phase_completed",
            factory_id="one",
            phase="factory.workspace",
            ordinal=0,
            outcome="failed",
            error_code=code,
        ),
        observation("runtime.model_call.failed", scope="primary", code=code),
    ]
    for field in SCOPE:
        events.append(
            observation(
                "runtime.workspace.execution_completed",
                **workspace_summary(),
                **{field: "other"},
            )
        )
    result = query._project(events, SCOPE, truncated=False)
    assert len(result["workspace_executions"]) == 1 and not result["model_errors"]
    assert result["graph_executions"][0]["error_code"] == code
    assert result["startup"]["phases"][0]["error_code"] == code
    assert "CANARY" not in json.dumps(result)
    extra = [
        observation("runtime.workspace.execution_completed", **workspace_summary())
        for _ in range(21)
    ]
    result = query._project(events + extra, SCOPE, truncated=False)
    assert result["truncated"] and len(result["workspace_executions"]) == 20
    assert query.empty_diagnostics("not_configured")["workspace_executions"] == []


@pytest.mark.parametrize(
    "bad",
    [
        {"attempts": True},
        {"attempts": 0},
        {"attempts": 5},
        {"attempts": 1.0},
        {"retry_wait_ms": float("nan")},
        {"retry_wait_ms": float("inf")},
        {"retry_wait_ms": -1},
        {"retry_wait_ms": False},
        {"backend": "cloud"},
        {"phase": []},
        {"outcome": "success"},
        {"command_state": "guessed"},
        {"code": ["runtime.workspace.unavailable"]},
    ],
)
def test_workspace_malformed_summary_is_not_exported_or_projected(monkeypatch, bad):
    export = AsyncMock()
    callback = langfuse._RuntimeDiagnosticsCallback("reference_agent", SCOPE)
    monkeypatch.setattr(langfuse, "record_diagnostic_event", export)
    summary = workspace_summary(**bad)
    callback.on_custom_event(
        "runtime.workspace.execution_completed", summary, run_id="callback"
    )
    export.assert_not_called()
    result = query._project(
        [observation("runtime.workspace.execution_completed", **summary)],
        SCOPE,
        truncated=False,
    )
    assert result["workspace_executions"] == []


def test_workspace_callback_uses_trusted_scope_and_graph_startup_codes(monkeypatch):
    events = []
    monkeypatch.setattr(
        langfuse,
        "record_diagnostic_event",
        lambda event, fields: events.append((event, fields)),
    )
    callback = langfuse._RuntimeDiagnosticsCallback("reference_agent", SCOPE)
    callback.on_custom_event(
        "runtime.workspace.execution_completed",
        workspace_summary(**{key: "spoof" for key in SCOPE}, command="CANARY"),
        run_id="callback",
    )
    assert all(events[0][1][key] == value for key, value in SCOPE.items())
    assert "CANARY" not in repr(events)
    callback.on_chain_start({}, {}, run_id="callback")
    callback.on_chain_error(
        RuntimeWorkspaceError("runtime.workspace.unavailable"), run_id="callback"
    )
    assert events[-1][1]["error_code"] == "runtime.workspace.unavailable"
    callback.on_chain_error(
        RuntimeError("runtime.workspace.unavailable"), run_id="callback"
    )
    assert events[-1][1]["error_code"] is None
    monkeypatch.setattr(
        startup,
        "record_diagnostic_event",
        lambda event, fields: events.append((event, fields)),
    )
    with pytest.raises(RuntimeWorkspaceError):
        with startup.StartupDiagnostics("reference_agent") as collector:
            collector.authorize(
                {"metadata": {"run_id": SCOPE["run_id"]}}, _local_test_facts()
            )
            with collector.phase("factory.workspace"):
                raise RuntimeWorkspaceError("runtime.workspace.unavailable")
    assert (
        events[-2][1]["error_code"]
        == events[-1][1]["error_code"]
        == "runtime.workspace.unavailable"
    )
    monkeypatch.setattr(
        langfuse,
        "record_diagnostic_event",
        lambda *args: (_ for _ in ()).throw(RuntimeError("CANARY")),
    )
    callback.on_custom_event(
        "runtime.workspace.execution_completed", workspace_summary(), run_id="callback"
    )


def test_safe_projection_scope_multiple_executions_and_bounds():
    events = [
        observation(
            "runtime.model_call.failed",
            scope="primary",
            code="provider_rate_limited",
            namespace=["model:one"],
            error_type="RateLimitError",
            provider_status=429,
            duration_ms=1,
            message="CANARY",
            body="CANARY",
        ),
        observation("runtime.graph.completed", outcome="success", duration_ms=3),
        observation(
            "runtime.startup.completed", factory_id="factory-one", duration_ms=2
        ),
    ]
    for field in SCOPE:
        events.append(
            observation(
                "runtime.model_call.failed",
                **{field: "wrong"},
                scope="primary",
                code="provider_auth_failed",
            )
        )
    result = query._project(events, SCOPE, truncated=False)
    assert result["availability"] == "available"
    assert len(result["model_errors"]) == 1
    assert result["graph_executions"][0]["outcome"] == "success"
    assert result["graph_executions"][0]["error_code"] is None
    assert result["correlation"]["execution_request_id"] == "execution-request"
    assert "CANARY" not in json.dumps(result)
    assert result["trace"]["url"] is None
    extra = [
        observation(
            "runtime.model_call.failed",
            scope="subagent",
            namespace=["bad/secret"],
            code="provider_timeout",
            duration_ms=float("nan"),
        )
        for _ in range(25)
    ]
    result = query._project(events + extra, SCOPE, truncated=False)
    assert result["availability"] == "partial" and result["truncated"]
    assert len(result["model_errors"]) == 20
    assert result["model_errors"][1]["duration_ms"] is None
    assert result["model_errors"][1]["namespace"] == []
    result = query._project(
        events + [observation("runtime.startup.completed", factory_id="factory-two")],
        SCOPE,
        truncated=False,
    )
    assert result["startup"] is None and result["availability"] == "partial"


def test_query_disabled_failure_timeout_and_cancellation(monkeypatch):
    monkeypatch.setattr(query, "_client", None)
    assert (
        asyncio.run(query.query_run_diagnostics(**SCOPE))["availability"] == "disabled"
    )
    call = AsyncMock(side_effect=RuntimeError("secret"))
    monkeypatch.setattr(
        query, "_client", SimpleNamespace(observations=SimpleNamespace(get_many=call))
    )
    assert (
        asyncio.run(query.query_run_diagnostics(**SCOPE))["unavailable_reason"]
        == "backend_unavailable"
    )
    call.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(query.query_run_diagnostics(**SCOPE))


def test_preparation_and_retry_projection_bounds_duplicates_and_canaries():
    prepare = observation(
        "runtime.prepare.completed",
        scope="primary",
        namespace=[],
        component="workspace",
        outcome="reused",
        duration_ms=0,
        fingerprint="CANARY",
    )
    retry = observation(
        "runtime.retry.completed",
        scope="primary",
        namespace=[],
        unit="task",
        role="research",
        attempts=2,
        outcome="exhausted",
        code="provider_rate_limited",
        message="CANARY",
        duration_ms=10,
    )
    result = query._project([prepare, retry, retry], SCOPE, truncated=False)
    assert len(result["retries"]) == 1 and len(result["preparations"]) == 1
    assert result["preparations"][0]["duration_ms"] == 0
    assert result["retries"][0]["attempts"] == 2
    assert "CANARY" not in json.dumps(result)
    invalid = [
        observation(
            "runtime.retry.completed",
            scope="primary",
            unit="model",
            attempts=attempts,
            outcome="success",
        )
        for attempts in (0, 3, True, 1.5)
    ]
    assert not query._project(invalid, SCOPE, truncated=False)["retries"]
    rows = [
        observation(
            "runtime.retry.completed",
            scope="subagent",
            unit="model",
            attempts=1,
            outcome="failed",
            code="provider_timeout",
        )
        for _ in range(25)
    ]
    result = query._project(rows, SCOPE, truncated=False)
    assert len(result["retries"]) == 20 and result["truncated"]
    assert query.empty_diagnostics("not_configured")["preparations"] == []


def test_sdk_metadata_only_queries_and_legacy_fallback(monkeypatch):
    requests = []
    event = observation("runtime.graph.completed", outcome="failed")
    metadata = event["metadata"]

    async def respond(request):
        requests.append(request)
        assert request.url.params["fields"] == "core,basic,time,metadata"
        data = (
            []
            if "traceId" in request.url.params
            else [
                {
                    "id": event["id"],
                    "traceId": "a" * 32,
                    "name": event["name"],
                    "startTime": "2026-10-06T00:00:00Z",
                    "endTime": "2026-10-06T00:00:00Z",
                    "projectId": "langfuse-project",
                    "parentObservationId": None,
                    "type": "EVENT",
                    "metadata": metadata,
                }
            ]
        )
        return httpx.Response(
            200, json={"data": data, "meta": {"cursor": "more" if data else None}}
        )

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(respond)
        ) as transport:
            monkeypatch.setattr(
                query,
                "_client",
                AsyncLangfuseAPI(
                    base_url="http://langfuse.test",
                    username="test",
                    password="test",
                    httpx_client=transport,
                ),
            )
            return await query.query_run_diagnostics(**SCOPE)

    result = asyncio.run(run())
    assert len(requests) == 2 and "sessionId" in requests[1].url.params
    assert result["availability"] == "partial" and result["truncated"]
    assert result["graph_executions"][0]["outcome"] == "failed"
