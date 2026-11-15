"""Explicit read → propose → validate workflow, with at most one format repair."""

import json
from contextvars import copy_context
from typing import Annotated

from langchain_core.messages import AIMessage
from langchain_core.runnables.config import var_child_runnable_config
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from runtime_service.errors import RuntimeAuthError
from runtime_service.middlewares.execution_budget import (
    GraphBudgetState,
    check_graph_budget,
)
from runtime_service.runtime import RuntimeContext


class AssistantInput(TypedDict, total=False):
    work_item_id: str
    job_id: str


class AssistantState(AssistantInput, GraphBudgetState, total=False):
    messages: Annotated[list, add_messages]
    snapshot: dict
    proposal: dict
    validation: dict
    attempt: int
    response: str


def build_graph(
    model_agent_for=None,
    *,
    read_current=None,
    model_config=None,
    runtime_context=None,
    probe_only=False,
):
    async def prepare(state):
        if probe_only:
            raise RuntimeAuthError("runtime.graph.probe_only")
        snapshot = await read_current(state)
        return {"snapshot": snapshot, "attempt": 0, "validation": {}}

    async def propose(state, runtime):
        await read_current(state)
        budget = check_graph_budget(state, runtime, graph_key="evaluation_assistant")
        config = {**(model_config or {}), **(var_child_runnable_config.get() or {})}
        config["configurable"] = {
            **(model_config or {}).get("configurable", {}),
            **config.get("configurable", {}),
        }
        writer_context = copy_context()

        def writer(notice):
            writer_context.run(runtime.stream_writer, notice)

        agent = await model_agent_for(state, writer=writer)
        messages = [
            {
                "role": "user",
                "content": json.dumps(state["snapshot"], ensure_ascii=False),
            }
        ]
        if state.get("attempt"):
            messages.append(
                {
                    "role": "user",
                    "content": "上次输出未通过校验，请仅修复以下结构问题，不改变业务标准："
                    + json.dumps(state["validation"], ensure_ascii=False),
                }
            )
        result = await agent.ainvoke(
            {"messages": messages},
            config=config,
            context=runtime_context or runtime.context,
        )
        message = result["messages"][-1]
        content = message.content
        if isinstance(content, list):
            content = "".join(
                block.get("text", "") for block in content if isinstance(block, dict)
            )
        return {**budget, "response": content, "attempt": state.get("attempt", 0) + 1}

    async def validate(state):
        await read_current(state)
        text = state["response"].strip()
        if text.startswith("```json") and text.endswith("```"):
            text = text[7:-3].strip()
        try:
            if len(text) > 250_000:
                raise ValueError("large")
            proposal = json.loads(text)
            result = await read_current(
                state, operation="validate", payload={"proposal": proposal}
            )
        except ValueError:
            return {
                "validation": {"valid": False, "reason": "请返回符合schema的JSON对象"}
            }
        return {"proposal": proposal, "validation": result}

    def route(state):
        if state["validation"].get("valid"):
            return "complete"
        return "propose" if state["attempt"] < 2 else "invalid"

    async def complete(state):
        await read_current(state)
        await read_current(
            state, operation="complete", payload={"proposal": state["proposal"]}
        )
        return {
            "messages": [
                AIMessage(content=json.dumps(state["proposal"], ensure_ascii=False))
            ]
        }

    def invalid(state):
        raise ValueError("评测方案经一次修复后仍不符合执行规则，请补充口径后重试。")

    graph = StateGraph(
        AssistantState, input_schema=AssistantInput, context_schema=RuntimeContext
    )
    for name, node in (
        ("prepare", prepare),
        ("propose", propose),
        ("validate", validate),
        ("complete", complete),
        ("invalid", invalid),
    ):
        graph.add_node(name, node)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "propose")
    graph.add_edge("propose", "validate")
    graph.add_conditional_edges(
        "validate", route, {name: name for name in ("complete", "propose", "invalid")}
    )
    graph.add_edge("complete", END)
    graph.add_edge("invalid", END)
    # GraphHarbor installs the durable saver; no process-local checkpoint store here.
    return graph.compile()
