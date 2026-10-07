from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from langchain.agents.middleware import ModelRequest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_openai.chat_models.base import OpenAIModelNotFoundError
from langgraph.errors import GraphBubbleUp
from openai import APIStatusError, APITimeoutError, RateLimitError
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from runtime_service.middlewares import model_errors
from runtime_service.observability import langfuse, otel, startup
from runtime_service.observability.diagnostics import trace_id_for
from runtime_service.observability.errors import classify_exception
from runtime_service.services.reference_agent.agent import _local_test_facts

CANARY = "provider-secret-canary-DO-NOT-EXPORT"


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (429, {}, "provider_rate_limited"),
        (529, {}, "provider_overloaded"),
        (401, {}, "provider_auth_failed"),
        (403, {}, "provider_access_denied"),
        (503, {}, "provider_unavailable"),
        (400, {"error": {"code": "context_length_exceeded"}}, "context_too_long"),
        (429, {"error": {"code": "model_not_found"}}, "model_unavailable"),
        (400, {"error": {"type": "authentication_error"}}, "provider_auth_failed"),
    ],
)
def test_real_provider_exception_precedence(status, body, expected):
    response = httpx.Response(
        status, request=httpx.Request("POST", "https://provider.invalid")
    )
    exc = APIStatusError(CANARY, response=response, body=body)
    assert classify_exception(exc) == expected


def test_timeout_wrapping_control_flow_and_hostile_properties():
    timeout = APITimeoutError(request=httpx.Request("POST", "https://provider.invalid"))
    outer = RuntimeError(CANARY)
    outer.__cause__ = timeout
    assert classify_exception(outer) == "provider_timeout"
    outer.__cause__ = outer
    assert classify_exception(outer) == "model_call_failed"
    assert classify_exception(asyncio.CancelledError()) is None
    assert classify_exception(GraphBubbleUp()) is None

    class HostileError(Exception):
        @property
        def body(self):
            raise ValueError(CANARY)

        @property
        def status_code(self):
            raise ValueError(CANARY)

        def __str__(self):
            raise ValueError(CANARY)

    assert classify_exception(HostileError()) == "model_call_failed"


def test_known_model_not_found_does_not_classify_arbitrary_404():
    response = httpx.Response(
        404, request=httpx.Request("POST", "https://provider.invalid")
    )
    error = OpenAIModelNotFoundError(CANARY, response=response, body={})
    assert classify_exception(error) == "model_unavailable"
    assert (
        classify_exception(APIStatusError(CANARY, response=response, body={}))
        == "model_call_failed"
    )


def test_middleware_safe_event_and_original_exception(monkeypatch, caplog):
    events = []
    metadata = {
        "tenant_id": "tenant",
        "project_id": "project",
        "run_id": str(uuid4()),
        "thread_id": str(uuid4()),
    }
    middleware = model_errors.ModelErrorMiddleware(metadata, scope="subagent")
    monkeypatch.setattr(
        model_errors,
        "get_config",
        lambda: {"metadata": {"langgraph_checkpoint_ns": "tools:one|model:two"}},
    )
    monkeypatch.setattr(
        model_errors,
        "record_diagnostic_event",
        lambda name, fields: events.append((name, fields)),
    )
    response = httpx.Response(
        429, request=httpx.Request("POST", "https://provider.invalid")
    )
    error = RateLimitError(CANARY, response=response, body={"secret": CANARY})

    async def handler(request):
        raise error

    request = ModelRequest(model=FakeListChatModel(responses=["ok"]), messages=[])
    with caplog.at_level("INFO"), pytest.raises(RateLimitError) as raised:
        asyncio.run(middleware.awrap_model_call(request, handler))
    assert raised.value is error
    name, fields = events[0]
    assert name == "runtime.model_call.failed"
    assert fields["code"] == "provider_rate_limited"
    assert fields["scope"] == "subagent" and fields["namespace"] == [
        "tools:one",
        "model:two",
    ]
    assert fields["run_id"] == metadata["run_id"]
    assert CANARY not in caplog.text and CANARY not in json.dumps(events)

    monkeypatch.setattr(
        model_errors,
        "record_diagnostic_event",
        lambda *args: (_ for _ in ()).throw(ValueError(CANARY)),
    )
    with pytest.raises(RateLimitError) as raised:
        asyncio.run(middleware.awrap_model_call(request, handler))
    assert raised.value is error


