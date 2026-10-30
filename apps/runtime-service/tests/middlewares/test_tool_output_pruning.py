from __future__ import annotations

import asyncio
from types import SimpleNamespace

from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from runtime_service.middlewares.tool_output_pruning import (
    ToolOutputPruningMiddleware,
    prune_messages_for_model,
)


def test_prune_messages_noop_when_tools_under_keep_recent():
    messages = [
        HumanMessage(content="hello"),
        AIMessage(
            content="thinking", tool_calls=[{"name": "t1", "args": {}, "id": "1"}]
        ),
        ToolMessage(content="result 1" * 50, tool_call_id="1", name="t1"),
        AIMessage(
            content="thinking 2", tool_calls=[{"name": "t2", "args": {}, "id": "2"}]
        ),
        ToolMessage(content="result 2" * 50, tool_call_id="2", name="t2"),
    ]
    # keep_recent=2, total tools=2 -> noop
    pruned = prune_messages_for_model(messages, keep_recent=2, min_chars=100)
    assert pruned is messages


def test_default_pruning_retains_small_evidence_and_large_head_tail_reference():
    from runtime_service.middlewares.tool_output_pruning import _prune_tool_content

    short = "important qualifier " * 100
    assert _prune_tool_content(short, "source", 8192) == (short, False)
    raw = (
        "HEAD_CANARY\n/large_tool_results/hash/source\n" + "x" * 12000 + "\nTAIL_CANARY"
    )
    preview, changed = _prune_tool_content(raw, "source", 8192)
    assert changed and len(preview) <= 6000
    assert preview.startswith("HEAD_CANARY") and preview.endswith("TAIL_CANARY")
    assert "Full text: /large_tool_results/hash/source" in preview
    assert "checkpoint" not in preview


def test_prune_messages_folds_older_tools_keeps_recent():
    messages = [
        HumanMessage(content="hello"),
        # Tool 1 (older)
        AIMessage(
            content="call 1", tool_calls=[{"name": "search_web", "args": {}, "id": "1"}]
        ),
        ToolMessage(content="x" * 1000, tool_call_id="1", name="search_web"),
        # Tool 2 (older with file reference)
        AIMessage(
            content="call 2",
            tool_calls=[{"name": "github_query", "args": {}, "id": "2"}],
        ),
        ToolMessage(
            content="Tool result saved in the filesystem at this path: /large_tool_results/abc123/2 preview:\n"
            + ("y" * 800),
            tool_call_id="2",
            name="github_query",
        ),
        # Tool 3 (older but short -> should NOT fold)
        AIMessage(content="call 3", tool_calls=[{"name": "ls", "args": {}, "id": "3"}]),
        ToolMessage(content="short output", tool_call_id="3", name="ls"),
        # Tool 4 (recent -> keep full)
        AIMessage(
            content="call 4", tool_calls=[{"name": "execute", "args": {}, "id": "4"}]
        ),
        ToolMessage(content="z" * 1500, tool_call_id="4", name="execute"),
    ]

    # keep_recent=1: tools 1, 2, 3 are older; tool 4 is recent
    pruned = prune_messages_for_model(messages, keep_recent=1, min_chars=300)
    assert len(pruned) == len(messages)

    # Tool 1: folded with char count
    t1 = pruned[2]
    assert isinstance(t1, ToolMessage)
    assert t1.tool_call_id == "1"
    assert "Earlier 'search_web' result" in t1.content
    assert t1.content.startswith("x") and t1.content.endswith("x")
    assert "checkpoint" not in t1.content

    # Tool 2: folded with file reference
    t2 = pruned[4]
    assert isinstance(t2, ToolMessage)
    assert t2.tool_call_id == "2"
    assert "Full text: /large_tool_results/abc123/2" in t2.content

    # Tool 3: short (<300), remains intact
    t3 = pruned[6]
    assert t3.content == "short output"

    # Tool 4: recent, remains full 1500 chars
    t4 = pruned[8]
    assert t4.content == "z" * 1500


def test_prune_messages_preserves_multimodal_blocks():
    image_block = {"type": "image", "data": "base64..."}
    messages = [
        AIMessage(content="call 1", tool_calls=[{"name": "t1", "args": {}, "id": "1"}]),
        ToolMessage(
            content=[{"type": "text", "text": "w" * 800}, image_block],
            tool_call_id="1",
            name="t1",
        ),
        AIMessage(content="call 2", tool_calls=[{"name": "t2", "args": {}, "id": "2"}]),
        ToolMessage(content="recent", tool_call_id="2", name="t2"),
    ]

    pruned = prune_messages_for_model(messages, keep_recent=1, min_chars=300)
    t1 = pruned[1]
    assert isinstance(t1.content, list)
    assert len(t1.content) == 2
    assert t1.content[1] == image_block
    assert "Earlier 't1' result" in t1.content[0]["text"]


