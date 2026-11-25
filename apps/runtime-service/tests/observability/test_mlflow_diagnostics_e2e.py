from __future__ import annotations

import asyncio
import io
import json
import logging
from types import SimpleNamespace
from uuid import uuid4

import mlflow
import pytest
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import AIMessage
from support import BindableFakeMessagesChatModel

from runtime_service.observability import (
    diagnostics as diag_module,
)
from runtime_service.observability import (
    langfuse,
    mlflow_tracer,
    query,
    startup,
    with_tracing,
)
from runtime_service.observability import (
    logging as runtime_logging,
)


def _setup_mlflow(tmp_path, monkeypatch, *, experiment_name: str):
    monkeypatch.setenv("TRACING_PROVIDER", "mlflow")
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    monkeypatch.setenv("MLFLOW_ENABLE_ASYNC_TRACE_LOGGING", "false")
    uri = "sqlite:///" + str(tmp_path / "mlflow.db")
    monkeypatch.setenv("MLFLOW_TRACKING_URI", uri)
    monkeypatch.delenv("AGENT_LOOP_OBSERVATION_ENABLED", raising=False)
    monkeypatch.setattr(langfuse, "_client", None)
    monkeypatch.setattr(query, "_client", None)
    monkeypatch.setattr(mlflow_tracer, "_mlflow_initialized", False)

    previous_uri = mlflow.get_tracking_uri()
    mlflow.set_tracking_uri(uri)
    client = mlflow.tracking.MlflowClient(tracking_uri=uri)
    if client.get_experiment_by_name(experiment_name) is None:
        mlflow.create_experiment(
            experiment_name, artifact_location=(tmp_path / "artifacts").as_uri()
        )
    mlflow.set_experiment(experiment_name)
    return previous_uri, uri


def _clear_mlflow_buffers():
    with mlflow_tracer._diagnostic_lock:
        mlflow_tracer._active_root_spans.clear()
        mlflow_tracer._pending_span_events.clear()
        mlflow_tracer._recorded_run_events.clear()


