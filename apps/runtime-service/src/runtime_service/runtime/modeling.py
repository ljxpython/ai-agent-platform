"""Explicit Provider-to-ChatModel construction for resolved Runtime config."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from collections.abc import Mapping
from typing import Any

import httpx
import openai
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk, ChatResult
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI

try:
    from langchain_anthropic import ChatAnthropic
except ImportError:  # pragma: no cover
    ChatAnthropic = None  # type: ignore[assignment, misc]

from dataclasses import replace

from runtime_service.errors import RuntimeAuthError, RuntimeResolutionError
from runtime_service.runtime.contracts import (
    ModelConnectionBundle,
    ModelResiliencePolicy,
    ResolvedRuntimeConfig,
)


def _reasoning_text(message: Mapping[str, object]) -> str:
    for field in ("reasoning_content", "reasoning"):
        value = message.get(field)
        if isinstance(value, str) and value:
            return value
    details = message.get("reasoning_details")
    if isinstance(details, list):
        return "".join(
            item["text"]
            for item in details
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        )
    return ""


class ChatOpenAIWithReasoning(ChatOpenAI):
    """Preserve reasoning fields returned by OpenAI-compatible providers."""

    def _create_chat_result(
        self, response: dict | openai.BaseModel, generation_info: dict | None = None
    ) -> ChatResult:
        result = super()._create_chat_result(response, generation_info)
        data = response if isinstance(response, dict) else response.model_dump()
        for choice, generation in zip(
            data.get("choices", []), result.generations, strict=False
        ):
            generation.message.response_metadata = {
                **generation.message.response_metadata,
                "model_provider": "openai_compatible",
            }
            reasoning = _reasoning_text(choice.get("message", {}))
            if reasoning:
                generation.message.additional_kwargs["reasoning_content"] = reasoning
        return result

    def _convert_chunk_to_generation_chunk(
        self, chunk: dict, default_chunk_class: type, base_generation_info: dict | None
    ) -> ChatGenerationChunk | None:
        result = super()._convert_chunk_to_generation_chunk(
            chunk, default_chunk_class, base_generation_info
        )
        if (
            result
            and isinstance(result.message, AIMessageChunk)
            and chunk.get("choices")
        ):
            result.message.response_metadata = {
                **result.message.response_metadata,
                "model_provider": "openai_compatible",
            }
            reasoning = _reasoning_text(chunk["choices"][0].get("delta") or {})
            if reasoning:
                result.message.additional_kwargs["reasoning_content"] = reasoning
        return result

    def _get_request_payload(
        self,
        input_: LanguageModelInput,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        messages_input = self._convert_input(input_).to_messages()

        if "messages" in payload and isinstance(payload["messages"], list):
            cleaned_messages: list[dict[str, Any]] = []
            for idx, msg_dict in enumerate(payload["messages"]):
                msg_obj = messages_input[idx] if idx < len(messages_input) else None

                if msg_dict.get("role") == "assistant":
                    # 1. 恢复 reasoning_content 传递给支持思考链的 OpenAI 兼容端点（如 DeepSeek/Thinking 模型）
                    if "reasoning_content" not in msg_dict and msg_obj is not None:
                        reasoning = (
                            msg_obj.additional_kwargs.get("reasoning_content")
                            or msg_obj.additional_kwargs.get("reasoning")
                            or getattr(msg_obj, "reasoning_content", None)
                        )
                        if reasoning and isinstance(reasoning, str):
                            msg_dict["reasoning_content"] = reasoning

                    # 2. 净化 content 结构（移除非标准 content blocks，如 reasoning、tool_call，防止 400 校验失败）
                    content = msg_dict.get("content")
                    if isinstance(content, list):
                        valid_blocks = []
                        for b in content:
                            if isinstance(b, dict):
                                b_type = b.get("type")
                                if b_type in (
                                    "reasoning",
                                    "thinking",
                                    "reasoning_content",
                                    "tool_call",
                                    "invalid_tool_call",
                                ):
                                    continue
                                valid_blocks.append(b)
                            else:
                                valid_blocks.append(b)
                        if not valid_blocks:
                            msg_dict["content"] = (
                                None
                                if (
                                    "tool_calls" in msg_dict
                                    or "function_call" in msg_dict
                                )
                                else ""
                            )
                        elif (
                            len(valid_blocks) == 1
                            and isinstance(valid_blocks[0], dict)
                            and valid_blocks[0].get("type") == "text"
                        ):
                            msg_dict["content"] = valid_blocks[0].get("text", "")
                        else:
                            msg_dict["content"] = valid_blocks

                cleaned_messages.append(msg_dict)
            payload["messages"] = cleaned_messages

        return payload


def _generation_kwargs(
    config: ResolvedRuntimeConfig, *, max_retries: int | None = None
) -> dict[str, object]:
    kwargs = {
        key: value
        for key, value in {
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "top_p": config.top_p,
        }.items()
        if value is not None
    }
    if max_retries is not None:
        kwargs["max_retries"] = max_retries
    return kwargs


def _required(settings: Mapping[str, str], name: str) -> str:
    value = settings.get(name)
    if not value:
        raise RuntimeResolutionError("runtime.model.initialization_failed", "model_id")
    return value


def resolve_model_max_output_tokens(
    *,
    model_name: str | None = None,
    provider: str | None = None,
    capacity: int | None = None,
    explicit_max_output: int | None = None,
) -> int:
    """Resolve a safe, sensible maximum output tokens bound for model profiling.

    1. If explicitly configured (> 0), respect it.
    2. Otherwise infer physical limit from well-known model/family signatures:
       - Reasoning / Thinking models (o1, o3, r1): 32768
       - GPT-4o / GPT-4-turbo / Claude 3.7: 16384
       - DeepSeek / Qwen / Claude / GLM / Kimi / MiniMax: 8192
       - Default unknown: 4096
    3. Dynamic safety clamp: Never exceed 25% of total capacity if capacity is small,
       with a safe lower floor of 512, to prevent tiny-context models from having negative input budget.
    """
    if (
        explicit_max_output is not None
        and isinstance(explicit_max_output, int)
        and explicit_max_output > 0
    ):
        return explicit_max_output

    name = (model_name or "").lower()
    prov = (provider or "").lower()

    if any(k in name for k in ("-r1", "deepseek-r1", "o1", "o3", "reasoner")):
        physical_limit = 32768
    elif any(k in name for k in ("gpt-4o", "gpt-4-turbo", "claude-3-7")):
        physical_limit = 16384
    elif any(
        k in name for k in ("deepseek", "qwen", "claude", "glm", "kimi", "minimax")
    ):
        physical_limit = 8192
    elif any(
        k in prov for k in ("deepseek", "qwen", "anthropic", "maomaoai", "doubao")
    ):
        physical_limit = 8192
    else:
        physical_limit = 4096

    if capacity is not None and capacity > 0:
        # Dynamic clamp to 25% of capacity for small models, with a safe lower floor of 512.
        safe_ratio_cap = max(512, capacity // 4)
        return max(512, min(physical_limit, safe_ratio_cap))

    return physical_limit


def _with_context_capacity(
    model: BaseChatModel, connection: Mapping[str, object] | None
) -> BaseChatModel:
    capacity = connection.get("context_window_tokens") if connection else None
    if capacity is not None:
        if type(capacity) is not int or capacity <= 0:
            raise RuntimeResolutionError(
                "runtime.model.initialization_failed", "context_window_tokens"
            )
        model_name = str(
            connection.get("model")
            or getattr(model, "model_name", None)
            or getattr(model, "model", "")
        )
        provider = str(connection.get("provider") or "")
        explicit_max = connection.get("max_output_tokens")
        max_output = resolve_model_max_output_tokens(
            model_name=model_name,
            provider=provider,
            capacity=capacity,
            explicit_max_output=explicit_max if isinstance(explicit_max, int) else None,
        )
        model.profile = {
            **(model.profile or {}),
            "max_input_tokens": capacity,
            "max_output_tokens": max_output,
        }
    return model


def build_model(
    config: ResolvedRuntimeConfig,
    *,
    env: Mapping[str, str] | None = None,
    connection: Mapping[str, Any] | None = None,
    max_retries: int | None = None,
) -> BaseChatModel:
    """Build a model from a resolved ID; never accepts raw request config."""

    if not isinstance(config, ResolvedRuntimeConfig):
        raise RuntimeResolutionError("runtime.model.invalid_config")
    settings = os.environ if env is None else env
    provider, separator, model_name = config.model_id.partition(":")
    model_name = model_name if separator else config.model_id
    if not separator:
        if "deepseek" in config.model_id.lower():
            provider = "deepseek"
        elif "gpt" in config.model_id.lower() or "openai" in config.model_id.lower():
            provider = "openai"
    provider = provider.strip().lower()
    protocol = ""

    if connection is not None:
        provider = str(connection.get("provider", provider)).strip().lower()
        model_name = connection.get("model", model_name)
        protocol = str(connection.get("protocol", "")).strip().lower()

    from runtime_service.runtime.token_budget import token_budget_enabled

    # SDK retries run inside one callback and cannot report separate usage facts.
    kwargs = _generation_kwargs(
        config, max_retries=0 if token_budget_enabled() else max_retries
    )
    from runtime_service.observability.usage import safe_pricing

    kwargs["metadata"] = {
        "runtime_usage_model": {
            "model_id": connection.get("model_id") if connection else None,
            "provider": provider,
            "protocol": protocol,
            "model_name": model_name,
            "pricing": safe_pricing(connection.get("pricing")) if connection else None,
        }
    }

    try:
        conn_api_key = connection.get("api_key") if connection is not None else None
        conn_base_url = connection.get("base_url") if connection is not None else None

        if provider in ("deepseek", "deepseek-proxy") or protocol == "deepseek":
            return _with_context_capacity(
                ChatDeepSeek(
                    model=model_name,
                    api_key=conn_api_key
                    or _required(settings, "DEEPSEEK_PROXY_API_KEY"),
                    base_url=conn_base_url or _required(settings, "DEEPSEEK_PROXY_URL"),
                    stream_usage=True,
                    **kwargs,
                ),
                connection,
            )
        if provider in ("openai", "gpt-proxy") or protocol in (
            "openai",
            "openai-compatible",
            "openai_compatible",
        ):
            return _with_context_capacity(
                ChatOpenAIWithReasoning(
                    model=model_name,
                    api_key=conn_api_key
                    or settings.get("GPT_PROXY_API_KEY")
                    or "EMPTY",
                    base_url=conn_base_url or _required(settings, "GPT_PROXY_URL"),
                    stream_usage=True,
                    **kwargs,
                ),
                connection,
            )
        if (
            protocol in ("anthropic", "anthropic-messages")
            or (
                connection is not None
                and provider in ("anthropic", "claude", "anthropic-proxy")
            )
            or provider == "anthropic-proxy"
        ):
            if ChatAnthropic is None:
                raise RuntimeResolutionError(
                    "runtime.model.initialization_failed",
                    "langchain-anthropic not installed",
                )
            return _with_context_capacity(
                ChatAnthropic(
                    model=model_name,
                    api_key=conn_api_key
                    or settings.get("ANTHROPIC_PROXY_API_KEY")
                    or settings.get("ANTHROPIC_API_KEY")
                    or "EMPTY",
                    base_url=conn_base_url
                    or settings.get("ANTHROPIC_PROXY_URL")
                    or settings.get("ANTHROPIC_API_URL")
                    or "https://api.anthropic.com",
                    stream_usage=True,
                    **kwargs,
                ),
                connection,
            )
        if connection is not None and conn_base_url:
            return _with_context_capacity(
                ChatOpenAIWithReasoning(
                    model=model_name,
                    api_key=conn_api_key or "EMPTY",
                    base_url=conn_base_url,
                    stream_usage=True,
                    **kwargs,
                ),
                connection,
            )
        return _with_context_capacity(
            init_chat_model(config.model_id, **kwargs), connection
        )
    except RuntimeResolutionError:
        raise
    except Exception as exc:
        raise RuntimeResolutionError(
            "runtime.model.initialization_failed", "model_id"
        ) from exc


async def fetch_model_bundle(
    reference: object,
    *,
    model_id: str,
    project_id: str,
    allowed_model_ids: tuple[str, ...] | None = None,
) -> ModelConnectionBundle:
    """Resolve a server-issued opaque reference without persisting credentials."""
    if reference is None:
        return ModelConnectionBundle()
    endpoint = os.getenv("PLATFORM_RUNTIME_MODEL_CONFIG_URL", "").strip()
    if (
        not isinstance(reference, str)
        or not reference
        or not endpoint
        or not project_id
    ):
        raise RuntimeResolutionError("runtime.model.initialization_failed", "model_id")
    headers = {"x-runtime-model-ref": reference, "x-project-id": project_id}
    secret = os.getenv("PLATFORM_RUNTIME_DELEGATION_SECRET", "")
    if secret:
        timestamp = str(int(time.time()))
        headers["x-runtime-model-time"] = timestamp
        headers["x-runtime-model-signature"] = hmac.new(
            secret.encode(),
            f"{timestamp}\n{project_id}\n{reference}".encode(),
            hashlib.sha256,
        ).hexdigest()
    try:
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            response = await client.get(
                endpoint,
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        code = (
            "runtime.model.reference_denied"
            if exc.response.status_code in {401, 403}
            else "runtime.model.initialization_failed"
        )
        raise RuntimeResolutionError(code, "model_id") from None
    except (httpx.HTTPError, ValueError):
        raise RuntimeResolutionError(
            "runtime.model.initialization_failed", "model_id"
        ) from None
    primary = _parse_connection(payload, model_id=model_id)
    if "resilience_version" not in payload and "model_resilience" not in payload:
        return ModelConnectionBundle(primary=primary)
    if (
        type(payload.get("resilience_version")) is not int
        or payload["resilience_version"] != 1
    ):
        raise RuntimeResolutionError("runtime.model.invalid_resilience")
    policy = ModelResiliencePolicy.from_payload(payload.get("model_resilience"))
    if not policy.enabled:
        raise RuntimeResolutionError("runtime.model.invalid_resilience")
    fallback = None
    if policy.fallback_model_id and policy.fallback_model_id != model_id:
        if (
            allowed_model_ids is not None
            and policy.fallback_model_id not in allowed_model_ids
        ):
            raise RuntimeAuthError("runtime.model.not_allowed", "fallback_model_id")
        fallback = _parse_connection(
            payload.get("fallback_connection"), model_id=policy.fallback_model_id
        )
    elif payload.get("fallback_connection") is not None:
        raise RuntimeResolutionError("runtime.model.invalid_resilience")
    return ModelConnectionBundle(primary=primary, fallback=fallback, policy=policy)


def _parse_connection(payload: object, *, model_id: str) -> Mapping[str, Any]:
    required = ("provider", "base_url", "protocol", "model", "api_key")
    if (
        not isinstance(payload, dict)
        or payload.get("model_id") != model_id
        or any(
            not isinstance(payload.get(key), str) or not payload[key]
            for key in required
        )
    ):
        raise RuntimeResolutionError("runtime.model.initialization_failed", "model_id")
    context_window_tokens = payload.get("context_window_tokens")
    if context_window_tokens is not None and (
        isinstance(context_window_tokens, bool)
        or not isinstance(context_window_tokens, int)
        or context_window_tokens <= 0
    ):
        raise RuntimeResolutionError(
            "runtime.model.initialization_failed", "context_window_tokens"
        )
    from runtime_service.observability.usage import safe_pricing

    connection = {key: payload[key] for key in required} | {
        "model_id": model_id,
        "context_window_tokens": context_window_tokens,
    }
    pricing = safe_pricing(payload.get("pricing"))
    if pricing is not None:
        connection["pricing"] = pricing
    return connection


async def fetch_model_connection(
    reference: object, *, model_id: str, project_id: str
) -> dict[str, Any] | None:
    bundle = await fetch_model_bundle(
        reference, model_id=model_id, project_id=project_id
    )
    return dict(bundle.primary) if bundle.primary is not None else None


def build_fallback_model(
    config: ResolvedRuntimeConfig, bundle: ModelConnectionBundle
) -> BaseChatModel | None:
    if bundle.fallback is None:
        return None
    return build_model(
        replace(config, model_id=bundle.policy.fallback_model_id),
        connection=bundle.fallback,
        max_retries=0,
    )


__all__ = [
    "build_model",
    "build_fallback_model",
    "fetch_model_bundle",
    "fetch_model_connection",
    "resolve_model_max_output_tokens",
]