@pytest.mark.parametrize("error", [asyncio.CancelledError(), GraphBubbleUp()])
def test_model_control_flow_is_not_failure(monkeypatch, error):
    observer = AsyncMock()
    monkeypatch.setattr(model_errors, "record_diagnostic_event", observer)
    middleware = model_errors.ModelErrorMiddleware({})

    async def handler(request):
        raise error

    with pytest.raises(type(error)):
        asyncio.run(middleware.awrap_model_call(None, handler))
    observer.assert_not_called()


def test_startup_uses_monotonic_clock_and_is_fail_soft(monkeypatch):
    ticks = iter([10_000_000, 20_000_000, 30_000_000, 50_000_000])
    clock = iter([2_000_000_000, 2_000_000_000, 1_000_000_000, 1_000_000_000])
    monkeypatch.setattr(startup.time, "monotonic_ns", lambda: next(ticks))
    monkeypatch.setattr(startup.time, "time_ns", lambda: next(clock))
    collector = startup.StartupDiagnostics("reference_agent")
    collector.authorize({"metadata": {"run_id": str(uuid4())}}, _local_test_facts())
    with collector.phase("factory.model_build"):
        pass
    monkeypatch.setattr(
        startup,
        "record_diagnostic_event",
        lambda *args: (_ for _ in ()).throw(RuntimeError(CANARY)),
    )
    collector.finish()
    assert collector.phases[0]["duration_ms"] == 10
    assert collector.phases[0]["started_at"] > collector.phases[0]["ended_at"]
    assert collector.execution_span is None