@pytest.mark.parametrize("asynchronous", [False, True])
def test_mlflow_writes_startup_and_runtime_events_and_queries_available(
    tmp_path, monkeypatch, asynchronous
):
    project_id = str(uuid4())
    tenant_id = "tenant-a"
    thread_id = str(uuid4())
    run_id = str(uuid4())
    request_id = "req-" + uuid4().hex[:16]
    platform_trace_id = uuid4().hex
    previous_uri, _ = _setup_mlflow(
        tmp_path, monkeypatch, experiment_name=f"project-{project_id}"
    )

    @tool
    def synthetic_tool(query_text: str) -> str:
        """Return safe synthetic output."""
        return "synthetic-result"

    class _FakeFacts:
        def __init__(self):
            self.request_id = request_id
            self.platform_trace_id = platform_trace_id
            self.scope = SimpleNamespace(thread_id=thread_id)
            self.principal = SimpleNamespace(
                tenant_id=tenant_id,
                project_id=project_id,
                user_id="user-1",
            )

    try:
        _clear_mlflow_buffers()
        config = {
            "configurable": {"thread_id": thread_id, "run_id": run_id},
            "metadata": {"run_id": run_id},
        }
        diag = startup.StartupDiagnostics("synthetic_graph")
        diag.authorize(config, _FakeFacts())
        with diag:
            with diag.phase("factory.context_resolution"):
                pass
            with diag.phase("factory.agent_compile"):
                pass

        model = BindableFakeMessagesChatModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "id": "call-1",
                            "name": "synthetic_tool",
                            "args": {"query_text": "SECRET_CANARY_INPUT"},
                        }
                    ],
                ),
                AIMessage(content="all done"),
            ]
        )
        base_graph = create_agent(model, tools=[synthetic_tool])
        traced_graph = with_tracing(
            base_graph,
            config,
            graph_id="synthetic_graph",
            trusted_metadata={
                "tenant_id": tenant_id,
                "project_id": project_id,
                "user_id": "user-1",
                "model_id": "model-1",
                "request_id": request_id,
                "platform_trace_id": platform_trace_id,
            },
            startup=diag,
        )

        # Mid-run diagnostic events emitted while trace is running.
        langfuse.record_diagnostic_event(
            "runtime.retry.completed",
            {
                **diag.metadata,
                "schema_version": 1,
                "scope": "primary",
                "namespace": ["model"],
                "unit": "model",
                "attempts": 2,
                "outcome": "success",
                "duration_ms": 12.5,
            },
        )
        # No active root span yet until invoke starts; verify it buffers cleanly.
        payload = {"messages": [("user", "run diagnostics check")]}
        if asynchronous:
            asyncio.run(traced_graph.ainvoke(payload))
        else:
            traced_graph.invoke(payload)

        mlflow.flush_trace_async_logging()

        # Verify compact diagnostic tag stays well below MLflow's 4096-byte tag limit.
        client = mlflow.tracking.MlflowClient()
        exp = client.get_experiment_by_name(f"project-{project_id}")
        stored = client.search_traces(
            locations=[exp.experiment_id], include_spans=False
        )
        assert stored
        raw_tag = stored[0].info.tags["runtime.diag.events"]
        assert len(raw_tag.encode("utf-8")) <= mlflow_tracer._MAX_DIAG_TAG_BYTES
        assert all(
            k not in json.loads(raw_tag)[0]["metadata"]
            for k in ("tenant_id", "project_id", "thread_id", "run_id")
        )

        # Verify query_run_diagnostics succeeds via trace tag fast path without heavy get_trace calls.
        monkeypatch.setattr(
            mlflow.tracking.MlflowClient,
            "get_trace",
            lambda *a, **kw: (_ for _ in ()).throw(
                AssertionError(
                    "get_trace should not be called when runtime.diag.events tag is present"
                )
            ),
        )
        diagnosed = asyncio.run(
            query.query_run_diagnostics(
                tenant_id=tenant_id,
                project_id=project_id,
                graph_id="synthetic_graph",
                thread_id=thread_id,
                run_id=run_id,
            )
        )
        assert diagnosed["availability"] == "available"
        assert diagnosed["unavailable_reason"] is None
        assert diagnosed["trace"]["provider"] == "mlflow"
        assert diagnosed["trace"]["trace_id"].startswith("tr-")
        assert diagnosed["correlation"] == {
            "execution_request_id": request_id,
            "platform_trace_id": platform_trace_id,
        }
        assert diagnosed["graph_executions"][0]["outcome"] == "success"
        assert diagnosed["startup"] is not None
        assert [p["name"] for p in diagnosed["startup"]["phases"]] == [
            "factory.context_resolution",
            "factory.agent_compile",
        ]
        assert len(diagnosed["retries"]) == 1
        assert diagnosed["retries"][0]["attempts"] == 2
        assert "SECRET_CANARY_INPUT" not in json.dumps(diagnosed)

        # Strict tenant/project/run isolation on MLflow queries.
        other_run = asyncio.run(
            query.query_run_diagnostics(
                tenant_id=tenant_id,
                project_id=project_id,
                graph_id="synthetic_graph",
                thread_id=thread_id,
                run_id=str(uuid4()),
            )
        )
        assert other_run["availability"] == "unavailable"
        assert other_run["unavailable_reason"] == "not_recorded"

        other_tenant = asyncio.run(
            query.query_run_diagnostics(
                tenant_id="tenant-b",
                project_id=project_id,
                graph_id="synthetic_graph",
                thread_id=thread_id,
                run_id=run_id,
            )
        )
        assert other_tenant["availability"] == "unavailable"
        assert other_tenant["unavailable_reason"] == "not_recorded"
    finally:
        _clear_mlflow_buffers()
        mlflow.set_tracking_uri(previous_uri)


