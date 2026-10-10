import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from deepagents import create_deep_agent
from deepagents.middleware import FilesystemMiddleware, SummarizationMiddleware
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from support import BindableFakeMessagesChatModel

from runtime_service.services.dearflow_agent.workspace.backend import build_backend


@pytest.mark.parametrize("graph_name", ["dearflow_agent", "showcase_demo"])
@pytest.mark.parametrize("enabled", ["0", "1"])
def test_schema_only_graph_reads_offloading_terminal_state(
    monkeypatch, graph_name, enabled
):
    from importlib import import_module

    from langgraph.channels.delta import DeltaChannel

    from runtime_service.middlewares import ConversationOffloadingMiddleware

    async def run():
        monkeypatch.setenv("AGENT_CONTEXT_MANAGEMENT_ENABLED", enabled)
        module = import_module(
            "runtime_service.services.dearflow_agent.agent"
            if graph_name == "dearflow_agent"
            else "runtime_service.services.demo.showcase_demo.agent"
        )
        saver = InMemorySaver()
        cfg = {"configurable": {"thread_id": "state-probe"}}
        status = {
            "type": "conversation_offloading",
            "status": "completed",
            "trigger": "manual",
            "operation_id": "operation",
            "run_id": "run",
            "history_saved": True,
        }
        writer = create_deep_agent(
            model=BindableFakeMessagesChatModel(responses=[AIMessage(content="ok")]),
            checkpointer=saver,
            state_schema=ConversationOffloadingMiddleware.state_schema,
        )
        await writer.aupdate_state(
            cfg,
            {
                "messages": [HumanMessage(content="old")],
                "conversation_offloading": status,
            },
            as_node="model",
        )
        reader = await module.get_agent(cfg)
        reader.checkpointer = saver
        assert isinstance(reader.channels["messages"], DeltaChannel)
        assert (await reader.aget_state(cfg)).values[
            "conversation_offloading"
        ] == status

    asyncio.run(run())


def test_dearflow_maintenance_composition_skips_business_setup(monkeypatch, tmp_path):
    from runtime_service.middlewares import (
        ConversationOffloadingMiddleware,
        ResultFilesystemMiddleware,
        RuntimeConfigMiddleware,
    )
    from runtime_service.runtime import RuntimeContext, runtime_context_hash
    from runtime_service.services.dearflow_agent import agent
    from runtime_service.services.dearflow_agent.middleware.skills import (
        ExecutionSkillsMiddleware,
    )
    from runtime_service.services.dearflow_agent.workspace.backend import (
        DearWorkspaceBackend,
        WorkspaceMiddleware,
    )

    from .test_agent import config

    monkeypatch.setenv("AGENT_CONTEXT_MANAGEMENT_ENABLED", "1")
    monkeypatch.setenv("RUNTIME_DEAR_GOVERNANCE_ENABLED", "1")
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path))
    model = BindableFakeMessagesChatModel(
        responses=[AIMessage(content="summary")],
        profile={"max_input_tokens": 30000, "max_output_tokens": 2048},
    )
    monkeypatch.setattr(agent, "build_model", lambda *args, **kwargs: model)
    mcp = AsyncMock(side_effect=AssertionError("maintenance connected MCP"))
    memory = AsyncMock(side_effect=AssertionError("maintenance read memory"))
    monkeypatch.setattr(agent, "load_mcp_tools", mcp)
    monkeypatch.setattr(agent, "memory_allowed", memory)
    captured = []
    original = agent.create_deep_agent

    def capture(**kwargs):
        captured.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(agent, "create_deep_agent", capture)
    cfg = config()
    cfg["context"] = {"offload_conversation": True, "max_tokens": 2048}
    user = cfg["configurable"]["langgraph_auth_user"]
    user["runtime_context_hash"] = runtime_context_hash(cfg["context"])
    graph = asyncio.run(agent.get_agent(cfg))
    root = captured[0]
    expected_tool_limit = 1653
    root_filesystem = next(
        mw for mw in root["middleware"] if isinstance(mw, FilesystemMiddleware)
    )
    assert root_filesystem._tool_token_limit_before_evict == expected_tool_limit
    assert isinstance(root_filesystem, ResultFilesystemMiddleware)
    wrappers = [
        mw
        for mw in root["middleware"]
        if isinstance(mw, ConversationOffloadingMiddleware)
    ]
    assert len(wrappers) == 1 and wrappers[0].manual
    assert (
        sum(
            name == "SummarizationMiddleware.before_model"
            for name in graph.get_graph().nodes
        )
        == 1
    )
    for child in root["subagents"]:
        child_filesystem = next(
            mw for mw in child["middleware"] if isinstance(mw, FilesystemMiddleware)
        )
        assert isinstance(child_filesystem, ResultFilesystemMiddleware)
        assert child_filesystem._tool_token_limit_before_evict == expected_tool_limit
        wrappers = [
            mw
            for mw in child["middleware"]
            if isinstance(mw, ConversationOffloadingMiddleware)
        ]
        assert len(wrappers) == 1 and not wrappers[0].manual
    runtime = SimpleNamespace(
        context=RuntimeContext(offload_conversation=True, max_tokens=2048),
        server_info=SimpleNamespace(
            user=user, assistant_id="dearflow_agent", graph_id="dearflow_agent"
        ),
        execution_info=SimpleNamespace(
            thread_id="dear-thread", run_id="maintain", task_id="maintain"
        ),
    )
    for mw in root["middleware"]:
        if isinstance(mw, RuntimeConfigMiddleware):
            assert asyncio.run(mw.abefore_agent({}, runtime)) is None
        elif isinstance(mw, WorkspaceMiddleware):
            assert asyncio.run(mw.abefore_agent({}, runtime, cfg)) is None
        elif isinstance(mw, ExecutionSkillsMiddleware):
            assert asyncio.run(mw.abefore_agent({}, runtime, cfg)) is None
    mcp.assert_not_awaited()
    memory.assert_not_awaited()
    assert not DearWorkspaceBackend("tenant", "project", "dear-thread").root.exists()


