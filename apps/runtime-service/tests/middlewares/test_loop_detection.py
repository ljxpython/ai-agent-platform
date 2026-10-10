from __future__ import annotations

import asyncio
import json
import statistics
import time
from uuid import uuid4

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware, ModelCallLimitMiddleware
from langchain.agents.middleware.model_call_limit import ModelCallLimitExceededError
from langchain.tools import tool
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.runtime import Runtime
from support import BindableFakeMessagesChatModel

from runtime_service.middlewares.execution_budget import WRAPUP_INSTRUCTION
from runtime_service.middlewares.loop_detection import (
    MAX_MESSAGES,
    LoopDetectionMiddleware,
    _completed_batch,
    loop_detection_enabled,
)
from runtime_service.runtime.errors import RuntimeExecutionError


def batch(calls=None, contents=None, *, ai_id="ai"):
    calls = calls or [{"name": "read_file", "args": {"file_path": "/a"}, "id": "c1"}]
    return [
        AIMessage(id=ai_id, content="", tool_calls=calls),
        *[
            ToolMessage(content=content, tool_call_id=call["id"], name=call["name"])
            for call, content in zip(
                calls, contents or ["ok"] * len(calls), strict=True
            )
        ],
    ]


def signature(messages):
    result = _completed_batch(messages, {"ls", "read_file", "grep"})
    return result[1] if result else None


def test_complete_batch_preserves_multiset_and_result_pairing():
    a = {
        "name": "read_file",
        "args": {"file_path": "/a", "offset": 0, "limit": 100},
        "id": "a",
    }
    b = {"name": "grep", "args": {"path": "/", "pattern": "x"}, "id": "b"}
    original = batch([a, b], ["first", "second"])
    reordered = batch(
        [
            {**b, "args": {"pattern": "x", "path": "/"}, "id": "new-b"},
            {**a, "args": {"file_path": "/a"}, "id": "new-a"},
        ],
        ["second", "first"],
        ai_id="new",
    )
    assert signature(original) == signature(reordered)
    assert signature(original) != signature(batch([a, b], ["second", "first"]))
    assert signature(batch([a, {**a, "id": "a2"}])) != signature(batch([a]))
    assert signature(original) == signature([original[0], *reversed(original[1:])])


@pytest.mark.parametrize(
    "change", [{"offset": 100}, {"limit": 50}, {"file_path": "/b"}]
)
def test_read_pagination_is_progress(change):
    assert signature(batch()) != signature(
        batch([{"name": "read_file", "args": {"file_path": "/a", **change}, "id": "c"}])
    )


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "duplicate",
        "invalid",
        "mixed",
        "multimodal",
        "large",
        "nan",
        "nonjson",
        "offloaded",
        "truncated",
        "artifact",
    ],
)
def test_unreliable_evidence_is_skipped(kind):
    messages = batch()
    if kind == "missing":
        messages.pop()
    elif kind == "duplicate":
        messages.append(messages[-1])
    elif kind == "invalid":
        messages[0].invalid_tool_calls = [
            {"name": "bad", "args": "{", "id": "bad", "error": "invalid"}
        ]
    elif kind == "mixed":
        messages = batch(
            messages[0].tool_calls + [{"name": "write_file", "args": {}, "id": "write"}]
        )
    elif kind == "multimodal":
        messages[-1].content = [{"type": "image", "url": "x"}]
    elif kind == "large":
        messages[-1].content = "x" * 65537
    elif kind in {"nan", "nonjson"}:
        messages[0].tool_calls[0]["args"]["offset"] = (
            float("nan") if kind == "nan" else object()
        )
    elif kind == "offloaded":
        messages[-1].additional_kwargs = {"lc_evicted_to": "/result"}
    elif kind == "truncated":
        messages[-1].content = "x\n[Output was truncated due to size limits]"
    else:
        messages[-1].artifact = {"private": True}
    assert signature(messages) is None
    assert signature(batch() + [HumanMessage(content="new input")]) is None


