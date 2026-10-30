import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult
from support import BindableFakeMessagesChatModel

from runtime_service.observability.usage import (
    MAX_TOKEN,
    RuntimeUsageCallback,
    estimate_usage_cost,
    normalize_usage,
    with_runtime_usage,
)


def test_request_profile_counts_components_without_exporting_content():
    from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

    from runtime_service.observability.usage import _request_profile

    messages = [
        [
            SystemMessage(content="private-system"),
            HumanMessage(
                content=[
                    {"type": "text", "text": "中文秘密"},
                    {"type": "image_url", "image_url": {"url": "private-image"}},
                ]
            ),
            AIMessage(content="private-answer"),
            ToolMessage(content="private-result", tool_call_id="call-1"),
        ]
    ]
    tools = [
        {
            "type": "function",
            "function": {"name": "read", "description": "private-schema"},
        }
    ]
    before = repr((messages, tools))
    profile = _request_profile(messages, tools)
    assert profile["components"]["system"]["text_chars"] == 14
    assert profile["components"]["user"]["text_bytes"] == 12
    assert profile["components"]["user"]["nontext_blocks"] == 1
    assert profile["components"]["tool"]["messages"] == 1
    assert profile["tool_schema_count"] == 1
    assert profile["estimated_input_tokens"] > 0
    assert profile["injection_provenance"] == "unavailable"
    encoded = json.dumps(profile)
    assert not any(s in encoded for s in ("private", "秘密", "call-1"))
    assert repr((messages, tools)) == before


def test_response_schema_is_measured_and_reserved_without_exporting_it():
    from runtime_service.observability.usage import (
        _estimate_input_tokens,
        _request_profile,
    )

    messages = [[AIMessage(content="hello")]]
    schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "private-report",
            "schema": {"description": "private-schema" * 100},
        },
    }
    profile = _request_profile(messages, [], schema)
    assert profile["response_schema_chars"] > 1000
    assert len(profile["response_schema_sha256"]) == 64
    assert (
        _estimate_input_tokens(messages, [], schema)
        > _estimate_input_tokens(messages, []) + 250
    )
    assert "private-" not in json.dumps(profile)


def test_usage_callback_logs_profile_once_without_public_payload_change(monkeypatch):
    from runtime_service.observability import usage as module

    events = []
    monkeypatch.setattr(module, "log_context_metric", events.append)

    async def write(*args):
        return True

    async def run():
        handler = RuntimeUsageCallback({"run_id": str(uuid4())})
        monkeypatch.setattr(handler, "_write", write)
        call_id = uuid4()
        for _ in range(2):
            await handler.on_chat_model_start(
                {},
                [[AIMessage(content="do-not-export")]],
                run_id=call_id,
                invocation_params={"tools": []},
                metadata={"langgraph_checkpoint_ns": "tools:child|model:step"},
            )
        assert len(events) == 1
        assert events[0]["scope"] == "subagent"
        assert events[0]["model_call_id"] == str(call_id)
        assert "do-not-export" not in json.dumps(events)
        assert "request_profile" not in handler._calls[call_id]

    asyncio.run(run())


def price(**updates):
    return {
        "currency": "USD",
        "basis": "per_million_tokens",
        "source": "configured_catalog",
        "version": str(uuid4()),
        "updated_at": datetime.now(UTC).isoformat(),
        "input": "2",
        "output": "8",
        "cache_read": "0.2",
        "cache_write": "3",
        "cache_write_5m": "2.5",
        "cache_write_1h": "4",
        **updates,
    }


def test_namespace_preserves_child_identity_and_normalizes_model_step(monkeypatch):
    async def write(*args):
        return True

    async def run():
        handler = RuntimeUsageCallback({})
        monkeypatch.setattr(handler, "_write", write)
        for namespace in (
            "model:root",
            "tools:child-a|model:step-1",
            "tools:child-a|model:step-2",
            "tools:child-b|model:step-3",
        ):
            await handler.on_chat_model_start(
                {}, [], run_id=uuid4(), metadata={"langgraph_checkpoint_ns": namespace}
            )
        calls = list(handler._calls.values())
        assert calls[0]["namespace"] == ["model"]
        assert (
            calls[1]["namespace"] == calls[2]["namespace"] == ["tools:child-a", "model"]
        )
        assert calls[3]["namespace"] == ["tools:child-b", "model"]
        assert [call["scope"] for call in calls] == [
            "primary",
            "subagent",
            "subagent",
            "subagent",
        ]

    asyncio.run(run())


