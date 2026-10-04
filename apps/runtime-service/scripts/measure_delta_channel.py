"""Measure serialized in-memory checkpoints for full snapshots and DeltaChannel.

This is an offline sizing signal, not a production PostgreSQL benchmark. The
script deliberately uses the same graph shape and input sequence for both
variants, then reports serialized checkpoint tuple bytes and reconstruction
time. It never writes to a configured production checkpointer.
"""

from __future__ import annotations

import argparse
import pickle
import time
from operator import add
from typing import Annotated, TypedDict

from langgraph.channels import DeltaChannel
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph


class State(TypedDict):
    items: Annotated[list[str], add]


class DeltaState(TypedDict):
    items: Annotated[
        list[str],
        DeltaChannel(
            lambda s, ws: s + [x for w in ws for x in w],
            typ=list,
            snapshot_frequency=100,
        ),
    ]


def _graph(state_type: type, checkpointer: InMemorySaver):
    builder = StateGraph(state_type)
    builder.add_node("append", lambda state: {"items": [f"node:{len(state['items'])}"]})
    builder.add_edge(START, "append")
    builder.add_edge("append", END)
    return builder.compile(checkpointer=checkpointer)


def _run(state_type: type, rounds: int) -> tuple[int, float, list[str]]:
    saver = InMemorySaver()
    graph = _graph(state_type, saver)
    config = {"configurable": {"thread_id": f"measure-{state_type.__name__}"}}
    started = time.perf_counter()
    for index in range(rounds):
        graph.invoke({"items": [f"input:{index}"]}, config)
    elapsed = time.perf_counter() - started
    checkpoints = list(saver.list(config))
    size = sum(
        len(pickle.dumps(item, protocol=pickle.HIGHEST_PROTOCOL))
        for item in checkpoints
    )
    restored = graph.get_state(config).values["items"]
    return size, elapsed, restored


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=200)
    args = parser.parse_args()
    full_size, full_time, full_items = _run(State, args.rounds)
    delta_size, delta_time, delta_items = _run(DeltaState, args.rounds)
    if full_items != delta_items:
        raise RuntimeError("full snapshot and DeltaChannel final states differ")
    print(
        {
            "rounds": args.rounds,
            "full_snapshot_bytes": full_size,
            "delta_channel_bytes": delta_size,
            "byte_ratio": round(delta_size / full_size, 4) if full_size else None,
            "full_run_seconds": round(full_time, 4),
            "delta_run_seconds": round(delta_time, 4),
            "final_items": len(delta_items),
        }
    )


if __name__ == "__main__":
    main()