def test_mlflow_legacy_trace_without_span_events_returns_partial(tmp_path, monkeypatch):
    project_id = str(uuid4())
    tenant_id = "tenant-legacy"
    thread_id = str(uuid4())
    run_id = str(uuid4())
    request_id = "req-" + uuid4().hex[:12]
    platform_trace_id = uuid4().hex
    previous_uri, _ = _setup_mlflow(
        tmp_path, monkeypatch, experiment_name=f"project-{project_id}"
    )

    try:
        model = BindableFakeMessagesChatModel(responses=[AIMessage(content="ok")])
        graph = create_agent(model, tools=[])
        cb = mlflow_tracer.MLflowFailSoftCallback(
            graph_id="legacy_graph",
            bound_metadata={
                "tenant_id": tenant_id,
                "project_id": project_id,
                "graph_id": "legacy_graph",
                "thread_id": thread_id,
                "run_id": run_id,
                "request_id": request_id,
                "platform_trace_id": platform_trace_id,
            },
        )
        graph.invoke(
            {"messages": [("user", "legacy run")]},
            {"callbacks": [cb], "metadata": {"run_id": run_id}},
        )
        mlflow.flush_trace_async_logging()

        # Verify TraceInfo-level partial fallback even when legacy trace lacks diag tags and get_trace fails.
        monkeypatch.setattr(
            mlflow.tracking.MlflowClient,
            "get_trace",
            lambda *a, **kw: (_ for _ in ()).throw(TimeoutError("simulated timeout")),
        )
        diagnosed = asyncio.run(
            query.query_run_diagnostics(
                tenant_id=tenant_id,
                project_id=project_id,
                graph_id="legacy_graph",
                thread_id=thread_id,
                run_id=run_id,
            )
        )
        assert diagnosed["availability"] == "partial"
        assert diagnosed["unavailable_reason"] is None
        assert diagnosed["trace"]["provider"] == "mlflow"
        assert diagnosed["correlation"] == {
            "execution_request_id": request_id,
            "platform_trace_id": platform_trace_id,
        }
        assert diagnosed["graph_executions"][0]["outcome"] == "success"
        assert diagnosed["graph_executions"][0]["duration_ms"] >= 0
        assert diagnosed["startup"] is None
    finally:
        mlflow.set_tracking_uri(previous_uri)


def test_mlflow_not_configured_and_backend_unavailable(monkeypatch):
    monkeypatch.setenv("TRACING_PROVIDER", "mlflow")
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    monkeypatch.setattr(query, "_client", None)

    not_cfg = asyncio.run(
        query.query_run_diagnostics(
            tenant_id="t",
            project_id="p",
            graph_id="g",
            thread_id=str(uuid4()),
            run_id=str(uuid4()),
        )
    )
    assert not_cfg["availability"] == "disabled"
    assert not_cfg["unavailable_reason"] == "not_configured"

    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:9")
    monkeypatch.setattr(
        query,
        "_query_mlflow_sync",
        lambda *_: (_ for _ in ()).throw(RuntimeError("down")),
    )
    down = asyncio.run(
        query.query_run_diagnostics(
            tenant_id="t",
            project_id="p",
            graph_id="g",
            thread_id=str(uuid4()),
            run_id=str(uuid4()),
        )
    )
    assert down["availability"] == "unavailable"
    assert down["unavailable_reason"] == "backend_unavailable"


