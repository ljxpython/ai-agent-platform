"""Persist the deployment token policy and native-Run stop reason."""

from alembic import op

revision = "0003_token_budget"
down_revision = "0002_run_control"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
ALTER TABLE runtime_usage_runs
    ADD COLUMN IF NOT EXISTS token_budget_policy jsonb;
ALTER TABLE runtime_usage_runs
    ADD COLUMN IF NOT EXISTS token_budget_stop_code text;
ALTER TABLE runtime_usage_runs
    DROP CONSTRAINT IF EXISTS runtime_usage_runs_token_budget_stop_code_check;
ALTER TABLE runtime_usage_runs
    ADD CONSTRAINT runtime_usage_runs_token_budget_stop_code_check
    CHECK (token_budget_stop_code IS NULL OR token_budget_stop_code IN (
        'token_budget_exhausted', 'token_budget_unverifiable'
    ));
""")


def downgrade():
    # Budget facts are retained; old Runtime versions ignore additive columns.
    pass
