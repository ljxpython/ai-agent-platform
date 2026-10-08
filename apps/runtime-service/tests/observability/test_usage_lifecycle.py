import asyncio
import importlib
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from support import BindableFakeMessagesChatModel

from runtime_service.observability.usage import RuntimeUsageCallback, with_runtime_usage
from tests.observability.test_usage import price, response


def bound(graph, **kwargs):
    return with_runtime_usage(
        graph,
        {"metadata": {"thread_id": str(uuid4()), "run_id": str(uuid4())}, **kwargs},
        graph_id="lifecycle",
        trusted_metadata={"tenant_id": "t", "project_id": "p"},
    )


def model(contents):
    return BindableFakeMessagesChatModel(
        responses=[
            AIMessage(
                content=c,
                usage_metadata={
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "total_tokens": 15,
                },
            )
            for c in contents
        ],
        metadata={
            "runtime_usage_model": {
                "provider": "openai",
                "model_name": "test",
                "model_id": str(uuid4()),
                "pricing": price(),
            }
        },
    )


def test_sync_stategraph_human_queue_and_parallel_models(monkeypatch):
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "true")

    async def write(self, *args):
        pass

    monkeypatch.setattr(RuntimeUsageCallback, "_write", write)
    chat = model(["one", "two"])
    builder = StateGraph(dict)

    def sync(state):
        chat.invoke("hello")
        return {}

    builder.add_node("sync", sync)
    builder.add_edge(START, "sync")
    builder.add_edge("sync", END)
    graph = bound(builder.compile())
    graph.invoke({})
    handler = graph.config["callbacks"][0]
    assert len(handler._calls) == 1 and not handler._active

    async def parallel(state):
        await asyncio.gather(chat.ainvoke("one"), chat.ainvoke("two"))
        return {}

    builder = StateGraph(dict)
    builder.add_node("parallel", parallel)
    builder.add_edge(START, "parallel")
    builder.add_edge("parallel", END)
    graph = bound(builder.compile())
    asyncio.run(graph.ainvoke({}))
    assert len(graph.config["callbacks"][0]._calls) == 2
    queued = bound(create_agent(model(["done"])))
    asyncio.run(
        queued.ainvoke(
            {"messages": [HumanMessage(content="one"), HumanMessage(content="two")]}
        )
    )
    assert len(queued.config["callbacks"][0]._calls) == 1


def test_summarization_call_and_actual_model_identity(monkeypatch):
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "true")

    async def write(self, *args):
        pass

    monkeypatch.setattr(RuntimeUsageCallback, "_write", write)
    summary = model(["short summary"])
    main = model(["answer"])
    graph = bound(
        create_agent(
            main,
            middleware=[
                SummarizationMiddleware(
                    model=summary, trigger=("messages", 4), keep=("messages", 2)
                )
            ],
        )
    )
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
    calls = graph.config["callbacks"][0]._calls.values()
    assert len(calls) == 2
    assert {c["model_id"] for c in calls} == {
        main.metadata["runtime_usage_model"]["model_id"],
        summary.metadata["runtime_usage_model"]["model_id"],
    }
    assert any(c["purpose"] == "summarization" for c in calls)


def test_hitl_resume_has_independent_native_run_identity(monkeypatch):
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "true")

    async def write(self, *args):
        pass

    monkeypatch.setattr(RuntimeUsageCallback, "_write", write)
    chat = model(["after approval"])

    async def node(state):
        interrupt({"approval": "read"})
        await chat.ainvoke("continue")
        return {}

    builder = StateGraph(dict)
    builder.add_node("approval", node)
    builder.add_edge(START, "approval")
    builder.add_edge("approval", END)
    graph = builder.compile(checkpointer=InMemorySaver())
    first = bound(graph, configurable={"thread_id": "test-thread"})
    assert asyncio.run(first.ainvoke({}))["__interrupt__"]
    assert not first.config["callbacks"][0]._calls
    second = bound(graph, configurable={"thread_id": "test-thread"})
    asyncio.run(second.ainvoke(Command(resume=True)))
    assert len(second.config["callbacks"][0]._calls) == 1
    assert (
        second.config["callbacks"][0].identity["run_id"]
        != first.config["callbacks"][0].identity["run_id"]
    )


