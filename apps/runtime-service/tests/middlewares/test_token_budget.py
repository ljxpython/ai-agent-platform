import asyncio
from importlib import import_module
from uuid import uuid4

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware, SummarizationMiddleware
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from pydantic import PrivateAttr
from support import BindableFakeMessagesChatModel

from runtime_service.db.repositories import usage as repository
from runtime_service.middlewares.retry import RuntimeModelRetryMiddleware
from runtime_service.middlewares.token_budget import TokenBudgetMiddleware
from runtime_service.observability.usage import (
    RuntimeUsageCallback,
    usage_only_config,
    with_runtime_usage,
)
from runtime_service.runtime.errors import (
    TokenBudgetExceededError,
    TokenBudgetUnverifiableError,
)


class CountingModel(BindableFakeMessagesChatModel):
    _requests = PrivateAttr(default=0)

    def _generate(self, *args, **kwargs):
        self._requests += 1
        return super()._generate(*args, **kwargs)


def message(total=10, **kwargs):
    return AIMessage(
        content="done",
        usage_metadata={
            "input_tokens": total,
            "output_tokens": 0,
            "total_tokens": total,
        },
        **kwargs,
    )


@pytest.fixture
def ledger(monkeypatch):
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_TOKEN_BUDGET_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_TOKEN_BUDGET_MAX_TOKENS", "10")
    writes = []
    monkeypatch.setattr(
        repository, "begin_collection", lambda *args: writes.append(args)
    )
    monkeypatch.setattr(repository, "upsert_call", lambda *args: writes.append(args))
    monkeypatch.setattr(
        repository, "finish_collection", lambda *args: writes.append(args)
    )
    monkeypatch.setattr(
        repository,
        "read_budget",
        lambda identity: {
            "policy": {"version": 1, "max_tokens": 10, "warn_at_tokens": 8},
            "used_tokens": 0,
            "unverifiable": False,
            "stop_code": None,
            "calls": [],
        },
    )
    return writes


def bound(graph):
    return with_runtime_usage(
        graph,
        {"metadata": {"thread_id": str(uuid4()), "run_id": str(uuid4())}},
        graph_id="token-test",
        trusted_metadata={"tenant_id": "t", "project_id": "p"},
    )


@pytest.mark.parametrize("asynchronous", [False, True])
def test_real_dispatch_guard_blocks_second_hidden_call(ledger, asynchronous):
    model = CountingModel(responses=[message()])
    builder = StateGraph(dict)

    def invoke(state):
        model.invoke("one")
        model.invoke("two")
        return {}

    async def ainvoke(state):
        await model.ainvoke("one")
        await model.ainvoke("two")
        return {}

    builder.add_node("model", ainvoke if asynchronous else invoke)
    builder.add_edge(START, "model")
    builder.add_edge("model", END)
    graph = bound(builder.compile())
    with pytest.raises(TokenBudgetExceededError):
        if asynchronous:
            asyncio.run(graph.ainvoke({}))
        else:
            graph.invoke({})
    assert model._requests == 1
    usage = next(
        c for c in graph.config["callbacks"] if isinstance(c, RuntimeUsageCallback)
    )
    assert len(usage._calls) == 1 and usage.token_budget.used_tokens == 10
    assert ledger[-1][-1] == "token_budget_exhausted"


def test_async_callback_alone_is_not_a_sync_dispatch_guard():
    class Refuse(AsyncCallbackHandler):
        raise_error = True
        run_inline = True

        async def on_chat_model_start(self, *args, **kwargs):
            raise TokenBudgetExceededError()

    model = CountingModel(responses=[message()])
    model.invoke("probe", config={"callbacks": [Refuse()]})
    assert model._requests == 1


@pytest.mark.parametrize("asynchronous", [False, True])
def test_cap_refuses_tool_before_side_effect_and_preserves_precise_error(
    ledger, asynchronous
):
    effects = []

    @tool
    def write_file() -> str:
        """Write a test file."""
        effects.append("written")
        return "written"

    model = CountingModel(
        responses=[
            message(
                tool_calls=[
                    {
                        "name": "write_file",
                        "args": {},
                        "id": "write-1",
                    }
                ]
            )
        ]
    )
    graph = bound(
        create_agent(model, tools=[write_file], middleware=[TokenBudgetMiddleware()])
    )
    with pytest.raises(TokenBudgetExceededError):
        if asynchronous:
            asyncio.run(graph.ainvoke({"messages": [("user", "write")]}))
        else:
            graph.invoke({"messages": [("user", "write")]})
    assert not effects and model._requests == 1


