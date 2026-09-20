"""Replace catalog-based grants with explicit project/user denials."""
from alembic import op
import sqlalchemy as sa

revision = "20260920_0002"
down_revision = "20260910_0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "runtime_tool_restrictions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("graph_id", sa.String(128), nullable=False),
        sa.Column("subject_type", sa.String(16), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("tool_name", sa.String(128), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("project_id", "graph_id", "subject_type", "subject_id", "tool_name", name="uq_runtime_tool_restriction"),
        sa.CheckConstraint("subject_type IN ('project', 'user')", name="ck_tool_restriction_subject"),
    )
    op.create_index("ix_runtime_tool_restrictions_project_id", "runtime_tool_restrictions", ["project_id"])
    op.drop_table("project_tool_policies")


def downgrade():
    raise RuntimeError("Retired tool grants are not recoverable; use the new governance schema")
