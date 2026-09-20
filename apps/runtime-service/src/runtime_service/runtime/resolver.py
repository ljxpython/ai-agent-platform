"""Pure parsing and resolution of Runtime values."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from runtime_service.runtime.contracts import (
    AgentDefaults,
    ResolvedRuntimeConfig,
    RuntimeContext,
    RuntimePolicy,
    RuntimePrincipal,
)
from runtime_service.runtime.errors import RuntimeResolutionError

_CONTEXT_FIELDS = frozenset({"model_id", "temperature", "max_tokens", "top_p", "execution_mode", "access_policy"})
_IDENTITY_FIELDS = frozenset(
    {"user_id", "tenant_id", "project_id", "role", "permissions", "secret", "token", "api_key"}
)
_FORBIDDEN_CONFIGURABLE_FIELDS = frozenset(
    {
        "backend",
        "backend_factory",
        "command",
        "headers",
        "mcp",
        "mcp_command",
        "mcp_headers",
        "mcp_token",
        "mcp_url",
        "skill_path",
        "skills",
        "subagent",
        "subagents",
        "token",
        "tool",
        "tool_impl",
        "tool_overrides",
        "tool_policy_version",
        "tools",
    }
)


def _fail(code: str, field: str | None = None) -> RuntimeResolutionError:
    return RuntimeResolutionError(code, field)


def reject_untrusted_configurable(raw: Mapping[str, Any]) -> None:
    """Reject resource, credential, and implementation injection via configurable."""

    if not isinstance(raw, Mapping):
        raise _fail("runtime.configurable.invalid_shape")
    forbidden = sorted(set(raw) & _FORBIDDEN_CONFIGURABLE_FIELDS)
    if forbidden:
        raise _fail("runtime.configurable.forbidden", forbidden[0])


def _identifier(value: object, field: str, code: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip() or len(value) > 128:
        raise _fail(code, field)
    if not value.isascii() or not all(char.isprintable() and not char.isspace() for char in value):
        raise _fail(code, field)
    return value


def _text(value: object, field: str, code: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 100_000:
        raise _fail(code, field)
    return value


def _names(value: object, field: str, code: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise _fail("runtime.context.invalid_field_type", field)
    names = tuple(_identifier(item, field, code) for item in value)
    if len(set(names)) != len(names):
        raise _fail(code, field)
    return tuple(sorted(names))


def _number(value: object, field: str, *, minimum: float, maximum: float) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail("runtime.context.invalid_field_type", field)
    number = float(value)
    if not math.isfinite(number) or number < minimum or number > maximum:
        raise _fail("runtime.context.invalid_value", field)
    return number


def _max_tokens(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise _fail("runtime.context.invalid_field_type", "max_tokens")
    if value <= 0:
        raise _fail("runtime.context.invalid_value", "max_tokens")
    return value


def parse_runtime_context(raw: Mapping[str, Any] | RuntimeContext | None) -> RuntimeContext:
    """Parse the untrusted Context boundary with no compatibility fallback."""

    if raw is None:
        return RuntimeContext()
    if isinstance(raw, RuntimeContext):
        return _validate_context(raw)
    if not isinstance(raw, Mapping):
        raise _fail("runtime.context.invalid_shape")
    keys = set(raw)
    if any(not isinstance(key, str) for key in keys):
        raise _fail("runtime.context.unknown_field")
    identity = keys & _IDENTITY_FIELDS
    if identity:
        raise _fail("runtime.context.identity_field_forbidden", sorted(identity)[0])
    unknown = keys - _CONTEXT_FIELDS
    if unknown:
        raise _fail("runtime.context.unknown_field", sorted(unknown)[0])
    return _validate_context(
        RuntimeContext(
            model_id=raw.get("model_id"),
            temperature=raw.get("temperature"),
            max_tokens=raw.get("max_tokens"),
            top_p=raw.get("top_p"),
            execution_mode=raw.get("execution_mode"),
            access_policy=raw.get("access_policy"),
        )
    )


def parse_runtime_principal(raw: Mapping[str, Any] | RuntimePrincipal) -> RuntimePrincipal:
    if isinstance(raw, RuntimePrincipal):
        return _validate_principal(raw)
    if not isinstance(raw, Mapping):
        raise _fail("runtime.auth.invalid_principal")
    expected = {"user_id", "tenant_id", "project_id", "role", "permissions"}
    if set(raw) != expected:
        raise _fail("runtime.auth.invalid_principal")
    return _validate_principal(
        RuntimePrincipal(
            user_id=raw["user_id"],
            tenant_id=raw["tenant_id"],
            project_id=raw["project_id"],
            role=raw["role"],
            permissions=tuple(raw["permissions"]) if isinstance(raw["permissions"], list) else raw["permissions"],
        )
    )


def parse_tool_overrides(raw: object) -> tuple[str, ...]:
    if not isinstance(raw, dict) or len(raw) > 128 or any(value is not False for value in raw.values()):
        raise _fail("runtime.auth.invalid_claim", "tool_overrides")
    names = _names(list(raw), "tool_overrides", "runtime.auth.invalid_claim")
    if len(json.dumps(raw, separators=(",", ":")).encode()) > 4096:
        raise _fail("runtime.auth.invalid_claim", "tool_overrides")
    return names


def parse_runtime_policy(raw: Mapping[str, Any] | RuntimePolicy) -> RuntimePolicy:
    if isinstance(raw, RuntimePolicy):
        return _validate_policy(raw)
    if not isinstance(raw, Mapping):
        raise _fail("runtime.auth.invalid_claim")
    expected = {"version", "allowed_model_ids", "tool_overrides", "tool_policy_version"}
    if set(raw) != expected:
        raise _fail("runtime.auth.invalid_claim")
    return _validate_policy(
        RuntimePolicy(
            version=raw["version"],
            allowed_model_ids=tuple(raw["allowed_model_ids"])
            if isinstance(raw["allowed_model_ids"], list)
            else raw["allowed_model_ids"],
            denied_tool_names=parse_tool_overrides(raw["tool_overrides"]),
            tool_policy_version=raw["tool_policy_version"],
        )
    )


def _validate_context(value: RuntimeContext) -> RuntimeContext:
    if not isinstance(value, RuntimeContext):
        raise _fail("runtime.context.invalid_shape")
    if value.execution_mode is not None and (
        not isinstance(value.execution_mode, str)
        or value.execution_mode not in {"flash", "standard", "pro", "ultra"}
    ):
        raise _fail("runtime.context.invalid_value", "execution_mode")
    if value.access_policy is not None and (
        not isinstance(value.access_policy, str)
        or value.access_policy not in {"review", "workspace_write", "full_access"}
    ):
        raise _fail("runtime.context.invalid_value", "access_policy")
    model_id = None if value.model_id is None else _identifier(value.model_id, "model_id", "runtime.context.invalid_value")
    temperature = _number(value.temperature, "temperature", minimum=0, maximum=2)
    top_p = _number(value.top_p, "top_p", minimum=0, maximum=1)
    if top_p == 0:
        raise _fail("runtime.context.invalid_value", "top_p")
    max_tokens = _max_tokens(value.max_tokens)
    return replace(value, model_id=model_id, temperature=temperature, max_tokens=max_tokens, top_p=top_p)


def _validate_principal(value: RuntimePrincipal) -> RuntimePrincipal:
    if not isinstance(value, RuntimePrincipal):
        raise _fail("runtime.auth.invalid_principal")
    return replace(
        value,
        user_id=_identifier(value.user_id, "user_id", "runtime.auth.invalid_principal"),
        tenant_id=_identifier(value.tenant_id, "tenant_id", "runtime.auth.invalid_principal"),
        project_id=_identifier(value.project_id, "project_id", "runtime.auth.invalid_principal"),
        role=_identifier(value.role, "role", "runtime.auth.invalid_principal"),
        permissions=_names(value.permissions, "permissions", "runtime.auth.invalid_principal"),
    )


def _validate_policy(value: RuntimePolicy) -> RuntimePolicy:
    if not isinstance(value, RuntimePolicy):
        raise _fail("runtime.auth.invalid_claim")
    _text(value.version, "policy_version", "runtime.auth.invalid_claim")
    models = _names(value.allowed_model_ids, "allowed_model_ids", "runtime.auth.invalid_claim")
    if not models:
        raise _fail("runtime.auth.invalid_claim", "allowed_model_ids")
    denied = _names(value.denied_tool_names, "tool_overrides", "runtime.auth.invalid_claim")
    version = _text(value.tool_policy_version, "tool_policy_version", "runtime.auth.invalid_claim")
    return replace(value, allowed_model_ids=models, denied_tool_names=denied, tool_policy_version=version)


def _validate_defaults(value: AgentDefaults) -> AgentDefaults:
    if not isinstance(value, AgentDefaults):
        raise _fail("runtime.defaults.invalid")
    required = _names(value.required_tool_names, "required_tool_names", "runtime.defaults.invalid")
    optional = _names(value.optional_tool_names, "optional_tool_names", "runtime.defaults.invalid")
    if set(required) & set(optional):
        raise _fail("runtime.defaults.invalid", "tool_names")
    return replace(
        value,
        model_id=_identifier(value.model_id, "model_id", "runtime.defaults.invalid"),
        system_prompt=_text(value.system_prompt, "system_prompt", "runtime.defaults.invalid"),
        prompt_version=_text(value.prompt_version, "prompt_version", "runtime.defaults.invalid"),
        temperature=_number(value.temperature, "temperature", minimum=0, maximum=2),
        max_tokens=_max_tokens(value.max_tokens),
        top_p=_number(value.top_p, "top_p", minimum=0, maximum=1),
        required_tool_names=required,
        optional_tool_names=optional,
    )


def _sha256(value: str) -> str:
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def runtime_context_hash(raw: Mapping[str, Any] | RuntimeContext | None) -> str:
    """Hash only the normalized, non-sensitive Runtime Context fields."""

    context = parse_runtime_context(raw)
    payload = {
        "schema": "runtime-context/v4",
        "model_id": context.model_id,
        "temperature": context.temperature,
        "max_tokens": context.max_tokens,
        "top_p": context.top_p,
    }
    if context.execution_mode is not None:
        payload.update(schema="runtime-context/v4", execution_mode=context.execution_mode)
    if context.access_policy is not None:
        payload.update(schema="runtime-context/v4", access_policy=context.access_policy)
    return _sha256(_canonical_json(payload))


def _config_hash(config: ResolvedRuntimeConfig) -> str:
    payload = {
        "schema": "runtime-config/v3",
        "principal": {
            "tenant_id": config.principal.tenant_id,
            "project_id": config.principal.project_id,
            "user_id": config.principal.user_id,
            "role": config.principal.role,
            "permissions": list(config.principal.permissions),
        },
        "model_id": config.model_id,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "top_p": config.top_p,
        "required_tool_names": list(config.required_tool_names),
        "optional_tool_names": list(config.optional_tool_names),
        "prompt_version": config.prompt_version,
        "prompt_hash": config.prompt_hash,
        "policy_version": config.policy_version,
        "tool_policy_version": config.tool_policy_version,
        "tool_declaration_version": config.tool_declaration_version,
    }
    if config.execution_mode is not None:
        payload.update(schema="runtime-config/v3", execution_mode=config.execution_mode)
    canonical = json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    return _sha256(canonical)


def resolve_runtime_config(
    *,
    principal: RuntimePrincipal,
    context: RuntimeContext,
    policy: RuntimePolicy,
    defaults: AgentDefaults,
    available_tool_names: tuple[str, ...] | frozenset[str] | None = None,
) -> ResolvedRuntimeConfig:
    """Validate, merge and hash a single Run without side effects."""

    principal = _validate_principal(principal)
    context = _validate_context(context)
    policy = _validate_policy(policy)
    defaults = _validate_defaults(defaults)
    model_id = context.model_id if context.model_id is not None else defaults.model_id
    # Keep provider-prefixed defaults compatible with catalog keys after the
    # Platform has already restricted the delegation allowlist.
    if model_id not in policy.allowed_model_ids and ":" in model_id:
        _, catalog_model_id = model_id.split(":", 1)
        if policy.allowed_model_ids.count(catalog_model_id) == 1:
            model_id = catalog_model_id
    if model_id not in policy.allowed_model_ids:
        raise _fail("runtime.model.not_allowed", "model_id")
    temperature = context.temperature if context.temperature is not None else defaults.temperature
    max_tokens = context.max_tokens if context.max_tokens is not None else defaults.max_tokens
    top_p = context.top_p if context.top_p is not None else defaults.top_p

    required = defaults.required_tool_names
    declared = set(required) | set(defaults.optional_tool_names)
    denied = set(policy.denied_tool_names)
    if denied - declared:
        raise _fail("runtime.tool.restriction_unknown", "tool_overrides")
    if denied & set(required):
        raise _fail("runtime.required_tool.not_allowed", "required_tool_names")
    available = declared if available_tool_names is None else set(available_tool_names)
    if set(required) - available:
        raise _fail("runtime.required_tool.unavailable", "required_tool_names")
    optional = tuple(name for name in defaults.optional_tool_names if name not in denied and name in available)

    prompt_hash = _sha256(defaults.system_prompt)
    resolved = ResolvedRuntimeConfig(
        principal=principal,
        model_id=model_id,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=top_p,
        required_tool_names=required,
        optional_tool_names=optional,
        prompt_version=defaults.prompt_version,
        prompt_hash=prompt_hash,
        policy_version=policy.version,
        config_hash="",
        tool_policy_version=policy.tool_policy_version,
        tool_declaration_version=_sha256(_canonical_json([defaults.required_tool_names, defaults.optional_tool_names])),
        execution_mode=context.execution_mode,
    )
    return replace(resolved, config_hash=_config_hash(resolved))


def runtime_config_snapshot(config: ResolvedRuntimeConfig) -> dict[str, object]:
    """Project resolved execution facts into a JSON-safe, secret-free snapshot."""

    if not isinstance(config, ResolvedRuntimeConfig):
        raise _fail("runtime.snapshot.invalid")
    return {
        "schema": "runtime-config/v3",
        **({"execution_mode": config.execution_mode} if config.execution_mode is not None else {}),
        "principal": {
            "user_id": config.principal.user_id,
            "tenant_id": config.principal.tenant_id,
            "project_id": config.principal.project_id,
            "role": config.principal.role,
            "permissions": list(config.principal.permissions),
        },
        "model_id": config.model_id,
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        "top_p": config.top_p,
        "required_tool_names": list(config.required_tool_names),
        "optional_tool_names": list(config.optional_tool_names),
        "prompt_version": config.prompt_version,
        "prompt_hash": config.prompt_hash,
        "policy_version": config.policy_version,
        "tool_policy_version": config.tool_policy_version,
        "tool_declaration_version": config.tool_declaration_version,
        "config_hash": config.config_hash,
    }


def resolved_runtime_config_from_snapshot(raw: Mapping[str, Any]) -> ResolvedRuntimeConfig:
    """Restore a snapshot only when its schema and deterministic hash are valid."""

    expected = {
        "schema",
        "principal",
        "model_id",
        "temperature",
        "max_tokens",
        "top_p",
        "required_tool_names",
        "optional_tool_names",
        "prompt_version",
        "prompt_hash",
        "policy_version",
        "tool_policy_version",
        "tool_declaration_version",
        "config_hash",
    }
    if isinstance(raw, Mapping) and "execution_mode" in raw:
        expected.add("execution_mode")
        if raw.get("execution_mode") not in ("flash", "standard", "pro", "ultra"):
            raise _fail("runtime.snapshot.invalid")
    if not isinstance(raw, Mapping) or set(raw) != expected or raw.get("schema") != "runtime-config/v3":
        raise _fail("runtime.snapshot.invalid")
    principal = parse_runtime_principal(raw["principal"])
    try:
        config = ResolvedRuntimeConfig(
            principal=principal,
            model_id=_identifier(raw["model_id"], "model_id", "runtime.snapshot.invalid"),
            temperature=_number(raw["temperature"], "temperature", minimum=0, maximum=2),
            max_tokens=_max_tokens(raw["max_tokens"]),
            top_p=_number(raw["top_p"], "top_p", minimum=0, maximum=1),
            required_tool_names=_names(raw["required_tool_names"], "required_tool_names", "runtime.snapshot.invalid"),
            optional_tool_names=_names(raw["optional_tool_names"], "optional_tool_names", "runtime.snapshot.invalid"),
            prompt_version=_text(raw["prompt_version"], "prompt_version", "runtime.snapshot.invalid"),
            prompt_hash=_identifier(raw["prompt_hash"], "prompt_hash", "runtime.snapshot.invalid"),
            policy_version=_text(raw["policy_version"], "policy_version", "runtime.snapshot.invalid"),
            tool_policy_version=_text(raw["tool_policy_version"], "tool_policy_version", "runtime.snapshot.invalid"),
            tool_declaration_version=_identifier(raw["tool_declaration_version"], "tool_declaration_version", "runtime.snapshot.invalid"),
            config_hash=_identifier(raw["config_hash"], "config_hash", "runtime.snapshot.invalid"),
            execution_mode=raw.get("execution_mode"),
        )
    except (KeyError, TypeError):
        raise _fail("runtime.snapshot.invalid") from None
    if config.config_hash != _config_hash(config):
        raise _fail("runtime.snapshot.hash_mismatch", "config_hash")
    if set(config.required_tool_names) & set(config.optional_tool_names):
        raise _fail("runtime.snapshot.invalid", "tool_names")
    return config


__all__ = [
    "parse_runtime_context",
    "parse_runtime_policy",
    "parse_runtime_principal",
    "resolve_runtime_config",
    "resolved_runtime_config_from_snapshot",
    "runtime_config_snapshot",
    "runtime_context_hash",
    "reject_untrusted_configurable",
]
