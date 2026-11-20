"""Tool identities survive compatible-provider deltas and Graph v3 assembly."""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from langchain_core.messages import AIMessageChunk, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

from runtime_service.runtime.modeling import ChatOpenAIWithReasoning


@pytest.mark.parametrize("name", [None, "", "probe_echo"])
def test_chunk_normalization_does_not_invent_names_or_repair_invalid_json(name):
    model = ChatOpenAIWithReasoning(model="compatible-test", api_key="test")
    result = model._convert_chunk_to_generation_chunk(
        {
            "choices": [
                {
                    "delta": {
                        "tool_calls": [
                            {
                                "index": 0,
                                "id": "call_invalid",
                                "type": "function",
                                "function": {"name": name, "arguments": "not-json"},
                            }
                        ]
                    }
                }
            ]
        },
        AIMessageChunk,
        None,
    )
    assert result is not None
    assert result.message.tool_call_chunks[0]["name"] == (name or None)
    assert result.message.tool_calls == []
    assert result.message.invalid_tool_calls[0]["args"] == "not-json"


def _wire(*, empty_names: bool) -> str:
    deltas = [
        {"role": "assistant", "reasoning_content": "Use both tools."},
        {
            "tool_calls": [
                {
                    "index": 0,
                    "id": "call_echo",
                    "type": "function",
                    "function": {"name": "probe_echo", "arguments": ""},
                }
            ]
        },
        {
            "tool_calls": [
                {
                    "index": 1,
                    "id": "call_number",
                    "type": "function",
                    "function": {"name": "probe_number", "arguments": ""},
                }
            ]
        },
    ]
    for index, arguments in [
        (0, '{"text":'),
        (1, '{"number":'),
        (0, '"probe"}'),
        (1, "7}"),
    ]:
        function = {"arguments": arguments}
        if empty_names:
            function["name"] = ""
        deltas.append({"tool_calls": [{"index": index, "function": function}]})
    deltas.append({"function_call": {"arguments": "", "name": ""}})
    events = [
        {
            "id": "chatcmpl-probe",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "compatible-test",
            "choices": [{"index": 0, "delta": delta, "finish_reason": None}],
        }
        for delta in deltas
    ]
    events.append(
        {
            "id": "chatcmpl-probe",
            "object": "chat.completion.chunk",
            "created": 1,
            "model": "compatible-test",
            "choices": [{"index": 0, "delta": {}, "finish_reason": "tool_calls"}],
        }
    )
    return (
        "".join("data: " + json.dumps(event) + "\n\n" for event in events)
        + "data: [DONE]\n\n"
    )


@pytest.mark.parametrize("empty_names", [False, True])
def test_regular_stream_keeps_tool_names_arguments_and_reasoning(empty_names):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text=_wire(empty_names=empty_names),
        )
    )
    with httpx.Client(transport=transport) as client:
        model = ChatOpenAIWithReasoning(
            model="compatible-test", api_key="test", http_client=client
        )
        chunks = list(model.stream("Use both tools."))
    combined = chunks[0]
    for chunk in chunks[1:]:
        combined += chunk
    assert [(c["name"], c["args"], c["id"]) for c in combined.tool_calls] == [
        ("probe_echo", {"text": "probe"}, "call_echo"),
        ("probe_number", {"number": 7}, "call_number"),
    ]
    assert combined.additional_kwargs["reasoning_content"] == "Use both tools."


@pytest.mark.parametrize("empty_names", [False, True])
def test_graph_v3_executes_parallel_streamed_tool_calls(empty_names):
    asyncio.run(_run_tools(empty_names))


async def _run_tools(empty_names):
    called = []

    @tool
    def probe_echo(text: str) -> str:
        """Return the input text."""
        called.append(("probe_echo", text))
        return text

    @tool
    def probe_number(number: int) -> str:
        """Return the input number."""
        called.append(("probe_number", number))
        return str(number)

    wire = _wire(empty_names=empty_names)
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200, headers={"content-type": "text/event-stream"}, text=wire
        )
    )
    async with httpx.AsyncClient(transport=transport) as client:
        model = ChatOpenAIWithReasoning(
            model="compatible-test", api_key="test", http_async_client=client
        ).bind_tools([probe_echo, probe_number])

        async def model_node(state):
            return {"messages": [await model.ainvoke(state["messages"])]}

        graph = (
            StateGraph(MessagesState)
            .add_node("model", model_node)
            .add_node("tools", ToolNode([probe_echo, probe_number]))
            .add_edge(START, "model")
            .add_edge("model", "tools")
            .add_edge("tools", END)
            .compile()
        )
        stream = await graph.astream_events(
            {"messages": [("user", "Use both tools.")]}, version="v3"
        )
        async with stream:
            async for _ in stream:
                pass
        assert sorted(called) == [("probe_echo", "probe"), ("probe_number", 7)]
        output = await stream.output()
        assert output is not None
        results = [m for m in output["messages"] if isinstance(m, ToolMessage)]
        assert {m.tool_call_id for m in results} == {"call_echo", "call_number"}
        assert all(m.status == "success" for m in results)
