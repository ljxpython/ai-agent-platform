"""Native-Run token budget policy and in-process projection."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from threading import RLock
from typing import Any

from runtime_service.runtime.errors import (
    RuntimeResolutionError,
    TokenBudgetExceededError,
    TokenBudgetUnverifiableError,
)

MAX_SAFE_INTEGER = 2**53 - 1
TOKEN_BUDGET_STOP_CODES = frozenset(
    {"token_budget_exhausted", "token_budget_unverifiable"}
)
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def token_budget_enabled() -> bool:
    raw = os.getenv("RUNTIME_TOKEN_BUDGET_ENABLED", "false").strip().lower()
    if raw not in _TRUE_VALUES | {"0", "false", "no", "off"}:
        raise RuntimeResolutionError(
            "runtime.token_budget.invalid_enabled", "RUNTIME_TOKEN_BUDGET_ENABLED"
        )
    return raw in _TRUE_VALUES


@dataclass(frozen=True, slots=True)
class TokenBudgetPolicy:
    """Frozen deployment policy copied into each native Run."""

    max_tokens: int
    warn_at_tokens: int
    version: int = 1

    def as_dict(self) -> dict[str, int]:
        return {
            "version": self.version,
            "max_tokens": self.max_tokens,
            "warn_at_tokens": self.warn_at_tokens,
        }

    @classmethod
    def from_dict(cls, value: Any) -> TokenBudgetPolicy:
        if not isinstance(value, dict):
            raise ValueError("invalid persisted token budget policy")
        version = value.get("version")
        maximum = value.get("max_tokens")
        warning = value.get("warn_at_tokens")
        if (
            type(version) is not int
            or version != 1
            or type(maximum) is not int
            or not 1 <= maximum <= MAX_SAFE_INTEGER
            or type(warning) is not int
            or warning != (maximum * 4 + 4) // 5
        ):
            raise ValueError("invalid persisted token budget policy")
        return cls(maximum, warning, version)


def resolve_token_budget_policy() -> TokenBudgetPolicy | None:
    """Read the deployment-only cap; client RuntimeContext never supplies it."""

    if not token_budget_enabled():
        return None
    if os.getenv("RUNTIME_USAGE_ENABLED", "false").strip().lower() not in _TRUE_VALUES:
        raise RuntimeResolutionError("runtime.token_budget.usage_required")
    raw = os.getenv("RUNTIME_TOKEN_BUDGET_MAX_TOKENS", "100000").strip()
    try:
        maximum = int(raw)
    except ValueError as exc:
        raise RuntimeResolutionError(
            "runtime.token_budget.invalid_max_tokens", "RUNTIME_TOKEN_BUDGET_MAX_TOKENS"
        ) from exc
    if type(maximum) is not int or not 1 <= maximum <= MAX_SAFE_INTEGER:
        raise RuntimeResolutionError(
            "runtime.token_budget.invalid_max_tokens", "RUNTIME_TOKEN_BUDGET_MAX_TOKENS"
        )
    return TokenBudgetPolicy(maximum, (maximum * 4 + 4) // 5)


@dataclass(slots=True)
class _CallUsage:
    total_tokens: int | None
    quality: str


@dataclass(slots=True)
class RunTokenBudget:
    """Thread-safe, rebuildable projection over the Runtime usage ledger."""

    policy: TokenBudgetPolicy
    _calls: dict[str, _CallUsage] = field(default_factory=dict)
    _used_tokens: int = 0
    _unknown_calls: int = 0
    _unverifiable: bool = False
    _stop_code: str | None = None
    _notice_codes: set[str] = field(default_factory=set)
    _lock: RLock = field(default_factory=RLock, repr=False)

    @property
    def used_tokens(self) -> int:
        with self._lock:
            return self._used_tokens

    @property
    def stop_code(self) -> str | None:
        with self._lock:
            return self._stop_code

    @property
    def unverifiable(self) -> bool:
        with self._lock:
            return (
                self._unverifiable
                or self._unknown_calls > 0
                or self._used_tokens > MAX_SAFE_INTEGER
            )

    def load(
        self,
        *,
        policy: TokenBudgetPolicy | None = None,
        used_tokens: int | None,
        unverifiable: bool,
        stop_code: str | None,
        calls: list[dict] | None = None,
    ) -> None:
        """Replace the projection with a persisted Run snapshot."""

        if used_tokens is not None and (
            type(used_tokens) is not int or used_tokens < 0
        ):
            raise ValueError("invalid persisted token usage")
        if stop_code not in (None, *TOKEN_BUDGET_STOP_CODES):
            raise ValueError("invalid persisted token budget stop code")
        with self._lock:
            if policy is not None:
                self.policy = policy
            self._calls.clear()
            self._unknown_calls = 0
            for call in calls or []:
                self._calls[str(call["model_call_id"])] = _CallUsage(
                    call["total_tokens"], call["quality"]
                )
                self._unknown_calls += call["quality"] not in {
                    "reported",
                    "derived_from_reported",
                    "started",
                }
            self._used_tokens = used_tokens or 0
            self._unverifiable = bool(unverifiable)
            self._stop_code = stop_code

    def mark_unverifiable(self) -> None:
        with self._lock:
            self._unverifiable = True

    def begin_call(self, call_id: str) -> None:
        with self._lock:
            self._calls.setdefault(call_id, _CallUsage(None, "started"))

    def record_call(
        self,
        call_id: str,
        *,
        total_tokens: int | None,
        quality: str,
    ) -> None:
        """Idempotently replace a call's contribution when richer usage arrives."""

        if (
            total_tokens is not None
            and (
                type(total_tokens) is not int
                or not 0 <= total_tokens <= MAX_SAFE_INTEGER
            )
        ) or (
            total_tokens is None and quality in {"reported", "derived_from_reported"}
        ):
            total_tokens = None
            quality = "invalid"
        with self._lock:
            previous = self._calls.get(call_id)
            if previous and previous.quality in {"reported", "derived_from_reported"}:
                return
            if previous and previous.total_tokens is not None:
                self._used_tokens -= previous.total_tokens
            if previous and previous.quality not in {
                "reported",
                "derived_from_reported",
                "started",
            }:
                self._unknown_calls -= 1
            self._calls[call_id] = _CallUsage(total_tokens, quality)
            self._unknown_calls += quality not in {
                "reported",
                "derived_from_reported",
                "started",
            }
            if total_tokens is not None:
                self._used_tokens += total_tokens

    def check(self) -> str:
        """Return ``ok``, ``approaching`` or a refusal state."""

        with self._lock:
            if self._stop_code == "token_budget_exhausted":
                return "exhausted"
            if self._stop_code == "token_budget_unverifiable" or self.unverifiable:
                return "unverifiable"
            if self._used_tokens >= self.policy.max_tokens:
                return "exhausted"
            if self._used_tokens >= self.policy.warn_at_tokens:
                return "approaching"
            return "ok"

    def mark_stop(self, code: str) -> None:
        if code not in TOKEN_BUDGET_STOP_CODES:
            raise ValueError("invalid token budget stop code")
        with self._lock:
            self._stop_code = self._stop_code or code

    def claim_notice(self, code: str) -> bool:
        with self._lock:
            if code in self._notice_codes:
                return False
            self._notice_codes.add(code)
            return True

    def public_snapshot(self) -> dict[str, Any]:
        with self._lock:
            unknown = self.unverifiable
            known = self._used_tokens if self._used_tokens <= MAX_SAFE_INTEGER else None
            coverage = (
                ("partial" if known else "unavailable") if unknown else "complete"
            )
            remaining = (
                None if unknown else max(0, self.policy.max_tokens - self._used_tokens)
            )
            return {
                "version": self.policy.version,
                "budget_scope": "run",
                "unit": "tokens_total",
                "max_tokens": self.policy.max_tokens,
                "warn_at_tokens": self.policy.warn_at_tokens,
                "known_used_tokens": known,
                "remaining_tokens": remaining,
                "coverage": coverage,
                "stop_code": self._stop_code,
            }


__all__ = [
    "MAX_SAFE_INTEGER",
    "RunTokenBudget",
    "TokenBudgetExceededError",
    "TokenBudgetPolicy",
    "TokenBudgetUnverifiableError",
    "resolve_token_budget_policy",
    "token_budget_enabled",
]
