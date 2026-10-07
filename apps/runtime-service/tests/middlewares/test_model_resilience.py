from __future__ import annotations

import asyncio
import json
import statistics
import time
import tracemalloc
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import anthropic
import httpx
import openai
import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest, ModelResponse
from langchain_core.exceptions import ContextOverflowError
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage
from langchain_core.outputs import ChatGenerationChunk
from support import BindableFakeChatModel

from runtime_service.middlewares.model_call_timeout import ModelCallTimeoutMiddleware
from runtime_service.middlewares.model_resilience import (
    ModelResilienceMiddleware,
    _OutputObserver,
    is_transient_model_error,
    retry_after_seconds,
)
from runtime_service.runtime.contracts import ModelResiliencePolicy
from runtime_service.runtime.errors import RuntimeResolutionError

A = "00000000-0000-0000-0000-000000000001"
B = "00000000-0000-0000-0000-000000000002"


def _error(status=503, code="overloaded", headers=None):
    response = httpx.Response(
        status, request=httpx.Request("POST", "https://secret.invalid"), headers=headers
    )
    return openai.APIStatusError(
        "secret provider text", response=response, body={"error": {"code": code}}
    )


@pytest.mark.parametrize(
    "status,code,expected",
    [
        (429, "rate_limit", True),
        (529, "overloaded", True),
        (401, "auth", False),
        (400, "bad_request", False),
        (429, "insufficient_quota", False),
        (409, "conflict", False),
    ],
)
def test_error_classification(status, code, expected):
    assert is_transient_model_error(_error(status, code)) is expected
    assert not is_transient_model_error(ValueError("bug"))
    assert not is_transient_model_error(
        RuntimeResolutionError("runtime.tool.not_allowed")
    )


def test_retry_after_and_policy_validation():
    assert retry_after_seconds(_error(headers={"retry-after": "5"})) == 5
    assert retry_after_seconds(_error(headers={"retry-after": "bad"})) == 0
    for invalid in (
        {"max_attempts": True},
        {"attempt_timeout_seconds": float("nan")},
        {"fallback_model_id": "provider:model"},
    ):
        with pytest.raises(RuntimeResolutionError):
            ModelResiliencePolicy(**invalid)


@pytest.mark.parametrize(
    "permanent,fallback,expected",
    [
        (False, True, ["A", "B", "A"]),
        (False, False, ["A", "A", "A"]),
        (True, True, ["A"]),
    ],
)
def test_official_composition_has_shared_physical_budget(
    monkeypatch, permanent, fallback, expected
):
    monkeypatch.setattr(
        "langchain.agents.middleware.model_retry.calculate_delay",
        lambda *args, **kwargs: 0,
    )
    primary = BindableFakeChatModel(responses=["ok"])
    backup = BindableFakeChatModel(responses=["backup"]) if fallback else None
    policy = ModelResiliencePolicy(
        enabled=True, fallback_model_id=B if fallback else None
    )
    middleware = ModelResilienceMiddleware(policy, backup, primary_model_id=A)
    request = ModelRequest(model=primary, messages=[HumanMessage("hello")])
    calls = []

    async def handler(candidate):
        calls.append("B" if candidate.model.responses == ["backup"] else "A")
        raise _error(401 if permanent else 503)

    with pytest.raises(RuntimeResolutionError) as error:
        asyncio.run(middleware.awrap_model_call(request, handler))
    assert calls == expected
    assert error.value.code == (
        "runtime.model.provider_rejected"
        if permanent
        else "runtime.model.retry_exhausted"
    )
    assert "secret" not in str(error.value)


def test_success_summary_and_timeout_order():
    primary = BindableFakeChatModel(responses=["ok"])
    backup = BindableFakeChatModel(responses=["backup"])
    policy = ModelResiliencePolicy(enabled=True, fallback_model_id=B)
    middleware = ModelResilienceMiddleware(policy, backup, primary_model_id=A)
    timeout = ModelCallTimeoutMiddleware(0.01)
    calls = []

    async def provider(candidate):
        calls.append(candidate.model.responses)
        if candidate.model.responses == ["ok"]:
            await asyncio.sleep(1)
        return ModelResponse(result=[AIMessage(content="backup")])

    async def handler(candidate):
        return await timeout.awrap_model_call(candidate, provider)

    result = asyncio.run(
        middleware.awrap_model_call(ModelRequest(model=primary, messages=[]), handler)
    )
    assert len(calls) == 2
    assert (
        result.result[0].response_metadata["platform_model_resilience"][
            "effective_model_id"
        ]
        == B
    )


class _PartialModel(BindableFakeChatModel):
    partial: AIMessageChunk = AIMessageChunk(content="partial")

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        yield ChatGenerationChunk(message=self.partial)
        raise _error()