def test_tail_is_bounded_and_status_and_result_are_semantic():
    messages = batch()
    assert signature([HumanMessage(content="old")] * 10000 + messages) == signature(
        messages
    )
    assert signature([messages[0]] + [messages[1]] * MAX_MESSAGES) is None
    changed = batch(contents=["changed"])
    assert signature(messages) != signature(changed)
    changed = batch()
    changed[-1].status = "error"
    assert signature(messages) != signature(changed)


def test_directory_listing_is_not_an_offloaded_result():
    calls = [{"name": "ls", "args": {"path": "/"}, "id": "root"}]
    assert signature(batch(calls, ["['/large_tool_results/', '/workspace/']"]))
    assert (
        signature(
            batch(
                calls,
                [
                    "Tool result too large, the result of this tool call root was saved "
                    "in the filesystem at this path: /large_tool_results/root"
                ],
            )
        )
        is None
    )


def loop_responses(count=6):
    prefix = uuid4().hex
    return [
        AIMessage(
            id=f"{prefix}-ai-{i}",
            content="",
            tool_calls=[
                {
                    "name": "read_reference",
                    "args": {"topic": "same"},
                    "id": f"{prefix}-call-{i}",
                }
            ],
        )
        for i in range(count)
    ] + [AIMessage(id=f"{prefix}-final", content="done")]


def graph_fixture(responses=None, *, saver=None, interrupt=None, extra=()):
    calls, prompts = [], []

    @tool
    def read_reference(topic: str) -> str:
        """Return a stable read-only reference."""
        calls.append(topic)
        return "stable reference"

    class Capture(AgentMiddleware):
        def wrap_model_call(self, request, handler):
            prompts.append(
                request.system_message.content if request.system_message else ""
            )
            return handler(request)

        async def awrap_model_call(self, request, handler):
            prompts.append(
                request.system_message.content if request.system_message else ""
            )
            return await handler(request)

    graph = create_agent(
        BindableFakeMessagesChatModel(responses=responses or loop_responses()),
        tools=[read_reference],
        checkpointer=saver,
        interrupt_after=interrupt,
        middleware=[*extra, LoopDetectionMiddleware(["read_reference"]), Capture()],
    )
    return graph, calls, prompts


@pytest.mark.parametrize("asynchronous", [False, True])
def test_real_graph_warns_once_then_blocks_sixth_model(asynchronous):
    graph, calls, prompts = graph_fixture()
    assert "runtime_loop_state" not in graph.get_input_jsonschema()["properties"]
    assert "runtime_loop_state" not in graph.get_output_jsonschema()["properties"]
    config = {"metadata": {"run_id": str(uuid4())}, "recursion_limit": 100}
    notices = []

    async def run():
        async for _mode, payload in graph.astream(
            {"messages": [("user", "loop")]}, config, stream_mode=["custom"]
        ):
            notices.append(payload)

    def sync_run():
        for _mode, payload in graph.stream(
            {"messages": [("user", "loop")]}, config, stream_mode=["custom"]
        ):
            notices.append(payload)

    with pytest.raises(RuntimeExecutionError) as caught:
        asyncio.run(run()) if asynchronous else sync_run()
    assert caught.value.code == "runtime.loop.detected"
    assert len(calls) == len(prompts) == 5
    assert all(WRAPUP_INSTRUCTION not in prompt for prompt in prompts[:3])
    assert all(WRAPUP_INSTRUCTION in prompt for prompt in prompts[3:])
    assert [row["code"] for row in notices] == [
        "tool_loop_approaching",
        "tool_loop_reached",
    ]
    assert [(row["used"], row["remaining"]) for row in notices] == [(3, 2), (5, 0)]


def test_warning_allows_natural_success_and_budget_keeps_precedence():
    graph, calls, prompts = graph_fixture(loop_responses(3))
    result = graph.invoke({"messages": [("user", "loop")]}, {"recursion_limit": 100})
    assert result["messages"][-1].content == "done"
    assert len(calls) == 3 and WRAPUP_INSTRUCTION in prompts[-1]
    graph, calls, _ = graph_fixture(
        extra=[ModelCallLimitMiddleware(run_limit=2, exit_behavior="error")]
    )
    with pytest.raises(ModelCallLimitExceededError):
        graph.invoke({"messages": [("user", "loop")]}, {"recursion_limit": 100})
    assert len(calls) == 2


