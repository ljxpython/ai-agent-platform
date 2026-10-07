"""Consume the Worker-only attempt budget; never start a new clock in a graph."""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from langchain_core.runnables import RunnableConfig

from runtime_service.runtime.errors import RuntimeResolutionError

RUN_BUDGET_KEY = "__graphharbor_run_budget"
DEFAULT_WRAPUP_RESERVE_SECONDS = 120


def resolve_wrapup_reserve_seconds(
    timeout_seconds: float, raw: str | None = None
) -> int:
    value = (
        os.getenv("AGENT_RUN_WRAPUP_RESERVE_SECONDS", "") if raw is None else raw
    ).strip()
    try:
        reserve = int(value) if value else DEFAULT_WRAPUP_RESERVE_SECONDS
    except ValueError as exc:
        raise ValueError(
            "AGENT_RUN_WRAPUP_RESERVE_SECONDS must be a non-negative integer"
        ) from exc
    if reserve < 0 or (reserve > 0 and reserve >= timeout_seconds):
        raise ValueError(
            "AGENT_RUN_WRAPUP_RESERVE_SECONDS must be zero or less than the run timeout"
        )
    return reserve


@dataclass(frozen=True, slots=True)
class RunBudget:
    run_id: str
    thread_id: str
    deadline_at: datetime
    timeout_seconds: float
    deadline_monotonic: float
    wrapup_reserve_seconds: int

    @property
    def soft_deadline_monotonic(self) -> float:
        return self.deadline_monotonic - self.wrapup_reserve_seconds


def read_run_budget(
    config: RunnableConfig, *, required: bool = True
) -> RunBudget | None:
    configurable = config.get("configurable") or {}
    raw = configurable.get(RUN_BUDGET_KEY)
    if raw is None and not required:
        return None
    if not isinstance(raw, Mapping):
        raise RuntimeResolutionError("runtime.run_budget.missing_or_invalid")
    if type(raw.get("version")) is not int or raw["version"] != 1:
        raise RuntimeResolutionError("runtime.run_budget.invalid_version")
    metadata = config.get("metadata") or {}
    run_id, thread_id = raw.get("run_id"), raw.get("thread_id")
    if (
        not isinstance(run_id, str)
        or not run_id
        or run_id != metadata.get("run_id")
        or not isinstance(thread_id, str)
        or not thread_id
        or thread_id != configurable.get("thread_id")
    ):
        raise RuntimeResolutionError("runtime.run_budget.identity_mismatch")
    for key in ("timeout_seconds", "deadline_monotonic"):
        number = raw.get(key)
        if (
            isinstance(number, bool)
            or not isinstance(number, (int, float))
            or not math.isfinite(number)
        ):
            raise RuntimeResolutionError("runtime.run_budget.invalid_number", key)
    timeout_seconds = float(raw["timeout_seconds"])
    if timeout_seconds <= 0:
        raise RuntimeResolutionError(
            "runtime.run_budget.invalid_number", "timeout_seconds"
        )
    try:
        started_at = datetime.fromisoformat(raw["started_at"])
        deadline_at = datetime.fromisoformat(raw["deadline_at"])
        if (
            started_at.utcoffset() is None
            or deadline_at.utcoffset() is None
            or not math.isclose(
                (deadline_at - started_at).total_seconds(),
                timeout_seconds,
                abs_tol=1e-6,
            )
        ):
            raise ValueError("invalid UTC budget")
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeResolutionError("runtime.run_budget.invalid_deadline") from exc
    try:
        reserve = resolve_wrapup_reserve_seconds(timeout_seconds)
    except ValueError as exc:
        raise RuntimeResolutionError("runtime.run_budget.invalid_reserve") from exc
    return RunBudget(
        run_id,
        thread_id,
        deadline_at,
        timeout_seconds,
        float(raw["deadline_monotonic"]),
        reserve,
    )
