"""Check the actual v3 event boundary, independently of safe ToolMessages."""

import asyncio

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import ToolErrorMiddleware
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, interrupt
from support import BindableFakeMessagesChatModel

from runtime_service.patches import apply_langgraph_patches


def test_stream_tool_error_hides_original_error_and_keeps_id():
    @tool
    def failing(value: str) -> str:
        """Controlled exception with private details."""
        raise ValueError("TOKEN_CANARY /host/path https://provider.invalid")

    async def run():
        graph = create_agent(
            BindableFakeMessagesChatModel(
                responses=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": failing.name,
                                "args": {"value": "probe"},
                                "id": "call-1",
                            }
                        ],
                    ),
                    AIMessage(content="continued"),
                ]
            ),
            tools=[failing],
            middleware=[
                ToolErrorMiddleware(on_error=lambda exc, request: "safe tool error")
            ],
        )
        events = [
            event
            async for event in graph.astream(
                {"messages": [("user", "probe")]},
                stream_mode=["tools", "updates"],
                version="v3",
            )
        ]
        errors = [
            data
            for kind, data in events
            if kind == "tools" and data["event"] == "tool-error"
        ]
        assert errors == [
            {
                "event": "tool-error",
                "tool_call_id": "call-1",
                "message": "tool.execution_failed",
            }
        ]
        assert "CANARY" not in str(events) and "provider.invalid" not in str(events)
        assert "continued" in str(events)

    apply_langgraph_patches()
    apply_langgraph_patches()
    asyncio.run(run())


def test_interrupt_and_resume_do_not_emit_tool_error():
    @tool
    def question(value: str) -> str:
        """Pause for a real checkpointed response."""
        return interrupt(value)

    async def run():
        graph = create_agent(
            BindableFakeMessagesChatModel(
                responses=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": question.name,
                                "args": {"value": "answer"},
                                "id": "interrupt-call",
                            }
                        ],
                    ),
                    AIMessage(content="continued"),
                ]
            ),
            tools=[question],
            checkpointer=InMemorySaver(),
        )
        cfg = {"configurable": {"thread_id": "interrupt-probe"}}
        before = [
            event
            async for event in graph.astream(
                {"messages": [("user", "probe")]},
                cfg,
                stream_mode=["tools", "updates"],
                version="v3",
            )
        ]
        pending = (await graph.aget_state(cfg)).tasks[0].interrupts[0]
        after = [
            event
            async for event in graph.astream(
                Command(resume={pending.id: "approved"}),
                cfg,
                stream_mode=["tools", "updates"],
                version="v3",
            )
        ]
        assert not any(
            kind == "tools" and data["event"] == "tool-error"
            for kind, data in before + after
        )
        assert "approved" in str(after) and "continued" in str(after)

    asyncio.run(run())


def test_cancelled_tool_does_not_emit_tool_error():
    entered = asyncio.Event()

    @tool
    async def cancel(value: str) -> str:
        """A tool cancelled by its caller."""
        entered.set()
        await asyncio.Event().wait()
        return value

    async def run():
        graph = create_agent(
            BindableFakeMessagesChatModel(
                responses=[
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "name": cancel.name,
                                "args": {"value": "probe"},
                                "id": "cancel-call",
                            }
                        ],
                    ),
                ]
            ),
            tools=[cancel],
        )
        events = []

        async def consume():
            async for event in graph.astream(
                {"messages": [("user", "probe")]},
                stream_mode=["tools", "updates"],
                version="v3",
            ):
                events.append(event)

        task = asyncio.create_task(consume())
        await asyncio.wait_for(entered.wait(), 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not any(
            kind == "tools" and data["event"] == "tool-error" for kind, data in events
        )

    asyncio.run(run())
