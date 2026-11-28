"""Core evaluation domain contracts aligned with Agent Platform and 7D whitepaper."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def fingerprint(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(raw.encode()).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Turn(StrictModel):
    role: Literal["user", "system"] = "user"
    content: str = Field(min_length=1, max_length=20000)
    fixture: dict[str, str] = Field(default_factory=dict)
    approval: str | None = None


class SimulationSpec(StrictModel):
    goal: str = Field(min_length=1, max_length=4000)
    scenario: str = ""
    persona: str = ""
    user_mode: Literal[
        "cooperative",
        "terse",
        "impatient_reversal",
        "skeptical_challenger",
        "ambiguous_changer",
    ] = "cooperative"
    hidden_facts: list[Any] = Field(default_factory=list)
    delayed_fixtures: dict[str, dict[str, str]] | list[dict[str, Any]] = Field(
        default_factory=dict
    )
    interrupt_strategy: dict[str, Any] = Field(default_factory=dict)
    max_turns: int = Field(default=6, ge=1, le=20)
    duration_seconds: int = Field(default=300, ge=30, le=3600)
    max_requests: int = Field(default=30, ge=1, le=100)
    max_output_tokens: int = Field(default=100000, ge=100)


class ArtifactAssertion(StrictModel):
    path: str = Field(min_length=1, max_length=512)
    kind: Literal[
        "equals", "contains", "json_equals", "json_subset", "csv_rows", "absent"
    ] = "contains"
    expected: Any = None


class ToolConstraint(StrictModel):
    required: list[str] = Field(default_factory=list)
    forbidden: list[str] = Field(default_factory=list)
    sequence: list[str] = Field(default_factory=list)
    arg_subsets: dict[str, dict[str, Any]] = Field(default_factory=dict)


class MetricSpec(StrictModel):
    name: str = Field(min_length=1, max_length=64)
    threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    hard_gate: bool | None = None
    criteria: str = Field(default="", max_length=4000)
    params: dict[str, Any] = Field(default_factory=dict)


class Case(StrictModel):
    case_key: str = Field(min_length=1, max_length=128)
    split: Literal["dev", "holdout"] = "dev"
    schema_version: str = "3"
    access_policy: str = "workspace_write"
    required_capabilities: list[str] = Field(default_factory=list)
    fixture: dict[str, str] = Field(default_factory=dict)
    turns: list[Turn] = Field(default_factory=list)
    simulation: SimulationSpec | None = None
    turn_expectations: list[dict[str, Any]] = Field(default_factory=list)
    business_rules: list[str] = Field(default_factory=list)
    expectations: dict[str, Any] = Field(default_factory=dict)
    metrics: list[MetricSpec] = Field(default_factory=list)

    @field_validator("metrics", mode="before")
    @classmethod
    def _coerce_metrics(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return value
        normalized = []
        for item in value:
            if isinstance(item, str):
                normalized.append({"name": item})
            else:
                normalized.append(item)
        return normalized


class Evidence(StrictModel):
    case_key: str
    attempt_idx: int = 1
    thread_id: str | None = None
    run_ids: list[str] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)
    final_answer: str = ""
    messages: list[dict[str, Any]] = Field(default_factory=list)
    initial_artifacts: dict[str, str] = Field(default_factory=dict)
    artifacts: dict[str, str] = Field(default_factory=dict)
    retrieved_contexts: list[str] = Field(default_factory=list)
    contexts_state: Literal["recorded", "recorded_empty", "not_recorded"] = (
        "not_recorded"
    )
    tool_events: list[dict[str, Any]] = Field(default_factory=list)
    approval_snapshots: list[dict[str, Any]] = Field(default_factory=list)
    loop_signals: int = 0
    checks: dict[str, Any] = Field(default_factory=dict)
    ttft_ms: int | None = None
    duration_ms: int = 0
    judge_duration_ms: int = 0
    timing_breakdown: dict[str, int | None] = Field(default_factory=dict)
    usage: dict[str, Any] = Field(default_factory=dict)
    judge_usage: dict[str, Any] = Field(default_factory=dict)
    cost_usd: float = 0.0
    terminal_status: str = "success"
    error_category: Literal[
        "none", "fail", "runtime_error", "stream_timeout", "eval_error"
    ] = "none"
    errors: list[str] = Field(default_factory=list)


class MetricResult(StrictModel):
    name: str
    layer: Literal["L1", "L2"] = "L1"
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    reason: str = ""
    evidence_refs: list[str] = Field(default_factory=list)


class GateLimits(StrictModel):
    min_l1_pass_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    min_tsr: float = Field(default=0.8, ge=0.0, le=1.0)
    max_loop_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    max_p95_ttft_ms: int | None = Field(default=None, ge=1)