def test_worker_diagnostic_and_context_logs_emit_without_root_handler(monkeypatch):
    stream = io.StringIO()
    diag_logger = diag_module.logger
    root_logger = logging.getLogger()
    orig_root_handlers = list(root_logger.handlers)
    orig_diag_handlers = list(diag_logger.handlers)
    orig_diag_level = diag_logger.level
    try:
        root_logger.handlers = []
        diag_logger.handlers = []
        orig_stream_handler = logging.StreamHandler
        monkeypatch.setattr(
            logging, "StreamHandler", lambda *a, **kw: orig_stream_handler(stream)
        )
        diag_module.log_diagnostic(
            "runtime.graph.completed",
            {
                "project_id": "proj-1",
                "thread_id": "thread-1",
                "run_id": "run-1",
                "platform_trace_id": "a" * 32,
                "outcome": "success",
                "prompt": "SECRET_PROMPT",
            },
        )
        line = stream.getvalue().strip()
        assert line
        payload = json.loads(line)
        assert payload["event"] == "runtime.graph.completed"
        assert payload["project_id"] == "proj-1"
        assert payload["thread_id"] == "thread-1"
        assert payload["platform_trace_id"] == "a" * 32
        assert "SECRET_PROMPT" not in line
    finally:
        root_logger.handlers = orig_root_handlers
        diag_logger.handlers = orig_diag_handlers
        diag_logger.setLevel(orig_diag_level)

    # Verify log_context_metric carries project/thread/trace correlation when present in config.
    metric_stream = io.StringIO()
    orig_ctx_handlers = list(runtime_logging._context_metrics.handlers)
    try:
        runtime_logging._context_metrics.handlers = [orig_stream_handler(metric_stream)]
        monkeypatch.setattr(
            runtime_logging,
            "get_config",
            lambda: {
                "metadata": {
                    "run_id": "run-2",
                    "langgraph_checkpoint_ns": "tools:1",
                    "project_id": "proj-2",
                    "thread_id": "thread-2",
                    "platform_trace_id": "b" * 32,
                    "request_id": "req-2",
                    "secret": "DO_NOT_LEAK",
                }
            },
        )
        runtime_logging.log_context_metric({"event": "runtime.tool_output.view"})
        metric_line = metric_stream.getvalue().strip()
        parsed = json.loads(metric_line)
        assert parsed["project_id"] == "proj-2"
        assert parsed["thread_id"] == "thread-2"
        assert parsed["platform_trace_id"] == "b" * 32
        assert parsed["request_id"] == "req-2"
        assert "DO_NOT_LEAK" not in metric_line
    finally:
        runtime_logging._context_metrics.handlers = orig_ctx_handlers


