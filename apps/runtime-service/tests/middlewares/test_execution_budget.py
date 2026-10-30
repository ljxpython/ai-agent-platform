from __future__ import annotations

import asyncio
import json
import statistics
import time
from typing import Annotated

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelCallLimitMiddleware,
    ModelRequest,
)
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain.agents.middleware.types import AgentState, PrivateStateAttr
from langchain.tools import tool
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_config
from langgraph.errors import GraphRecursionError
from langgraph.managed.is_last_step import RemainingStepsManager
from support import BindableFakeMessagesChatModel

from runtime_service.middlewares.execution_budget import (
    WRAPUP_INSTRUCTION,
    ExecutionBudgetMiddleware,
)


@tool
def echo(value: str) -> str:
    """Return a value without side effects."""
    return value


def loop_model():
    return BindableFakeMessagesChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[{"name": "echo", "args": {"value": "ok"}, "id": "echo-1"}],
            )
        ]
    )


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("behavior", ["error", "end"])
def test_last_call_never_executes_provider_tool_request(asynchronous, behavior):
    executed = []

    @tool
    def forbidden() -> str:
        """Record a call that must not run during delivery."""
        executed.append(True)
        return "unexpected"

    model = BindableFakeMessagesChatModel(
        responses=[
            AIMessage(
                content=[
                    {
                        "type": "tool_call",
                        "name": "forbidden",
                        "args": {},
                        "id": "denied",
                    }
                ],
                tool_calls=[{"name": "forbidden", "args": {}, "id": "denied"}],
            )
        ]
    )
    graph = create_agent(
        model,
        tools=[forbidden],
        middleware=[ExecutionBudgetMiddleware(run_limit=1, exit_behavior=behavior)],
    )

    def invoke():
        inputs = {"messages": [("user", "deliver")]}
        return (
            asyncio.run(graph.ainvoke(inputs)) if asynchronous else graph.invoke(inputs)
        )

    if behavior == "error":
        with pytest.raises(ModelCallLimitExceededError):
            invoke()
    else:
        result = invoke()
        assert not result["messages"][-1].tool_calls
        assert "未完成" in result["messages"][-1].content
    assert executed == []


@pytest.mark.parametrize(
    "behavior,recursion,exception,after",
    [
        ("error", 100, ModelCallLimitExceededError, False),
        ("end", 100, None, True),
        ("end", 1, GraphRecursionError, False),
    ],
)
def test_official_limit_lifecycle(behavior, recursion, exception, after):
    completed = []

    class Observer(AgentMiddleware):
        def after_agent(self, state, runtime):
            completed.append(True)

    graph = create_agent(
        loop_model(),
        tools=[echo],
        middleware=[
            ModelCallLimitMiddleware(run_limit=1, exit_behavior=behavior),
            Observer(),
        ],
    )

    async def run():
        return await graph.ainvoke(
            {"messages": [("user", "loop")]}, {"recursion_limit": recursion}
        )

    if exception:
        with pytest.raises(exception):
            asyncio.run(run())
    else:
        assert (
            "Model call limits exceeded" in asyncio.run(run())["messages"][-1].content
        )
    assert bool(completed) is after


def test_managed_remaining_is_private_and_live():
    observed = []

    class State(AgentState):
        remaining_steps: Annotated[int, PrivateStateAttr, RemainingStepsManager]

    class Observer(AgentMiddleware):
        state_schema = State

        def before_model(self, state, runtime):
            observed.append(
                (
                    state["remaining_steps"],
                    get_config()["configurable"].get("checkpoint_ns"),
                )
            )

    graph = create_agent(
        BindableFakeMessagesChatModel(responses=[AIMessage(content="done")]),
        middleware=[Observer()],
    )
    assert "remaining_steps" not in graph.get_input_jsonschema()["properties"]
    assert "remaining_steps" not in graph.get_output_jsonschema()["properties"]
    result = graph.invoke({"messages": [("user", "hello")]}, {"recursion_limit": 20})
    assert observed[0][0] == 19
    assert "remaining_steps" not in result


