"""Explicit Provider-to-ChatModel construction for resolved Runtime config."""

from __future__ import annotations

import os
import hashlib
import hmac
import time
from collections.abc import Mapping

import httpx
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI

from runtime_service.runtime.contracts import ResolvedRuntimeConfig
from runtime_service.runtime.errors import RuntimeResolutionError


def _generation_kwargs(config: ResolvedRuntimeConfig) -> dict[str, object]:
    return {
        key: value
        for key, value in {
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
            "top_p": config.top_p,
        }.items()
        if value is not None
    }


def _required(settings: Mapping[str, str], name: str) -> str:
    value = settings.get(name)
    if not value:
        raise RuntimeResolutionError("runtime.model.initialization_failed", "model_id")
    return value


def build_model(
    config: ResolvedRuntimeConfig,
    *,
    env: Mapping[str, str] | None = None,
    connection: Mapping[str, str] | None = None,
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

    kwargs = _generation_kwargs(config)

    try:
        conn_api_key = connection.get("api_key") if connection is not None else None
        conn_base_url = connection.get("base_url") if connection is not None else None

        if provider in ("deepseek", "deepseek-proxy") or protocol == "deepseek":
            return ChatDeepSeek(
                model=model_name,
                api_key=conn_api_key or _required(settings, "DEEPSEEK_PROXY_API_KEY"),
                base_url=conn_base_url or _required(settings, "DEEPSEEK_PROXY_URL"),
                **kwargs,
            )
        if provider in ("openai", "gpt-proxy") or protocol in ("openai", "openai-compatible", "openai_compatible"):
            return ChatOpenAI(
                model=model_name,
                api_key=conn_api_key or settings.get("GPT_PROXY_API_KEY") or "EMPTY",
                base_url=conn_base_url or _required(settings, "GPT_PROXY_URL"),
                **kwargs,
            )
        if connection is not None and conn_base_url:
            return ChatOpenAI(
                model=model_name,
                api_key=conn_api_key or "EMPTY",
                base_url=conn_base_url,
                **kwargs,
            )
        return init_chat_model(config.model_id, **kwargs)
    except RuntimeResolutionError:
        raise
    except Exception as exc:
        raise RuntimeResolutionError("runtime.model.initialization_failed", "model_id") from exc


async def fetch_model_connection(
    reference: object,
    *,
    model_id: str,
    project_id: str,
) -> dict[str, str] | None:
    """Resolve a server-issued opaque reference without persisting credentials."""
    if reference is None:
        return None
    endpoint = os.getenv("PLATFORM_RUNTIME_MODEL_CONFIG_URL", "").strip()
    if not isinstance(reference, str) or not reference or not endpoint or not project_id:
        raise RuntimeResolutionError("runtime.model.initialization_failed", "model_id")
    headers = {"x-runtime-model-ref": reference, "x-project-id": project_id}
    secret = os.getenv("PLATFORM_RUNTIME_DELEGATION_SECRET", "")
    if secret:
        timestamp = str(int(time.time()))
        headers["x-runtime-model-time"] = timestamp
        headers["x-runtime-model-signature"] = hmac.new(
            secret.encode(), f"{timestamp}\n{project_id}\n{reference}".encode(), hashlib.sha256
        ).hexdigest()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                endpoint,
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeResolutionError("runtime.model.initialization_failed", "model_id") from exc
    required = ("provider", "base_url", "protocol", "model", "api_key")
    if (
        not isinstance(payload, dict)
        or payload.get("model_id") != model_id
        or any(not isinstance(payload.get(key), str) or not payload[key] for key in required)
    ):
        raise RuntimeResolutionError("runtime.model.initialization_failed", "model_id")
    return {key: payload[key] for key in required} | {"model_id": model_id}


__all__ = ["build_model", "fetch_model_connection"]
