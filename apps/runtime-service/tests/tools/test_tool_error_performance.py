"""Opt-in measurements; no invented latency SLO or external provider calls."""

import asyncio
import json
import os
import pickle
import time
import tracemalloc

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import ToolErrorMiddleware
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from support import BindableFakeMessagesChatModel

from runtime_service.tools.errors import on_tool_error, tool_error_content


@pytest.mark.parametrize("parallel", [1, 4])
def test_record_formatter_graph_overhead_and_payload(parallel):
    if os.getenv("TOOL_ERROR_PERF_TEST") != "1":
        pytest.skip(
            "TOOL_ERROR_PERF_TEST=1 records measurements without a performance SLO"
        )

    @tool
    def read_reference(kind: str) -> str:
        """Synthetic approved read-only tool."""
        if kind == "known":
            raise ValueError("PRIVATE_CANARY")
        if kind == "unknown":
            raise RuntimeError("PRIVATE_CANARY")
        return "success"

    async def measure(kind, middleware):
        model = BindableFakeMessagesChatModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": "read_reference", "args": {"kind": kind}, "id": str(i)}
                        for i in range(parallel)
                    ],
                ),
                AIMessage(content="done"),
            ]
        )
        saver = InMemorySaver()
        graph = create_agent(
            model, tools=[read_reference], middleware=middleware, checkpointer=saver
        )
        sizes = []
        tracemalloc.start()
        cpu, wall = time.process_time(), time.perf_counter()
        for i in range(10):
            if kind == "unknown":
                model.i = 0
            events = []
            try:
                async for event in graph.astream(
                    {"messages": [("user", "measure")]},
                    {"configurable": {"thread_id": str(i)}},
                    stream_mode=["tools", "values"],
                    version="v3",
                ):
                    events.append(event)
            except RuntimeError:
                assert kind == "unknown"
            else:
                assert kind != "unknown"
            assert "PRIVATE_CANARY" not in str(events)
            sizes.append(sum(len(json.dumps(e, default=str).encode()) for e in events))
        result = {
            "kind": kind,
            "middleware": bool(middleware),
            "parallel": parallel,
            "wall_ms_per_run": round((time.perf_counter() - wall) * 100, 3),
            "cpu_ms_per_run": round((time.process_time() - cpu) * 100, 3),
            "peak_bytes": tracemalloc.get_traced_memory()[1],
            "stream_json_bytes_per_run": sum(sizes) // 10,
            "checkpoint_bytes_per_run": len(
                pickle.dumps({k: dict(v) for k, v in saver.storage.items()})
            )
            // 10,
        }
        tracemalloc.stop()
        return result

    async def run():
        for kind, enabled in (
            ("success", False),
            ("success", True),
            ("known", True),
            ("unknown", True),
        ):
            result = await measure(
                kind, [ToolErrorMiddleware(on_error=on_tool_error)] if enabled else []
            )
            print(json.dumps(result))
        content = tool_error_content(ValueError("PRIVATE_CANARY"), "read_reference")
        assert len(content.encode()) <= 2048
        print(json.dumps({"error_content_bytes": len(content.encode())}))

    asyncio.run(run())
