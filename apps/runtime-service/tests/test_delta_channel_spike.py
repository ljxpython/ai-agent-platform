from __future__ import annotations

from operator import add
from typing import Annotated, TypedDict

from langgraph.channels import DeltaChannel
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph


def append_batches(state: list[str], writes: list[list[str]]) -> list[str]:
    result = list(state)
    for write in writes:
        result.extend(write)
    return result


class SpikeState(TypedDict):
    items: Annotated[
        list[str], DeltaChannel(append_batches, typ=list, snapshot_frequency=10)
    ]


def _build_graph(checkpointer: InMemorySaver):
    builder = StateGraph(SpikeState)
    builder.add_node("append", lambda state: {"items": [f"node:{len(state['items'])}"]})
    builder.add_edge(START, "append")
    builder.add_edge("append", END)
    return builder.compile(checkpointer=checkpointer)


def test_delta_reducer_is_batching_invariant() -> None:
    state = ["seed"]
    writes = [["a"], ["b", "c"], ["d"]]
    assert append_batches(state, writes) == append_batches(
        append_batches(state, writes[:1]), writes[1:]
    )


def test_delta_graph_reconstructs_after_multiple_invocations() -> None:
    saver = InMemorySaver()
    graph = _build_graph(saver)
    config = {"configurable": {"thread_id": "delta-spike"}}

    graph.invoke({"items": ["input:0"]}, config)
    result = graph.invoke({"items": ["input:1"]}, config)

    assert result["items"][:2] == ["input:0", "node:1"]
    assert result["items"][2:] == ["input:1", "node:3"]
    assert len(list(saver.list(config))) >= 2


class StandardState(TypedDict):
    items: Annotated[list[str], add]


def _build_standard_graph(checkpointer: InMemorySaver):
    builder = StateGraph(StandardState)
    builder.add_node("append", lambda state: {"items": [f"node:{len(state['items'])}"]})
    builder.add_edge(START, "append")
    builder.add_edge("append", END)
    return builder.compile(checkpointer=checkpointer)


def test_delta_channel_worker_restart_and_resume() -> None:
    """验证 Worker 进程销毁与重启后，新实例能够从持久化 Checkpoint 完整恢复 Delta 状态。"""
    shared_saver = InMemorySaver()
    config = {"configurable": {"thread_id": "worker-restart-thread"}}

    # Worker 实例 1 运行前 3 轮
    graph_worker_1 = _build_graph(shared_saver)
    for i in range(3):
        graph_worker_1.invoke({"items": [f"input:{i}"]}, config)

    # 模拟 Worker 崩溃/重启，实例 1 销毁，创建全新 Worker 实例 2
    del graph_worker_1
    graph_worker_2 = _build_graph(shared_saver)

    # 实例 2 恢复并续跑第 4 轮
    result = graph_worker_2.invoke({"items": ["input:resume"]}, config)

    # 4 轮 input + 4 轮 node = 8 items
    assert len(result["items"]) == 8
    assert result["items"][-2:] == ["input:resume", "node:7"]
    recovered_state = graph_worker_2.get_state(config)
    assert len(recovered_state.values["items"]) == 8


def test_delta_channel_rollback_via_snapshot_dump() -> None:
    """验证 Delta 线程通过快照扁平化 dump 导出后，可无损迁移回滚至标准快照图新线程。"""
    saver = InMemorySaver()
    delta_config = {"configurable": {"thread_id": "delta-origin-thread"}}
    delta_graph = _build_graph(saver)

    # 在 Delta 图上运行积累状态
    for i in range(4):
        delta_graph.invoke({"items": [f"delta-input:{i}"]}, delta_config)

    # 演练回滚：提取 Delta 累积状态快照（flatten dump）
    delta_state = delta_graph.get_state(delta_config)
    dumped_items = list(delta_state.values["items"])
    assert len(dumped_items) == 8

    # 迁移至回滚的标准快照图新线程
    standard_config = {"configurable": {"thread_id": "standard-rollback-thread"}}
    standard_graph = _build_standard_graph(saver)

    # 使用 dump 数据初始化回滚线程，并继续执行
    rollback_result = standard_graph.invoke({"items": dumped_items}, standard_config)
    assert len(rollback_result["items"]) == 9  # 8 个历史 item + 1 个初始节点产物

    # 标准图在新线程上继续正常运转
    next_step = standard_graph.invoke(
        {"items": ["new-standard-input"]}, standard_config
    )
    assert next_step["items"][-2:] == ["new-standard-input", "node:10"]
