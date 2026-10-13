"""Retain workspace identity independently of replaceable containers."""

from alembic import op

revision = "0006_workspace_locations"
down_revision = ("0005_usage_projection", "0004_background_token_budget")
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE runtime_workspace_locations (
            execution_host text NOT NULL, tenant_id text NOT NULL,
            project_id text NOT NULL, thread_id text NOT NULL, graph_id text NOT NULL,
            target text NOT NULL CHECK(target IN ('local','remote')), node_id text,
            workspace_id text NOT NULL, storage_path text, status text NOT NULL DEFAULT 'retained'
                CHECK(status IN ('retained','deleting','purged')),
            created_at timestamptz NOT NULL DEFAULT now(),
            CHECK ((target='remote' AND node_id IS NOT NULL AND storage_path IS NULL)
                OR (target='local' AND node_id IS NULL AND storage_path IS NOT NULL)),
            PRIMARY KEY(execution_host,tenant_id,project_id,thread_id,graph_id)
        )
    """)
    op.execute("ALTER TABLE runtime_background_tasks ADD COLUMN sandbox_node_id text")


def downgrade():
    raise RuntimeError(
        "Retain sandbox location facts and migration head; roll back the application instead"
    )