@pytest.mark.parametrize(
    "partial",
    [
        AIMessageChunk(content="partial"),
        AIMessageChunk(
            content="", additional_kwargs={"reasoning_content": "reasoning"}
        ),
        AIMessageChunk(
            content="",
            tool_call_chunks=[
                {"name": "search", "args": '{"query":', "id": "call-1", "index": 0}
            ],
        ),
    ],
)
def test_real_graph_stream_does_not_fallback_after_content(partial):
    backup = BindableFakeChatModel(responses=["backup", "must not be called"])
    graph = create_agent(
        model=_PartialModel(responses=["unused"], partial=partial),
        middleware=[
            ModelResilienceMiddleware(
                ModelResiliencePolicy(enabled=True, fallback_model_id=B),
                backup,
                primary_model_id=A,
            ),
            ModelCallTimeoutMiddleware(1),
        ],
    )

    async def stream():
        output = []
        try:
            async for message, _ in graph.astream(
                {"messages": [HumanMessage("hello")]}, stream_mode="messages"
            ):
                output.append(message)
        except RuntimeResolutionError as exc:
            assert exc.code == "runtime.model.stream_interrupted"
        else:
            raise AssertionError("partial must fail")
        return output

    assert asyncio.run(stream())
    assert backup.i == 0


def test_total_budget_and_cancel_stop_requests(monkeypatch):
    monkeypatch.setattr(
        "langchain.agents.middleware.model_retry.calculate_delay",
        lambda *args, **kwargs: 10,
    )
    policy = replace(
        ModelResiliencePolicy(enabled=True),
        attempt_timeout_seconds=1,
        total_timeout_seconds=1,
    )
    primary = BindableFakeChatModel(responses=["ok"])
    middleware = ModelResilienceMiddleware(policy, primary_model_id=A)
    calls = 0

    async def handler(candidate):
        nonlocal calls
        calls += 1
        raise _error()

    with pytest.raises(RuntimeResolutionError, match="retry_budget_exceeded"):
        asyncio.run(
            middleware.awrap_model_call(
                ModelRequest(model=primary, messages=[]), handler
            )
        )
    assert calls == 1

    async def cancel():
        task = asyncio.create_task(
            middleware.awrap_model_call(
                ModelRequest(model=primary, messages=[]), handler
            )
        )
        await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel())
    assert calls == 2


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504, 529])
def test_both_provider_statuses_are_explicitly_retryable(status):
    error = anthropic.APIStatusError(
        "private body",
        response=httpx.Response(
            status, request=httpx.Request("POST", "https://secret.invalid")
        ),
        body={"type": "overloaded_error"},
    )
    assert is_transient_model_error(error)
    assert is_transient_model_error(_error(status))


def test_retry_after_date_and_unknown_transport_are_not_guessed():
    seconds = retry_after_seconds(
        _error(
            headers={
                "retry-after": format_datetime(
                    datetime.now(UTC) + timedelta(seconds=30)
                )
            }
        )
    )
    assert 28 <= seconds <= 30
    for value in (
        "NaN",
        "inf",
        "-1",
        format_datetime(datetime.now(UTC) - timedelta(seconds=1)),
    ):
        assert retry_after_seconds(_error(headers={"retry-after": value})) == 0
    assert is_transient_model_error(httpx.ReadTimeout("private"))
    assert not is_transient_model_error(httpx.LocalProtocolError("bug"))


def test_empty_chunks_do_not_commit_output():
    observer = _OutputObserver()
    observer.on_llm_new_token(
        "",
        chunk=ChatGenerationChunk(
            message=AIMessageChunk(
                content=[{"type": "text", "text": ""}], response_metadata={"usage": {}}
            )
        ),
    )
    assert not observer.has_output
    observer.on_llm_new_token(
        "",
        chunk=ChatGenerationChunk(
            message=AIMessageChunk(
                content=[{"type": "reasoning", "reasoning": "thinking"}]
            )
        ),
    )
    assert observer.has_output


@pytest.mark.parametrize(
    "failure", [ValueError("program defect"), ContextOverflowError("private overflow")]
)
def test_unknown_error_does_not_visit_backup(failure):
    model = BindableFakeChatModel(responses=["primary"])
    backup = BindableFakeChatModel(responses=["backup"])
    calls = []

    async def provider(request):
        calls.append(request)
        raise failure

    middleware = ModelResilienceMiddleware(
        ModelResiliencePolicy(enabled=True, fallback_model_id=B),
        backup,
        primary_model_id=A,
    )
    expected = ValueError if type(failure) is ValueError else RuntimeResolutionError
    with pytest.raises(expected):
        asyncio.run(
            middleware.awrap_model_call(
                ModelRequest(model=model, messages=[]), provider
            )
        )
    assert len(calls) == 1


