"""Add scope_type and project_id to runtime_catalog_models for BYOK support."""
from alembic import op
import sqlalchemy as sa

revision = "20260922_0004"
down_revision = "20260922_0003"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("runtime_catalog_models") as batch_op:
        batch_op.add_column(
            sa.Column(
                "scope_type",
                sa.String(16),
                nullable=False,
                server_default="platform",
            )
        )
        batch_op.add_column(
            sa.Column(
                "project_id",
                sa.Uuid(),
                sa.ForeignKey(
                    "projects.id",
                    ondelete="CASCADE",
                    name="fk_runtime_catalog_models_project_id",
                ),
                nullable=True,
            )
        )
        batch_op.create_index(
            "ix_runtime_catalog_models_scope_project",
            ["scope_type", "project_id"],
        )


def downgrade():
    with op.batch_alter_table("runtime_catalog_models") as batch_op:
        batch_op.drop_index("ix_runtime_catalog_models_scope_project")
        batch_op.drop_column("project_id")
        batch_op.drop_column("scope_type")
