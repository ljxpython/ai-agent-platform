"""Channel project_ids multi-project support.

Revision ID: 20261117_0014
Revises: 20261117_0013
Create Date: 2026-11-17
"""

import sqlalchemy as sa
from alembic import op

revision = "20261117_0014"
down_revision = "20261117_0013"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("notification_channels"):
        columns = [c["name"] for c in inspector.get_columns("notification_channels")]
        if "project_ids" not in columns:
            op.add_column(
                "notification_channels",
                sa.Column("project_ids", sa.JSON(), nullable=False, server_default="[]"),
            )

        if "project_id" in columns:
            # 兼容迁移历史单 project_id 到 project_ids 列表
            try:
                op.execute(
                    """
                    UPDATE notification_channels
                    SET project_ids = json_build_array(project_id::text)
                    WHERE project_id IS NOT NULL;
                    """
                )
            except Exception:
                pass

            # 删除旧索引和列
            indexes = [idx["name"] for idx in inspector.get_indexes("notification_channels")]
            if "ix_notification_channels_project_id" in indexes:
                op.drop_index("ix_notification_channels_project_id", table_name="notification_channels")
            op.drop_column("notification_channels", "project_id")


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("notification_channels"):
        columns = [c["name"] for c in inspector.get_columns("notification_channels")]
        if "project_id" not in columns:
            op.add_column(
                "notification_channels",
                sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=True),
            )
            op.create_index(
                "ix_notification_channels_project_id",
                "notification_channels",
                ["project_id"],
            )
        if "project_ids" in columns:
            op.drop_column("notification_channels", "project_ids")