@pytest.mark.parametrize("asynchronous", [False, True])
def test_unknown_usage_cannot_be_retried_or_fallback(ledger, asynchronous):
    class Fail(CountingModel):
        def _generate(self, *args, **kwargs):
            self._requests += 1
            raise ConnectionError("provider unavailable")

    primary = Fail(responses=[message()])
    fallback = CountingModel(responses=[message()])
    graph = bound(
        create_agent(
            primary,
            middleware=[
                TokenBudgetMiddleware(),
                ModelFallbackMiddleware(fallback),
                RuntimeModelRetryMiddleware(initial_delay=0),
            ],
        )
    )
    with pytest.raises(TokenBudgetUnverifiableError):
        if asynchronous:
            asyncio.run(graph.ainvoke({"messages": [("user", "hello")]}))
        else:
            graph.invoke({"messages": [("user", "hello")]})
    assert primary._requests == 1 and fallback._requests == 0


def test_natural_final_answer_at_cap_is_success(ledger):
    model = CountingModel(responses=[message()])
    graph = bound(create_agent(model, middleware=[TokenBudgetMiddleware()]))
    assert (
        asyncio.run(graph.ainvoke({"messages": [("user", "hello")]}))["messages"][
            -1
        ].content
        == "done"
    )
    usage = next(
        c for c in graph.config["callbacks"] if isinstance(c, RuntimeUsageCallback)
    )
    assert usage.token_budget.public_snapshot()["stop_code"] is None


def test_warning_at_natural_final_answer_is_emitted_once(ledger):
    async def run():
        notices = []
        graph = bound(
            create_agent(
                CountingModel(responses=[message(8)]),
                middleware=[TokenBudgetMiddleware(writer=notices.append)],
            )
        )
        await graph.ainvoke({"messages": [("user", "finish")]})
        assert [notice["code"] for notice in notices] == ["token_budget_approaching"]
        assert notices[0]["used"] == 8

    asyncio.run(run())


def test_warning_writer_failure_does_not_fail_or_repeat_dispatch(ledger):
    writes = []

    def unavailable_writer(notice):
        writes.append(notice["code"])
        raise ConnectionError("synthetic stream unavailable")

    graph = bound(
        create_agent(
            CountingModel(responses=[message(8)]),
            middleware=[TokenBudgetMiddleware(writer=unavailable_writer)],
        )
    )
    assert (
        asyncio.run(graph.ainvoke({"messages": [("user", "finish")]}))["messages"][
            -1
        ].content
        == "done"
    )
    usage = next(
        c for c in graph.config["callbacks"] if isinstance(c, RuntimeUsageCallback)
    )
    usage._emit_budget_notice("token_budget_approaching")
    assert writes == ["token_budget_approaching"]
    assert usage.token_budget.stop_code is None


@pytest.mark.parametrize("field", ["tenant_id", "project_id", "thread_id", "run_id"])
def test_enabled_budget_requires_trusted_native_run_identity(ledger, field):
    graph = create_agent(CountingModel(responses=[message()]))
    config = {"metadata": {"thread_id": str(uuid4()), "run_id": str(uuid4())}}
    trusted = {"tenant_id": "t", "project_id": "p"}
    (trusted if field in trusted else config["metadata"]).pop(field)
    with pytest.raises(TokenBudgetUnverifiableError):
        with_runtime_usage(
            graph, config, graph_id="token-test", trusted_metadata=trusted
        )
    assert not ledger


