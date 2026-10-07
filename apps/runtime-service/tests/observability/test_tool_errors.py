"""Native errors, raised errors and control flow have distinct diagnostics."""

import asyncio

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import ToolErrorMiddleware
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import ToolException, tool
from langgraph.errors import GraphBubbleUp
from support import BindableFakeMessagesChatModel

from runtime_service.observability import langfuse
from runtime_service.tools.errors import on_tool_error, tool_error_handler


@pytest.mark.parametrize("native", [False, True])
def test_real_tool_error_is_counted_once_without_run_failure_or_details(caplog, native):
    @tool("search_web")
    def fail(query: str) -> str:
        """Expected failure with private cause."""
        raise ToolException("invalid_research_query") from ValueError("SECRET_CANARY")

    fail.handle_tool_error = tool_error_handler(fail.name) if native else False
    graph = create_agent(
        BindableFakeMessagesChatModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": fail.name, "args": {"query": "probe"}, "id": "call"}
                    ],
                ),
                AIMessage(content="continued"),
            ]
        ),
        tools=[fail],
        middleware=[ToolErrorMiddleware(on_error=on_tool_error)],
    )
    callback = langfuse._RuntimeDiagnosticsCallback("probe", {"request_id": "req"})
    before = dict(langfuse._metrics)
    result = asyncio.run(
        graph.ainvoke({"messages": [("user", "probe")]}, {"callbacks": [callback]})
    )
    expected = "tool_result_error" if native else "tool_error"
    assert langfuse._metrics[expected] - before.get(expected, 0) == 1
    other = "tool_error" if native else "tool_result_error"
    assert langfuse._metrics[other] == before.get(other, 0)
    assert langfuse._metrics["run_failed"] == before.get("run_failed", 0)
    assert result["messages"][-1].content == "continued"
    assert "SECRET_CANARY" not in caplog.text
    records = [
        r
        for r in caplog.records
        if r.message in {"runtime_tool_error", "runtime_tool_result_error"}
    ]
    assert len(records) == 1 and records[0].request_id == "req"


def test_control_flow_does_not_increment_tool_failure_metrics():
    callback = langfuse._RuntimeDiagnosticsCallback("probe", {})
    before = dict(langfuse._metrics)
    callback.on_tool_error(GraphBubbleUp(), run_id="interrupt")
    callback.on_tool_error(asyncio.CancelledError(), run_id="cancel")
    assert dict(langfuse._metrics) == before
    callback.on_chain_start({}, {}, run_id="interrupt")
    callback.on_chain_error(GraphBubbleUp(), run_id="interrupt")
    assert "interrupt" not in callback._starts
    assert dict(langfuse._metrics) == before


def test_unstructured_native_error_uses_generic_diagnostic(caplog):
    callback = langfuse._RuntimeDiagnosticsCallback("probe", {})
    before = langfuse._metrics["tool_result_error"]
    callback.on_tool_end(
        ToolMessage(
            content='{"code":[],"error":"SECRET_CANARY"}',
            status="error",
            name="mcp_read",
            tool_call_id="call",
        ),
        run_id="call",
    )
    assert langfuse._metrics["tool_result_error"] == before + 1
    record = next(r for r in caplog.records if r.message == "runtime_tool_result_error")
    assert record.error_code == "tool.result_failed"
    assert "SECRET_CANARY" not in caplog.text


def test_logging_failure_cannot_break_native_error_recovery(monkeypatch):
    @tool("search_web")
    def fail(query: str) -> str:
        """Native known error."""
        raise ToolException("invalid_research_query")

    fail.handle_tool_error = tool_error_handler(fail.name)
    graph = create_agent(
        BindableFakeMessagesChatModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {"name": fail.name, "args": {"query": "probe"}, "id": "call"}
                    ],
                ),
                AIMessage(content="continued"),
            ]
        ),
        tools=[fail],
    )
    callback = langfuse._RuntimeDiagnosticsCallback("probe", {})

    def unavailable(*args, **kwargs):
        raise RuntimeError("logging unavailable")

    monkeypatch.setattr(langfuse.logger, "warning", unavailable)
    result = asyncio.run(
        graph.ainvoke({"messages": [("user", "probe")]}, {"callbacks": [callback]})
    )
    assert result["messages"][-1].content == "continued"
