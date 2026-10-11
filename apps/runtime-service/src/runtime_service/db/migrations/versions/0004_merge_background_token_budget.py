"""Join background receipts and Run token policy without changing data."""

revision = "0004_background_token_budget"
down_revision = ("0003_background_tasks", "0003_token_budget")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
