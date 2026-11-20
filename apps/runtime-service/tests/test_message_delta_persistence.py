"""Official message reducer semantics and native snapshot-to-delta recovery."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Annotated, TypedDict
from uuid import uuid4

import pytest
from deepagents.graph import DeepAgentState
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph, add_messages
from langgraph.graph.message import REMOVE_ALL_MESSAGES


class SnapshotState(TypedDict):
    messages: Annotated[list, add_messages]


def build_graph(saver, *, delta=True):
    builder = StateGraph(DeepAgentState if delta else SnapshotState)
    builder.add_node("pass", lambda state: {})
    builder.add_edge(START, "pass")
    builder.add_edge("pass", END)
    return builder.compile(checkpointer=saver)


def test_delta_preserves_message_ids_batches_tools_and_historical_forks():
    saver = InMemorySaver()
    config = {"configurable": {"thread_id": str(uuid4())}}
    old_graph = build_graph(saver, delta=False)
    old_graph.invoke({"messages": [HumanMessage("original", id="h1")]}, config)
    historical = old_graph.get_state(config).config
    graph = build_graph(saver)
    assert graph.get_state(config).values["messages"][0].content == "original"
    graph.invoke({"messages": [HumanMessage("second", id="h2")]}, config)
    graph.update_state(config, {"messages": [HumanMessage("edited", id="h1")]})
    graph.update_state(config, {"messages": [RemoveMessage(id="h2")]})
    call = AIMessage(
        "",
        id="a1",
        tool_calls=[
            {
                "name": "test_tool",
                "args": {},
                "id": "call1",
                "type": "tool_call",
            }
        ],
    )
    graph.update_state(
        config, {"messages": [call, ToolMessage("ok", id="t1", tool_call_id="call1")]}
    )
    for i in range(52):
        graph.update_state(
            config, {"messages": [HumanMessage(str(i), id=f"batch-{i}")]}
        )
    messages = graph.get_state(config).values["messages"]
    assert [m.id for m in messages[:3]] == ["h1", "a1", "t1"]
    assert messages[0].content == "edited"
    assert messages[2].tool_call_id == messages[1].tool_calls[0]["id"]
    assert len(messages) == 55
    assert graph.get_state(historical).values["messages"][0].content == "original"
    fork = graph.update_state(
        historical, {"messages": [HumanMessage("fork", id="fork")]}
    )
    assert [m.id for m in graph.get_state(fork).values["messages"]] == ["h1", "fork"]
    assert len(graph.get_state(config=historical).values["messages"]) == 1


def test_delta_preserves_parallel_batches_empty_writes_and_explicit_clear():
    saver = InMemorySaver()
    builder = StateGraph(DeepAgentState)
    for name in ("left", "right"):
        builder.add_node(
            name,
            lambda state, name=name: {"messages": [HumanMessage(name, id=name)]},
        )
        builder.add_edge(START, name)
        builder.add_edge(name, END)
    graph = builder.compile(checkpointer=saver)
    config = {"configurable": {"thread_id": str(uuid4())}}
    result = graph.invoke({"messages": [HumanMessage("seed", id="seed")]}, config)
    assert {message.id for message in result["messages"]} == {"seed", "left", "right"}
    assert len(result["messages"]) == 3
    historical = graph.get_state(config).config
    graph.update_state(config, {"messages": []}, as_node="left")
    assert graph.get_state(config).values["messages"] == result["messages"]
    graph.update_state(
        config,
        {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]},
        as_node="left",
    )
    assert graph.get_state(config).values["messages"] == []
    assert graph.get_state(historical).values["messages"] == result["messages"]


def run_process_step(mode, thread_id):
    import psycopg
    from dotenv import dotenv_values
    from langgraph.checkpoint.postgres import PostgresSaver

    root = Path(__file__).resolve().parents[3]
    state = json.loads((root / ".local-stack/environment.json").read_text())
    assert Path(state["root"]) == root
    dsn = dotenv_values(root / ".local-stack/runtime.env")["DATABASE_URI"]
    assert (
        psycopg.conninfo.conninfo_to_dict(dsn)["dbname"]
        == state["databases"]["runtime"]
    )
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS message_delta_test")
    with PostgresSaver.from_conn_string(
        psycopg.conninfo.make_conninfo(
            dsn,
            options="-c search_path=message_delta_test",
        )
    ) as saver:
        saver.setup()
        graph = build_graph(saver, delta=mode != "seed")
        config = {"configurable": {"thread_id": thread_id}}
        if mode == "seed":
            graph.invoke({"messages": [HumanMessage("snapshot", id="seed")]}, config)
        elif mode == "extend":
            for i in range(20):
                graph.invoke(
                    {"messages": [HumanMessage(str(i), id=f"delta-{i}")]}, config
                )
        values = graph.get_state(config).values["messages"]
        output = {
            "ids": [m.id for m in values],
            "contents": [m.content for m in values],
        }
        if mode == "cleanup":
            saver.delete_thread(thread_id)
        return output


def test_native_delta_snapshot_transition_survives_real_process_restart():
    if os.getenv("ASSISTANT_LOCAL_POSTGRES_TEST") != "1":
        pytest.skip("Explicit local Worktree PostgreSQL fixture required")
    thread_id = str(uuid4())

    def child(mode):
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), mode, thread_id],
            check=True,
            capture_output=True,
            text=True,
            timeout=90,
        )
        return json.loads(result.stdout.strip().splitlines()[-1])

    try:
        assert child("seed") == {"ids": ["seed"], "contents": ["snapshot"]}
        expected = child("extend")
        assert expected["ids"] == ["seed", *[f"delta-{i}" for i in range(20)]]
        assert child("inspect") == expected
    finally:
        child("cleanup")


if __name__ == "__main__":
    print(json.dumps(run_process_step(*sys.argv[1:])))
