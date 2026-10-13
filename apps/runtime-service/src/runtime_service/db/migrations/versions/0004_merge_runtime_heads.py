"""Join token-budget and background-task migrations for a fresh local stack."""

revision = "0004_merge_runtime_heads"
down_revision = ("0003_token_budget", "0003_background_tasks")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
