from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from langfuse.api.client import AsyncLangfuseAPI

from runtime_service.observability import query

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
