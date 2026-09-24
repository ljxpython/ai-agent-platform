import asyncio

import pytest
from deepagents import create_deep_agent
from deepagents.middleware import SummarizationMiddleware, FilesystemMiddleware
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from support import BindableFakeMessagesChatModel

from runtime_service.services.dearflow_agent.workspace.backend import build_backend


def test_memory_source_snapshot_survives_official_summarization(monkeypatch):
    from runtime_service.services.dearflow_agent.middleware import memory as module

    class Store:
        def read(self, scope):
            return {"epoch": 0, "automatic_candidates": False}

        def context(self, scope, query=""):
            return ""

    monkeypatch.setattr(module, "MemoryStorage", Store)
    monkeypatch.setattr(module, "memory_scope", lambda runtime: ("t", "p", "u"))
    monkeypatch.setattr(module, "memory_allowed", lambda runtime: asyncio.sleep(0, result=True))

    async def run():
        saver = InMemorySaver()
        backend = build_backend(None)
        summary_model = BindableFakeMessagesChatModel(responses=[AIMessage(content="Previous conversation summary")])
        model = BindableFakeMessagesChatModel(responses=[AIMessage(content="done")])
        graph = create_deep_agent(model=model, backend=backend, middleware=[
            SummarizationMiddleware(model=summary_model, backend=backend,
                                    trigger=("messages", 4), keep=("messages", 2)),
            module.MemoryContextMiddleware(model),
        ], checkpointer=saver)
        config = {"configurable": {"thread_id": "memory-summary"}}
        await graph.ainvoke({"messages": [HumanMessage(content="old one", id="old-1"),
            AIMessage(content="answer one"), HumanMessage(content="old two", id="old-2"),
            AIMessage(content="answer two"), HumanMessage(content="我偏好简洁中文", id="current")]}, config)
        checkpoint = await saver.aget_tuple(config)
        assert checkpoint.checkpoint["channel_values"]["dear_memory_source"]["id"] == "current"
        assert checkpoint.checkpoint["channel_values"]["dear_memory_source"]["text"] == "我偏好简洁中文"

    asyncio.run(run())


def test_official_summary_keeps_queue_receipts_and_archives_history():
    async def run():
        backend = build_backend(None)
        summary_model = BindableFakeMessagesChatModel(responses=[AIMessage(content="Goal: research cancellation. Source: https://docs.python.org. Next: report.")])
        model = BindableFakeMessagesChatModel(responses=[AIMessage(content="done")])
        # Test the same public middleware with a low threshold, not a custom summary loop.
        summarizer = SummarizationMiddleware(model=summary_model, backend=backend,
                                              trigger=("messages", 4), keep=("messages", 2))
        from runtime_service.middlewares.message_queue import MessageQueueMiddleware
        receipt = {"message_ids": ["supplement"], "run_id": "run"}
        class QueueReceipt(MessageQueueMiddleware):
            async def abefore_agent(self, state, runtime):
                return {"runtime_message_claim": receipt}
        graph = create_deep_agent(model=model, backend=backend, middleware=[
            summarizer, FilesystemMiddleware(backend=backend, tools=["read_file"]),
            QueueReceipt(),
        ], checkpointer=InMemorySaver())
        messages = [HumanMessage(content="Research cancellation"),
                    AIMessage(content="", tool_calls=[{"name": "fetch_page", "args": {}, "id": "source"}]),
                    ToolMessage(content="https://docs.python.org " + "evidence " * 200, tool_call_id="source"),
                    AIMessage(content="Read source"), HumanMessage(content="Keep source URLs"), AIMessage(content="Understood")]
        cfg = {"configurable": {"thread_id": "summary-test"}}
        # Private queue state is written by middleware/checkpoints, not user input.
        result = await graph.ainvoke({"messages": messages}, cfg)
        checkpoint = await graph.checkpointer.aget_tuple(cfg)
        assert receipt in checkpoint.checkpoint["channel_values"].values(), checkpoint.checkpoint["channel_values"].keys()
        assert result.get("files"), "history must be preserved in checkpoint-backed files"
        # Composite routes strip their prefix before writing to StateBackend.
        assert any(path.endswith(".md") for path in result["files"]), result["files"].keys()
        assert "docs.python.org" in str(result)
    asyncio.run(run())


def test_official_budget_survives_rebuilt_graph():
    async def run():
        saver = InMemorySaver()
        cfg = {"configurable": {"thread_id": "budget"}}
        def graph():
            return create_deep_agent(model=BindableFakeMessagesChatModel(responses=[AIMessage(content="done")]),
                                     middleware=[ModelCallLimitMiddleware(thread_limit=1, exit_behavior="error")], checkpointer=saver)
        await graph().ainvoke({"messages": [("user", "first")]}, cfg)
        from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
        with pytest.raises(ModelCallLimitExceededError):
            await graph().ainvoke({"messages": [("user", "second")]}, cfg)
    asyncio.run(run())
