"""Immutable runtime values shared by agent services."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RuntimePrincipal:
    user_id: str
    tenant_id: str
    project_id: str
    role: str
    permissions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    model_id: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    execution_mode: str | None = None
    access_policy: str | None = None


@dataclass(frozen=True, slots=True)
class RuntimePolicy:
    version: str
    allowed_model_ids: tuple[str, ...]
    denied_tool_names: tuple[str, ...]
    tool_policy_version: str


@dataclass(frozen=True, slots=True)
class AgentDefaults:
    model_id: str
    system_prompt: str
    prompt_version: str
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    required_tool_names: tuple[str, ...] = ()
    optional_tool_names: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ResolvedRuntimeConfig:
    principal: RuntimePrincipal
    model_id: str
    temperature: float | None
    max_tokens: int | None
    top_p: float | None
    required_tool_names: tuple[str, ...]
    optional_tool_names: tuple[str, ...]
    prompt_version: str
    prompt_hash: str
    policy_version: str
    config_hash: str
    tool_policy_version: str
    tool_declaration_version: str
    execution_mode: str | None = None