def test_late_error_usage_and_original_cancellation(monkeypatch):
    events = []

    async def write(self, name, *args):
        events.append((name, args))

    monkeypatch.setattr(RuntimeUsageCallback, "_write", write)
    handler = RuntimeUsageCallback(
        dict(
            tenant_id="t",
            project_id="p",
            graph_id="g",
            run_id=str(uuid4()),
            thread_id=str(uuid4()),
        )
    )
    root, child, call = uuid4(), uuid4(), uuid4()

    async def run():
        await handler.on_chain_start(None, {}, run_id=root)
        await handler.on_chain_start(None, {}, run_id=child, parent_run_id=root)
        await handler.on_chat_model_start(None, [], run_id=call, parent_run_id=child)
        await handler.on_chain_end({}, run_id=child)
        assert handler._active
        await handler.on_chain_error(asyncio.CancelledError(), run_id=root)
        await handler.on_llm_error(
            asyncio.CancelledError(),
            run_id=call,
            response=response(
                {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
            ),
        )

    asyncio.run(run())
    assert (
        handler._calls[call]["outcome"] == "cancelled"
        and handler._calls[call]["tokens"]["total_tokens"] == 15
    )
    assert [name for name, _ in events].count("finish_collection") == 1
    assert handler._calls[call]["ended_at"] >= datetime.now(UTC).isoformat()[:10]


@pytest.mark.parametrize(
    "service",
    ["demo.backend_demo", "demo.mcp_demo", "demo.deep_agent_demo", "dearflow_agent"],
)
def test_existing_graph_composition_roots_collect_usage(monkeypatch, tmp_path, service):
    from runtime_service.runtime import RuntimeContext, runtime_context_hash

    module = importlib.import_module("runtime_service.services." + service + ".agent")
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("RUNTIME_DEAR_GOVERNANCE_ENABLED", "0")

    async def write(self, *args):
        pass

    monkeypatch.setattr(RuntimeUsageCallback, "_write", write)
    chat = model(["done"])
    if service == "dearflow_agent":

        class AuthUser(dict):
            identity = "u"
            is_authenticated = True

        thread, run = str(uuid4()), str(uuid4())
        monkeypatch.setattr(module, "build_model", lambda *args, **kwargs: chat)
        cfg = {
            "metadata": {"thread_id": thread, "run_id": run},
            "context": {},
            "configurable": {
                "thread_id": thread,
                "graph_id": "dearflow_agent",
                "langgraph_auth_user": AuthUser(
                    {
                        "runtime_principal": {
                            "user_id": "u",
                            "tenant_id": "t",
                            "project_id": "p",
                            "role": "developer",
                            "permissions": [],
                        },
                        "runtime_policy": {
                            "version": "test",
                            "allowed_model_ids": [module._DEFAULTS.model_id],
                            "tool_overrides": {},
                            "tool_policy_version": "test",
                        },
                        "runtime_scope": {
                            "tenant_id": "t",
                            "project_id": "p",
                            "assistant_id": "dearflow_agent",
                            "thread_id": thread,
                            "operation": "run-create",
                        },
                        "runtime_context_hash": runtime_context_hash({}),
                    }
                ),
            },
        }
        from support import with_run_budget

        cfg = with_run_budget(cfg)
    else:
        cfg = {
            "metadata": {"thread_id": str(uuid4()), "run_id": str(uuid4())},
            "configurable": {
                "_runtime_test_model": chat,
                "_runtime_test_local_auth": True,
            },
        }
    if service == "demo.mcp_demo":

        async def tools(**kwargs):
            return []

        monkeypatch.setattr(module, "load_mcp_tools", tools)

    async def invoke():
        graph = await module.get_agent(cfg)
        await graph.ainvoke(
            {"messages": [HumanMessage(content="hello")]}, context=RuntimeContext()
        )
        handler = next(
            c for c in graph.config["callbacks"] if isinstance(c, RuntimeUsageCallback)
        )
        assert len(handler._calls) == 1 and not handler._active
        assert next(iter(handler._calls.values()))["tokens"]["total_tokens"] == 15

    asyncio.run(invoke())
