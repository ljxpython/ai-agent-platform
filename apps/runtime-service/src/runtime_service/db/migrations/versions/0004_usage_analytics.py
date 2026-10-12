"""Join the two application heads and index bounded usage windows."""

from alembic import op

revision = "0004_usage_analytics"
down_revision = ("0003_token_budget", "0003_background_tasks")
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "CREATE INDEX ix_runtime_usage_calls_project_time ON runtime_usage_calls (tenant_id,project_id,started_at,run_id,model_call_id)"
    )
    op.execute(
        "CREATE INDEX ix_runtime_usage_runs_project_time ON runtime_usage_runs (tenant_id,project_id,collection_started_at,run_id)"
    )


def downgrade():
    raise RuntimeError(
        "Usage facts and indexes are retained; roll back application readers instead"
    )
