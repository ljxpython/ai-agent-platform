"""Persist generic runtime completion ownership, events and read receipts."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20261009_0007"
down_revision = "20261007_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "run_requests", sa.Column("origin_ref", sa.String(128), nullable=True)
    )
    op.create_index(
        "ix_run_requests_origin_ref", "run_requests", ["origin_ref"], unique=True
    )
    op.create_table(
        "run_completion_origins",
        sa.Column("origin_ref", sa.String(128), primary_key=True),
        sa.Column("runtime_id", sa.String(64), nullable=False),
        sa.Column("source_kind", sa.String(16), nullable=False),
        sa.Column("source_id", sa.String(128), nullable=True),
        sa.Column("thread_mode", sa.String(16), nullable=False),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("thread_id", sa.String(128), nullable=True),
        sa.Column("agent_key", sa.String(128), nullable=False),
        sa.Column("requested_by", sa.String(255), nullable=True),
        sa.Column("run_id", sa.String(128), nullable=True),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("run_id", name="uq_run_completion_origins_run"),
    )
    for name, column in (
        ("project_id", "project_id"),
        ("thread_id", "thread_id"),
        ("requested_by", "requested_by"),
        ("source_id", "source_id"),
    ):
        op.create_index(
            f"ix_run_completion_origins_{name}", "run_completion_origins", [column]
        )
    op.create_index(
        "ix_run_completion_origins_run_id",
        "run_completion_origins",
        ["run_id"],
        unique=True,
    )
    op.create_table(
        "run_completion_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("runtime_id", sa.String(64), nullable=False),
        sa.Column("origin_ref", sa.String(128), nullable=False),
        sa.Column("run_id", sa.String(128), nullable=False),
        sa.Column("thread_id", sa.String(128), nullable=True),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reason", sa.String(64), nullable=True),
        sa.Column("reason_code", sa.String(128), nullable=True),
        sa.Column("model_error_code", sa.String(128), nullable=True),
        sa.Column("agent_key", sa.String(128), nullable=False),
        sa.Column("recipient_user_id", sa.String(64), nullable=True),
        sa.Column("suppressed", sa.Boolean(), nullable=False),
        sa.Column("detail_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dedup_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("body_digest", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("runtime_id", "run_id", name="uq_run_completion_event_run"),
    )
    for name, column in (
        ("origin_ref", "origin_ref"),
        ("thread_id", "thread_id"),
        ("project_id", "project_id"),
        ("run_id", "run_id"),
    ):
        op.create_index(
            f"ix_run_completion_events_{name}", "run_completion_events", [column]
        )
    op.create_index(
        "ix_run_completion_feed",
        "run_completion_events",
        ["project_id", "recipient_user_id", "accepted_at", "event_id"],
    )
    op.create_table(
        "run_completion_receipts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", sa.String(64), nullable=False),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "event_id", "actor_user_id", name="uq_run_completion_receipt_actor"
        ),
    )
    op.create_index(
        "ix_run_completion_receipts_event_id", "run_completion_receipts", ["event_id"]
    )
    op.create_index(
        "ix_run_completion_receipts_actor_user_id",
        "run_completion_receipts",
        ["actor_user_id"],
    )


def downgrade() -> None:
    raise RuntimeError(
        "Run completion history is retained; destructive downgrade is unsupported"
    )
