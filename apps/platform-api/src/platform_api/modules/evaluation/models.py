from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from platform_api.core.db.base import Base


class FeedbackEvent(Base):
    __tablename__ = "evaluation_feedback_events"
    __table_args__ = (
        UniqueConstraint(
            "thread_id",
            "message_id",
            "actor_id",
            "revision",
            name="uq_evaluation_feedback_revision",
        ),
    )
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    message_id: Mapped[str] = mapped_column(String(256), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EvaluationExport(Base):
    __tablename__ = "evaluation_exports"
    export_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="ready")
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    receipt: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EvalSuite(Base):
    __tablename__ = "eval_suites"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    suite_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="curated"
    )
    owner_project_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    source_project_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    default_graph_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="dearflow_agent"
    )
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EvalCase(Base):
    __tablename__ = "eval_cases"
    __table_args__ = (
        UniqueConstraint("suite_id", "case_key", name="uq_eval_cases_suite_key"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    suite_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    case_key: Mapped[str] = mapped_column(String(128), nullable=False)
    split: Mapped[str] = mapped_column(String(16), nullable=False, default="dev")
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False, default="3")
    required_capabilities_json: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    turns_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    simulation_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    expectations_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    metrics_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EvalSuiteVersion(Base):
    __tablename__ = "eval_suite_versions"
    __table_args__ = (
        UniqueConstraint("suite_id", "version_num", name="uq_eval_suite_version_num"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    suite_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version_num: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    frozen_cases_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    published_by: Mapped[str] = mapped_column(String(64), nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EvalRun(Base):
    __tablename__ = "eval_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    suite_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    owner_project_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    target_project_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    target_graph_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_model_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_snapshot_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )
    judge_model_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding_model_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    matrix_group_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    mode: Mapped[str] = mapped_column(String(32), nullable=False, default="regression")
    concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    repeat_k: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    gate_exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary_metrics_json: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class EvalRunCase(Base):
    __tablename__ = "eval_run_cases"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "case_key", "attempt_idx", name="uq_eval_run_case_attempt"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    case_key: Mapped[str] = mapped_column(String(128), nullable=False)
    attempt_idx: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    thread_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    trace_ids_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    rule_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ttft_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_usage_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    results_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class EvalHumanReview(Base):
    __tablename__ = "eval_human_reviews"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_case_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    reviewer_id: Mapped[str] = mapped_column(String(64), nullable=False)
    human_verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    aligned_with_judge: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EvalPatrolSchedule(Base):
    __tablename__ = "eval_patrol_schedules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    suite_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    version_id: Mapped[str] = mapped_column(String(36), nullable=False)
    owner_project_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True
    )
    target_project_id: Mapped[str] = mapped_column(String(64), nullable=False)
    target_graph_id: Mapped[str] = mapped_column(String(64), nullable=False)
    judge_model_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cron_expr: Mapped[str] = mapped_column(String(64), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notify_channels_json: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    last_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EvalSandboxProject(Base):
    __tablename__ = "eval_sandbox_projects"
    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    is_sandbox: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
