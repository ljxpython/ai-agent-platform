"""Track bounded, restartable registration of platform Thread retention."""

import sqlalchemy as sa
from alembic import op

revision = "20261030_0010"
down_revision = "20261011_0009"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "thread_access",
        sa.Column("retention_configured_at", sa.DateTime(timezone=True)),
    )
    op.add_column(
        "thread_access", sa.Column("retention_attempted_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "run_requests", sa.Column("snapshots_cleared_at", sa.DateTime(timezone=True))
    )
    op.add_column(
        "run_completion_events",
        sa.Column("details_cleared_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_thread_retention_pending",
        "thread_access",
        ["retention_configured_at", "retention_attempted_at"],
    )
    op.create_index(
        "ix_completion_details_pending",
        "run_completion_events",
        ["details_cleared_at", "detail_expires_at"],
    )
    op.create_index(
        "ix_completion_dedup_expiry", "run_completion_events", ["dedup_expires_at"]
    )


def downgrade():
    op.drop_index("ix_completion_dedup_expiry", table_name="run_completion_events")
    op.drop_index("ix_completion_details_pending", table_name="run_completion_events")
    op.drop_index("ix_thread_retention_pending", table_name="thread_access")
    op.drop_column("run_completion_events", "details_cleared_at")
    op.drop_column("run_requests", "snapshots_cleared_at")
    op.drop_column("thread_access", "retention_attempted_at")
    op.drop_column("thread_access", "retention_configured_at")
