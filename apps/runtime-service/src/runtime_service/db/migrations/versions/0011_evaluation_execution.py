"""Keep evaluated Worker identity independently of Trace export."""

from alembic import op

revision = "0011_evaluation_execution"
down_revision = "0010_terminal_cleanup_binding"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE runtime_evaluation_execution (
            tenant_id text NOT NULL, project_id text NOT NULL,
            thread_id uuid NOT NULL, run_id uuid NOT NULL,
            graph_id text NOT NULL, attempt_id uuid NOT NULL,
            manifest jsonb NOT NULL, context_hash text NOT NULL,
            config_hash text NOT NULL, recorded_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenant_id, project_id, thread_id, run_id)
        )
    """)


def downgrade():
    raise RuntimeError("Preserve execution evidence; roll back application only")