def test_checkpoint_rebuild_same_run_retains_counter_and_new_run_resets():
    saver = InMemorySaver()
    config = {
        "configurable": {"thread_id": "loop-thread"},
        "metadata": {"run_id": "same-run"},
        "recursion_limit": 100,
    }
    graph, _, _ = graph_fixture(saver=saver, interrupt=["tools"])
    graph.invoke({"messages": [("user", "loop")]}, config)
    for _ in range(3):
        graph.invoke(None, config)
    saved = graph.get_state(config).values["runtime_loop_state"]
    assert saved["repetitions"] == 3
    assert len(json.dumps(saved)) < 700
    rebuilt, calls, _ = graph_fixture(loop_responses()[4:], saver=saver)
    with pytest.raises(RuntimeExecutionError):
        rebuilt.invoke(None, config)
    assert len(calls) == 1
    rebuilt, _, _ = graph_fixture(loop_responses(1), saver=saver)
    new_config = {**config, "metadata": {"run_id": "new-run"}}
    result = rebuilt.invoke({"messages": [("user", "new task")]}, new_config)
    assert result["messages"][-1].content == "done"
    assert (
        rebuilt.get_state(new_config).values["runtime_loop_state"]["repetitions"] == 1
    )


def test_message_replay_new_user_changed_batch_and_maintenance(monkeypatch):
    from runtime_service.middlewares import loop_detection as module

    marker = {
        "owner": "local",
        "cursor": None,
        "signature": None,
        "sequence": None,
        "repetitions": 0,
        "user": None,
    }
    mw = LoopDetectionMiddleware(["read_file"])
    monkeypatch.setattr(module, "get_config", lambda: {})
    messages = []
    for i in range(3):
        messages.extend(batch(ai_id=f"ai-{i}"))
        state = {"messages": messages, "runtime_loop_state": marker}
        marker = mw.before_model(state, Runtime())["runtime_loop_state"]
        assert (
            mw.before_model({**state, "runtime_loop_state": marker}, Runtime()) is None
        )
    assert marker["repetitions"] == 3
    state = {
        "messages": messages + [HumanMessage(id="new-user", content="check again")],
        "runtime_loop_state": marker,
    }
    marker = mw.before_model(state, Runtime())["runtime_loop_state"]
    assert marker["repetitions"] == 0
    monkeypatch.setattr(module, "is_conversation_maintenance", lambda runtime: True)
    assert mw.before_agent(state, Runtime()) is None
    assert mw.before_model(state, Runtime()) is None


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, False),
        ("0", False),
        ("1", True),
        ("true", None),
        ("", None),
        (" 1", None),
    ],
)
def test_deployment_switch_is_strict(monkeypatch, value, expected):
    if value is None:
        monkeypatch.delenv("AGENT_LOOP_DETECTION_ENABLED", raising=False)
    else:
        monkeypatch.setenv("AGENT_LOOP_DETECTION_ENABLED", value)
    if expected is None:
        with pytest.raises(ValueError):
            loop_detection_enabled()
    else:
        assert loop_detection_enabled() is expected


def test_long_threads_constant_state_and_compiled_step_cost():
    from langchain.agents.middleware import ModelCallLimitMiddleware
    from langgraph.config import get_config

    def make_graph(enabled):
        steps, calls, state_sizes = [], [], []

        @tool
        def read_reference(topic: str) -> str:
            """Read one reference page."""
            calls.append(topic)
            return topic

        class Steps(AgentMiddleware):
            def wrap_model_call(self, request, handler):
                steps.append(get_config()["metadata"]["langgraph_step"])
                state_sizes.append(
                    len(
                        json.dumps(request.state.get("runtime_loop_state", {})).encode()
                    )
                )
                return handler(request)

        graph = create_agent(
            BindableFakeMessagesChatModel(responses=loop_responses(1)),
            tools=[read_reference],
            middleware=[
                ModelCallLimitMiddleware(run_limit=10),
                *([LoopDetectionMiddleware(["read_reference"])] if enabled else []),
                Steps(),
            ],
        )
        return graph, calls, steps, state_sizes

    metrics = {}
    for enabled in (False, True):
        timings = []
        for _ in range(5):
            graph, calls, steps, state_sizes = make_graph(enabled)
            started = time.perf_counter()
            result = graph.invoke(
                {"messages": [("user", "normal")]}, {"recursion_limit": 100}
            )
            timings.append((time.perf_counter() - started) * 1000)
            assert len(calls) == 1 and result["messages"][-1].content == "done"
            assert "runtime_loop_state" not in result
        metrics[str(enabled)] = {
            "model_calls": len(steps),
            "last_model_step": steps[-1],
            "median_ms": round(statistics.median(timings), 3),
            "loop_state_bytes": state_sizes[-1],
        }
    assert metrics["True"]["model_calls"] == metrics["False"]["model_calls"] == 2
    assert metrics["True"]["last_model_step"] - metrics["False"]["last_model_step"] == 3
    assert metrics["False"]["loop_state_bytes"] == 2
    assert 2 < metrics["True"]["loop_state_bytes"] < 700
    print("f02-cost " + json.dumps(metrics))


