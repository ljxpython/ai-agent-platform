"""Pin remote execution IDs before submission so unknown outcomes remain queryable."""

from alembic import op

revision = "0007_sandbox_resources"
down_revision = "0006_workspace_locations"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""ALTER TABLE runtime_run_resources
        ADD COLUMN sandbox_node_id text, ADD COLUMN sandbox_operation_id text;
        CREATE UNIQUE INDEX runtime_remote_operation_resource
        ON runtime_run_resources(sandbox_node_id,sandbox_operation_id)
        WHERE sandbox_node_id IS NOT NULL;""")


def downgrade():
    raise RuntimeError(
        "Retain sandbox resource facts and migration head; roll back the application instead"
    )
