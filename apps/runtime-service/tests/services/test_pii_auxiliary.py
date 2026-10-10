"""Auxiliary model entrances use synthetic input and safe fallback behavior."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from services.showcase_demo.test_images_chart import png
from services.test_suggestions import _facts

from runtime_service.runtime.errors import RuntimePrivacyError
from runtime_service.runtime.pii import PiiRedactionConfig
from runtime_service.services.dearflow_agent.middleware import memory
from runtime_service.services.suggestions import generate_suggestions
from runtime_service.tools import images
from runtime_service.utils.title_summarizer import summarize_thread_title

EMAIL = "alice@example.test"
SECRET = "synthetic-redaction-secret-32-bytes"


@pytest.fixture
def policy():
    return PiiRedactionConfig(True, SECRET, scope=("tenant", "project", "thread"))


@pytest.mark.parametrize(
    "result",
    [
        AIMessage("正常主题"),
        AIMessage(EMAIL),
        AIMessage("[EMAIL_abc]"),
        RuntimeError("PRIVATE_CANARY " + EMAIL),
    ],
)
def test_title_full_scan_before_cut_and_safe_output(policy, result, caplog):
    agent = SimpleNamespace(ainvoke=AsyncMock())
    if isinstance(result, Exception):
        agent.ainvoke.side_effect = result
    else:
        agent.ainvoke.return_value = {"messages": [result]}
    # Put the identifier across the old 200-character cutoff.
    message = "x" * 193 + " " + EMAIL
    title = asyncio.run(
        summarize_thread_title(
            [{"role": "user", "content": message}], agent=agent, pii_config=policy
        )
    )
    assert title == ("正常主题" if result == AIMessage("正常主题") else "新对话")
    prompt = agent.ainvoke.call_args.args[0]["messages"][0].content
    assert EMAIL not in prompt and "alice@" not in prompt
    assert EMAIL not in caplog.text and "PRIVATE_CANARY" not in caplog.text


def test_title_and_suggestions_missing_scope_zero_calls(monkeypatch):
    monkeypatch.setenv("RUNTIME_PII_REDACTION_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_PII_TOKEN_SECRET", SECRET)
    model = SimpleNamespace(ainvoke=AsyncMock())
    assert (
        asyncio.run(
            summarize_thread_title([{"role": "user", "content": EMAIL}], agent=model)
        )
        == "新对话"
    )
    model.ainvoke.assert_not_awaited()
    assert (
        asyncio.run(
            generate_suggestions(
                facts=_facts(),
                thread_id="wrong",
                payload={
                    "messages": [{"role": "user", "content": EMAIL}],
                    "context": {},
                },
                model=model,
            )
        )
        == []
    )
    model.ainvoke.assert_not_awaited()


def test_suggestions_input_and_output_protected(monkeypatch):
    monkeypatch.setenv("RUNTIME_PII_REDACTION_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_PII_TOKEN_SECRET", SECRET)
    model = SimpleNamespace(
        ainvoke=AsyncMock(return_value=AIMessage('["联系 ' + EMAIL + '"]'))
    )
    result = asyncio.run(
        generate_suggestions(
            facts=_facts(),
            thread_id="thread-1",
            payload={"messages": [{"role": "user", "content": EMAIL}], "context": {}},
            model=model,
        )
    )
    assert EMAIL not in str(model.ainvoke.call_args) and EMAIL not in str(result)
    assert "[EMAIL_" in result[0]


def test_vision_preserves_binary_and_blocks_unscoped(policy, monkeypatch, tmp_path):
    seen = []

    class Vision:
        def __init__(self, **kwargs):
            pass

        async def ainvoke(self, messages, **kwargs):
            seen.extend(messages)
            return AIMessage("square")

    monkeypatch.setattr(images, "ChatOpenAI", Vision)
    monkeypatch.setattr(
        images,
        "resolve_vision_config",
        lambda: ("fixture", "synthetic", "http://fixture.invalid", 128),
    )
    workspace = images.ImageWorkspace(tmp_path)
    path = workspace.save(png(), "generated")
    analyze = next(
        t
        for t in images.build_image_tools(workspace, policy)
        if t.name == "analyze_image"
    )
    assert (
        asyncio.run(analyze.ainvoke({"image_path": path, "question": EMAIL}))
        == "square"
    )
    assert EMAIL not in seen[0]["content"][0]["text"]
    assert seen[0]["content"][1]["image_url"]["url"].startswith(
        "data:image/png;base64,"
    )
    monkeypatch.setenv("RUNTIME_PII_REDACTION_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_PII_TOKEN_SECRET", SECRET)
    unscoped = next(
        t for t in images.build_image_tools(workspace) if t.name == "analyze_image"
    )
    with pytest.raises(RuntimePrivacyError):
        asyncio.run(unscoped.ainvoke({"image_path": path, "question": EMAIL}))
    assert len(seen) == 1


def memory_runtime():
    return SimpleNamespace(
        execution_info=SimpleNamespace(thread_id="thread", run_id="run")
    )


@pytest.mark.parametrize(
    "content",
    [
        "x" * 5999 + " " + EMAIL,
        [{"type": "text", "text": "alice@"}, {"type": "text", "text": "example.test"}],
    ],
)
def test_memory_full_source_filter_before_truncation_and_stale_source(
    policy, monkeypatch, content
):
    monkeypatch.setattr(
        memory, "memory_allowed", lambda _: asyncio.sleep(0, result=True)
    )
    monkeypatch.setattr(memory, "memory_scope", lambda _: ("t", "p", "u"))
    storage = SimpleNamespace(
        read=lambda *a: pytest.fail("filtered source must not query storage"),
        begin_extraction=lambda *a, **kw: pytest.fail(
            "filtered source must not enter running"
        ),
    )
    monkeypatch.setattr(memory, "MemoryStorage", lambda: storage)
    model = SimpleNamespace(
        with_structured_output=lambda *a, **kw: pytest.fail(
            "filtered source must not invoke model"
        )
    )
    mw = memory.MemoryContextMiddleware(model, policy)
    state = {
        "messages": [HumanMessage(content, id="source")],
        "dear_memory_source": {
            "id": "source",
            "text": "x" * 5999 + " ",
            "enabled": True,
            "epoch": 1,
        },
    }
    assert asyncio.run(mw.abefore_agent(state, memory_runtime())) == {
        "dear_memory_source": {}
    }
    asyncio.run(mw.aafter_agent(state, memory_runtime()))


def test_memory_mixed_queue_sources_keep_quote_and_filter_candidate_pii(
    policy, monkeypatch
):
    events = []

    class Store:
        def begin_extraction(self, *args, **kwargs):
            events.append(("begin", kwargs))
            return kwargs["deadline_at"]

        def reserve_extraction_attempt(self, *args, **kwargs):
            return True

        def propose(self, *args, **kwargs):
            events.append(("propose", kwargs))
            assert kwargs["source_text"] == "我喜欢中文"
            assert kwargs["candidates"][0]["quote"] in kwargs["source_text"]
            assert len(kwargs["candidates"]) == 1
            return {"status": "proposed", "added": 1}

        def finish_extraction(self, *args, **kwargs):
            events.append(("finish", kwargs))

    class Inbox:
        def __init__(self, dsn):
            pass

        def memory_sources(self, **kwargs):
            assert kwargs["sender_id"] == "u"
            return [{"id": "queued", "content": EMAIL}]

    monkeypatch.setenv("DATABASE_URI", "fixture")
    monkeypatch.setattr(memory, "MessageInbox", Inbox)
    monkeypatch.setattr(memory, "MemoryStorage", Store)
    monkeypatch.setattr(
        memory, "memory_allowed", lambda _: asyncio.sleep(0, result=True)
    )
    monkeypatch.setattr(memory, "memory_scope", lambda _: ("t", "p", "u"))
    candidates = memory.Candidates(
        candidates=[
            memory.Candidate(
                text="喜欢中文",
                quote="中文",
                source_message_id="main",
                scope="personal",
                durability="stable",
                authority="personal_fact",
            ),
            memory.Candidate(
                text=EMAIL,
                quote="中文",
                scope="personal",
                durability="stable",
                authority="personal_fact",
            ),
        ]
    )
    invoke = AsyncMock(
        return_value={"parsed": candidates, "raw": SimpleNamespace(usage_metadata={})}
    )
    model = SimpleNamespace(
        with_structured_output=lambda *a, **kw: SimpleNamespace(ainvoke=invoke)
    )
    mw = memory.MemoryContextMiddleware(model, policy)
    state = {
        "messages": [HumanMessage("我喜欢中文", id="main")],
        "dear_memory_source": {
            "id": "main",
            "text": "我喜欢中文",
            "enabled": True,
            "epoch": 1,
        },
        "runtime_message_claim": {"run_id": "run", "message_ids": ["queued"]},
    }
    asyncio.run(mw.aafter_agent(state, memory_runtime()))
    assert invoke.await_count == 1 and EMAIL not in str(invoke.call_args)
    assert [item[0] for item in events] == ["begin", "propose", "finish"]
    assert events[-1][1]["status"] == "succeeded"


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("sensitive_tail", [False, True])
def test_memory_long_inbox_source_scans_before_original_limit(
    policy, monkeypatch, enabled, sensitive_tail
):
    content = "x" * 5999 + " " + (EMAIL if sensitive_tail else "safe tail")
    storage = SimpleNamespace(
        read=lambda *a: {"epoch": 1, "automatic_candidates": True},
        begin_extraction=Mock(side_effect=lambda *a, **kw: kw["deadline_at"]),
        reserve_extraction_attempt=lambda *a, **kw: True,
        propose=Mock(return_value={"status": "proposed", "added": 0}),
        finish_extraction=Mock(),
    )
    monkeypatch.setenv("DATABASE_URI", "fixture")
    monkeypatch.setattr(memory, "MemoryStorage", lambda: storage)
    monkeypatch.setattr(
        memory,
        "MessageInbox",
        lambda _: SimpleNamespace(
            memory_sources=lambda **kw: [{"id": "queued", "content": content}]
        ),
    )
    monkeypatch.setattr(
        memory, "memory_allowed", lambda _: asyncio.sleep(0, result=True)
    )
    monkeypatch.setattr(memory, "memory_scope", lambda _: ("t", "p", "u"))
    invoke = AsyncMock(
        return_value={
            "parsed": memory.Candidates(candidates=[]),
            "raw": SimpleNamespace(usage_metadata={}),
        }
    )
    model = SimpleNamespace(
        with_structured_output=lambda *a, **kw: SimpleNamespace(ainvoke=invoke)
    )
    middleware = memory.MemoryContextMiddleware(
        model, policy if enabled else PiiRedactionConfig()
    )
    state = {"runtime_message_claim": {"run_id": "run", "message_ids": ["queued"]}}
    asyncio.run(middleware.aafter_agent(state, memory_runtime()))
    if enabled and sensitive_tail:
        invoke.assert_not_awaited()
        storage.begin_extraction.assert_not_called()
    else:
        invoke.assert_awaited_once()
        assert invoke.call_args.args[0][-1].content == content[:6000]
        assert storage.propose.call_args.kwargs["source_text"] == content[:6000]
