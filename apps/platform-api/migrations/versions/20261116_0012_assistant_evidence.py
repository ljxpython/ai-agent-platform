"""Assistant evidence receipts; application rollback preserves authorization records."""

import sqlalchemy as sa
from alembic import op

revision = "20261116_0012"
down_revision = "20261113_0011"
branch_labels = None
depends_on = None


def upgrade():
    if not sa.inspect(op.get_bind()).has_table("assistant_evidence"):
        op.create_table(
            "assistant_evidence",
            sa.Column("evidence_id", sa.String(36), primary_key=True),
            sa.Column("project_id", sa.String(64), nullable=False),
            sa.Column("actor_id", sa.String(64), nullable=False),
            sa.Column("thread_id", sa.String(128), nullable=False),
            sa.Column("run_id", sa.String(128), nullable=False),
            sa.Column("operation", sa.String(32), nullable=False),
            sa.Column("source", sa.JSON, nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_assistant_evidence_project_id", "assistant_evidence", ["project_id"]
        )
        op.create_index(
            "ix_assistant_evidence_thread_id", "assistant_evidence", ["thread_id"]
        )


def downgrade():
    # Existing history must not lose its source authorization receipts on rollback.
    pass
