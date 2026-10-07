"""Real PostgreSQL checkpoints; deterministic provider isolates storage behavior."""

import asyncio
import os
from uuid import uuid4

import pytest
from deepagents import create_deep_agent
from deepagents.middleware.summarization import SummarizationMiddleware
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from support import BindableFakeMessagesChatModel

from runtime_service.middlewares import (
    ConversationOffloadingMiddleware,
    MaintenanceSafeToolCallsMiddleware,
)
from runtime_service.runtime import RuntimeContext
from runtime_service.services.dearflow_agent.workspace.backend import build_backend


def test_two_compactions_survive_connections_and_wrapper_rollback():
    dsn = os.getenv("CONTEXT_TEST_CHECKPOINT_DSN")
    if not dsn:
        pytest.skip(
            "CONTEXT_TEST_CHECKPOINT_DSN must be a disposable PostgreSQL database"
        )

    async def run():
        config = {"configurable": {"thread_id": "context-pg-" + uuid4().hex}}
        backend = build_backend(None)
        model = BindableFakeMessagesChatModel(
            responses=[
                AIMessage(
                    content="Remember ANCHOR_A /workspace/work/report.txt https://docs.python.org Task unfinished."
                )
            ],
            profile={"max_input_tokens": 24000, "max_output_tokens": 2048},
        )
        history = [
            message
            for i in range(8)
            for message in (
                HumanMessage(content="ANCHOR_A " + "word " * 300, id=f"h{i}"),
                AIMessage(
                    content="",
                    tool_calls=[{"name": "lookup", "args": {}, "id": f"call{i}"}],
                    id=f"a{i}",
                ),
                ToolMessage(
                    content="source " * 200, tool_call_id=f"call{i}", id=f"t{i}"
                ),
                AIMessage(content="answer", id=f"end{i}"),
            )
        ]
        cutoff = 0
        session = None
        for index in range(2):
            async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
                await saver.setup()
                mw = ConversationOffloadingMiddleware(
                    model, backend, output_budget_tokens=2048, manual=True
                )
                mw._lc_helper.keep = ("messages", 4)
                graph = create_deep_agent(
                    model=model,
                    backend=backend,
                    checkpointer=saver,
                    context_schema=RuntimeContext,
                    middleware=[mw, MaintenanceSafeToolCallsMiddleware()],
                )
                if index:
                    history += [
                        HumanMessage(content="new " + "word " * 200, id="new-h"),
                        AIMessage(content="new reply", id="new-a"),
                    ]
                await graph.aupdate_state(config, {"messages": history})
                await graph.ainvoke({}, config, context={"offload_conversation": True})
                state = (await graph.aget_state(config)).values
                assert [m.id for m in state["messages"]] == [m.id for m in history]
                event = state["_summarization_event"]
                assert event["cutoff_index"] > cutoff
                cutoff = event["cutoff_index"]
                assert "ANCHOR_A" in str(event["summary_message"].content)
                assert session is None or session == state["_summarization_session_id"]
                session = state["_summarization_session_id"]
                assert (
                    state["files"]
                    and state["conversation_offloading"]["status"] == "completed"
                )
        async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
            restored = create_deep_agent(
                model=model,
                backend=backend,
                checkpointer=saver,
                middleware=[
                    SummarizationMiddleware(
                        model=model, backend=backend, trigger=("tokens", 100000)
                    )
                ],
            )
            before = (await restored.aget_state(config)).values
            assert before["_summarization_session_id"] == session
            await restored.ainvoke({"messages": [("user", "continue")]}, config)
            after = (await restored.aget_state(config)).values
            assert after["_summarization_event"]["cutoff_index"] == cutoff
            assert [m.id for m in after["messages"][: len(history)]] == [
                m.id for m in history
            ]

    asyncio.run(run())
