"""Locked-version behavior needed by the plan approval boundary."""

import asyncio
from typing import NotRequired

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain.tools import ToolRuntime, tool
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from support import BindableFakeMessagesChatModel


class SpikeState(AgentState):
    draft: NotRequired[str]
    stopped: NotRequired[bool]


class SpikeMiddleware(AgentMiddleware):
    state_schema = SpikeState

    @hook_config(can_jump_to=["end"])
    async def abefore_model(self, state, runtime):
        return {"jump_to": "end"} if state.get("stopped") else None


def call(name, args=None):
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args or {}, "id": name}]
    )


def test_saved_state_interrupt_resume_and_end():
    saves = []

    @tool
    def save(runtime: ToolRuntime) -> Command:
        """Save a draft in checkpoint state."""
        saves.append("saved")
        return Command(
            update={
                "draft": "reviewed draft",
                "messages": [
                    ToolMessage(content="saved", tool_call_id=runtime.tool_call_id)
                ],
            }
        )

    @tool
    def submit(runtime: ToolRuntime) -> Command:
        """Submit the already committed draft."""
        answer = interrupt({"draft": runtime.state["draft"]})
        return Command(
            update={
                "stopped": answer == "abandon",
                "messages": [
                    ToolMessage(content=answer, tool_call_id=runtime.tool_call_id)
                ],
            }
        )

    async def run():
        graph = create_agent(
            BindableFakeMessagesChatModel(
                responses=[
                    call("save"),
                    call("submit"),
                    AIMessage(content="must not run"),
                ]
            ),
            tools=[save, submit],
            middleware=[SpikeMiddleware()],
            checkpointer=InMemorySaver(),
        )
        config = {"configurable": {"thread_id": "spike"}}
        result = await graph.ainvoke({"messages": [("user", "plan")]}, config)
        pending = result["__interrupt__"][0]
        assert pending.value["draft"] == "reviewed draft"
        assert saves == ["saved"]
        result = await graph.ainvoke(Command(resume={pending.id: "abandon"}), config)
        assert result["stopped"] and result["messages"][-1].type == "tool"
        assert saves == ["saved"]
        assert not (await graph.aget_state(config)).next

    asyncio.run(run())


def test_nested_interrupt_rebuild_retains_checkpoint():
    @tool
    def review() -> str:
        """Wait for a human reply."""
        return interrupt({"kind": "nested"})

    model = BindableFakeMessagesChatModel(
        responses=[call("review"), AIMessage(content="done")]
    )

    def inner():
        return create_agent(model, tools=[review], checkpointer=True)

    async def respond(state):
        return await inner().ainvoke(state)

    async def run():
        saver = InMemorySaver()

        def outer():
            builder = StateGraph(AgentState)
            builder.add_node("respond", respond)
            builder.add_edge(START, "respond")
            builder.add_edge("respond", END)
            return builder.compile(checkpointer=saver)

        config = {"configurable": {"thread_id": "nested-spike"}}
        result = await outer().ainvoke({"messages": [("user", "review")]}, config)
        pending = result["__interrupt__"][0]
        result = await outer().ainvoke(Command(resume={pending.id: "approved"}), config)
        assert any(
            m.type == "tool" and m.content == "approved" for m in result["messages"]
        )

    asyncio.run(run())
