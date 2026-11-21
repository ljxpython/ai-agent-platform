import asyncio

from fixtures.v3_browser import BrowserModel, get_agent
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command


def test_streaming_fixture_tools_child_and_id_mapped_approval():
    async def check():
        graph = await get_agent({})
        graph.checkpointer = InMemorySaver()
        for prompt in ("V3_TOOLS", "V3_CHILD", "V3_USAGE", "V3_REASONING"):
            result = await graph.ainvoke(
                {"messages": [("human", prompt)]},
                {"configurable": {"thread_id": prompt}},
            )
            messages = result["messages"]
            assert messages[-1].type == "ai"
            if prompt == "V3_TOOLS":
                assert [m.status for m in messages if m.type == "tool"] == [
                    "success",
                    "error",
                    "success",
                ]
            if prompt == "V3_CHILD":
                assert messages[-1].text == "父任务继续完成"
        for prompt in ("V3_REASONING", "V3_USAGE", "V3_TOOLS"):
            chunks = [
                chunk async for chunk in BrowserModel().astream([("human", prompt)])
            ]
            if prompt == "V3_REASONING":
                assert any(
                    block.get("type") == "reasoning"
                    for chunk in chunks
                    for block in chunk.content
                    if isinstance(block, dict)
                )
            if prompt == "V3_USAGE":
                assert (
                    next(
                        chunk.usage_metadata for chunk in chunks if chunk.usage_metadata
                    )["total_tokens"]
                    == 18
                )
            if prompt == "V3_TOOLS":
                assert sum(bool(chunk.tool_call_chunks) for chunk in chunks) == 4
        events = [
            event
            async for event in graph.astream(
                {"messages": [("human", "V3_CHILD")]},
                {"configurable": {"thread_id": "child-stream"}},
                stream_mode="messages",
                subgraphs=True,
            )
        ]
        assert any(namespace for namespace, _ in events)
        config = {"configurable": {"thread_id": "approval"}}
        result = await graph.ainvoke({"messages": [("human", "V3_APPROVAL")]}, config)
        pending = result["__interrupt__"][0]
        result = await graph.ainvoke(
            Command(resume={pending.id: {"decisions": [{"type": "approve"}]}}), config
        )
        assert result["messages"][-1].text == "验收完成"

    asyncio.run(check())
