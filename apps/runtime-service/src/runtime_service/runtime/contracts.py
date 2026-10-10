"""Immutable runtime values shared by agent services."""

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from uuid import UUID

from runtime_service.runtime.errors import RuntimeResolutionError


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
    offload_conversation: bool = False
    plan_mode: bool = False
    plan_execution_id: str | None = None


@dataclass(frozen=True, slots=True)
class ModelResiliencePolicy:
    enabled: bool = False
    fallback_model_id: str | None = None
    max_attempts: int = 3
    attempt_timeout_seconds: float = 600.0
    total_timeout_seconds: float = 900.0

    def __post_init__(self) -> None:
        valid = type(self.enabled) is bool and type(self.max_attempts) is int
        valid = valid and 1 <= self.max_attempts <= 5
        for value, maximum in (
            (self.attempt_timeout_seconds, 900),
            (self.total_timeout_seconds, 1200),
        ):
            valid = valid and type(value) in (int, float)
            if type(value) in (int, float):
                valid = valid and math.isfinite(value) and 1 <= value <= maximum
        if not valid or self.total_timeout_seconds < self.attempt_timeout_seconds:
            raise RuntimeResolutionError("runtime.model.invalid_resilience")
        if self.fallback_model_id is not None:
            try:
                if not isinstance(self.fallback_model_id, str):
                    raise ValueError
                UUID(self.fallback_model_id)
            except ValueError:
                raise RuntimeResolutionError(
                    "runtime.model.invalid_resilience"
                ) from None

    @classmethod
    def from_payload(cls, payload: object) -> "ModelResiliencePolicy":
        fields = {
            "enabled",
            "fallback_model_id",
            "max_attempts",
            "attempt_timeout_seconds",
            "total_timeout_seconds",
        }
        if not isinstance(payload, Mapping) or set(payload) != fields:
            raise RuntimeResolutionError("runtime.model.invalid_resilience")
        return cls(**payload)


@dataclass(frozen=True, slots=True)
class ModelConnectionBundle:
    primary: Mapping[str, str] | None = field(default=None, repr=False)
    fallback: Mapping[str, str] | None = field(default=None, repr=False)
    policy: ModelResiliencePolicy = field(default_factory=ModelResiliencePolicy)


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
