"""Loop protection and official compaction sharing real PostgreSQL checkpoints."""

import asyncio
import os
from uuid import uuid4

import pytest
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from middlewares.test_loop_detection import loop_responses
from pydantic import Field
from support import BindableFakeMessagesChatModel

from runtime_service.middlewares import (
    ConversationOffloadingMiddleware,
    LoopDetectionMiddleware,
    MaintenanceSafeToolCallsMiddleware,
)
from runtime_service.runtime import RuntimeContext
from runtime_service.runtime.errors import RuntimeExecutionError


def test_postgres_loop_survives_auto_and_manual_offloading(tmp_path):
    dsn = os.getenv("LOOP_TEST_CHECKPOINT_DSN")
    if not dsn:
        pytest.skip("LOOP_TEST_CHECKPOINT_DSN must be a disposable PostgreSQL database")

    class Model(BindableFakeMessagesChatModel):
        calls: list[str] = Field(default_factory=list)
        finished: bool = False
        max_tokens: int = 256

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            summary = "nostream" in (self.tags or [])
            self.calls.append("summary" if summary else "normal")
            if summary or self.finished:
                return ChatResult(
                    generations=[
                        ChatGeneration(message=AIMessage(content="goal retained"))
                    ]
                )
            return super()._generate(
                messages, stop=stop, run_manager=run_manager, **kwargs
            )

    calls = []

    @tool
    def read_reference(topic: str) -> str:
        """Read the same reference."""
        calls.append(topic)
        return "unchanged source"

    async def run():
        model = Model(
            responses=loop_responses(5),
            profile={"max_input_tokens": 12000, "max_output_tokens": 1024},
        )
        backend = FilesystemBackend(root_dir=str(tmp_path), virtual_mode=True)
        config = {
            "recursion_limit": 100,
            "configurable": {"thread_id": "f02-compaction-" + uuid4().hex},
            "metadata": {"run_id": "same-run"},
        }
        async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
            await saver.setup()
            summary = ConversationOffloadingMiddleware(model, backend)
            summary._lc_helper._trigger_clauses = [{"messages": 6}]
            summary._lc_helper.keep = ("messages", 2)
            graph = create_deep_agent(
                model=model,
                backend=backend,
                tools=[read_reference],
                middleware=[summary, LoopDetectionMiddleware(["read_reference"])],
                checkpointer=saver,
                context_schema=RuntimeContext,
            )
            with pytest.raises(RuntimeExecutionError) as caught:
                await graph.ainvoke(
                    {"messages": [HumanMessage(content="goal", id="goal")]}, config
                )
            assert caught.value.code == "runtime.loop.detected"
            before = (await graph.aget_state(config)).values
            assert len(calls) == model.calls.count("normal") == 5
            assert model.calls.count("summary") >= 1
            assert (
                before["_summarization_event"]["summary_message"].additional_kwargs[
                    "lc_source"
                ]
                == "summarization"
            )
            marker = before["runtime_loop_state"]
            assert marker["repetitions"] == 4
            # End the failed continuation before requesting a separate maintenance Run.
            await graph.aupdate_state(config, None, as_node="__end__")

        async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
            summary = ConversationOffloadingMiddleware(model, backend, manual=True)
            summary._lc_helper.keep = ("messages", 2)
            maintenance = create_deep_agent(
                model=model,
                backend=backend,
                tools=[read_reference],
                middleware=[
                    summary,
                    MaintenanceSafeToolCallsMiddleware(),
                    LoopDetectionMiddleware(["read_reference"]),
                ],
                checkpointer=saver,
                context_schema=RuntimeContext,
            )
            await maintenance.ainvoke(
                {},
                {**config, "metadata": {"run_id": "maintenance"}},
                context={"offload_conversation": True},
            )
            after = (await maintenance.aget_state(config)).values
            assert after["runtime_loop_state"] == marker
            assert after["messages"] == before["messages"]
            assert after["conversation_offloading"]["status"] in {
                "completed",
                "skipped",
            }
            assert len(calls) == model.calls.count("normal") == 5

            model.finished = True
            normal = create_deep_agent(
                model=model,
                backend=backend,
                tools=[read_reference],
                middleware=[LoopDetectionMiddleware(["read_reference"])],
                checkpointer=saver,
            )
            await normal.ainvoke(
                {"messages": [("user", "continue")]},
                {**config, "metadata": {"run_id": "new-run"}},
            )
            final = (await normal.aget_state(config)).values
            assert final["runtime_loop_state"]["repetitions"] == 0
            assert final["runtime_loop_state"]["owner"] != marker["owner"]
            assert final["messages"][-1].content == "goal retained"

    asyncio.run(run())