@pytest.mark.parametrize(
    "service",
    ["dearflow_agent", "demo.showcase_demo", "reference_agent", "demo.workflow_demo"],
)
def test_enabled_budget_schema_probe_has_no_usage_model_or_network_io(
    monkeypatch, service
):
    monkeypatch.setenv("RUNTIME_TOKEN_BUDGET_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "true")
    module = import_module("runtime_service.services." + service + ".agent")

    def forbidden(*args, **kwargs):
        pytest.fail("schema probe attempted execution I/O")

    monkeypatch.setattr(module, "build_model", forbidden)
    monkeypatch.setattr(module, "fetch_model_bundle", forbidden)
    for name in ("begin_collection", "read_budget", "upsert_call"):
        monkeypatch.setattr(repository, name, forbidden)

    async def probe():
        graph = await module.get_agent({"configurable": {"graph_id": service}})
        graph.get_input_jsonschema()
        graph.get_output_jsonschema()
        assert "token_budget" not in str(graph.get_context_jsonschema())

    asyncio.run(probe())


@pytest.mark.parametrize("purpose", ["vision", "memory_extraction", "summarization"])
def test_hidden_usage_only_config_cannot_bypass_dispatch(ledger, purpose):
    model = CountingModel(responses=[message()])

    async def node(state):
        await model.ainvoke("first", config=usage_only_config(purpose))
        await model.ainvoke("second", config=usage_only_config(purpose))
        return {}

    builder = StateGraph(dict)
    builder.add_node("hidden", node)
    builder.add_edge(START, "hidden")
    builder.add_edge("hidden", END)
    graph = bound(builder.compile())
    with pytest.raises(TokenBudgetExceededError):
        asyncio.run(graph.ainvoke({}))
    assert model._requests == 1
    usage = next(
        c for c in graph.config["callbacks"] if isinstance(c, RuntimeUsageCallback)
    )
    assert next(iter(usage._calls.values()))["purpose"] == purpose


def test_official_summary_consumes_shared_cap_before_primary_model(ledger):
    summary = CountingModel(responses=[message()])
    main = CountingModel(responses=[message()])
    graph = bound(
        create_agent(
            main,
            middleware=[
                TokenBudgetMiddleware(),
                SummarizationMiddleware(
                    model=summary, trigger=("messages", 4), keep=("messages", 2)
                ),
            ],
        )
    )
    with pytest.raises(TokenBudgetExceededError):
        asyncio.run(
            graph.ainvoke(
                {
                    "messages": [
                        HumanMessage(content="one"),
                        AIMessage(content="two"),
                        HumanMessage(content="three"),
                        AIMessage(content="four"),
                        HumanMessage(content="five"),
                    ]
                }
            )
        )
    assert summary._requests == 1 and main._requests == 0


def test_parallel_inflight_calls_finish_but_no_additional_dispatch(ledger):
    class BarrierModel(CountingModel):
        async def _agenerate(self, *args, **kwargs):
            self._requests += 1
            if self._requests == 2:
                ready.set()
            await ready.wait()
            return BindableFakeMessagesChatModel._generate(self, *args, **kwargs)

    async def run():
        nonlocal ready
        ready = asyncio.Event()
        model = BarrierModel(responses=[message(6)])

        async def node(state):
            await asyncio.gather(model.ainvoke("one"), model.ainvoke("two"))
            await model.ainvoke("three")
            return {}

        builder = StateGraph(dict)
        builder.add_node("parallel", node)
        builder.add_edge(START, "parallel")
        builder.add_edge("parallel", END)
        graph = bound(builder.compile())
        with pytest.raises(TokenBudgetExceededError):
            await graph.ainvoke({})
        usage = next(
            c for c in graph.config["callbacks"] if isinstance(c, RuntimeUsageCallback)
        )
        assert model._requests == 2 and usage.token_budget.used_tokens == 12

    ready = None
    asyncio.run(run())


@pytest.mark.parametrize("failure", ["begin_collection", "read_budget", "upsert_call"])
def test_ledger_failure_refuses_new_work_and_remains_degraded(
    ledger, monkeypatch, failure
):
    def fail(*args):
        raise ConnectionError("synthetic ledger unavailable")

    monkeypatch.setattr(repository, failure, fail)
    model = CountingModel(responses=[message(4)])

    async def node(state):
        await model.ainvoke("one")
        await model.ainvoke("two")
        return {}

    builder = StateGraph(dict)
    builder.add_node("fault", node)
    builder.add_edge(START, "fault")
    builder.add_edge("fault", END)
    graph = bound(builder.compile())
    with pytest.raises(TokenBudgetUnverifiableError):
        asyncio.run(graph.ainvoke({}))
    assert model._requests == 0
    usage = next(
        c for c in graph.config["callbacks"] if isinstance(c, RuntimeUsageCallback)
    )
    assert usage.token_budget.unverifiable


def test_memory_optional_postprocessing_skips_exhausted_budget(ledger, monkeypatch):
    from runtime_service.services.dearflow_agent.middleware import memory

    model = CountingModel(responses=[message()])

    async def node(state):
        answer = await model.ainvoke("final answer")
        await memory.MemoryContextMiddleware(model).aafter_agent({}, object())
        return {"answer": answer.content}

    builder = StateGraph(dict)
    builder.add_node("final", node)
    builder.add_edge(START, "final")
    builder.add_edge("final", END)
    assert asyncio.run(bound(builder.compile()).ainvoke({}))["answer"] == "done"
    assert model._requests == 1


def test_disabled_budget_has_no_extra_budget_read(ledger, monkeypatch):
    monkeypatch.setenv("RUNTIME_TOKEN_BUDGET_ENABLED", "false")

    def reject_read(*args):
        pytest.fail("disabled budget attempted a recovery read")

    monkeypatch.setattr(repository, "read_budget", reject_read)
    graph = bound(create_agent(CountingModel(responses=[message()])))
    assert (
        asyncio.run(graph.ainvoke({"messages": [("user", "done")]}))["messages"][
            -1
        ].content
        == "done"
    )