def test_official_thread_budget_survives_graph_rebuild():
    saver = InMemorySaver()
    config = {"configurable": {"thread_id": "thread-budget"}, "recursion_limit": 100}
    for _ in range(2):
        graph = create_agent(
            BindableFakeMessagesChatModel(responses=[AIMessage(content="done")]),
            middleware=[ModelCallLimitMiddleware(run_limit=1, thread_limit=2)],
            checkpointer=saver,
        )
        assert (
            graph.invoke({"messages": [("user", "hello")]}, config)["messages"][
                -1
            ].content
            == "done"
        )
    graph = create_agent(
        loop_model(),
        tools=[echo],
        middleware=[ModelCallLimitMiddleware(run_limit=1, thread_limit=2)],
        checkpointer=saver,
    )
    result = graph.invoke({"messages": [("user", "hello")]}, config)
    assert "thread limit (2/2)" in result["messages"][-1].content


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("behavior", ["end", "error"])
def test_model_budget_notice_and_original_exit(asynchronous, behavior):
    notices, prompts = [], []

    class Capture(AgentMiddleware):
        def wrap_model_call(self, request, handler):
            prompts.append(
                request.system_message.content if request.system_message else None
            )
            return handler(request)

        async def awrap_model_call(self, request, handler):
            prompts.append(
                request.system_message.content if request.system_message else None
            )
            return await handler(request)

    graph = create_agent(
        loop_model(),
        tools=[echo],
        middleware=[
            ExecutionBudgetMiddleware(
                run_limit=5,
                warning_calls=2,
                exit_behavior=behavior,
                writer=notices.append,
            ),
            Capture(),
        ],
    )
    config = {"recursion_limit": 100, "metadata": {"run_id": "run-1"}}

    def run():
        if asynchronous:
            return asyncio.run(graph.ainvoke({"messages": [("user", "loop")]}, config))
        return graph.invoke({"messages": [("user", "loop")]}, config)

    if behavior == "error":
        with pytest.raises(ModelCallLimitExceededError) as error:
            run()
        assert error.value.run_count == 5
    else:
        marker = run()["messages"][-1].additional_kwargs["runtime_budget_notice"]
        assert marker == notices[-1]
    assert [n["code"] for n in notices] == [
        "model_call_limit_approaching",
        "model_call_limit_reached",
    ]
    assert notices[0]["remaining"] == 2
    assert len(prompts) == 5
    assert all(p is None for p in prompts[:3])
    assert all(WRAPUP_INSTRUCTION in p for p in prompts[3:])


def test_natural_last_call_and_literal_marker_do_not_report_stop():
    notices = []
    graph = create_agent(
        BindableFakeMessagesChatModel(
            responses=[
                AIMessage(content="Model call limits exceeded is a quoted phrase")
            ]
        ),
        middleware=[ExecutionBudgetMiddleware(run_limit=1, writer=notices.append)],
    )
    result = graph.invoke(
        {"messages": [("user", "hello")]}, {"metadata": {"run_id": "run-1"}}
    )
    assert not result["messages"][-1].additional_kwargs
    assert [n["code"] for n in notices] == ["model_call_limit_approaching"]
    assert not any("runtime_budget" in key or "call_count" in key for key in result)


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize(
    "scope,count,expected_tools",
    [
        ("run", 2, True),
        ("run", 3, False),
        ("thread", 2, True),
        ("thread", 3, False),
    ],
)
def test_last_model_call_reserves_tool_free_delivery(
    asynchronous, scope, count, expected_tools
):
    middleware = ExecutionBudgetMiddleware(**{f"{scope}_limit": 4})
    request = ModelRequest(
        model=loop_model(),
        messages=[],
        tools=[echo],
        state={f"{scope}_model_call_count": count, "runtime_budget_wrapup": True},
        model_settings={"temperature": 0.25},
    )
    seen = []

    def capture(updated):
        seen.append(updated)
        return None

    async def acapture(updated):
        return capture(updated)

    if asynchronous:
        asyncio.run(middleware.awrap_model_call(request, acapture))
    else:
        middleware.wrap_model_call(request, capture)
    assert seen[0].tools == ([echo] if expected_tools else [])
    assert seen[0].tool_choice == (None if expected_tools else "none")
    assert WRAPUP_INSTRUCTION in seen[0].system_message.content
    assert request.tools == [echo]
    assert request.model_settings == {"temperature": 0.25}
    assert seen[0].model_settings == (
        {"temperature": 0.25}
        if expected_tools
        else {"temperature": 0.25, "tool_choice": "none"}
    )


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("protocol", ["openai", "anthropic"])
def test_delivery_disables_tools_in_provider_request(
    asynchronous, protocol, monkeypatch
):
    import httpx
    from langchain_anthropic import ChatAnthropic
    from langchain_openai import ChatOpenAI

    payloads = []

    def respond(request):
        payloads.append(json.loads(request.content))
        reply = {
            "id": "delivery",
            "object": "chat.completion",
            "created": 0,
            "model": "test",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "done"},
                    "finish_reason": "stop",
                }
            ],
        }
        if protocol == "anthropic":
            reply = {
                "id": "delivery",
                "type": "message",
                "role": "assistant",
                "model": "test",
                "content": [{"type": "text", "text": "done"}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 10, "output_tokens": 1},
            }
        return httpx.Response(200, json=reply)

    def build_model(client, asynchronous):
        if protocol == "anthropic":
            factory = (
                "_get_default_async_httpx_client"
                if asynchronous
                else "_get_default_httpx_client"
            )
            monkeypatch.setattr(
                f"langchain_anthropic.chat_models.{factory}", lambda **kwargs: client
            )
            return ChatAnthropic(model="test", api_key="test")
        kwargs = {"http_async_client" if asynchronous else "http_client": client}
        return ChatOpenAI(model="test", api_key="test", **kwargs)

    async def invoke():
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            model = build_model(client, True)
            graph = create_agent(
                model, tools=[echo], middleware=[ExecutionBudgetMiddleware(run_limit=1)]
            )
            return await graph.ainvoke({"messages": [("user", "report now")]})

    if asynchronous:
        result = asyncio.run(invoke())
    else:
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            model = build_model(client, False)
            graph = create_agent(
                model, tools=[echo], middleware=[ExecutionBudgetMiddleware(run_limit=1)]
            )
            result = graph.invoke({"messages": [("user", "report now")]})
    assert result["messages"][-1].text == "done"
    assert payloads[0].get("tool_choice") == (
        {"type": "none"} if protocol == "anthropic" else "none"
    )
    assert not payloads[0].get("tools")