def test_startup_and_execution_spans_end_and_probe_exports_nothing(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(startup, "initialize_otel", lambda: provider)
    collector = startup.StartupDiagnostics("reference_agent")
    collector.authorize({"metadata": {"run_id": str(uuid4())}}, _local_test_facts())
    with collector.phase("factory.agent_compile"):
        pass
    collector.finish()
    assert not exporter.get_finished_spans()
    callback = otel.OTelDiagnosticsCallback(
        provider, "reference_agent", collector.metadata, startup=collector
    )
    callback.on_chain_start({}, {}, run_id="callback")
    callback.on_chain_error(RuntimeError(CANARY), run_id="callback")
    spans = {span.name: span for span in exporter.get_finished_spans()}
    assert set(spans) == {
        "runtime.execution",
        "runtime.startup",
        "factory.agent_compile",
        "runtime.graph",
    }
    assert (
        spans["runtime.graph"].parent.span_id
        == spans["runtime.execution"].context.span_id
    )
    assert (
        spans["runtime.startup"].parent.span_id
        == spans["runtime.execution"].context.span_id
    )
    assert (
        spans["runtime.execution"].start_time
        <= spans["runtime.startup"].start_time
        <= spans["runtime.startup"].end_time
        <= spans["runtime.graph"].start_time
        <= spans["runtime.execution"].end_time
    )
    assert CANARY not in repr(
        [(span.attributes, span.status, span.events) for span in spans.values()]
    )
    probe = startup.StartupDiagnostics("reference_agent")
    probe.finish(RuntimeError(CANARY))
    assert len(exporter.get_finished_spans()) == 4
    provider.shutdown()


def test_langfuse_real_callback_exports_no_exception_text(monkeypatch):
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    key = f"pk-test-{uuid4()}"
    client = Langfuse(
        public_key=key,
        secret_key="test-only",
        base_url="http://127.0.0.1:1",
        tracer_provider=provider,
        span_exporter=exporter,
        mask=langfuse._mask,
        mask_otel_spans=langfuse._mask_spans,
    )
    callback = langfuse._FailSoftCallback(CallbackHandler(public_key=key))
    run_id = uuid4()
    callback.on_chain_start({"name": "test"}, {"prompt": CANARY}, run_id=run_id)
    callback.on_chain_error(RuntimeError(CANARY), run_id=run_id)
    client.flush()
    spans = exporter.get_finished_spans()
    assert spans
    assert CANARY not in repr(
        [(span.name, span.attributes, span.status, span.events) for span in spans]
    )
    client.shutdown()


def test_trace_id_uses_native_run_and_isolates_projects():
    metadata = {"tenant_id": "tenant", "project_id": "project", "run_id": str(uuid4())}
    assert trace_id_for(metadata) == trace_id_for(dict(metadata))
    assert trace_id_for(metadata) != trace_id_for({**metadata, "project_id": "another"})
    assert trace_id_for({**metadata, "run_id": "callback-id"}) is None


def test_diagnostic_event_uses_current_sdk_and_session(monkeypatch):
    from langfuse import Langfuse

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    client = Langfuse(
        public_key=f"pk-test-{uuid4()}",
        secret_key="test-only",
        base_url="http://127.0.0.1:1",
        tracer_provider=provider,
        span_exporter=exporter,
        mask=langfuse._mask,
        mask_otel_spans=langfuse._mask_spans,
    )
    fields = {
        "tenant_id": "tenant",
        "project_id": "project",
        "run_id": str(uuid4()),
        "thread_id": str(uuid4()),
        "code": "provider_rate_limited",
        "message": CANARY,
    }
    monkeypatch.setattr(langfuse, "_client", client)
    before = langfuse.get_observability_metrics().get("event_dropped", 0)
    langfuse.record_diagnostic_event("runtime.model_call.failed", fields)
    client.flush()
    spans = exporter.get_finished_spans()
    assert len(spans) == 1 and spans[0].name == "runtime.model_call.failed"
    assert spans[0].attributes["session.id"] == fields["thread_id"]
    assert format(spans[0].context.trace_id, "032x") == trace_id_for(fields)
    assert CANARY not in repr((spans[0].attributes, spans[0].events))
    assert langfuse.get_observability_metrics().get("event_dropped", 0) == before
    client.shutdown()


@pytest.mark.parametrize("phase", sorted(startup.PHASE_NAMES - {"node.model_prepare"}))
@pytest.mark.parametrize("failure", [RuntimeError(CANARY), asyncio.CancelledError()])
def test_startup_failure_preserves_exception_and_closes_phase(
    monkeypatch, phase, failure
):
    events = []
    monkeypatch.setattr(
        startup, "log_diagnostic", lambda name, fields: events.append((name, fields))
    )
    monkeypatch.setattr(startup, "record_diagnostic_event", lambda *args: None)
    monkeypatch.setattr(startup, "initialize_otel", lambda: None)
    collector = startup.StartupDiagnostics("reference_agent")
    run_id = str(uuid4())
    collector.authorize({"metadata": {"run_id": run_id}}, _local_test_facts())
    with pytest.raises(type(failure)) as raised, collector:
        with collector.phase(phase):
            raise failure
    assert raised.value is failure
    assert len(events) == 2 and events[-1][1]["run_id"] == run_id
    assert events[0][1]["outcome"] == (
        "cancelled" if isinstance(failure, asyncio.CancelledError) else "failed"
    )
    assert events[0][1]["duration_ms"] >= 0
    assert CANARY not in json.dumps(events)


def test_parallel_startup_collectors_and_phase_bounds(monkeypatch):
    monkeypatch.setattr(startup, "record_diagnostic_event", lambda *args: None)

    async def construct(run_id):
        with startup.StartupDiagnostics("reference_agent") as collector:
            collector.authorize(
                {"metadata": {"run_id": run_id}, "configurable": {"thread_id": "one"}},
                _local_test_facts(),
            )
            for _ in range(20):
                with collector.phase("factory.model_build"):
                    await asyncio.sleep(0)
        return collector

    async def parallel():
        return await asyncio.gather(*(construct(str(uuid4())) for _ in range(3)))

    collectors = asyncio.run(parallel())
    assert len({item.metadata["run_id"] for item in collectors}) == 3
    assert len({item.metadata["factory_id"] for item in collectors}) == 3
    assert all(len(item.phases) == 16 for item in collectors)
    assert all(
        [phase["ordinal"] for phase in item.phases] == list(range(16))
        for item in collectors
    )


def test_real_fallback_retry_and_timeout_log_attempts_separately(monkeypatch, caplog):
    from typing import ClassVar

    from langchain_core.messages import AIMessage
    from support import BindableFakeMessagesChatModel

    from runtime_service.services.reference_agent.agent import get_agent

    class FailModel(BindableFakeMessagesChatModel):
        attempts: ClassVar[int] = 0
        recover: ClassVar[bool] = False

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            type(self).attempts += 1
            if self.recover and type(self).attempts > 1:
                return super()._generate(
                    messages, stop=stop, run_manager=run_manager, **kwargs
                )
            raise ConnectionError(CANARY)

    async def invoke(configurable):
        graph = await get_agent(
            {"metadata": {"run_id": str(uuid4())}, "configurable": configurable}
        )
        return await graph.ainvoke({"messages": [{"role": "user", "content": "hello"}]})

    with caplog.at_level("INFO"):
        result = asyncio.run(
            invoke(
                {
                    "_runtime_model": FailModel(
                        responses=[AIMessage(content="primary")]
                    ),
                    "_runtime_fallback_model": BindableFakeMessagesChatModel(
                        responses=[AIMessage(content="fallback")]
                    ),
                }
            )
        )
    assert result["messages"][-1].content == "fallback"
    events = [
        json.loads(record.message)
        for record in caplog.records
        if record.message.startswith('{"schema_version"')
    ]
    assert (
        len(
            [event for event in events if event["event"] == "runtime.model_call.failed"]
        )
        == 1
    )
    assert [
        event["outcome"]
        for event in events
        if event["event"] == "runtime.graph.completed"
    ] == ["success"]
    assert CANARY not in caplog.text
    caplog.clear()
    FailModel.attempts = 0
    FailModel.recover = True
    with caplog.at_level("INFO"):
        result = asyncio.run(
            invoke(
                {
                    "_runtime_model": FailModel(
                        responses=[AIMessage(content="recovered")]
                    ),
                    "_runtime_model_retry": True,
                }
            )
        )
    assert result["messages"][-1].content == "recovered" and FailModel.attempts == 2
    caplog.clear()
    monkeypatch.setenv("AGENT_MODEL_CALL_TIMEOUT_SECONDS", "0.001")

    class SlowModel(BindableFakeMessagesChatModel):
        async def _agenerate(self, *args, **kwargs):
            await asyncio.sleep(1)
            return await super()._agenerate(*args, **kwargs)

    with caplog.at_level("INFO"), pytest.raises(TimeoutError):
        asyncio.run(
            invoke({"_runtime_model": SlowModel(responses=[AIMessage(content="late")])})
        )
    events = [
        json.loads(record.message)
        for record in caplog.records
        if record.message.startswith('{"schema_version"')
    ]
    assert any(event.get("code") == "provider_timeout" for event in events)
    assert any(
        event.get("outcome") == "timeout"
        and event["event"] == "runtime.graph.completed"
        for event in events
    )


def test_fallback_exhaustion_and_later_tool_failure_keep_separate_evidence(
    monkeypatch, caplog
):
    from langchain_core.messages import AIMessage
    from langchain_core.tools import tool
    from support import BindableFakeMessagesChatModel

    from runtime_service.services.reference_agent import agent

    class FailModel(BindableFakeMessagesChatModel):
        def _generate(self, *args, **kwargs):
            raise ConnectionError(CANARY)

    @tool
    def read_reference(topic: str) -> str:
        """Fail in the tool after the model has recovered."""
        raise LookupError(CANARY)

    monkeypatch.setattr(agent, "read_reference", read_reference)

    async def invoke(fallback):
        graph = await agent.get_agent(
            {
                "metadata": {"run_id": str(uuid4())},
                "configurable": {
                    "_runtime_model": FailModel(responses=[]),
                    "_runtime_fallback_model": fallback,
                },
            }
        )
        return await graph.ainvoke({"messages": [{"role": "user", "content": "hello"}]})

    for fallback, expected_exception, attempts in (
        (FailModel(responses=[]), ConnectionError, 2),
        (
            BindableFakeMessagesChatModel(
                responses=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": "read_reference",
                                "args": {"topic": "test"},
                                "id": "call-one",
                            }
                        ],
                    )
                ]
            ),
            LookupError,
            1,
        ),
    ):
        caplog.clear()
        with caplog.at_level("INFO"), pytest.raises(expected_exception):
            asyncio.run(invoke(fallback))
        events = [
            json.loads(record.message)
            for record in caplog.records
            if record.message.startswith('{"schema_version"')
        ]
        failures = [
            event for event in events if event["event"] == "runtime.model_call.failed"
        ]
        assert len(failures) == attempts
        completed = [
            event for event in events if event["event"] == "runtime.graph.completed"
        ]
        assert len(completed) == 1 and completed[0]["outcome"] == "failed"
        assert "code" not in completed[0] and "error_code" not in completed[0]
        if expected_exception is LookupError:
            assert any(event["event"] == "runtime.tool.failed" for event in events)
        assert CANARY not in caplog.text
