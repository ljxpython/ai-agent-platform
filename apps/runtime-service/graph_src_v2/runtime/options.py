from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass, field
from typing import Any, Mapping

from graph_src_v2.conf.settings import require_model_spec

DEFAULT_SYSTEM_PROMPT = (
    "You are an expert researcher. Your job is to conduct thorough research and then "
    "write a polished report."
)


@dataclass
class ModelSpec:
    model_provider: str
    model: str
    base_url: str
    api_key: str


@dataclass
class AppRuntimeConfig:
    environment: str = "test"
    model_id: str | None = None
    model_spec: ModelSpec = field(
        default_factory=lambda: ModelSpec(
            model_provider="", model="", base_url="", api_key=""
        )
    )
    system_prompt: str = ""
    enable_tools: bool = False
    tools: list[str] | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _parse_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_int(value: Any, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def read_configurable(config: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(config, Mapping):
        return {}
    configurable = config.get("configurable")
    return configurable if isinstance(configurable, Mapping) else {}


def context_to_mapping(raw: Any) -> Mapping[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, Mapping):
        return raw
    if dataclasses.is_dataclass(raw) and not isinstance(raw, type):
        return dataclasses.asdict(raw)
    if hasattr(raw, "__dict__") and isinstance(raw.__dict__, dict):
        return raw.__dict__
    return {}


def merge_trusted_auth_context(
    config: Mapping[str, Any] | None,
    runtime_context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(runtime_context or {})
    configurable = read_configurable(config)

    auth_user_id = configurable.get("langgraph_auth_user_id")
    if auth_user_id is not None:
        merged["user_id"] = str(auth_user_id)

    auth_user = configurable.get("langgraph_auth_user")
    auth_role = None
    auth_org_id = None
    auth_permissions = None
    if isinstance(auth_user, Mapping):
        auth_role = auth_user.get("role")
        auth_org_id = auth_user.get("org_id")
        auth_permissions = auth_user.get("permissions")
    elif auth_user is not None:
        auth_role = getattr(auth_user, "role", None)
        auth_org_id = getattr(auth_user, "org_id", None)
        auth_permissions = getattr(auth_user, "permissions", None)

    if auth_org_id is not None:
        merged["tenant_id"] = str(auth_org_id)
    if auth_role is not None:
        merged["role"] = str(auth_role)
    if isinstance(auth_permissions, (list, tuple, set)):
        merged["permissions"] = [str(item) for item in auth_permissions]

    return merged


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_tool_names(raw: Any) -> list[str] | None:
    if raw is None:
        return None
    if isinstance(raw, (list, tuple, set)):
        values = [str(item).strip() for item in raw if str(item).strip()]
    elif isinstance(raw, str):
        values = _split_csv(raw)
    else:
        values = [str(raw).strip()]

    normalized: list[str] = []
    seen: set[str] = set()
    for item in values:
        key = item.lower()
        if key in {"", "none"} or key in seen:
            continue
        seen.add(key)
        normalized.append(key)
    return normalized


def build_runtime_config(
    config: Mapping[str, Any] | None,
    runtime_context: Mapping[str, Any] | None = None,
) -> AppRuntimeConfig:
    configurable = read_configurable(config)
    context_data = runtime_context or {}

    environment = str(
        context_data.get("environment")
        or configurable.get("environment")
        or os.getenv("APP_ENV")
        or os.getenv("DYNACONF_ENV")
        or "test"
    ).lower()

    model_id_raw = (
        context_data.get("model_id")
        or configurable.get("model_id")
        or os.getenv("MODEL_ID")
    )
    resolved_model_id, model_spec = require_model_spec(
        str(model_id_raw).strip() if model_id_raw is not None else None
    )

    resolved_model_spec = ModelSpec(
        model_provider=model_spec["model_provider"],
        model=model_spec["model"],
        base_url=model_spec["base_url"],
        api_key=model_spec["api_key"],
    )

    system_prompt = str(
        context_data.get("system_prompt")
        or context_data.get("system_message")
        or configurable.get("system_prompt")
        or configurable.get("x-system-prompt")
        or os.getenv("SYSTEM_PROMPT")
        or ""
    )
    enable_tools = _parse_bool(
        (
            context_data.get("enable_tools")
            if "enable_tools" in context_data
            else (
                configurable.get("enable_tools")
                if "enable_tools" in configurable
                else (
                    configurable.get("x-enable-tools")
                    if "x-enable-tools" in configurable
                    else os.getenv("ENABLE_TOOLS")
                )
            )
        ),
        default=False,
    )

    raw_tools = context_data.get("tools")
    if raw_tools is None:
        raw_tools = (
            configurable.get("tools")
            if "tools" in configurable
            else (
                configurable.get("x-tools")
                if "x-tools" in configurable
                else os.getenv("TOOLS")
            )
        )

    tools = _parse_tool_names(raw_tools)
    if not enable_tools:
        tools = []

    temperature = _parse_float(
        (
            context_data.get("temperature")
            if "temperature" in context_data
            else configurable.get("temperature")
        ),
        default=None,
    )
    top_p = _parse_float(
        (
            context_data.get("top_p")
            if "top_p" in context_data
            else configurable.get("top_p")
        ),
        default=None,
    )
    max_tokens = _parse_int(
        (
            context_data.get("max_tokens")
            if "max_tokens" in context_data
            else configurable.get("max_tokens")
        ),
        default=None,
    )

    return AppRuntimeConfig(
        environment=environment,
        model_id=resolved_model_id,
        model_spec=resolved_model_spec,
        system_prompt=system_prompt,
        enable_tools=enable_tools,
        tools=tools,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
    )