@pytest.mark.parametrize("known_profile", [True, False])
def test_fallback_cannot_drop_image_semantics(known_profile):
    primary = BindableFakeChatModel(responses=["primary"])
    backup = BindableFakeChatModel(
        responses=["backup"], profile={"image_inputs": False} if known_profile else {}
    )
    calls = []

    async def provider(request):
        calls.append(request)
        if len(calls) == 1:
            raise _error()
        assert request.messages[0].content_blocks[0]["type"] == "image"
        raise _error(400, "unsupported_image")

    middleware = ModelResilienceMiddleware(
        ModelResiliencePolicy(enabled=True, fallback_model_id=B),
        backup,
        primary_model_id=A,
    )
    request = ModelRequest(
        model=primary,
        messages=[
            HumanMessage(
                content=[
                    {
                        "type": "image_url",
                        "image_url": {"url": "https://example.com/image.png"},
                    }
                ]
            )
        ],
    )
    with pytest.raises(RuntimeResolutionError, match="fallback_incompatible") as error:
        asyncio.run(middleware.awrap_model_call(request, provider))
    assert error.value.__context__ is None
    assert len(calls) == (1 if known_profile else 2)


def test_retry_after_and_cancel_apply_to_candidate_cooldown():
    model = BindableFakeChatModel(responses=["primary"])
    backup = BindableFakeChatModel(responses=["backup"])
    policy = ModelResiliencePolicy(
        enabled=True,
        fallback_model_id=B,
        attempt_timeout_seconds=1,
        total_timeout_seconds=1,
    )
    middleware = ModelResilienceMiddleware(policy, backup, primary_model_id=A)
    calls = []

    async def provider(request):
        calls.append(request)
        raise _error(headers={"retry-after": "100"})

    with pytest.raises(RuntimeResolutionError, match="retry_budget_exceeded"):
        asyncio.run(
            middleware.awrap_model_call(
                ModelRequest(model=model, messages=[]), provider
            )
        )
    assert len(calls) == 2


def test_invocations_have_independent_budgets_and_callback_cleanup(monkeypatch):
    monkeypatch.setattr(
        "langchain.agents.middleware.model_retry.calculate_delay",
        lambda *args, **kwargs: 0,
    )
    model = BindableFakeChatModel(responses=["primary"])
    middleware = ModelResilienceMiddleware(
        ModelResiliencePolicy(enabled=True), primary_model_id=A
    )
    calls = {}

    async def provider(request):
        key = request.messages[0].content
        calls[key] = calls.get(key, 0) + 1
        await asyncio.sleep(0)
        if calls[key] < 3:
            raise _error()
        return AIMessage("result " + key)

    async def run():
        return await asyncio.gather(
            *(
                middleware.awrap_model_call(
                    ModelRequest(model=model, messages=[HumanMessage(str(i))]), provider
                )
                for i in range(8)
            )
        )

    results = asyncio.run(run())
    assert set(calls.values()) == {3}
    assert all(
        result.response_metadata["platform_model_resilience"]["attempts"] == 3
        for result in results
    )
    assert model.callbacks is None


@pytest.mark.parametrize("phase", ["provider", "cooldown"])
def test_cancel_cleans_up_provider_and_cooldown_without_followup(monkeypatch, phase):
    monkeypatch.setattr(
        "langchain.agents.middleware.model_retry.calculate_delay",
        lambda *args, **kwargs: 0,
    )
    model = BindableFakeChatModel(responses=["primary"])
    middleware = ModelResilienceMiddleware(
        ModelResiliencePolicy(enabled=True), primary_model_id=A
    )
    calls = []
    entered = asyncio.Event()
    closed = asyncio.Event()

    async def provider(request):
        calls.append(request)
        entered.set()
        if phase == "cooldown":
            raise _error(headers={"retry-after": "100"})
        try:
            await asyncio.sleep(100)
        finally:
            closed.set()

    async def run():
        task = asyncio.create_task(
            middleware.awrap_model_call(
                ModelRequest(model=model, messages=[]), provider
            )
        )
        await entered.wait()
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0)
        assert len(calls) == 1 and model.callbacks is None
        assert not [
            item for item in asyncio.all_tasks() if item is not asyncio.current_task()
        ]
        if phase == "provider":
            assert closed.is_set()

    asyncio.run(run())


def test_first_success_overhead_sample_has_no_extra_provider_calls(tmp_path):
    model = BindableFakeChatModel(responses=["primary"])

    async def sample(enabled):
        middleware = ModelResilienceMiddleware(
            ModelResiliencePolicy(enabled=enabled), primary_model_id=A
        )
        calls, timings = [], []

        async def provider(request):
            calls.append(request)
            await asyncio.sleep(0)
            return AIMessage("success")

        tracemalloc.start()
        for _ in range(20):
            start = time.perf_counter()
            await middleware.awrap_model_call(
                ModelRequest(model=model, messages=[]), provider
            )
            timings.append((time.perf_counter() - start) * 1000)
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        assert len(calls) == 20 and model.callbacks is None
        return {
            "samples": 20,
            "provider_calls": len(calls),
            "p50_ms": statistics.median(timings),
            "p95_ms": sorted(timings)[18],
            "python_peak_bytes": peak,
            "transport": "in-process handler; no network pool",
        }

    async def run():
        return {"disabled": await sample(False), "enabled": await sample(True)}

    evidence = asyncio.run(run())
    (tmp_path / "performance-evidence.json").write_text(json.dumps(evidence, indent=2))
    print(json.dumps(evidence))
