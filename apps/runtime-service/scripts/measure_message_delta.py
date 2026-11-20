"""Compare official message snapshots at K=10/50/200 in registered Worktree PG.

Uses deterministic human/tool/assistant messages, not a model latency benchmark.
Only deletes the measurement's own UUID threads in a separate schema.
"""

from __future__ import annotations

import asyncio
import json
import math
import statistics
import time
from importlib.metadata import version
from pathlib import Path
from typing import Annotated, TypedDict
from uuid import uuid4

import psycopg
from deepagents.graph import DeepAgentState
from dotenv import dotenv_values
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langgraph.channels import DeltaChannel
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph, add_messages


def build_graph(state_type, saver):
    def answer(state):
        i = len(state["messages"]) // 4
        return {
            "messages": [
                AIMessage(
                    "",
                    id=f"call-{i}",
                    tool_calls=[
                        {
                            "name": "fixture_tool",
                            "args": {},
                            "id": f"tool-{i}",
                            "type": "tool_call",
                        }
                    ],
                ),
                ToolMessage("t" * 1024, id=f"result-{i}", tool_call_id=f"tool-{i}"),
                AIMessage("a" * 1024, id=f"answer-{i}"),
            ]
        }

    builder = StateGraph(state_type)
    builder.add_node("answer", answer)
    builder.add_edge(START, "answer")
    builder.add_edge("answer", END)
    return builder.compile(checkpointer=saver)


async def main():
    root = Path(__file__).resolve().parents[3]
    entry = json.loads((root / ".local-stack/environment.json").read_text())
    assert Path(entry["root"]) == root and entry["id"].startswith("wt_")
    dsn = dotenv_values(root / ".local-stack/runtime.env")["DATABASE_URI"]
    assert (
        psycopg.conninfo.conninfo_to_dict(dsn)["dbname"]
        == entry["databases"]["runtime"]
    )
    schema = "checkpoint_message_measure"
    async with await psycopg.AsyncConnection.connect(dsn, autocommit=True) as conn:
        assert conn.info.user == conn.info.dbname
        await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    scoped = psycopg.conninfo.make_conninfo(dsn, options=f"-c search_path={schema}")
    prototype = build_graph(DeepAgentState, None).channels["messages"]
    assert isinstance(prototype, DeltaChannel) and prototype.snapshot_frequency == 50
    result = {
        "environment": entry["id"],
        "rounds": 200,
        "messages_per_round": 4,
        "versions": {p: version(p) for p in ("langgraph", "deepagents", "graphharbor")},
        "cases": [],
    }
    expected = None
    for frequency in (None, 10, 50, 200):
        state_type = TypedDict(  # noqa: UP013 - channel metadata is selected per case.
            "MeasuredMessages",
            {
                "messages": Annotated[
                    list[AnyMessage],
                    add_messages
                    if frequency is None
                    else DeltaChannel(
                        prototype.reducer,
                        snapshot_frequency=frequency,
                    ),
                ]
            },
        )
        thread = str(uuid4())
        config = {"configurable": {"thread_id": thread}}
        reads = []
        try:
            async with AsyncPostgresSaver.from_conn_string(scoped) as saver:
                await saver.setup()
                graph = build_graph(state_type, saver)
                start = time.perf_counter()
                for i in range(200):
                    await graph.ainvoke(
                        {"messages": [HumanMessage("h" * 1024, id=f"human-{i}")]},
                        config,
                    )
                    if i >= 180:
                        before = time.perf_counter()
                        state = await graph.aget_state(config)
                        reads.append((time.perf_counter() - before) * 1000)
                seconds = time.perf_counter() - start
                messages = [m.model_dump(mode="json") for m in state.values["messages"]]
                assert len(messages) == 800
                if expected is None:
                    expected = messages
                assert messages == expected
                rows = {}
                async with await psycopg.AsyncConnection.connect(scoped) as conn:
                    for table in (
                        "checkpoints",
                        "checkpoint_writes",
                        "checkpoint_blobs",
                    ):
                        cursor = await conn.execute(
                            f"SELECT count(*),coalesce(sum(pg_column_size(t)),0) FROM {table} t WHERE thread_id=%s",
                            (thread,),
                        )
                        count, size = await cursor.fetchone()
                        rows[table] = {"rows": count, "bytes": size}
                result["cases"].append(
                    {
                        "snapshot_frequency": frequency,
                        "rows": rows,
                        "logical_bytes": sum(r["bytes"] for r in rows.values()),
                        "write_and_read_seconds": seconds,
                        "read_samples_ms": reads,
                        "read_p50_ms": statistics.median(reads),
                        "read_p95_ms": sorted(reads)[math.ceil(len(reads) * 0.95) - 1],
                        "full_messages_equal": True,
                    }
                )
        finally:
            async with AsyncPostgresSaver.from_conn_string(scoped) as saver:
                await saver.adelete_thread(thread)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