def response(usage, **metadata):
    return LLMResult(
        generations=[
            [
                ChatGeneration(
                    message=AIMessage(
                        content="secret-do-not-store",
                        usage_metadata=usage,
                        response_metadata=metadata,
                    )
                )
            ]
        ]
    )


def test_standard_ttl_and_generic_cost_and_no_double_count():
    usage = normalize_usage(
        response(
            {
                "input_tokens": 1000,
                "output_tokens": 100,
                "total_tokens": 1100,
                "input_token_details": {
                    "cache_read": 200,
                    "cache_creation": 0,
                    "ephemeral_5m_input_tokens": 40,
                    "ephemeral_1h_input_tokens": 60,
                },
                "output_token_details": {"reasoning": 30},
            }
        )
    )
    assert usage["tokens"]["cache_creation_tokens"] == 100
    assert estimate_usage_cost(usage, price()) == ("0.002580000000", None)
    assert estimate_usage_cost(usage, price(cache_write_1h=None)) == (
        None,
        "missing_rate",
    )
    generic = normalize_usage(
        {
            "input_tokens": 1000,
            "output_tokens": 100,
            "total_tokens": 1100,
            "input_token_details": {"cache_read": 200, "cache_creation": 100},
        }
    )
    assert estimate_usage_cost(generic, price()) == ("0.002540000000", None)


@pytest.mark.parametrize("value", [True, -1, 1.5, "1", MAX_TOKEN + 1])
def test_bad_counts_are_unknown_not_clamped(value):
    assert (
        normalize_usage({"input_tokens": value, "output_tokens": 1})["quality"]
        == "invalid"
    )


@pytest.mark.parametrize("value", [False, [], "", 0])
def test_invalid_details_are_not_treated_as_absent(value):
    assert (
        normalize_usage(
            {"input_tokens": 1, "output_tokens": 1, "input_token_details": value}
        )["quality"]
        == "invalid"
    )


def test_aliases_missing_zero_and_conflicts():
    ds = normalize_usage(
        {"prompt_tokens": 500, "completion_tokens": 50, "prompt_cache_hit_tokens": 0},
        provider="deepseek",
    )
    assert estimate_usage_cost(ds, price()) == ("0.001400000000", None)
    assert ds["tokens"]["total_tokens"] == 550
    anthropic = normalize_usage(
        {
            "input_tokens": 700,
            "output_tokens": 100,
            "cache_read_input_tokens": 200,
            "cache_creation_input_tokens": 100,
            "cache_creation": {
                "ephemeral_5m_input_tokens": 40,
                "ephemeral_1h_input_tokens": 60,
            },
        }
    )
    assert anthropic["tokens"]["input_tokens"] == 1000
    assert normalize_usage(None)["quality"] == "missing"
    assert (
        normalize_usage({"input_tokens": 1, "output_tokens": 2, "total_tokens": 99})[
            "quality"
        ]
        == "partial"
    )
    assert (
        normalize_usage(
            {
                "input_tokens": 1,
                "output_tokens": 2,
                "input_token_details": {"cache_read": 2, "cache_creation": 0},
            }
        )["quality"]
        == "invalid"
    )
    assert (
        normalize_usage(
            {
                "input_tokens": 1,
                "output_tokens": 2,
                "output_token_details": {"reasoning": 3},
            }
        )["quality"]
        == "invalid"
    )


def test_one_source_preferred_over_duplicate_provider_response():
    result = response(
        {"input_tokens": 5, "output_tokens": 2, "total_tokens": 7},
        token_usage={"prompt_tokens": 100, "completion_tokens": 100},
    )
    result.llm_output = {"token_usage": {"total_tokens": 500}}
    assert normalize_usage(result)["tokens"]["total_tokens"] == 7


