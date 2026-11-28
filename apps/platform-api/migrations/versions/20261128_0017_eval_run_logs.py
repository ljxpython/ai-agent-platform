"""Add eval_run_logs table for bounded real-time evaluation execution logs."""

import sqlalchemy as sa
from alembic import op

revision = "20261128_0017"
down_revision = "20261128_0016"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "eval_run_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(16), nullable=False, server_default="INFO"),
        sa.Column("case_key", sa.String(128), nullable=True),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("run_id", "seq", name="uq_eval_run_logs_run_seq"),
    )
    op.create_index("ix_eval_run_logs_run_id", "eval_run_logs", ["run_id"])


def downgrade():
    op.drop_index("ix_eval_run_logs_run_id", table_name="eval_run_logs")
    op.drop_table("eval_run_logs")
