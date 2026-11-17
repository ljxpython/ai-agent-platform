"""Notification and alert center tables.

Revision ID: 20261117_0013
Revises: 20261116_0012
Create Date: 2026-11-17
"""

import sqlalchemy as sa
from alembic import op

revision = "20261117_0013"
down_revision = "20261116_0012"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("notifications"):
        op.create_table(
            "notifications",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("recipient_user_id", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("content", sa.Text(), nullable=False, server_default=""),
            sa.Column(
                "level", sa.String(32), nullable=False, server_default="info"
            ),
            sa.Column(
                "category", sa.String(64), nullable=False, server_default="system"
            ),
            sa.Column(
                "status", sa.String(32), nullable=False, server_default="unread"
            ),
            sa.Column("action_url", sa.String(512), nullable=True),
            sa.Column("metadata", sa.JSON(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            "ix_notifications_recipient_user_id",
            "notifications",
            ["recipient_user_id"],
        )
        op.create_index(
            "ix_notifications_project_id", "notifications", ["project_id"]
        )
        op.create_index("ix_notifications_status", "notifications", ["status"])
        op.create_index(
            "ix_notifications_created_at", "notifications", ["created_at"]
        )

    if not inspector.has_table("notification_channels"):
        op.create_table(
            "notification_channels",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column(
                "channel_type",
                sa.String(32),
                nullable=False,
                server_default="feishu",
            ),
            sa.Column("endpoint_url", sa.Text(), nullable=False),
            sa.Column("secret_token", sa.String(256), nullable=True),
            sa.Column(
                "is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column("subscribed_events", sa.JSON(), nullable=False),
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
        )
        op.create_index(
            "ix_notification_channels_project_id",
            "notification_channels",
            ["project_id"],
        )

    if not inspector.has_table("alert_events"):
        op.create_table(
            "alert_events",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("fingerprint", sa.String(64), nullable=False),
            sa.Column("source", sa.String(64), nullable=False),
            sa.Column("alert_type", sa.String(64), nullable=False),
            sa.Column("target_id", sa.String(128), nullable=False),
            sa.Column("level", sa.String(32), nullable=False),
            sa.Column("summary", sa.String(512), nullable=False),
            sa.Column("details", sa.JSON(), nullable=False),
            sa.Column(
                "occurrence_count",
                sa.Integer(),
                nullable=False,
                server_default="1",
            ),
            sa.Column(
                "first_seen_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "last_seen_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            "ix_alert_events_fingerprint", "alert_events", ["fingerprint"]
        )


def downgrade():
    op.drop_table("alert_events")
    op.drop_table("notification_channels")
    op.drop_table("notifications")
