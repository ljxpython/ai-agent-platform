from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import ModelRequest
from langchain_core.messages import AIMessage, SystemMessage
from support import BindableFakeMessagesChatModel

from runtime_service.middlewares import (
    ModelCallTimeoutError,
    ModelCallTimeoutMiddleware,
    TimeoutWrapupMiddleware,
)
from runtime_service.middlewares.timeout_wrapup import TIMEOUT_WRAPUP_INSTRUCTION
from runtime_service.runtime.run_budget import RunBudget


def budget(reserve=20):
    return RunBudget("run", "thread", datetime.now(UTC), 100, 100, reserve)


@pytest.mark.parametrize("now,expected", [(79, False), (80, True), (81, True)])
@pytest.mark.parametrize(
    "system",
    [
        None,
        SystemMessage(content="rules"),
        SystemMessage(
            content=[
                {
                    "type": "text",
                    "text": "rules",
                    "cache_control": {"type": "ephemeral"},
                },
                {
                    "type": "image_url",
                    "image_url": {"url": "https://example.invalid/img"},
                },
            ],
            additional_kwargs={"custom": "keep"},
        ),
    ],
)
def test_wrapup_boundary_preserves_request_and_content(
    monkeypatch, now, expected, system
):
    monkeypatch.setattr(
        "runtime_service.middlewares.timeout_wrapup.monotonic", lambda: now
    )
    model = BindableFakeMessagesChatModel(responses=[AIMessage(content="ok")])
    request = ModelRequest(
        model=model, messages=[], system_message=system, state={}, runtime=None
    )
    middleware = TimeoutWrapupMiddleware(budget())
    captured = []

    async def handler(value):
        captured.append(value)
        return value

    async def run():
        changed = await middleware.awrap_model_call(request, handler)
        repeated = await middleware.awrap_model_call(changed, handler)
        assert request.system_message is system
        if expected:
            assert (
                str(changed.system_message.content).count(TIMEOUT_WRAPUP_INSTRUCTION)
                == 1
            )
            assert repeated.system_message == changed.system_message
            if system is not None:
                assert changed.system_message.content[:-1] == (
                    system.content
                    if isinstance(system.content, list)
                    else system.content_blocks
                )
                assert (
                    changed.system_message.additional_kwargs == system.additional_kwargs
                )
        else:
            assert changed is request

    asyncio.run(run())


def test_real_agent_receives_wrapup_and_disabled_budget_does_not(monkeypatch):
    monkeypatch.setattr(
        "runtime_service.middlewares.timeout_wrapup.monotonic", lambda: 90
    )
    prompts = []

    class Capture(BindableFakeMessagesChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            prompts.append(messages[0].text)
            return super()._generate(
                messages, stop=stop, run_manager=run_manager, **kwargs
            )

    for reserve in (20, 0):
        graph = create_agent(
            model=Capture(responses=[AIMessage(content="partial report")]),
            system_prompt="original",
            middleware=[TimeoutWrapupMiddleware(budget(reserve))],
        )
        asyncio.run(graph.ainvoke({"messages": [("user", "work")]}))
    assert TIMEOUT_WRAPUP_INSTRUCTION in prompts[0]
    assert prompts[1] == "original"


def test_model_timeout_source_and_cancellation_are_preserved():
    async def run():
        middleware = ModelCallTimeoutMiddleware(0.01)

        async def slow(_request):
            await asyncio.sleep(1)

        with pytest.raises(ModelCallTimeoutError, match="runtime.model_call_timeout"):
            await middleware.awrap_model_call(None, slow)
        provider_error = TimeoutError("provider")

        async def provider(_request):
            raise provider_error

        with pytest.raises(TimeoutError) as caught:
            await middleware.awrap_model_call(None, provider)
        assert caught.value is provider_error

        async def cancelled(_request):
            raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            await middleware.awrap_model_call(None, cancelled)

    asyncio.run(run())
