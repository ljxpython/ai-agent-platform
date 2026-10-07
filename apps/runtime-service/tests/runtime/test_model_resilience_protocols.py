from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_deepseek import ChatDeepSeek

from runtime_service.middlewares import (
    ModelCallTimeoutMiddleware,
    ModelResilienceMiddleware,
)
from runtime_service.runtime import (
    AgentDefaults,
    RuntimeContext,
    RuntimePolicy,
    RuntimePrincipal,
    modeling,
    resolve_runtime_config,
)
from runtime_service.runtime.contracts import (
    ModelConnectionBundle,
    ModelResiliencePolicy,
)
from runtime_service.runtime.errors import RuntimeResolutionError
from runtime_service.services.reference_agent.tools import read_reference

A = "00000000-0000-0000-0000-000000000001"
B = "00000000-0000-0000-0000-000000000002"
IMAGE = "data:image/png;base64,aGVsbG8="


def history(*, thinking=False):
    content = [
        {"type": "text", "text": "prior answer", "cache_control": {"type": "ephemeral"}}
    ]
    if thinking:
        content.insert(
            0,
            {
                "type": "thinking",
                "thinking": "prior thought",
                "signature": "fixture-signature",
            },
        )
    return [
        HumanMessage(
            content=[
                {"type": "text", "text": "prior question"},
                {"type": "image_url", "image_url": {"url": IMAGE}},
            ]
        ),
        AIMessage(
            content=content,
            tool_calls=[
                {
                    "name": "read_reference",
                    "args": {"topic": "history"},
                    "id": "toolu_history",
                    "type": "tool_call",
                }
            ],
            response_metadata={"model_provider": "anthropic"},
        ),
        ToolMessage(
            "existing tool result", tool_call_id="toolu_history", name="read_reference"
        ),
        HumanMessage("continue with exactly sdk-ok"),
    ]


def reply(protocol):
    if protocol == "anthropic":
        return {
            "id": "msg_fixture",
            "type": "message",
            "role": "assistant",
            "model": "backup",
            "content": [{"type": "text", "text": "sdk-ok"}],
            "stop_reason": "end_turn",
            "stop_sequence": None,
            "usage": {"input_tokens": 12, "output_tokens": 3},
        }
    return {
        "id": "chatcmpl-fixture",
        "object": "chat.completion",
        "model": "backup",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "sdk-ok"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 3, "total_tokens": 15},
    }


def config():
    return resolve_runtime_config(
        principal=RuntimePrincipal("u", "t", "p", "developer", ()),
        context=RuntimeContext(),
        policy=RuntimePolicy("p1", (A, B), (), "tools-v2"),
        defaults=AgentDefaults(
            model_id=A, system_prompt="fixture", prompt_version="v1", max_tokens=100
        ),
    )


async def sdk_pair(monkeypatch, primary_protocol, backup_protocol, messages):
    calls = []

    def respond(request):
        body = json.loads(request.content)
        calls.append(body)
        if body["model"] == "primary":
            return httpx.Response(
                503,
                json={
                    "error": {
                        "type": "overloaded_error",
                        "message": "private detail",
                        "code": "overloaded",
                    }
                },
            )
        return httpx.Response(200, json=reply(backup_protocol))

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        openai_constructor, deepseek_constructor = (
            modeling.ChatOpenAIWithReasoning,
            modeling.ChatDeepSeek,
        )
        monkeypatch.setattr(
            modeling,
            "ChatOpenAIWithReasoning",
            lambda **kwargs: openai_constructor(http_async_client=client, **kwargs),
        )
        monkeypatch.setattr(
            modeling,
            "ChatDeepSeek",
            lambda **kwargs: deepseek_constructor(http_async_client=client, **kwargs),
        )
        monkeypatch.setattr(
            "langchain_anthropic.chat_models._get_default_async_httpx_client",
            lambda **kwargs: client,
        )

        def connection(protocol, name):
            return {
                "provider": protocol,
                "protocol": protocol,
                "model": name,
                "api_key": "fixture-key-" + name,
                "base_url": "https://sdk-fixture.invalid/v1",
            }

        resolved = config()
        primary = modeling.build_model(
            resolved, connection=connection(primary_protocol, "primary"), max_retries=0
        )
        policy = ModelResiliencePolicy(enabled=True, fallback_model_id=B)
        bundle = ModelConnectionBundle(
            primary=connection(primary_protocol, "primary"),
            fallback=connection(backup_protocol, "backup"),
            policy=policy,
        )
        backup = modeling.build_fallback_model(resolved, bundle)
        assert primary.max_retries == backup.max_retries == 0
        graph = create_agent(
            primary,
            tools=[read_reference],
            middleware=[
                ModelResilienceMiddleware(policy, backup, primary_model_id=A),
                ModelCallTimeoutMiddleware(1),
            ],
        )
        try:
            result = await graph.ainvoke({"messages": messages})
        except RuntimeResolutionError as exc:
            return calls, exc
        return calls, result


@pytest.mark.parametrize(
    "primary,backup",
    [
        ("openai-compatible", "anthropic"),
        ("anthropic", "openai-compatible"),
        ("deepseek", "openai-compatible"),
        ("openai-compatible", "deepseek"),
        ("anthropic", "anthropic"),
    ],
)
def test_real_sdks_preserve_image_and_history_tool_pair(monkeypatch, primary, backup):
    calls, result = asyncio.run(sdk_pair(monkeypatch, primary, backup, history()))
    assert isinstance(result, dict), result
    assert [call["model"] for call in calls] == ["primary", "backup"]
    wire = json.dumps(calls[1])
    assert all(
        value in wire
        for value in (
            "prior question",
            "aGVsbG8=",
            "prior answer",
            "existing tool result",
            "toolu_history",
            "history",
            "read_reference",
        )
    )
    assert result["messages"][-1].response_metadata["platform_model_resilience"] == {
        "version": 1,
        "requested_model_id": A,
        "effective_model_id": B,
        "attempts": 2,
        "fallback_used": True,
    }
    assert result["messages"][-1].usage_metadata["total_tokens"] == 15


@pytest.mark.parametrize(
    "backup,compatible",
    [("anthropic", True), ("openai-compatible", False), ("deepseek", False)],
)
def test_native_thinking_is_preserved_or_rejected_before_backup(
    monkeypatch, backup, compatible
):
    calls, result = asyncio.run(
        sdk_pair(monkeypatch, "anthropic", backup, history(thinking=True))
    )
    assert len(calls) == (2 if compatible else 1)
    if compatible:
        assert "fixture-signature" in json.dumps(calls[1])
        assert "prior thought" in json.dumps(calls[1])
        assert "cache_control" in json.dumps(calls[1])
    else:
        assert result.code == "runtime.model.fallback_incompatible"
        assert result.__context__ is None


def test_reasoning_binding_keeps_generation_retries_disabled():
    from runtime_service.services.dearflow_agent.modes import (
        apply_reasoning,
        resolve_mode,
    )

    model = ChatDeepSeek(model="deepseek-v4-flash", api_key="fixture", max_retries=0)
    bound, _ = apply_reasoning(model, resolve_mode("ultra"))
    assert bound.max_retries == 0
    assert bound.extra_body == {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    }
