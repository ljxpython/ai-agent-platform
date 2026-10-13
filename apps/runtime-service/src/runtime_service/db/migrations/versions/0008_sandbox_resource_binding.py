"""Recover remote resources in their original scope after a Worker restart."""

from alembic import op

revision = "0008_sandbox_resource_binding"
down_revision = "0007_sandbox_resources"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE runtime_run_resources ADD COLUMN sandbox_binding jsonb")


def downgrade():
    raise RuntimeError(
        "Retain sandbox resource facts and migration head; roll back the application instead"
    )
