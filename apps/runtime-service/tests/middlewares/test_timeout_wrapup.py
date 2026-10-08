from __future__ import annotations

import asyncio

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ModelRequest
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.checkpoint.memory import InMemorySaver
from support import BindableFakeMessagesChatModel

from runtime_service.middlewares.execution_budget import (
    WRAPUP_INSTRUCTION,
    add_wrapup_instruction,
)
from runtime_service.middlewares.timeout_wrapup import (
    TimeoutWrapupMiddleware,
    resolve_wrapup_after_seconds,
)


@pytest.mark.parametrize("value", [True, 0, -1, float("nan"), float("inf"), "oops"])
def test_invalid_soft_threshold_is_rejected(value):
    with pytest.raises(ValueError):
        TimeoutWrapupMiddleware(value)


@pytest.mark.parametrize("value", ["0", "-1", "NaN", "Infinity", "oops"])
def test_invalid_explicit_environment_is_rejected(monkeypatch, value):
    monkeypatch.setenv("AGENT_WRAPUP_AFTER_SECONDS", value)
    with pytest.raises(ValueError):
        resolve_wrapup_after_seconds()


def test_soft_timeout_defaults_off(monkeypatch):
    monkeypatch.delenv("AGENT_WRAPUP_AFTER_SECONDS", raising=False)
    assert resolve_wrapup_after_seconds() is None
    monkeypatch.setenv("AGENT_WRAPUP_AFTER_SECONDS", "1.5")
    assert resolve_wrapup_after_seconds() == 1.5


def test_structured_system_blocks_and_metadata_survive_idempotent_wrapup():
    model = BindableFakeMessagesChatModel(responses=[AIMessage(content="done")])
    message = SystemMessage(
        content=[
            {"type": "text", "text": "original", "cache_control": {"type": "ephemeral"}}
        ],
        additional_kwargs={"custom": "preserved"},
    )
    request = ModelRequest(
        model=model, messages=[], system_message=message, state={}, runtime=None
    )
    once = add_wrapup_instruction(request)
    twice = add_wrapup_instruction(once)
    assert twice is once
    assert once.system_message.additional_kwargs == message.additional_kwargs
    assert once.system_message.content[0] == message.content[0]
    assert once.system_message.content[1]["text"] == WRAPUP_INSTRUCTION
    assert len(message.content) == 1


def test_clock_resets_for_serial_invocations_and_is_not_checkpointed():
    now = [0.0]
    notices, prompts = [], []

    class Advance(AgentMiddleware):
        def before_model(self, state, runtime):
            now[0] += 10

        async def abefore_model(self, state, runtime):
            return self.before_model(state, runtime)

    class Capture(AgentMiddleware):
        async def awrap_model_call(self, request, handler):
            prompts.append(
                request.system_message.content if request.system_message else None
            )
            return await handler(request)

    graph = create_agent(
        BindableFakeMessagesChatModel(responses=[AIMessage(content="done")]),
        middleware=[
            Advance(),
            TimeoutWrapupMiddleware(10, clock=lambda: now[0], writer=notices.append),
            Capture(),
        ],
        checkpointer=InMemorySaver(),
    )

    async def run():
        for index in range(3):
            result = await graph.ainvoke(
                {"messages": [("user", "hello")]},
                {
                    "metadata": {"run_id": f"run-{index}"},
                    "configurable": {"thread_id": "soft-clock"},
                },
            )
            assert not any(key.startswith("runtime_wrapup") for key in result)
            checkpoint = await graph.aget_state(
                {"configurable": {"thread_id": "soft-clock"}}
            )
            assert not any(
                key.startswith("runtime_wrapup") for key in checkpoint.values
            )
            now[0] += 1000

    asyncio.run(run())
    assert [n["used"] for n in notices] == [10, 10, 10]
    assert len(prompts) == 3
    assert all(WRAPUP_INSTRUCTION in prompt for prompt in prompts)


def test_parallel_invocations_have_independent_soft_clocks():
    from langgraph.config import get_config

    notices = []

    def clock():
        metadata = get_config()["metadata"]
        start = 1000.0 * int(metadata["run_id"][-1])
        return start + (
            11 if metadata["langgraph_node"].endswith(".before_model") else 0
        )

    graph = create_agent(
        BindableFakeMessagesChatModel(responses=[AIMessage(content="done")]),
        middleware=[TimeoutWrapupMiddleware(10, clock=clock, writer=notices.append)],
    )

    async def run_one(index):
        await graph.ainvoke(
            {"messages": [("user", "hello")]},
            {"metadata": {"run_id": f"parallel-{index}"}},
        )

    async def run():
        await asyncio.gather(*(run_one(index) for index in range(2)))

    asyncio.run(run())
    assert sorted(n["used"] for n in notices) == [11, 11]
    assert len({n["run_id"] for n in notices}) == 2


def test_soft_boundary_and_cancel_do_not_add_a_model_call(monkeypatch):
    from langgraph.runtime import Runtime

    from runtime_service.middlewares import execution_budget

    monkeypatch.setattr(
        execution_budget, "get_config", lambda: {"metadata": {"run_id": "run-clock"}}
    )
    now = [0.0]
    notices = []
    middleware = TimeoutWrapupMiddleware(
        10, clock=lambda: now[0], writer=notices.append
    )
    state = middleware.before_agent({}, Runtime())
    for timestamp, triggered in ((9.0, False), (10.0, True), (20.0, True)):
        now[0] = timestamp
        state.update(middleware.before_model(state, Runtime()))
        assert state["runtime_wrapup_started"] is triggered
    assert len(notices) == 1
    model = BindableFakeMessagesChatModel(responses=[AIMessage(content="done")])
    request = ModelRequest(model=model, messages=[], state=state, runtime=Runtime())

    async def cancelled(request):
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(middleware.awrap_model_call(request, cancelled))