def test_internal_diagnostics_http_endpoint_returns_mlflow_trace(tmp_path, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from runtime_service.http import diagnostics as diagnostics_http

    project_id = str(uuid4())
    tenant_id = "tenant-http"
    thread_id = str(uuid4())
    run_id = str(uuid4())
    request_id = "req-" + uuid4().hex[:12]
    platform_trace_id = uuid4().hex
    previous_uri, _ = _setup_mlflow(
        tmp_path, monkeypatch, experiment_name=f"project-{project_id}"
    )

    try:
        _clear_mlflow_buffers()
        config = {
            "configurable": {"thread_id": thread_id, "run_id": run_id},
            "metadata": {"run_id": run_id},
        }
        diag = startup.StartupDiagnostics("http_graph")
        diag.authorize(
            config,
            SimpleNamespace(
                request_id=request_id,
                platform_trace_id=platform_trace_id,
                scope=SimpleNamespace(thread_id=thread_id),
                principal=SimpleNamespace(
                    tenant_id=tenant_id, project_id=project_id, user_id="u-http"
                ),
            ),
        )
        with diag:
            with diag.phase("factory.context_resolution"):
                pass
        model = BindableFakeMessagesChatModel(responses=[AIMessage(content="ok")])
        traced = with_tracing(
            create_agent(model, tools=[]),
            config,
            graph_id="http_graph",
            trusted_metadata={
                "tenant_id": tenant_id,
                "project_id": project_id,
                "user_id": "u-http",
                "request_id": request_id,
                "platform_trace_id": platform_trace_id,
            },
            startup=diag,
        )
        asyncio.run(traced.ainvoke({"messages": [("user", "hi")]}))
        mlflow.flush_trace_async_logging()

        async def _fake_auth(_authorization=None):
            return {
                "runtime_scope": {
                    "operation": "diagnostics-read",
                    "thread_id": thread_id,
                    "assistant_id": "http_graph",
                    "tenant_id": tenant_id,
                    "project_id": project_id,
                },
                "runtime_principal": {
                    "tenant_id": tenant_id,
                    "project_id": project_id,
                    "user_id": "u-http",
                },
            }

        async def _fake_acl(*_args, **_kwargs):
            return None

        monkeypatch.setattr(diagnostics_http, "authenticate", _fake_auth)
        monkeypatch.setattr(diagnostics_http, "authorize_thread_targets", _fake_acl)

        app = FastAPI()
        app.include_router(diagnostics_http.router)
        with TestClient(app) as client:
            resp = client.get(
                f"/internal/threads/{thread_id}/runs/{run_id}/diagnostics",
                headers={"Authorization": "Bearer synthetic-token"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["availability"] == "available"
        assert body["trace"]["provider"] == "mlflow"
        assert body["correlation"]["platform_trace_id"] == platform_trace_id
        assert body["graph_executions"][0]["outcome"] == "success"
        assert body["startup"]["phases"][0]["name"] == "factory.context_resolution"
    finally:
        _clear_mlflow_buffers()
        mlflow.set_tracking_uri(previous_uri)


def test_mlflow_span_events_fallback_when_search_returns_empty_tracedata(
    tmp_path, monkeypatch
):
    project_id = str(uuid4())
    tenant_id = "tenant-span-fallback"
    thread_id = str(uuid4())
    run_id = str(uuid4())
    request_id = "req-" + uuid4().hex[:12]
    platform_trace_id = uuid4().hex
    previous_uri, _ = _setup_mlflow(
        tmp_path, monkeypatch, experiment_name=f"project-{project_id}"
    )

    try:
        _clear_mlflow_buffers()
        config = {
            "configurable": {"thread_id": thread_id, "run_id": run_id},
            "metadata": {"run_id": run_id},
        }
        diag = startup.StartupDiagnostics("fallback_graph")
        diag.authorize(
            config,
            SimpleNamespace(
                request_id=request_id,
                platform_trace_id=platform_trace_id,
                scope=SimpleNamespace(thread_id=thread_id),
                principal=SimpleNamespace(
                    tenant_id=tenant_id, project_id=project_id, user_id="u-fb"
                ),
            ),
        )
        with diag:
            with diag.phase("factory.context_resolution"):
                pass

        # Simulate trace recorded with SpanEvents but without runtime.diag.events tag (e.g. broken/missing tag).
        monkeypatch.setattr(
            mlflow_tracer, "_flush_run_events_to_trace_tags", lambda *_a: None
        )
        traced = with_tracing(
            create_agent(
                BindableFakeMessagesChatModel(responses=[AIMessage(content="ok")]),
                tools=[],
            ),
            config,
            graph_id="fallback_graph",
            trusted_metadata={
                "tenant_id": tenant_id,
                "project_id": project_id,
                "user_id": "u-fb",
                "request_id": request_id,
                "platform_trace_id": platform_trace_id,
            },
            startup=diag,
        )
        asyncio.run(traced.ainvoke({"messages": [("user", "hi")]}))

        orig_get_trace = mlflow.tracking.MlflowClient.get_trace
        get_calls: list[str] = []

        def tracked_get_trace(self, trace_id, *args, **kwargs):
            get_calls.append(trace_id)
            return orig_get_trace(self, trace_id, *args, **kwargs)

        monkeypatch.setattr(
            mlflow.tracking.MlflowClient, "get_trace", tracked_get_trace
        )
        diagnosed = asyncio.run(
            query.query_run_diagnostics(
                tenant_id=tenant_id,
                project_id=project_id,
                graph_id="fallback_graph",
                thread_id=thread_id,
                run_id=run_id,
            )
        )
        assert len(get_calls) == 1
        assert diagnosed["availability"] == "available"
        assert [p["name"] for p in diagnosed["startup"]["phases"]] == [
            "factory.context_resolution"
        ]
        assert diagnosed["graph_executions"][0]["outcome"] == "success"
    finally:
        _clear_mlflow_buffers()
        mlflow.set_tracking_uri(previous_uri)
