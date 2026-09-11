"""Network-only UI acceptance graph: parallel HITL and nested scoped tokens.

Loaded only by the isolated acceptance runner, never the deployment catalog.
"""

import asyncio
import operator
from typing import Annotated

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import Send, interrupt


class ContractState(MessagesState):
    outcomes: Annotated[list[dict], operator.add]
    todos: list[dict]
    files: dict


def get_agent(config):
    async def nested_text(state):
        result = await FakeListChatModel(
            responses=["NESTED_PRIVATE scoped text"], sleep=0.04
        ).ainvoke(state["messages"])
        return {"messages": [result]}

    nested = StateGraph(MessagesState).add_node("nested_writer", nested_text)
    nested.add_edge(START, "nested_writer").add_edge("nested_writer", END)
    nested_graph = nested.compile(name="nested")

    def specialist(label):
        async def talk(state):
            if label == "LEFT":
                await nested_graph.ainvoke(
                    {"messages": [HumanMessage(content="nested request")]}
                )
            result = await FakeListChatModel(
                responses=[f"{label}_PRIVATE scoped text"], sleep=0.1
            ).ainvoke(state["messages"])
            return {"messages": [result]}

        def review(state):
            actions = [
                {
                    "name": "edit_file",
                    "args": {
                        "path": f"/{label.lower()}.txt",
                        "count": 1,
                        "enabled": True,
                    },
                }
            ]
            if label == "LEFT":
                actions.append(
                    {"name": "execute", "args": {"command": "verify", "count": 2}}
                )
            answer = interrupt(
                {
                    "action_requests": actions,
                    "review_configs": [
                        {
                            "action_name": action["name"],
                            "allowed_decisions": ["approve", "reject", "edit"],
                        }
                        for action in actions
                    ],
                }
            )
            decisions = answer["decisions"]
            assert len(decisions) == len(actions)
            outcomes = []
            for action, decision in zip(actions, decisions, strict=True):
                kind = decision["type"]
                assert kind in {"approve", "reject", "edit"}
                args = (
                    action["args"]
                    if kind != "edit"
                    else decision["edited_action"]["args"]
                )
                if kind == "edit":
                    assert decision["edited_action"]["name"] == action["name"]
                    assert args.keys() == action["args"].keys()
                    assert all(
                        type(args[key]) is type(value)
                        for key, value in action["args"].items()
                    )
                outcomes.append(
                    {
                        "branch": label,
                        "tool": action["name"],
                        "decision": kind,
                        "args": args,
                        "executed": kind != "reject",
                    }
                )
            return {"outcomes": outcomes}

        graph = StateGraph(ContractState)
        graph.add_node("talk", talk).add_node("review", review)
        graph.add_edge(START, "talk").add_edge("talk", "review").add_edge("review", END)
        return graph.compile(name="specialist")

    specialists = {label: specialist(label) for label in ("LEFT", "RIGHT")}

    async def specialist_call(state):
        label = state["label"]
        result = await specialists[label].ainvoke(
            {"messages": [HumanMessage(content=f"{label} task")]}
        )
        return {"outcomes": result["outcomes"]}

    async def start(state):
        # Give the browser time to attach scoped selectors before children finish.
        await asyncio.sleep(1)
        return {
            "messages": [AIMessage(content="开始并行检查")],
            "todos": [{"content": "两路审批", "status": "in_progress"}],
        }

    def finish(state):
        files = {
            item["args"]["path"]: {"content": "approved content", "complete": True}
            for item in state["outcomes"]
            if item["executed"] and item["tool"] == "edit_file"
        }
        return {
            "messages": [AIMessage(content="并行审批完成")],
            "files": files,
            "todos": [{"content": "两路审批", "status": "completed"}],
        }

    graph = StateGraph(ContractState)
    graph.add_node("start", start).add_node("specialist", specialist_call).add_node(
        "finish", finish
    )
    graph.add_edge(START, "start")
    graph.add_conditional_edges(
        "start",
        lambda state: [
            Send("specialist", {"label": label}) for label in ("LEFT", "RIGHT")
        ],
        ["specialist"],
    )
    graph.add_edge("specialist", "finish").add_edge("finish", END)
    return graph.compile()
