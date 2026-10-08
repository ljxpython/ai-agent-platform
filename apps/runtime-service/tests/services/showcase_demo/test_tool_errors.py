"""The teaching composition root and child use the same approved error policy."""

import asyncio
import json

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command

from runtime_service.runtime.errors import RuntimeWorkspaceError
from runtime_service.workspace import execution

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


@pytest.mark.parametrize("child", [False, True])
def test_workspace_fatal_propagates_through_approved_main_and_child(
    build, monkeypatch, child
):
    monkeypatch.setenv("RUNTIME_BACKEND", "docker")
    attempts = []

    async def failed(*args, **kwargs):
        attempts.append(args)
        raise RuntimeWorkspaceError("runtime.workspace.execution_outcome_unknown")

    monkeypatch.setattr(execution, "execute_in_workspace", failed)
    responses = [call("execute", {"command": "one"}, "workspace-error")]
    if child:
        responses.insert(
            0,
            call(
                "task",
                {"subagent_type": "general-purpose", "description": "execute one"},
            ),
        )
    responses.append(AIMessage(content="must not complete"))

    async def run():
        graph, cfg, model = await build(responses)
        result = await graph.ainvoke({"messages": [("user", "probe")]}, cfg, context={})
        assert result["__interrupt__"] and not attempts
        with pytest.raises(RuntimeWorkspaceError):
            await graph.ainvoke(
                Command(resume={"decisions": [{"type": "approve"}]}), cfg, context={}
            )
        assert len(attempts) == 1
        assert not any(
            isinstance(m, ToolMessage) and m.status == "error"
            for messages in model.seen_messages
            for m in messages
        )

    asyncio.run(run())
