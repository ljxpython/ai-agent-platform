"""Pydantic request and response contracts for native evaluation studio."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SuiteCreate(StrictBody):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=4000)
    suite_type: Literal["golden", "regression", "curated", "benchmark"] = "curated"
    source_project_id: str | None = Field(default=None, max_length=64)
    default_graph_id: Literal[
        "dearflow_agent", "showcase_demo", "reference_agent", "workflow_demo"
    ] = "dearflow_agent"


class SuiteUpdate(StrictBody):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=4000)
    suite_type: Literal["golden", "regression", "curated", "benchmark"] | None = None
    default_graph_id: (
        Literal["dearflow_agent", "showcase_demo", "reference_agent", "workflow_demo"]
        | None
    ) = None
    archived: bool | None = None


class CaseUpsert(StrictBody):
    case_key: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_.-]+$")
    split: Literal["dev", "holdout"] = "dev"
    schema_version: str = Field(default="3", max_length=16)
    required_capabilities: list[str] = Field(default_factory=list, max_length=20)
    turns: list[dict[str, Any]] = Field(default_factory=list, max_length=50)
    simulation: dict[str, Any] | None = None
    expectations: dict[str, Any] = Field(default_factory=dict)
    metrics: list[dict[str, Any] | str] = Field(default_factory=list, max_length=30)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PublishVersionRequest(StrictBody):
    note: str = Field(default="", max_length=500)


class ReadinessRequest(StrictBody):
    suite_id: UUID
    target_project_id: str = Field(min_length=1, max_length=64)
    agent_id: UUID
    model_id: UUID
    judge_model_id: UUID | None = None
    embedding_model_id: UUID | None = None
    case_keys: list[str] | None = Field(default=None, max_length=500)


class RunCreate(StrictBody):
    suite_id: UUID
    version_id: UUID
    target_project_id: str = Field(min_length=1, max_length=64)
    agent_id: UUID
    model_id: UUID
    judge_model_id: UUID | None = None
    embedding_model_id: UUID | None = None
    mode: Literal["regression", "historical", "matrix"] = "regression"
    concurrency: int = Field(default=3, ge=1, le=5)
    repeat_k: int = Field(default=1, ge=1, le=5)
    confirm_non_sandbox: bool = False
    skip_incompatible: bool = False
    case_keys: list[str] | None = Field(default=None, max_length=500)


class MatrixVariant(StrictBody):
    agent_id: UUID
    model_id: UUID
    label: str = Field(default="", max_length=64)


class MatrixCreate(StrictBody):
    suite_id: UUID
    version_id: UUID
    target_project_id: str = Field(min_length=1, max_length=64)
    judge_model_id: UUID | None = None
    embedding_model_id: UUID | None = None
    concurrency: int = Field(default=3, ge=1, le=5)
    repeat_k: int = Field(default=1, ge=1, le=5)
    confirm_non_sandbox: bool = False
    variants: list[MatrixVariant] = Field(min_length=1, max_length=8)
    case_keys: list[str] | None = Field(default=None, max_length=500)


class RunControlRequest(StrictBody):
    action: Literal["pause", "resume", "retry_failed", "rescore", "cancel"]


class HumanReviewCreate(StrictBody):
    human_verdict: Literal["pass", "fail"]
    reason: str = Field(default="", max_length=2000)


class PatrolGateConfig(StrictBody):
    min_tsr: float = Field(default=0.70, ge=0.0, le=1.0)
    min_l1_pass_rate: float = Field(default=0.90, ge=0.0, le=1.0)
    max_loop_rate: float = Field(default=0.10, ge=0.0, le=1.0)
    max_p95_ttft_ms: int | None = Field(default=None, ge=100, le=600000)
    regression_drop_threshold: float = Field(default=0.05, ge=0.0, le=1.0)
    ttft_spike_ratio: float = Field(default=0.50, ge=0.0, le=10.0)
    consecutive_alert_threshold: int = Field(default=1, ge=1, le=10)


class PatrolCreate(StrictBody):
    name: str = Field(min_length=1, max_length=128)
    suite_id: UUID
    version_policy: Literal["latest_published", "pinned"] = "latest_published"
    version_id: UUID | None = None
    target_project_id: str = Field(min_length=1, max_length=64)
    target_graph_id: (
        Literal["dearflow_agent", "showcase_demo", "reference_agent", "workflow_demo"]
        | None
    ) = None
    target_agent_id: UUID | None = None
    target_model_id: UUID | None = None
    judge_model_id: UUID | None = None
    embedding_model_id: UUID | None = None
    case_keys: list[str] = Field(default_factory=list, max_length=500)
    concurrency: int = Field(default=2, ge=1, le=5)
    repeat_k: int = Field(default=1, ge=1, le=5)
    skip_incompatible: bool = True
    confirm_non_sandbox: bool = False
    cron_expr: str = Field(min_length=5, max_length=64)
    timezone: str = Field(default="Asia/Shanghai", max_length=64)
    enabled: bool = True
    concurrency_policy: Literal["forbid", "allow"] = "forbid"
    gate_config: PatrolGateConfig = Field(default_factory=PatrolGateConfig)
    notify_channels: list[str] = Field(default_factory=list, max_length=10)
    notify_on_recovery: bool = True


class PatrolUpdate(StrictBody):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    version_policy: Literal["latest_published", "pinned"] | None = None
    version_id: UUID | None = None
    target_project_id: str | None = Field(default=None, min_length=1, max_length=64)
    target_graph_id: (
        Literal["dearflow_agent", "showcase_demo", "reference_agent", "workflow_demo"]
        | None
    ) = None
    target_agent_id: UUID | None = None
    target_model_id: UUID | None = None
    judge_model_id: UUID | None = None
    embedding_model_id: UUID | None = None
    case_keys: list[str] | None = Field(default=None, max_length=500)
    concurrency: int | None = Field(default=None, ge=1, le=5)
    repeat_k: int | None = Field(default=None, ge=1, le=5)
    skip_incompatible: bool | None = None
    confirm_non_sandbox: bool | None = None
    cron_expr: str | None = Field(default=None, min_length=5, max_length=64)
    timezone: str | None = Field(default=None, max_length=64)
    enabled: bool | None = None
    concurrency_policy: Literal["forbid", "allow"] | None = None
    gate_config: PatrolGateConfig | None = None
    notify_channels: list[str] | None = Field(default=None, max_length=10)
    notify_on_recovery: bool | None = None


class CronPreviewRequest(StrictBody):
    cron_expr: str = Field(min_length=5, max_length=64)
    timezone: str = Field(default="Asia/Shanghai", max_length=64)
    count: int = Field(default=5, ge=1, le=10)


class SandboxFlagRequest(StrictBody):
    is_sandbox: bool


class CaseImportRequest(StrictBody):
    items: list[CaseUpsert] = Field(min_length=1, max_length=200)


class SessionsToSuiteRequest(StrictBody):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=4000)
    suite_type: Literal["golden", "regression", "curated", "benchmark"] = "curated"
    source_project_id: str | None = Field(default=None, max_length=64)
    default_graph_id: Literal[
        "dearflow_agent", "showcase_demo", "reference_agent", "workflow_demo"
    ] = "dearflow_agent"
    thread_ids: list[str] = Field(min_length=1, max_length=20)
    agent_id: UUID | None = None


class ExpertThreadCreateRequest(StrictBody):
    graph_id: Literal["eval_copilot", "eval_diagnosis"]
    title: str = Field(default="", max_length=128)
    ref_id: str | None = Field(default=None, max_length=128)


class ExpertTurnStreamRequest(StrictBody):
    graph_id: Literal["eval_copilot", "eval_diagnosis"]
    content: str = Field(min_length=1, max_length=16000)
    model_id: str | None = Field(default=None, max_length=64)
    ref_id: str | None = Field(default=None, max_length=128)


class ExpertRespondRequest(StrictBody):
    graph_id: Literal["eval_copilot", "eval_diagnosis"]
    command: dict[str, Any]
    run_id: str | None = Field(default=None, max_length=128)
