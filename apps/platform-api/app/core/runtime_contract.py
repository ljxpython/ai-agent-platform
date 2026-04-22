from __future__ import annotations

from typing import Any, Iterable

from app.core.normalization import ensure_dict

RUNTIME_CONTEXT_READONLY_KEYS = (
    "user_id",
    "tenant_id",
    "role",
    "permissions",
    "project_id",
)

TRUSTED_RUNTIME_CONTEXT_KEYS = (
    *RUNTIME_CONTEXT_READONLY_KEYS,
    "projectId",
    "x-project-id",
)

PROJECT_SCOPE_ALIAS_KEYS = (
    "project_id",
    "projectId",
    "x-project-id",
)

RUNTIME_CONTEXT_BUSINESS_KEYS = (
    "model_id",
    "system_prompt",
    "temperature",
    "max_tokens",
    "top_p",
    "enable_tools",
    "tools",
)

RUNTIME_CONTEXT_PROPERTY_TYPES: dict[str, str] = {
    "user_id": "string",
    "tenant_id": "string",
    "role": "string",
    "permissions": "array[string]",
    "project_id": "string",
    "model_id": "string",
    "system_prompt": "string",
    "temperature": "number",
    "max_tokens": "number",
    "top_p": "number",
    "enable_tools": "boolean",
    "tools": "array[string]",
}

EXECUTION_CONFIG_PROPERTIES: dict[str, dict[str, Any]] = {
    "recursion_limit": {"type": "number", "required": False},
    "run_name": {"type": "string", "required": False},
    "max_concurrency": {"type": "number", "required": False},
}


def normalize_runtime_object(value: dict[str, Any] | None) -> dict[str, Any]:
    return ensure_dict(value)


def strip_keys(payload: dict[str, Any], keys: Iterable[str]) -> dict[str, Any]:
    next_payload = dict(payload)
    for key in keys:
        next_payload.pop(key, None)
    return next_payload


def move_runtime_business_fields_into_context(
    *,
    source: dict[str, Any],
    context: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    next_source = dict(source)
    next_context = dict(context)
    for key in RUNTIME_CONTEXT_BUSINESS_KEYS:
        if key not in next_source:
            continue
        value = next_source.pop(key)
        if value is None or key in next_context:
            continue
        next_context[key] = value
    return next_source, next_context


def normalize_runtime_contract(
    *,
    config: dict[str, Any],
    context: dict[str, Any],
    metadata: dict[str, Any],
    project_id: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    next_context = strip_keys(context, TRUSTED_RUNTIME_CONTEXT_KEYS)
    next_context["project_id"] = project_id

    next_config = strip_keys(config, PROJECT_SCOPE_ALIAS_KEYS)
    next_metadata = strip_keys(metadata, PROJECT_SCOPE_ALIAS_KEYS)

    next_config, next_context = move_runtime_business_fields_into_context(
        source=next_config,
        context=next_context,
    )

    configurable = next_config.get("configurable")
    configurable_dict = (
        strip_keys(dict(configurable), TRUSTED_RUNTIME_CONTEXT_KEYS)
        if isinstance(configurable, dict)
        else {}
    )
    configurable_dict, next_context = move_runtime_business_fields_into_context(
        source=configurable_dict,
        context=next_context,
    )
    if configurable_dict:
        next_config["configurable"] = configurable_dict
    else:
        next_config.pop("configurable", None)

    config_metadata = next_config.get("metadata")
    config_metadata_dict = (
        strip_keys(dict(config_metadata), PROJECT_SCOPE_ALIAS_KEYS)
        if isinstance(config_metadata, dict)
        else {}
    )
    if config_metadata_dict:
        next_config["metadata"] = config_metadata_dict
    else:
        next_config.pop("metadata", None)

    return next_config, next_context, next_metadata


def normalize_runtime_payload(
    *,
    payload: dict[str, Any] | None,
    project_id: str,
) -> dict[str, Any]:
    next_payload = strip_keys(normalize_runtime_object(payload), PROJECT_SCOPE_ALIAS_KEYS)
    next_config, next_context, next_metadata = normalize_runtime_contract(
        config=normalize_runtime_object(next_payload.get("config")),
        context=normalize_runtime_object(next_payload.get("context")),
        metadata=normalize_runtime_object(next_payload.get("metadata")),
        project_id=project_id,
    )

    if next_config:
        next_payload["config"] = next_config
    else:
        next_payload.pop("config", None)

    next_payload["context"] = next_context

    if next_metadata:
        next_payload["metadata"] = next_metadata
    else:
        next_payload.pop("metadata", None)

    return next_payload


def build_execution_config_schema_properties() -> dict[str, dict[str, Any]]:
    return {
        key: dict(value)
        for key, value in EXECUTION_CONFIG_PROPERTIES.items()
    }


def build_runtime_context_schema_properties(
    *,
    keys: Iterable[str] | None = None,
) -> dict[str, dict[str, Any]]:
    selected_keys = tuple(keys) if keys is not None else tuple(RUNTIME_CONTEXT_PROPERTY_TYPES)
    return {
        key: {
            "type": RUNTIME_CONTEXT_PROPERTY_TYPES[key],
            "required": False,
        }
        for key in selected_keys
        if key in RUNTIME_CONTEXT_PROPERTY_TYPES
    }
