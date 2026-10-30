"""Persist enough local terminal ownership to verify cleanup after API restart."""

from alembic import op

revision = "0010_terminal_cleanup_binding"
down_revision = "0009_merge_runtime_heads"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE runtime_run_resources ADD COLUMN local_binding jsonb")


def downgrade():
    raise RuntimeError(
        "Preserve terminal cleanup ownership; roll back application only"
    )
