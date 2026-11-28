"""Native evaluation studio tables for suites, versions, runs, checkpoints, reviews, and patrols."""

import sqlalchemy as sa
from alembic import op

revision = "20261128_0016"
down_revision = "20261118_0015"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "eval_suites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("suite_type", sa.String(32), nullable=False, server_default="curated"),
        sa.Column("owner_project_id", sa.String(64), nullable=False),
        sa.Column("source_project_id", sa.String(64), nullable=True),
        sa.Column(
            "default_graph_id",
            sa.String(64),
            nullable=False,
            server_default="dearflow_agent",
        ),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_eval_suites_owner_project_id", "eval_suites", ["owner_project_id"])

    op.create_table(
        "eval_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("suite_id", sa.String(36), nullable=False),
        sa.Column("case_key", sa.String(128), nullable=False),
        sa.Column("split", sa.String(16), nullable=False, server_default="dev"),
        sa.Column("schema_version", sa.String(16), nullable=False, server_default="3"),
        sa.Column("required_capabilities_json", sa.JSON(), nullable=False),
        sa.Column("turns_json", sa.JSON(), nullable=False),
        sa.Column("simulation_json", sa.JSON(), nullable=True),
        sa.Column("expectations_json", sa.JSON(), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("suite_id", "case_key", name="uq_eval_cases_suite_key"),
    )
    op.create_index("ix_eval_cases_suite_id", "eval_cases", ["suite_id"])

    op.create_table(
        "eval_suite_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("suite_id", sa.String(36), nullable=False),
        sa.Column("version_num", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("frozen_cases_json", sa.JSON(), nullable=False),
        sa.Column("published_by", sa.String(64), nullable=False),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("suite_id", "version_num", name="uq_eval_suite_version_num"),
    )
    op.create_index("ix_eval_suite_versions_suite_id", "eval_suite_versions", ["suite_id"])

    op.create_table(
        "eval_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("suite_id", sa.String(36), nullable=False),
        sa.Column("version_id", sa.String(36), nullable=False),
        sa.Column("owner_project_id", sa.String(64), nullable=False),
        sa.Column("target_project_id", sa.String(64), nullable=False),
        sa.Column("target_graph_id", sa.String(64), nullable=False),
        sa.Column("target_agent_id", sa.String(64), nullable=False),
        sa.Column("target_model_id", sa.String(64), nullable=False),
        sa.Column("target_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("judge_model_id", sa.String(64), nullable=True),
        sa.Column("embedding_model_id", sa.String(64), nullable=True),
        sa.Column("matrix_group_id", sa.String(36), nullable=True),
        sa.Column("mode", sa.String(32), nullable=False, server_default="regression"),
        sa.Column("concurrency", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("repeat_k", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("gate_exit_code", sa.Integer(), nullable=True),
        sa.Column("summary_metrics_json", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_eval_runs_suite_id", "eval_runs", ["suite_id"])
    op.create_index("ix_eval_runs_owner_project_id", "eval_runs", ["owner_project_id"])
    op.create_index("ix_eval_runs_target_project_id", "eval_runs", ["target_project_id"])
    op.create_index("ix_eval_runs_matrix_group_id", "eval_runs", ["matrix_group_id"])

    op.create_table(
        "eval_run_cases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("case_key", sa.String(128), nullable=False),
        sa.Column("attempt_idx", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("thread_id", sa.String(128), nullable=True),
        sa.Column("trace_ids_json", sa.JSON(), nullable=False),
        sa.Column("rule_passed", sa.Boolean(), nullable=True),
        sa.Column("overall_score", sa.Float(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("ttft_ms", sa.Integer(), nullable=True),
        sa.Column("token_usage_json", sa.JSON(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("error_category", sa.String(64), nullable=True),
        sa.Column("evidence_path", sa.String(512), nullable=True),
        sa.Column("results_json", sa.JSON(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "run_id", "case_key", "attempt_idx", name="uq_eval_run_case_attempt"
        ),
    )
    op.create_index("ix_eval_run_cases_run_id", "eval_run_cases", ["run_id"])

    op.create_table(
        "eval_human_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_case_id", sa.String(36), nullable=False),
        sa.Column("reviewer_id", sa.String(64), nullable=False),
        sa.Column("human_verdict", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("aligned_with_judge", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_eval_human_reviews_run_case_id", "eval_human_reviews", ["run_case_id"])

    op.create_table(
        "eval_patrol_schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("suite_id", sa.String(36), nullable=False),
        sa.Column("version_id", sa.String(36), nullable=False),
        sa.Column("owner_project_id", sa.String(64), nullable=False),
        sa.Column("target_project_id", sa.String(64), nullable=False),
        sa.Column("target_graph_id", sa.String(64), nullable=False),
        sa.Column("judge_model_id", sa.String(64), nullable=True),
        sa.Column("cron_expr", sa.String(64), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("notify_channels_json", sa.JSON(), nullable=False),
        sa.Column("last_run_id", sa.String(36), nullable=True),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_eval_patrol_schedules_suite_id", "eval_patrol_schedules", ["suite_id"])
    op.create_index(
        "ix_eval_patrol_schedules_owner_project_id",
        "eval_patrol_schedules",
        ["owner_project_id"],
    )

    op.create_table(
        "eval_sandbox_projects",
        sa.Column("project_id", sa.String(64), primary_key=True),
        sa.Column("is_sandbox", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_by", sa.String(64), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade():
    op.drop_table("eval_sandbox_projects")
    op.drop_index(
        "ix_eval_patrol_schedules_owner_project_id",
        table_name="eval_patrol_schedules",
    )
    op.drop_index("ix_eval_patrol_schedules_suite_id", table_name="eval_patrol_schedules")
    op.drop_table("eval_patrol_schedules")
    op.drop_index("ix_eval_human_reviews_run_case_id", table_name="eval_human_reviews")
    op.drop_table("eval_human_reviews")
    op.drop_index("ix_eval_run_cases_run_id", table_name="eval_run_cases")
    op.drop_table("eval_run_cases")
    op.drop_index("ix_eval_runs_matrix_group_id", table_name="eval_runs")
    op.drop_index("ix_eval_runs_target_project_id", table_name="eval_runs")
    op.drop_index("ix_eval_runs_owner_project_id", table_name="eval_runs")
    op.drop_index("ix_eval_runs_suite_id", table_name="eval_runs")
    op.drop_table("eval_runs")
    op.drop_index("ix_eval_suite_versions_suite_id", table_name="eval_suite_versions")
    op.drop_table("eval_suite_versions")
    op.drop_index("ix_eval_cases_suite_id", table_name="eval_cases")
    op.drop_table("eval_cases")
    op.drop_index("ix_eval_suites_owner_project_id", table_name="eval_suites")
    op.drop_table("eval_suites")