def test_zero_prices_missing_cache_and_money_overflow():
    zero = normalize_usage(
        {
            "input_tokens": 0,
            "output_tokens": 0,
            "input_token_details": {"cache_read": 0, "cache_creation": 0},
        }
    )
    assert estimate_usage_cost(zero, price(input=None, output=None)) == (
        "0.000000000000",
        None,
    )
    unknown = normalize_usage(
        {"input_tokens": 10, "output_tokens": 2}, provider="openai"
    )
    assert estimate_usage_cost(unknown, price())[0] is None
    overflow = normalize_usage(
        {
            "input_tokens": MAX_TOKEN - 1,
            "output_tokens": 1,
            "input_token_details": {"cache_read": 0, "cache_creation": 0},
        }
    )
    assert estimate_usage_cost(overflow, price(input="9999999999.9999999999")) == (
        None,
        "cost_overflow",
    )


def test_real_agent_callback_lifecycle_and_dedup(monkeypatch):
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "true")
    events = []

    async def write(self, name, *args):
        events.append((name, args))

    monkeypatch.setattr(RuntimeUsageCallback, "_write", write)
    identity = {"tenant_id": "tenant", "project_id": "project"}
    model = BindableFakeMessagesChatModel(
        responses=[
            AIMessage(
                content="done",
                usage_metadata={
                    "input_tokens": 5,
                    "output_tokens": 2,
                    "total_tokens": 7,
                },
            )
        ],
        metadata={
            "runtime_usage_model": {
                "model_id": str(uuid4()),
                "provider": "custom-provider",
                "protocol": "openai-compatible",
                "model_name": "test",
                "pricing": price(),
            }
        },
    )
    graph = with_runtime_usage(
        create_agent(model=model),
        {"metadata": {"run_id": str(uuid4()), "thread_id": str(uuid4())}},
        graph_id="test",
        trusted_metadata=identity,
    )
    callbacks = graph.config["callbacks"]
    handler = next(c for c in callbacks if isinstance(c, RuntimeUsageCallback))
    rebound = with_runtime_usage(
        graph, graph.config, graph_id="test", trusted_metadata=identity
    )
    assert (
        sum(isinstance(c, RuntimeUsageCallback) for c in rebound.config["callbacks"])
        == 1
    )
    result = asyncio.run(
        graph.ainvoke({"messages": [{"role": "user", "content": "hello"}]})
    )
    assert result["messages"][-1].content == "done"
    assert [name for name, _ in events].count("begin_collection") == 1
    assert [name for name, _ in events].count("finish_collection") == 1
    assert len(handler._calls) == 1
    call = next(iter(handler._calls.values()))
    assert call["tokens"]["total_tokens"] == 7 and call["model_id"]
    assert (
        call["provider"] == "custom-provider"
        and call["tokens"]["cache_creation_tokens"] == 0
    )
    assert "secret-do-not-store" not in str(call)


def test_persistence_failure_preserves_agent_result(monkeypatch):
    from runtime_service.db.repositories import usage

    def fail(*args):
        raise OSError("secret-error-body")

    monkeypatch.setattr(usage, "begin_collection", fail)
    handler = RuntimeUsageCallback(
        {
            "tenant_id": "t",
            "project_id": "p",
            "graph_id": "g",
            "thread_id": str(uuid4()),
            "run_id": str(uuid4()),
        }
    )
    asyncio.run(handler.on_chain_start(None, {}, run_id=uuid4()))
    assert handler._degraded


