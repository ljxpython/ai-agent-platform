"""Measure real PostgreSQL checkpoint rows for full snapshots and DeltaChannel.

The script uses two unique measurement threads and removes only those threads
after collecting metrics. It never reads or deletes application threads.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import time
from datetime import UTC, datetime
from operator import add
from pathlib import Path
from typing import Annotated, TypedDict
from uuid import uuid4

from dotenv import dotenv_values
from langgraph.channels import DeltaChannel
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from psycopg import AsyncConnection


class FullState(TypedDict):
    items: Annotated[list[str], add]


def delta_reducer(state: list[str], writes: list[list[str]]) -> list[str]:
    return list(state) + [item for write in writes for item in write]


class DeltaState(TypedDict):
    items: Annotated[
        list[str], DeltaChannel(delta_reducer, typ=list, snapshot_frequency=100)
    ]


def build_graph(state_type: type, saver: AsyncPostgresSaver):
    builder = StateGraph(state_type)
    builder.add_node("append", lambda state: {"items": [f"node:{len(state['items'])}"]})
    builder.add_edge(START, "append")
    builder.add_edge("append", END)
    return builder.compile(checkpointer=saver)


async def run_graph(
    state_type: type, saver: AsyncPostgresSaver, thread_id: str, rounds: int
) -> float:
    graph = build_graph(state_type, saver)
    config = {"configurable": {"thread_id": thread_id}}
    started = time.perf_counter()
    for index in range(rounds):
        await graph.ainvoke({"items": [f"input:{index}"]}, config)
    state = await graph.aget_state(config)
    if len(state.values["items"]) != rounds * 2:
        raise RuntimeError(
            f"unexpected final state length: {len(state.values['items'])}"
        )
    return time.perf_counter() - started


async def measure_rows(conn: AsyncConnection, thread_id: str) -> dict[str, int]:
    result: dict[str, int] = {}
    async with conn.cursor() as cursor:
        for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
            await cursor.execute(
                f"""
                SELECT count(*)::int,
                       coalesce(sum(pg_column_size(t)), 0)::bigint
                FROM {table} AS t
                WHERE thread_id = %s
                """,
                (thread_id,),
            )
            count, size = await cursor.fetchone()
            result[f"{table}_rows"] = count
            result[f"{table}_bytes"] = size
    return result


async def cleanup(conn: AsyncConnection, thread_ids: list[str]) -> None:
    async with conn.cursor() as cursor:
        for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
            await cursor.execute(
                f"DELETE FROM {table} WHERE thread_id = ANY(%s)", (thread_ids,)
            )
    await conn.commit()


async def main(args: argparse.Namespace) -> None:
    env = dotenv_values(Path(args.env))
    uri = str(env.get("DATABASE_URI") or os.environ.get("DATABASE_URI") or "").strip()
    if not uri:
        raise SystemExit(f"DATABASE_URI is missing from {args.env}")
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    thread_ids = [
        f"delta-pg-{stamp}-{uuid4().hex[:8]}-{kind}" for kind in ("full", "delta")
    ]
    async with AsyncPostgresSaver.from_conn_string(uri) as saver:
        full_seconds = await run_graph(FullState, saver, thread_ids[0], args.rounds)
        delta_seconds = await run_graph(DeltaState, saver, thread_ids[1], args.rounds)
    async with await AsyncConnection.connect(uri) as conn:
        full = await measure_rows(conn, thread_ids[0])
        delta = await measure_rows(conn, thread_ids[1])
        await cleanup(conn, thread_ids)
    full_bytes = sum(value for key, value in full.items() if key.endswith("_bytes"))
    delta_bytes = sum(value for key, value in delta.items() if key.endswith("_bytes"))
    print(
        {
            "rounds": args.rounds,
            "full": full,
            "delta": delta,
            "full_total_bytes": full_bytes,
            "delta_total_bytes": delta_bytes,
            "byte_ratio": round(delta_bytes / full_bytes, 4) if full_bytes else None,
            "full_run_seconds": round(full_seconds, 4),
            "delta_run_seconds": round(delta_seconds, 4),
            "cleaned_thread_ids": thread_ids,
        }
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--env", default=".env")
    parser.add_argument("--rounds", type=int, default=200)
    asyncio.run(main(parser.parse_args()))