def test_memory_source_snapshot_survives_official_summarization(monkeypatch):
    from runtime_service.services.dearflow_agent.middleware import memory as module

    class Store:
        def read(self, scope):
            return {"epoch": 0, "automatic_candidates": False}

        def context(self, scope, query=""):
            return ""

    monkeypatch.setattr(module, "MemoryStorage", Store)
    monkeypatch.setattr(module, "memory_scope", lambda runtime: ("t", "p", "u"))
    monkeypatch.setattr(
        module, "memory_allowed", lambda runtime: asyncio.sleep(0, result=True)
    )

    async def run():
        saver = InMemorySaver()
        backend = build_backend(None)
        summary_model = BindableFakeMessagesChatModel(
            responses=[AIMessage(content="Previous conversation summary")]
        )
        model = BindableFakeMessagesChatModel(responses=[AIMessage(content="done")])
        graph = create_deep_agent(
            model=model,
            backend=backend,
            middleware=[
                SummarizationMiddleware(
                    model=summary_model,
                    backend=backend,
                    trigger=("messages", 4),
                    keep=("messages", 2),
                ),
                module.MemoryContextMiddleware(model),
            ],
            checkpointer=saver,
        )
        config = {"configurable": {"thread_id": "memory-summary"}}
        await graph.ainvoke(
            {
                "messages": [
                    HumanMessage(content="old one", id="old-1"),
                    AIMessage(content="answer one"),
                    HumanMessage(content="old two", id="old-2"),
                    AIMessage(content="answer two"),
                    HumanMessage(content="我偏好简洁中文", id="current"),
                ]
            },
            config,
        )
        checkpoint = await saver.aget_tuple(config)
        assert (
            checkpoint.checkpoint["channel_values"]["dear_memory_source"]["id"]
            == "current"
        )
        assert (
            checkpoint.checkpoint["channel_values"]["dear_memory_source"]["text"]
            == "我偏好简洁中文"
        )

    asyncio.run(run())


def test_official_summary_keeps_queue_receipts_and_archives_history():
    async def run():
        backend = build_backend(None)
        summary_model = BindableFakeMessagesChatModel(
            responses=[
                AIMessage(
                    content="Goal: research cancellation. Source: https://docs.python.org. Next: report."
                )
            ]
        )
        model = BindableFakeMessagesChatModel(responses=[AIMessage(content="done")])
        # Test the same public middleware with a low threshold, not a custom summary loop.
        summarizer = SummarizationMiddleware(
            model=summary_model,
            backend=backend,
            trigger=("messages", 4),
            keep=("messages", 2),
        )
        from runtime_service.middlewares.message_queue import MessageQueueMiddleware

        receipt = {"message_ids": ["supplement"], "run_id": "run"}

        class QueueReceipt(MessageQueueMiddleware):
            async def abefore_agent(self, state, runtime):
                return {"runtime_message_claim": receipt}

        graph = create_deep_agent(
            model=model,
            backend=backend,
            middleware=[
                summarizer,
                FilesystemMiddleware(backend=backend, tools=["read_file"]),
                QueueReceipt(),
            ],
            checkpointer=InMemorySaver(),
        )
        messages = [
            HumanMessage(content="Research cancellation"),
            AIMessage(
                content="",
                tool_calls=[{"name": "fetch_page", "args": {}, "id": "source"}],
            ),
            ToolMessage(
                content="https://docs.python.org " + "evidence " * 200,
                tool_call_id="source",
            ),
            AIMessage(content="Read source"),
            HumanMessage(content="Keep source URLs"),
            AIMessage(content="Understood"),
        ]
        cfg = {"configurable": {"thread_id": "summary-test"}}
        # Private queue state is written by middleware/checkpoints, not user input.
        result = await graph.ainvoke({"messages": messages}, cfg)
        checkpoint = await graph.checkpointer.aget_tuple(cfg)
        assert receipt in checkpoint.checkpoint["channel_values"].values(), (
            checkpoint.checkpoint["channel_values"].keys()
        )
        assert result.get("files"), (
            "history must be preserved in checkpoint-backed files"
        )
        # Composite routes strip their prefix before writing to StateBackend.
        assert any(path.endswith(".md") for path in result["files"]), result[
            "files"
        ].keys()
        assert "docs.python.org" in str(result)

    asyncio.run(run())


def test_official_budget_survives_rebuilt_graph():
    async def run():
        saver = InMemorySaver()
        cfg = {"configurable": {"thread_id": "budget"}}

        def graph():
            return create_deep_agent(
                model=BindableFakeMessagesChatModel(
                    responses=[AIMessage(content="done")]
                ),
                middleware=[
                    ModelCallLimitMiddleware(thread_limit=1, exit_behavior="error")
                ],
                checkpointer=saver,
            )

        await graph().ainvoke({"messages": [("user", "first")]}, cfg)
        from langchain.agents.middleware.model_call_limit import (
            ModelCallLimitExceededError,
        )

        with pytest.raises(ModelCallLimitExceededError):
            await graph().ainvoke({"messages": [("user", "second")]}, cfg)

    asyncio.run(run())
