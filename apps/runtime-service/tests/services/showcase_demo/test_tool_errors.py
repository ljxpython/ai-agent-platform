"""The teaching composition root and child use the same approved error policy."""

import asyncio
import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage

from .test_agent import build as graph_builder
from .test_agent import call

build = graph_builder


@pytest.mark.parametrize("child", [False, True])
def test_showcase_main_or_child_receives_safe_error_and_continues(build, child):
    invalid = call("fetch_documentation", {"url": "http://private.invalid"}, "error")
    if child:
        # The chart child is restricted; a validation failure exercises its own policy.
        invalid = call("generate_bar_chart", {"data": []}, "error")
        responses = [
            call("task", {"subagent_type": "chart-agent", "description": "chart"}),
            invalid,
            AIMessage(content="child alternative"),
            AIMessage(content="done"),
        ]
    else:
        responses = [invalid, AIMessage(content="done")]

    async def run():
        graph, cfg, model = await build(responses)
        result = await graph.ainvoke({"messages": [("user", "probe")]}, cfg, context={})
        errors = [
            m
            for messages in model.seen_messages
            for m in messages
            if isinstance(m, ToolMessage) and m.status == "error"
        ]
        assert len(errors) == 1
        content = errors[0].content
        payload = json.loads(
            content[0]["text"] if isinstance(content, list) else content
        )
        assert (
            payload["code"] == "tool.invalid_input"
            and payload["name"] == errors[0].name
        )
        assert errors[0].tool_call_id == "error"
        assert result["messages"][-1].content == "done"

    asyncio.run(run())