def test_pruning_keeps_entire_latest_parallel_batch_until_model_consumes_it():
    calls = [{"name": "github_query", "args": {}, "id": str(i)} for i in range(6)]
    results = [
        ToolMessage(
            content=f"source {i}: " + "x" * 500,
            tool_call_id=str(i),
            name="github_query",
        )
        for i in range(6)
    ]
    messages = [
        HumanMessage(content="research"),
        AIMessage(content="", tool_calls=calls),
        *results,
    ]

    pruned = prune_messages_for_model(messages, keep_recent=4)
    assert pruned is messages
    assert all(
        m.content == original.content
        for m, original in zip(pruned[-6:], results, strict=True)
    )
    consumed = prune_messages_for_model(
        [*messages, AIMessage(content="finished")], keep_recent=4, min_chars=300
    )
    assert "omitted middle" in consumed[2].content

    next_messages = [
        *messages,
        AIMessage(
            content="observed all six",
            tool_calls=[{"name": "ls", "args": {}, "id": "next"}],
        ),
        ToolMessage(content="latest", tool_call_id="next", name="ls"),
    ]
    later = prune_messages_for_model(next_messages, keep_recent=4, min_chars=300)
    assert "omitted middle" in later[2].content
    assert next_messages[2].content == results[0].content


def test_pruning_preserves_current_turn_task_reports_but_folds_previous_turns():
    def result(name, call_id):
        return [
            AIMessage(
                content="", tool_calls=[{"name": name, "args": {}, "id": call_id}]
            ),
            ToolMessage(content="evidence " * 100, tool_call_id=call_id, name=name),
        ]

    messages = [
        HumanMessage(content="previous task"),
        *result("task", "old"),
        HumanMessage(content="current task"),
        *result("task", "current"),
        *result("github_query", "read1"),
        *result("github_query", "read2"),
        *result("github_query", "read3"),
        *result("github_query", "read4"),
        *result("github_query", "read5"),
    ]
    pruned = prune_messages_for_model(messages, keep_recent=4, min_chars=300)
    assert "omitted middle" in pruned[2].content
    assert pruned[5].content == messages[5].content
    assert "omitted middle" in pruned[7].content
    assert messages[2].content == "evidence " * 100


def test_middleware_does_not_discard_old_evidence_below_context_pressure():
    messages = [HumanMessage(content="research")]
    for i in range(6):
        messages.extend(
            [
                AIMessage(
                    content="",
                    tool_calls=[{"name": "read_file", "args": {}, "id": str(i)}],
                ),
                ToolMessage(
                    content="evidence " * 100, tool_call_id=str(i), name="read_file"
                ),
            ]
        )
    middleware = ToolOutputPruningMiddleware(trigger_tokens=10_000)
    request = ModelRequest(model=SimpleNamespace(), messages=messages)
    assert middleware._filter_request(request) is request


def test_middleware_pressure_includes_system_and_tool_schemas():
    from langchain_core.messages import SystemMessage

    messages = [
        HumanMessage(content="research"),
        AIMessage(
            content="", tool_calls=[{"name": "read_file", "args": {}, "id": "old"}]
        ),
        ToolMessage(content="evidence " * 100, tool_call_id="old", name="read_file"),
        AIMessage(
            content="", tool_calls=[{"name": "read_file", "args": {}, "id": "new"}]
        ),
        ToolMessage(content="recent", tool_call_id="new", name="read_file"),
    ]
    middleware = ToolOutputPruningMiddleware(
        trigger_tokens=500, keep_recent=1, min_chars=300
    )
    small = ModelRequest(model=SimpleNamespace(), messages=messages)
    assert middleware._filter_request(small) is small
    for request in [
        small.override(system_message=SystemMessage(content="policy " * 500)),
        small.override(
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "read_file",
                        "description": "schema " * 500,
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
            ]
        ),
    ]:
        projected = middleware._filter_request(request)
        assert "omitted middle" in projected.messages[2].content
        assert projected.messages[4].content == "recent"
        assert messages[2].content == "evidence " * 100


def test_middleware_wrap_model_call(monkeypatch):
    monkeypatch.setenv("AGENT_CONTEXT_TOOL_PRUNING_KEEP_COUNT", "1")
    monkeypatch.setenv("AGENT_CONTEXT_TOOL_PRUNING_MIN_CHARS", "200")

    mw = ToolOutputPruningMiddleware()
    messages = [
        HumanMessage(content="start"),
        ToolMessage(content="a" * 1000, tool_call_id="1", name="tool_a"),
        ToolMessage(content="b" * 1000, tool_call_id="2", name="tool_b"),
    ]

    dummy_model = SimpleNamespace()
    req = ModelRequest(model=dummy_model, messages=messages)

    captured_req = None

    def dummy_handler(r):
        nonlocal captured_req
        captured_req = r
        return SimpleNamespace()

    mw.wrap_model_call(req, dummy_handler)

    assert captured_req is not None
    # tool_a should be pruned, tool_b should be intact
    assert "Earlier 'tool_a' result" in captured_req.messages[1].content
    assert captured_req.messages[2].content == "b" * 1000
    # Original req messages remain unmutated!
    assert req.messages[1].content == "a" * 1000


def test_middleware_async_wrap_and_disabled(monkeypatch):
    monkeypatch.setenv("AGENT_CONTEXT_TOOL_PRUNING_ENABLED", "0")
    mw = ToolOutputPruningMiddleware()

    messages = [
        HumanMessage(content="start"),
        ToolMessage(content="a" * 1000, tool_call_id="1", name="tool_a"),
        ToolMessage(content="b" * 1000, tool_call_id="2", name="tool_b"),
    ]
    req = ModelRequest(model=SimpleNamespace(), messages=messages)

    async def dummy_async_handler(r):
        return r

    res = asyncio.run(mw.awrap_model_call(req, dummy_async_handler))
    # Disabled -> messages are identical
    assert res.messages[1].content == "a" * 1000
