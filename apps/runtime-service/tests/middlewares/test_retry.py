from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx
import openai
import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallRequest
from langchain_core.exceptions import (
    ContextOverflowError,
    ModelAPIError,
    ModelAuthenticationError,
    ModelConnectionError,
    ModelInvalidRequestError,
    ModelPermissionDeniedError,
    ModelRateLimitError,
    ModelTimeoutError,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessageChunk, ToolMessage
from langchain_core.outputs import ChatGenerationChunk
from langgraph.errors import GraphBubbleUp

from runtime_service.middlewares import ModelCallTimeoutMiddleware, retry
from runtime_service.runtime.errors import (
    RuntimeAuthError,
    RuntimeExecutionError,
    RuntimeWorkspaceError,
)
from runtime_service.tools.errors import on_tool_error


@pytest.mark.parametrize(
    "status", [408, 429, 500, 502, 503, 504, 529, 400, 401, 403, 409, 425, 501, 505]
)
def test_typed_retry_http_whitelist(status):
    request = httpx.Request("POST", "https://provider.invalid")
    exc = openai.APIStatusError(
        "CANARY", response=httpx.Response(status, request=request), body={}
    )
    assert retry.is_transient_model_error(exc) == (
        status in {408, 429, 500, 502, 503, 504, 529}
    )
    assert not retry.is_transient_model_error(RuntimeError("rate_limit_error"))
    assert not retry.is_transient_model_error(ModelAPIError("no trusted status"))
    assert not retry.is_transient_model_error(TimeoutError("database"))


def test_typed_transport_permissions_and_causes_are_not_text_inference():
    for error in (
        ModelConnectionError("CANARY"),
        ModelTimeoutError("CANARY"),
        httpx.ReadTimeout("CANARY"),
        openai.APIConnectionError(
            request=httpx.Request("POST", "https://provider.invalid")
        ),
    ):
        assert retry.is_transient_model_error(error)
    for error in (
        ModelAuthenticationError("CANARY"),
        ModelPermissionDeniedError("CANARY"),
        ModelInvalidRequestError("rate_limit_error"),
        asyncio.CancelledError(),
    ):
        assert not retry.is_transient_model_error(error)
    fake = type("APIConnectionError", (Exception,), {})("timeout")
    fake.__cause__ = ModelConnectionError("CANARY")
    assert not retry.is_transient_model_error(fake)


@pytest.mark.parametrize(
    "code,handled",
    [
        ("context_length_exceeded", True),
        ("invalid_prompt", True),
        ("unknown", False),
        (None, False),
    ],
)
def test_only_typed_readonly_invalid_prompt_is_feedback(code, handled):
    error = ModelInvalidRequestError("CANARY")
    error.body = {"error": {"code": code}}
    value = on_tool_error(error, tool_request("research"), readonly_roles={"research"})
    assert (value is not None) == handled
    if value:
        assert (
            "CANARY" not in value and json.loads(value)["recovery"] == "correct_input"
        )
    assert (
        on_tool_error(error, tool_request("writer"), readonly_roles={"research"})
        is None
    )


def test_observation_failures_do_not_change_retry_result(monkeypatch):
    def unavailable(*args, **kwargs):
        raise RuntimeError("observation backend unavailable")

    monkeypatch.setattr(retry, "log_diagnostic", unavailable)
    middleware = retry.RuntimeModelRetryMiddleware(initial_delay=0)
    assert middleware.wrap_model_call(object(), lambda request: "ok") == "ok"
    with pytest.raises(RuntimeExecutionError, match="provider_timeout"):
        middleware.wrap_model_call(
            object(), lambda request: (_ for _ in ()).throw(ModelTimeoutError("CANARY"))
        )


def test_model_budget_success_exhaustion_unknown_and_sync_parity(monkeypatch):
    events = []
    monkeypatch.setattr(
        retry, "log_diagnostic", lambda event, fields: events.append(fields)
    )
    for async_mode in (False, True):
        for fail_count in (1, 2):
            middleware = retry.RuntimeModelRetryMiddleware(initial_delay=0)
            calls = []

            def handle(_request, calls=calls, fail_count=fail_count):
                calls.append(1)
                if len(calls) <= fail_count:
                    raise ModelRateLimitError("CANARY")
                return "ok"

            async def ahandle(request, handle=handle):
                return handle(request)

            def run(
                middleware=middleware,
                async_mode=async_mode,
                ahandle=ahandle,
                handle=handle,
            ):
                return (
                    asyncio.run(middleware.awrap_model_call(object(), ahandle))
                    if async_mode
                    else middleware.wrap_model_call(object(), handle)
                )

            if fail_count == 2:
                with pytest.raises(
                    RuntimeExecutionError, match="provider_rate_limited"
                ) as error:
                    run()
                assert "CANARY" not in str(error.value)
                assert isinstance(error.value.__cause__, ModelRateLimitError)
            else:
                assert run() == "ok"
            assert len(calls) == events[-1]["attempts"] == 2
            assert events[-1]["outcome"] == (
                "exhausted" if fail_count == 2 else "success"
            )
    for exception in (
        RuntimeAuthError("denied"),
        RuntimeWorkspaceError("unavailable"),
        ValueError("rate_limit_error"),
        GraphBubbleUp(),
    ):

        async def bad(_, exception=exception):
            raise exception

        with pytest.raises(type(exception)):
            asyncio.run(middleware.awrap_model_call(object(), bad))


def tool_request(role):
    return ToolCallRequest(
        tool_call={
            "name": "task",
            "id": "call-task",
            "args": {"subagent_type": role},
            "type": "tool_call",
        },
        tool=None,
        state={},
        runtime=SimpleNamespace(),
    )


def test_only_declared_readonly_task_retries_children_not_model_and_safe_failure(
    monkeypatch,
):
    events = []
    monkeypatch.setattr(
        retry, "log_diagnostic", lambda event, fields: events.append(fields)
    )

    async def run():
        child = retry.RuntimeModelRetryMiddleware(delegated=True, initial_delay=0)
        parent = retry.DelegatedTaskRetryMiddleware({"research"}, initial_delay=0)
        calls = []

        async def provider(_):
            calls.append(1)
            raise ModelRateLimitError("CANARY")

        async def task(_):
            return await child.awrap_model_call(object(), provider)

        result = await parent.awrap_tool_call(tool_request("research"), task)
        assert (
            result.status == "error"
            and result.tool_call_id == "call-task"
            and result.name == "task"
        )
        assert (
            "CANARY" not in result.content
            and json.loads(result.content)["recovery"] == "choose_alternative"
        )
        assert len(calls) == 2
        assert events[-1]["unit"] == "task" and events[-1]["attempts"] == 2
        calls.clear()
        for role in ("general-purpose", "unknown", ["research"]):
            with pytest.raises(ModelRateLimitError):
                await parent.awrap_tool_call(tool_request(role), task)
        assert len(calls) == 3
        with pytest.raises(RuntimeAuthError):

            async def denied(_):
                raise RuntimeAuthError("denied")

            await parent.awrap_tool_call(tool_request("research"), denied)

    asyncio.run(run())


@pytest.mark.parametrize(
    "role,handled", [("research", True), ("general-purpose", False), ("unknown", False)]
)
def test_context_tool_feedback_is_readonly_only(role, handled):
    value = on_tool_error(
        ContextOverflowError("CANARY"), tool_request(role), readonly_roles={"research"}
    )
    assert (value is not None) == handled
    if value:
        assert (
            "CANARY" not in value and json.loads(value)["recovery"] == "correct_input"
        )


def test_cancel_during_backoff_and_inner_timeout_preserved(monkeypatch):
    events = []
    monkeypatch.setattr(
        retry, "log_diagnostic", lambda event, fields: events.append(fields)
    )

    async def run():
        entered = asyncio.Event()

        async def handler(_):
            entered.set()
            raise ModelRateLimitError("rate limited")

        middleware = retry.RuntimeModelRetryMiddleware(initial_delay=10)
        task = asyncio.create_task(middleware.awrap_model_call(object(), handler))
        await entered.wait()
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert events[-1]["outcome"] == "cancelled" and events[-1]["attempts"] == 1

        async def inner(_):
            raise TimeoutError("not our deadline")

        with pytest.raises(TimeoutError):
            await ModelCallTimeoutMiddleware(1).awrap_model_call(object(), inner)

        async def slow(_):
            await asyncio.sleep(1)

        with pytest.raises(ModelTimeoutError):
            await ModelCallTimeoutMiddleware(0.01).awrap_model_call(object(), slow)

    asyncio.run(run())


class PartialModel(BaseChatModel):
    attempts: int = 0
    block: str = "text"
    first_unstreamed_failure: bool = False

    @property
    def _llm_type(self):
        return "reliability-test"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise NotImplementedError

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        self.attempts += 1
        if self.first_unstreamed_failure and self.attempts == 1:
            raise ModelRateLimitError("first failure")
        if self.block == "text":
            message = AIMessageChunk(content="visible")
        elif self.block == "reasoning":
            message = AIMessageChunk(
                content="", additional_kwargs={"reasoning_content": "visible thinking"}
            )
        else:
            message = AIMessageChunk(
                content="",
                tool_call_chunks=[
                    {"name": "task", "args": "{", "id": "tool-1", "index": 0}
                ],
            )
        chunk = ChatGenerationChunk(message=message)
        if run_manager:
            await run_manager.on_llm_new_token(message.text, chunk=chunk)
        yield chunk
        raise ModelRateLimitError("CANARY")


@pytest.mark.parametrize("block", ["text", "reasoning", "tool"])
@pytest.mark.parametrize("first_unstreamed_failure", [False, True])
def test_real_v3_partial_stream_never_retries_or_duplicates(
    monkeypatch, block, first_unstreamed_failure
):
    events, streamed = [], []
    monkeypatch.setattr(
        retry, "log_diagnostic", lambda event, fields: events.append(fields)
    )

    async def run():
        model = PartialModel(
            block=block, first_unstreamed_failure=first_unstreamed_failure
        )
        graph = create_agent(
            model, middleware=[retry.RuntimeModelRetryMiddleware(initial_delay=0)]
        )
        with pytest.raises(RuntimeExecutionError):
            async for event in graph.astream(
                {"messages": [("user", "stream")]},
                version="v3",
                stream_mode=["messages"],
            ):
                streamed.append(event)
        expected = 2 if first_unstreamed_failure else 1
        assert model.attempts == events[-1]["attempts"] == expected
        assert events[-1]["outcome"] == "failed"
        assert (
            "visible" in str(streamed) if block != "tool" else "tool-1" in str(streamed)
        )

    asyncio.run(run())


def test_parallel_partial_child_guard_isolated(monkeypatch):
    events = []
    monkeypatch.setattr(
        retry, "log_diagnostic", lambda event, fields: events.append(fields)
    )

    async def run():
        parent = retry.DelegatedTaskRetryMiddleware({"research"}, initial_delay=0)
        child = retry.RuntimeModelRetryMiddleware(delegated=True, initial_delay=0)
        counts = {"partial": 0, "clean": 0}

        async def task(request):
            key = request.tool_call["id"]

            async def model(_):
                counts[key] += 1
                if key == "partial":
                    retry._StreamGuard(retry._call.get()).on_llm_new_token(
                        "already visible"
                    )
                raise ModelRateLimitError("failed")

            return await child.awrap_model_call(object(), model)

        first, second = tool_request("research"), tool_request("research")
        first.tool_call["id"], second.tool_call["id"] = "partial", "clean"
        results = await asyncio.gather(
            parent.awrap_tool_call(first, task), parent.awrap_tool_call(second, task)
        )
        assert all(isinstance(result, ToolMessage) for result in results)
        assert counts == {"partial": 1, "clean": 2}

    asyncio.run(run())