def test_history_reset_and_auto_summary_tail_do_not_erase_checkpoint_count(monkeypatch):
    from runtime_service.middlewares import loop_detection as module

    monkeypatch.setattr(module, "get_config", lambda: {})
    mw = LoopDetectionMiddleware(["read_file"])
    marker = {
        "owner": "local",
        "cursor": None,
        "signature": None,
        "sequence": None,
        "repetitions": 0,
        "user": None,
    }
    messages = [HumanMessage(id="original", content="goal")] * 10000
    sizes = []
    for i in range(4):
        current = batch(ai_id=f"tail-{i}")
        messages = (
            messages + current
            if i < 2
            else [
                HumanMessage(
                    id="summary",
                    content="summary",
                    additional_kwargs={"lc_source": "summarization"},
                ),
                *current,
            ]
        )
        state = {"messages": messages, "runtime_loop_state": marker}
        marker = mw.before_model(state, Runtime())["runtime_loop_state"]
        sizes.append(len(json.dumps(marker)))
    assert marker["repetitions"] == 4 and max(sizes) - min(sizes) < 10


def test_unavailable_custom_and_diagnostics_do_not_replace_stop(monkeypatch):
    from runtime_service.middlewares import loop_detection as module

    monkeypatch.setattr(
        module,
        "record_diagnostic_event",
        lambda *args: (_ for _ in ()).throw(ConnectionError()),
    )
    monkeypatch.setattr(
        module,
        "build_budget_notice",
        lambda **kwargs: {"run_id": "run", "code": kwargs["code"], "scope": "primary"},
    )
    monkeypatch.setattr(module, "get_config", lambda: {})
    runtime = Runtime(
        stream_writer=lambda notice: (_ for _ in ()).throw(ConnectionError())
    )
    mw = LoopDetectionMiddleware(["read_file"])
    state = {"messages": [], "runtime_loop_state": {"owner": "local", "repetitions": 0}}
    for i in range(5):
        state["messages"] = batch(ai_id=f"batch-{i}")
        if i < 4:
            state.update(mw.before_model(state, runtime))
        else:
            with pytest.raises(RuntimeExecutionError):
                mw.before_model(state, runtime)


def test_repaired_tool_result_is_not_execution_evidence():
    from runtime_service.middlewares.runtime_config import sanitize_tool_call_messages

    message = batch()[0]
    repaired, changed = sanitize_tool_call_messages([message])
    assert changed and repaired[-1].additional_kwargs["_runtime_tool_call_repaired"]
    assert signature(repaired) is None


def test_new_run_without_new_input_skips_completed_history(monkeypatch):
    from runtime_service.middlewares import loop_detection as module

    monkeypatch.setattr(module, "get_config", lambda: {})
    mw = LoopDetectionMiddleware(["read_file"])
    state = {"messages": batch(ai_id="old")}
    state.update(mw.before_agent(state, Runtime()))
    assert mw.before_model(state, Runtime()) is None
    assert state["runtime_loop_state"]["repetitions"] == 0
    state["messages"] += batch(ai_id="new")
    assert mw.before_model(state, Runtime())["runtime_loop_state"]["repetitions"] == 1
