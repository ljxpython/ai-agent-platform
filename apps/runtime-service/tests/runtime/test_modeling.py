from __future__ import annotations

import pytest
from langchain_core.messages import AIMessageChunk

from runtime_service.runtime import (
    AgentDefaults,
    RuntimeContext,
    RuntimePolicy,
    RuntimePrincipal,
    RuntimeResolutionError,
    modeling,
    resolve_runtime_config,
)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("reasoning_content", "Qwen thought"),
        ("reasoning", "DeepSeek thought"),
        ("reasoning_details", [{"type": "reasoning.text", "text": "detail thought"}]),
    ],
)
def test_openai_compatible_preserves_reasoning(field: str, value: object) -> None:
    model = modeling.ChatOpenAIWithReasoning(model="test", api_key="test")
    response = {
        "model": "test",
        "choices": [{"message": {"role": "assistant", "content": "OK", field: value}, "finish_reason": "stop"}],
    }
    expected = value[0]["text"] if isinstance(value, list) else value
    message = model._create_chat_result(response).generations[0].message
    assert message.content == "OK"
    assert message.additional_kwargs["reasoning_content"] == expected

    chunk = model._convert_chunk_to_generation_chunk(
        {"choices": [{"delta": {"role": "assistant", field: value}}]}, AIMessageChunk, None
    )
    assert chunk is not None
    assert chunk.message.additional_kwargs["reasoning_content"] == expected


def _resolved(model_id: str):
    return resolve_runtime_config(
        principal=RuntimePrincipal("u", "t", "p", "developer", ()),
        context=RuntimeContext(),
        policy=RuntimePolicy("p1", (model_id,), (), "test-tools-v2"),
        defaults=AgentDefaults(
            model_id=model_id,
            system_prompt="prompt",
            prompt_version="v1",
            temperature=0,
            max_tokens=100,
        ),
    )


def test_build_deepseek_uses_proxy_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def fake_constructor(**kwargs: object) -> object:
        calls.update(kwargs)
        return object()

    monkeypatch.setattr(modeling, "ChatDeepSeek", fake_constructor)
    model = modeling.build_model(
        _resolved("deepseek:deepseek-chat"),
        env={"DEEPSEEK_PROXY_API_KEY": "key", "DEEPSEEK_PROXY_URL": "https://deepseek.test/v1"},
    )

    assert model is not None
    assert calls["model"] == "deepseek-chat"
    assert calls["api_key"] == "key"
    assert calls["base_url"] == "https://deepseek.test/v1"
    assert calls["temperature"] == 0.0


def test_build_deepseek_without_prefix_uses_proxy_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def fake_constructor(**kwargs: object) -> object:
        calls.update(kwargs)
        return object()

    monkeypatch.setattr(modeling, "ChatDeepSeek", fake_constructor)
    model = modeling.build_model(
        _resolved("DeepSeek-V4-Flash"),
        env={"DEEPSEEK_PROXY_API_KEY": "key", "DEEPSEEK_PROXY_URL": "https://deepseek.test/v1"},
    )

    assert model is not None
    assert calls["model"] == "DeepSeek-V4-Flash"
    assert calls["api_key"] == "key"
    assert calls["base_url"] == "https://deepseek.test/v1"
    assert calls["temperature"] == 0.0


def test_build_openai_uses_gpt_proxy_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def fake_constructor(**kwargs: object) -> object:
        calls.update(kwargs)
        return object()

    monkeypatch.setattr(modeling, "ChatOpenAIWithReasoning", fake_constructor)
    modeling.build_model(
        _resolved("openai:gpt-5.5"),
        env={"GPT_PROXY_API_KEY": "key", "GPT_PROXY_URL": "https://gpt.test/v1"},
    )

    assert calls["model"] == "gpt-5.5"
    assert calls["api_key"] == "key"
    assert calls["base_url"] == "https://gpt.test/v1"


def test_build_model_uses_catalog_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def fake_constructor(**kwargs: object) -> object:
        calls.update(kwargs)
        return object()

    monkeypatch.setattr(modeling, "ChatDeepSeek", fake_constructor)
    modeling.build_model(
        _resolved("deepseek:catalog-chat"),
        env={},
        connection={
            "provider": "deepseek",
            "base_url": "https://catalog.test/v1",
            "protocol": "deepseek",
            "model": "catalog-chat",
            "api_key": "catalog-key",
        },
    )
    assert calls["api_key"] == "catalog-key"
    assert calls["base_url"] == "https://catalog.test/v1"


def test_build_model_rejects_missing_provider_settings() -> None:
    with pytest.raises(RuntimeResolutionError) as error:
        modeling.build_model(_resolved("deepseek:deepseek-chat"), env={})
    assert error.value.code == "runtime.model.initialization_failed"