def test_serial_runs_and_rebuilt_thread_keep_distinct_latches():
    saver = InMemorySaver()
    notices = []
    for index in range(3):
        graph = create_agent(
            BindableFakeMessagesChatModel(responses=[AIMessage(content="done")]),
            middleware=[
                ExecutionBudgetMiddleware(
                    run_limit=1, thread_limit=2, writer=notices.append
                )
            ],
            checkpointer=saver,
        )
        result = graph.invoke(
            {"messages": [("user", "hello")]},
            {
                "configurable": {"thread_id": "budget-thread"},
                "metadata": {"run_id": f"run-{index}"},
            },
        )
        if index == 2:
            assert (
                result["messages"][-1].additional_kwargs["runtime_budget_notice"][
                    "budget_scope"
                ]
                == "thread"
            )
    assert len({n["notice_id"] for n in notices}) == len(notices)
    assert any(n["run_id"] == "run-1" and n["budget_scope"] == "run" for n in notices)


def test_low_recursion_has_no_after_agent_dependency():
    graph = create_agent(
        loop_model(), tools=[echo], middleware=[ExecutionBudgetMiddleware(run_limit=50)]
    )
    with pytest.raises(GraphRecursionError):
        graph.invoke({"messages": [("user", "loop")]}, {"recursion_limit": 1})


def test_graph_remaining_notice_is_once_per_graph():
    notices = []
    graph = create_agent(
        loop_model(),
        tools=[echo],
        middleware=[
            ExecutionBudgetMiddleware(
                run_limit=50, warning_steps=8, writer=notices.append
            ),
        ],
    )
    with pytest.raises(GraphRecursionError):
        graph.invoke(
            {"messages": [("user", "loop")]},
            {
                "recursion_limit": 20,
                "metadata": {"run_id": "run-1"},
            },
        )
    assert [n["code"] for n in notices] == ["graph_step_limit_approaching"]
    assert 0 < notices[0]["remaining"] <= 8
    assert notices[0]["unit"] == "graph_supersteps"


def test_writer_failure_keeps_original_limit_exception(monkeypatch):
    from langgraph.runtime import Runtime

    from runtime_service.middlewares import execution_budget

    original = ModelCallLimitExceededError(0, 1, None, 1)

    def fail_limit(self, state, runtime):
        raise original

    def fail_writer(notice):
        raise OSError("delivery failure")

    monkeypatch.setattr(ModelCallLimitMiddleware, "before_model", fail_limit)
    monkeypatch.setattr(
        execution_budget, "get_config", lambda: {"metadata": {"run_id": "run-failure"}}
    )
    middleware = ExecutionBudgetMiddleware(run_limit=1, writer=fail_writer)
    with pytest.raises(ModelCallLimitExceededError) as error:
        middleware.before_model({"run_model_call_count": 1}, Runtime())
    assert error.value is original


def test_budget_extension_preserves_official_graph_cost(capsys):
    results = {}
    for name, middleware in (
        ("official", ModelCallLimitMiddleware(run_limit=2)),
        ("budget", ExecutionBudgetMiddleware(run_limit=2)),
    ):
        graph = create_agent(loop_model(), tools=[echo], middleware=[middleware])
        durations = []
        for index in range(6):
            started = time.perf_counter()
            events = list(
                graph.stream(
                    {"messages": [("user", "loop")]},
                    {"recursion_limit": 100, "metadata": {"run_id": f"cost-{index}"}},
                    stream_mode="updates",
                )
            )
            if index:
                durations.append(1000 * (time.perf_counter() - started))
        calls = sum("model" in event for event in events)
        assert calls == 2
        results[name] = {
            "model_calls": calls,
            "supersteps": len(events),
            "median_ms": round(statistics.median(durations), 3),
        }
    assert results["budget"]["supersteps"] <= results["official"]["supersteps"]
    with capsys.disabled():
        print("budget-cost " + json.dumps(results))


def test_notification_control_flow_is_not_swallowed(monkeypatch):
    from langgraph.errors import GraphInterrupt
    from langgraph.runtime import Runtime

    from runtime_service.middlewares import execution_budget

    monkeypatch.setattr(
        execution_budget, "get_config", lambda: {"metadata": {"run_id": "control-flow"}}
    )
    for original in (asyncio.CancelledError(), GraphInterrupt(())):

        def interrupted_writer(notice, error=original):
            raise error

        with pytest.raises(type(original)) as error:
            execution_budget.emit_budget_notice(
                execution_budget.build_budget_notice(
                    code="wrapup_started", budget_scope="run", unit="seconds"
                ),
                Runtime(),
                writer=interrupted_writer,
            )
        assert error.value is original
