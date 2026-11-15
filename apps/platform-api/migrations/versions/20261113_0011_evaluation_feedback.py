"""Source feedback and consent; rollback keeps audit and consent records."""

import sqlalchemy as sa
from alembic import op

revision = "20261113_0011"
down_revision = "20261030_0010"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("evaluation_feedback_events"):
        op.create_table(
            "evaluation_feedback_events",
            sa.Column("event_id", sa.String(36), primary_key=True),
            sa.Column("tenant_id", sa.String(64), nullable=False),
            sa.Column("project_id", sa.String(64), nullable=False),
            sa.Column("thread_id", sa.String(128), nullable=False),
            sa.Column("message_id", sa.String(256), nullable=False),
            sa.Column("actor_id", sa.String(64), nullable=False),
            sa.Column("revision", sa.Integer, nullable=False),
            sa.Column("digest", sa.String(64), nullable=False),
            sa.Column("payload", sa.JSON, nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.UniqueConstraint(
                "thread_id",
                "message_id",
                "actor_id",
                "revision",
                name="uq_evaluation_feedback_revision",
            ),
        )
        op.create_index(
            "ix_evaluation_feedback_events_project_id",
            "evaluation_feedback_events",
            ["project_id"],
        )
        op.create_index(
            "ix_evaluation_feedback_events_thread_id",
            "evaluation_feedback_events",
            ["thread_id"],
        )
    if not inspector.has_table("evaluation_exports"):
        op.create_table(
            "evaluation_exports",
            sa.Column("export_id", sa.String(36), primary_key=True),
            sa.Column("event_id", sa.String(36), nullable=False),
            sa.Column("project_id", sa.String(64), nullable=False),
            sa.Column("actor_id", sa.String(64), nullable=False),
            sa.Column("digest", sa.String(64), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("payload", sa.JSON, nullable=False),
            sa.Column("receipt", sa.JSON, nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
        op.create_index(
            "ix_evaluation_exports_project_id", "evaluation_exports", ["project_id"]
        )
        op.create_index(
            "ix_evaluation_exports_event_id", "evaluation_exports", ["event_id"]
        )


def downgrade():
    # Disable feature flags to roll back application behavior without deleting evidence.
    pass