def test_build_model_uses_standard_initializer_for_other_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def fake_initializer(model: str, **kwargs: object) -> object:
        calls["model"] = model
        calls["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(modeling, "init_chat_model", fake_initializer)
    modeling.build_model(_resolved("anthropic:claude-sonnet"), env={})
    assert calls == {"model": "anthropic:claude-sonnet", "kwargs": {"temperature": 0.0, "max_tokens": 100}}


def test_build_model_does_not_accept_raw_context() -> None:
    with pytest.raises(RuntimeResolutionError) as error:
        modeling.build_model(RuntimeContext())  # type: ignore[arg-type]
    assert error.value.code == "runtime.model.invalid_config"


def test_build_model_supports_proxy_providers_and_protocols(monkeypatch: pytest.MonkeyPatch) -> None:
    deepseek_calls: dict[str, object] = {}
    openai_calls: dict[str, object] = {}

    def fake_deepseek(**kwargs: object) -> object:
        deepseek_calls.update(kwargs)
        return object()

    def fake_openai(**kwargs: object) -> object:
        openai_calls.update(kwargs)
        return object()

    monkeypatch.setattr(modeling, "ChatDeepSeek", fake_deepseek)
    monkeypatch.setattr(modeling, "ChatOpenAIWithReasoning", fake_openai)

    # 1. deepseek-proxy
    modeling.build_model(
        _resolved("DeepSeek-V4-Flash"),
        env={},
        connection={
            "provider": "deepseek-proxy",
            "base_url": "http://proxy.test/v1",
            "protocol": "openai-compatible",
            "model": "DeepSeek-V4-Flash",
            "api_key": "test-key-ds",
        },
    )
    assert deepseek_calls["model"] == "DeepSeek-V4-Flash"
    assert deepseek_calls["api_key"] == "test-key-ds"
    assert deepseek_calls["base_url"] == "http://proxy.test/v1"

    # 2. gpt-proxy
    modeling.build_model(
        _resolved("gpt-4o"),
        env={},
        connection={
            "provider": "gpt-proxy",
            "base_url": "http://proxy.test/v1",
            "protocol": "openai-compatible",
            "model": "gpt-4o",
            "api_key": "test-key-gpt",
        },
    )
    assert openai_calls["model"] == "gpt-4o"
    assert openai_calls["api_key"] == "test-key-gpt"
    assert openai_calls["base_url"] == "http://proxy.test/v1"

    # 3. 自定义中转站 (custom provider + base_url)
    openai_calls.clear()
    modeling.build_model(
        _resolved("my-custom-model"),
        env={},
        connection={
            "provider": "custom-relay",
            "base_url": "http://relay.test/v1",
            "protocol": "openai-compatible",
            "model": "my-custom-model",
            "api_key": "relay-key",
        },
    )
    assert openai_calls["model"] == "my-custom-model"
    assert openai_calls["api_key"] == "relay-key"
    assert openai_calls["base_url"] == "http://relay.test/v1"

    # 4. anthropic 原生协议与提供商
    anthropic_calls: dict[str, object] = {}

    def fake_anthropic(**kwargs: object) -> object:
        anthropic_calls.update(kwargs)
        return object()

    monkeypatch.setattr(modeling, "ChatAnthropic", fake_anthropic)
    modeling.build_model(
        _resolved("claude-3-7-sonnet"),
        env={},
        connection={
            "provider": "anthropic",
            "base_url": "https://api.anthropic.com/v1",
            "protocol": "anthropic",
            "model": "claude-3-7-sonnet",
            "api_key": "sk-ant-test",
        },
    )
    assert anthropic_calls["model"] == "claude-3-7-sonnet"
    assert anthropic_calls["api_key"] == "sk-ant-test"
    assert anthropic_calls["base_url"] == "https://api.anthropic.com/v1"


def test_chat_openai_with_reasoning_exposes_streaming_reasoning_content_blocks() -> None:
    from langchain_core.messages import AIMessageChunk

    model = modeling.ChatOpenAIWithReasoning(
        model="glm-5.3",
        api_key="test-key",
        base_url="https://relay.example.com/v1",
    )
    gen_chunk = model._convert_chunk_to_generation_chunk(
        {
            "id": "chatcmpl-1",
            "choices": [
                {
                    "index": 0,
                    "delta": {
                        "role": "assistant",
                        "content": "",
                        "reasoning_content": "The user is asking a simple identity question.",
                    },
                }
            ],
        },
        AIMessageChunk,
        {},
    )
    assert gen_chunk is not None
    assert gen_chunk.message.additional_kwargs["reasoning_content"] == (
        "The user is asking a simple identity question."
    )
    assert gen_chunk.message.content_blocks == [
        {
            "type": "reasoning",
            "reasoning": "The user is asking a simple identity question.",
        }
    ]