def test_hidden_memory_model_inherits_usage_without_exporter(monkeypatch):
    from types import SimpleNamespace

    from langchain_core.callbacks import BaseCallbackHandler
    from langgraph.graph import END, START, StateGraph

    from runtime_service.services.dearflow_agent.middleware import memory

    class Store:
        def begin_extraction(self, *args, **kwargs):
            return kwargs["deadline_at"]

        def reserve_extraction_attempt(self, *args, **kwargs):
            return True

        def propose(self, *args, **kwargs):
            return {"status": "proposed", "added": 0}

        def finish_extraction(self, *args, **kwargs):
            return True

    exports = []

    class Exporter(BaseCallbackHandler):
        def on_llm_end(self, response, **kwargs):
            exports.append(response)

    monkeypatch.setattr(memory, "MemoryStorage", Store)
    monkeypatch.setattr(memory, "memory_scope", lambda _: ("t", "p", "u"))
    monkeypatch.setattr(
        memory, "memory_allowed", lambda _: asyncio.sleep(0, result=True)
    )
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "true")

    async def write(self, *args):
        pass

    monkeypatch.setattr(RuntimeUsageCallback, "_write", write)
    model = BindableFakeMessagesChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "Candidates",
                        "args": {"candidates": []},
                        "id": "candidate",
                    }
                ],
                usage_metadata={
                    "input_tokens": 50,
                    "output_tokens": 10,
                    "total_tokens": 60,
                },
            )
        ],
        metadata={
            "runtime_usage_model": {
                "provider": "openai",
                "model_name": "memory",
                "model_id": str(uuid4()),
                "pricing": price(),
            }
        },
    )

    async def extract(state):
        middleware = memory.MemoryContextMiddleware(model)
        await middleware.aafter_agent(
            {
                "dear_memory_source": {
                    "id": "human",
                    "text": "I prefer Chinese",
                    "epoch": 1,
                    "enabled": True,
                }
            },
            SimpleNamespace(
                execution_info=SimpleNamespace(thread_id="thread", run_id="run")
            ),
        )
        await middleware.drain_tasks()
        return {}

    builder = StateGraph(dict)
    builder.add_node("extract", extract)
    builder.add_edge(START, "extract")
    builder.add_edge("extract", END)
    graph = with_runtime_usage(
        builder.compile(),
        {
            "callbacks": [Exporter()],
            "metadata": {"thread_id": str(uuid4()), "run_id": str(uuid4())},
        },
        graph_id="memory",
        trusted_metadata={"tenant_id": "t", "project_id": "p"},
    )
    handler = next(
        c for c in graph.config["callbacks"] if isinstance(c, RuntimeUsageCallback)
    )
    asyncio.run(graph.ainvoke({}))
    assert len(handler._calls) == 1
    call = next(iter(handler._calls.values()))
    assert (
        call["purpose"] == "memory_extraction"
        and call["scope"] == "auxiliary"
        and call["tokens"]["total_tokens"] == 60
    )
    assert not exports


def test_hidden_vision_uses_own_model_and_unknown_price(monkeypatch, tmp_path):
    import io

    from langgraph.graph import END, START, StateGraph
    from PIL import Image

    from runtime_service.tools import images

    root = tmp_path / "workspace"
    root.mkdir()
    output = io.BytesIO()
    Image.new("RGB", (10, 10), "red").save(output, "PNG")
    workspace = images.ImageWorkspace(root)
    image = workspace.save(output.getvalue(), "generated")
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "true")
    monkeypatch.setenv("VISION_MODEL", "vision-probe")
    monkeypatch.setenv("VISION_API_KEY", "SECRET")
    monkeypatch.setenv("VISION_API_BASE", "https://provider.test")

    def vision(**kwargs):
        kwargs["metadata"]["runtime_usage_model"]["pricing"] = price()
        return BindableFakeMessagesChatModel(
            responses=[
                AIMessage(
                    content="a red image",
                    usage_metadata={
                        "input_tokens": 20,
                        "output_tokens": 10,
                        "total_tokens": 30,
                    },
                )
            ],
            metadata=kwargs["metadata"],
        )

    monkeypatch.setattr(images, "ChatOpenAI", vision)

    async def write(self, *args):
        pass

    monkeypatch.setattr(RuntimeUsageCallback, "_write", write)
    tool = next(
        t for t in images.build_image_tools(workspace) if t.name == "analyze_image"
    )

    async def node(state):
        assert await tool.ainvoke({"image_path": image}) == "a red image"
        return {}

    builder = StateGraph(dict)
    builder.add_node("vision", node)
    builder.add_edge(START, "vision")
    builder.add_edge("vision", END)
    graph = with_runtime_usage(
        builder.compile(),
        {"metadata": {"thread_id": str(uuid4()), "run_id": str(uuid4())}},
        graph_id="vision",
        trusted_metadata={"tenant_id": "t", "project_id": "p"},
    )
    handler = next(
        c for c in graph.config["callbacks"] if isinstance(c, RuntimeUsageCallback)
    )
    asyncio.run(graph.ainvoke({}))
    assert len(handler._calls) == 1
    call = next(iter(handler._calls.values()))
    assert (
        call["purpose"] == "vision"
        and call["model_id"] is None
        and call["estimated_cost_usd"] is None
    )
    assert call["pricing_snapshot"] is None
    assert call["tokens"]["total_tokens"] == 30
