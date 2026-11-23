import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from langchain.agents.middleware import ModelRequest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from runtime_service.middlewares.pii_redaction import PiiRedactionMiddleware
from runtime_service.runtime.pii import PiiRedactionConfig
from runtime_service.services.dearflow_agent.middleware import dynamic_context, memory


def request(messages):
    return ModelRequest(
        model=FakeMessagesListChatModel(responses=[AIMessage(content="ok")]),
        messages=messages,
        system_message=SystemMessage(content="stable rules"),
        runtime=SimpleNamespace(context={}),
        state={"messages": messages},
    )


def test_date_is_fresh_on_same_middleware_without_mutating_history(monkeypatch):
    class Clock(datetime):
        day = 23

        @classmethod
        def now(cls, tz=None):
            assert tz is UTC
            return cls(2026, 11, cls.day, tzinfo=UTC)

    monkeypatch.setattr(dynamic_context, "datetime", Clock)
    original = request([HumanMessage(content="date?", id="user-1")])

    async def run():
        async def handler(value):
            return value

        middleware = dynamic_context.CurrentDateMiddleware()
        first = await middleware.awrap_model_call(original, handler)
        Clock.day = 24
        second = await middleware.awrap_model_call(original, handler)
        return first, second

    first, second = asyncio.run(run())
    assert "2026-11-23 UTC" in first.messages[0].text
    assert "2026-11-24 UTC" in second.messages[0].text
    assert len(original.messages) == len(original.state["messages"]) == 1
    assert original.system_message is first.system_message is second.system_message
    assert first.messages[-1] is original.messages[0]
    assert memory.source_text(first.messages[0]) is None


def test_projection_preserves_multimodal_user_and_tool_pair():
    user = HumanMessage(
        content=[
            {"type": "text", "text": "read this"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,cA=="}},
        ]
    )
    assistant = AIMessage(
        content="",
        tool_calls=[{"id": "c1", "name": "read_file", "args": {"file_path": "x"}}],
    )
    result = ToolMessage(content="value", tool_call_id="c1")
    original = [user, assistant, result]
    projected = dynamic_context.with_turn_context(original, "runtime_date", "today")
    projected = dynamic_context.with_turn_context(projected, "user_memory", "fact")
    assert [m.name for m in projected[:2]] == ["runtime_date", "user_memory"]
    assert projected[2:] == original
    assert all(a is b for a, b in zip(projected[2:], original, strict=True))
    replaced = dynamic_context.with_turn_context(projected, "runtime_date", "tomorrow")
    assert sum(m.name == "runtime_date" for m in replaced) == 1
    assert len(original) == 3


@pytest.mark.parametrize("allowed", [True, False])
def test_recall_uses_real_query_and_pii_protects_temporary_memory(monkeypatch, allowed):
    seen = []

    def recall(self, scope, query):
        seen.append(query)
        return "Contact alice@example.test"

    async def access(runtime):
        return allowed

    monkeypatch.setattr(memory.MemoryStorage, "context", recall)
    monkeypatch.setattr(memory, "memory_scope", lambda runtime: ("t", "p", "u"))
    monkeypatch.setattr(memory, "memory_allowed", access)
    pii = PiiRedactionConfig(True, "test-secret-" * 4, scope=("t", "p", "thread"))
    original = request([HumanMessage(content="current query", id="real-user")])

    async def run():
        async def capture(value):
            return value

        async def protect(value):
            return await PiiRedactionMiddleware(pii).awrap_model_call(value, capture)

        async def recall_memory(value):
            return await memory.MemoryContextMiddleware(object()).awrap_model_call(
                value, protect
            )

        return await dynamic_context.CurrentDateMiddleware().awrap_model_call(
            original, recall_memory
        )

    outbound = asyncio.run(run())
    assert seen == (["current query"] if allowed else [])
    text = "\n".join(m.text for m in outbound.messages)
    assert "alice@example.test" not in text
    assert ("<user_memory>" in text) is allowed
    assert original.system_message.text == "stable rules"
    assert len(original.messages) == 1


def test_maintenance_does_not_inject_date():
    original = request([])
    original.runtime.context["offload_conversation"] = True

    async def handler(value):
        return value

    assert (
        asyncio.run(
            dynamic_context.CurrentDateMiddleware().awrap_model_call(original, handler)
        )
        is original
    )
