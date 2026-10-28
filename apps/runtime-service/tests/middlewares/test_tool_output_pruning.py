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
    assert "[Tool output collapsed: 'search_web' returned 1000 chars" in t1.content

    # Tool 2: folded with file reference
    t2 = pruned[4]
    assert isinstance(t2, ToolMessage)
    assert t2.tool_call_id == "2"
    assert (
        "[Tool output reference: 'github_query' offloaded to /large_tool_results/abc123/2"
        in t2.content
    )

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
    assert "[Tool output collapsed: 't1' returned 800 chars" in t1.content[0]["text"]


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
    assert "[Tool output collapsed: 'tool_a'" in captured_req.messages[1].content
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
