"""Upgrade eval_patrol_schedules and eval_runs for scheduled patrol execution & alerting."""

import sqlalchemy as sa
from alembic import op

revision = "20261128_0018"
down_revision = "20261128_0017"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("eval_patrol_schedules"):
        cols = {c["name"] for c in inspector.get_columns("eval_patrol_schedules")}
        with op.batch_alter_table("eval_patrol_schedules") as batch_op:
            batch_op.alter_column("version_id", existing_type=sa.String(36), nullable=True)

        additions = [
            ("version_policy", sa.Column("version_policy", sa.String(32), nullable=False, server_default="latest_published")),
            ("target_agent_id", sa.Column("target_agent_id", sa.String(64), nullable=True)),
            ("target_model_id", sa.Column("target_model_id", sa.String(64), nullable=True)),
            ("embedding_model_id", sa.Column("embedding_model_id", sa.String(64), nullable=True)),
            ("case_keys_json", sa.Column("case_keys_json", sa.JSON(), nullable=False, server_default="[]")),
            ("concurrency", sa.Column("concurrency", sa.Integer(), nullable=False, server_default="2")),
            ("repeat_k", sa.Column("repeat_k", sa.Integer(), nullable=False, server_default="1")),
            ("skip_incompatible", sa.Column("skip_incompatible", sa.Boolean(), nullable=False, server_default=sa.true())),
            ("confirm_non_sandbox", sa.Column("confirm_non_sandbox", sa.Boolean(), nullable=False, server_default=sa.false())),
            ("timezone", sa.Column("timezone", sa.String(64), nullable=False, server_default="Asia/Shanghai")),
            ("concurrency_policy", sa.Column("concurrency_policy", sa.String(32), nullable=False, server_default="forbid")),
            ("gate_config_json", sa.Column("gate_config_json", sa.JSON(), nullable=False, server_default="{}")),
            ("notify_on_recovery", sa.Column("notify_on_recovery", sa.Boolean(), nullable=False, server_default=sa.true())),
            ("next_run_at", sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True)),
            ("last_triggered_at", sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True)),
            ("last_status", sa.Column("last_status", sa.String(32), nullable=False, server_default="idle")),
            ("last_message", sa.Column("last_message", sa.Text(), nullable=False, server_default="")),
            ("consecutive_failures", sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0")),
            ("updated_at", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())),
        ]
        for col_name, col_def in additions:
            if col_name not in cols:
                op.add_column("eval_patrol_schedules", col_def)

        idxs = {idx["name"] for idx in inspector.get_indexes("eval_patrol_schedules")}
        if "ix_eval_patrol_schedules_next_run_at" not in idxs:
            op.create_index(
                "ix_eval_patrol_schedules_next_run_at",
                "eval_patrol_schedules",
                ["next_run_at"],
            )

    if inspector.has_table("eval_runs"):
        run_cols = {c["name"] for c in inspector.get_columns("eval_runs")}
        if "trigger_type" not in run_cols:
            op.add_column(
                "eval_runs",
                sa.Column("trigger_type", sa.String(32), nullable=False, server_default="manual"),
            )
        if "patrol_schedule_id" not in run_cols:
            op.add_column(
                "eval_runs",
                sa.Column("patrol_schedule_id", sa.String(36), nullable=True),
            )
        run_idxs = {idx["name"] for idx in inspector.get_indexes("eval_runs")}
        if "ix_eval_runs_trigger_type" not in run_idxs:
            op.create_index("ix_eval_runs_trigger_type", "eval_runs", ["trigger_type"])
        if "ix_eval_runs_patrol_schedule_id" not in run_idxs:
            op.create_index("ix_eval_runs_patrol_schedule_id", "eval_runs", ["patrol_schedule_id"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("eval_runs"):
        run_idxs = {idx["name"] for idx in inspector.get_indexes("eval_runs")}
        if "ix_eval_runs_patrol_schedule_id" in run_idxs:
            op.drop_index("ix_eval_runs_patrol_schedule_id", table_name="eval_runs")
        if "ix_eval_runs_trigger_type" in run_idxs:
            op.drop_index("ix_eval_runs_trigger_type", table_name="eval_runs")
        run_cols = {c["name"] for c in inspector.get_columns("eval_runs")}
        if "patrol_schedule_id" in run_cols:
            op.drop_column("eval_runs", "patrol_schedule_id")
        if "trigger_type" in run_cols:
            op.drop_column("eval_runs", "trigger_type")

    if inspector.has_table("eval_patrol_schedules"):
        idxs = {idx["name"] for idx in inspector.get_indexes("eval_patrol_schedules")}
        if "ix_eval_patrol_schedules_next_run_at" in idxs:
            op.drop_index("ix_eval_patrol_schedules_next_run_at", table_name="eval_patrol_schedules")
        cols = {c["name"] for c in inspector.get_columns("eval_patrol_schedules")}
        for col_name in [
            "updated_at",
            "consecutive_failures",
            "last_message",
            "last_status",
            "last_triggered_at",
            "next_run_at",
            "notify_on_recovery",
            "gate_config_json",
            "concurrency_policy",
            "timezone",
            "confirm_non_sandbox",
            "skip_incompatible",
            "repeat_k",
            "concurrency",
            "case_keys_json",
            "embedding_model_id",
            "target_model_id",
            "target_agent_id",
            "version_policy",
        ]:
            if col_name in cols:
                op.drop_column("eval_patrol_schedules", col_name)
