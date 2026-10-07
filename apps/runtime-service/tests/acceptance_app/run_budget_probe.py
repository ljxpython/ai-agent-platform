"""Deterministic model/checkpoint graph for isolated timeout acceptance only."""

import asyncio
import os
from pathlib import Path
from time import monotonic

from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from typing_extensions import TypedDict

from runtime_service.middlewares import (
    ModelCallTimeoutMiddleware,
    TimeoutWrapupMiddleware,
)
from runtime_service.middlewares.timeout_wrapup import TIMEOUT_WRAPUP_INSTRUCTION
from runtime_service.runtime.run_budget import read_run_budget


class State(TypedDict, total=False):
    messages: list
    marker: str
    finished: bool


async def get_agent(config):
    budget = read_run_budget(
        config, required=bool(config.get("metadata", {}).get("run_id"))
    )
    thread_id = str(config.get("configurable", {}).get("thread_id", "probe"))
    root = Path(os.environ["RUN_BUDGET_PROBE_WORKSPACE"])
    root.mkdir(parents=True, exist_ok=True)
    if budget is not None:
        with (root / f"{budget.run_id}.factory").open("a", encoding="utf-8") as log:
            log.write("opened\n")

    from langchain_core.language_models.fake_chat_models import (
        FakeMessagesListChatModel,
    )

    class ProbeModel(FakeMessagesListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

        async def _agenerate(self, messages, **kwargs):
            text = messages[-1].text
            if text in {"slow", "model-timeout", "restart", "drain"}:
                await asyncio.sleep((budget.timeout_seconds if budget else 30) + 30)
            wrapup = TIMEOUT_WRAPUP_INSTRUCTION in messages[0].text
            return ChatResult(
                generations=[
                    ChatGeneration(
                        message=AIMessage(
                            content=f"verified partial report; wrapup={wrapup}"
                        )
                    )
                ]
            )

    model_agent = create_agent(
        model=ProbeModel(responses=[]),
        system_prompt="Probe rules.",
        middleware=[TimeoutWrapupMiddleware(budget), ModelCallTimeoutMiddleware(600)],
    )

    async def prepare(state):
        root.mkdir(parents=True, exist_ok=True)
        (root / f"{thread_id}.txt").write_text("verified progress", encoding="utf-8")
        return {"marker": "checkpointed"}

    async def work(state, config):
        message = state["messages"][-1]
        text = message.get("content") if isinstance(message, dict) else message.text
        if text == "approval":
            interrupt("approve")
        if text == "wrapup":
            assert budget is not None
            if budget.wrapup_reserve_seconds:
                await asyncio.sleep(
                    max(0, budget.soft_deadline_monotonic - monotonic() + 0.05)
                )
        if text == "model-timeout":

            async def slow(_request):
                await asyncio.sleep(30)

            await ModelCallTimeoutMiddleware(0.03).awrap_model_call(None, slow)
        result = await model_agent.ainvoke({"messages": state["messages"]}, config)
        return {"messages": result["messages"], "finished": True}

    graph = StateGraph(State)
    graph.add_node("prepare", prepare)
    graph.add_node("work", work)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "work")
    graph.add_edge("work", END)
    return graph.compile()
