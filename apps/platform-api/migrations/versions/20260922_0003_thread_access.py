"""Platform Thread ownership, sharing and time-limited takeover grants."""
from alembic import op
import sqlalchemy as sa

revision = "20260922_0003"
down_revision = "20260920_0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "thread_access",
        sa.Column("thread_id", sa.String(128), primary_key=True),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("owner_user_id", sa.String(64), nullable=True),
        sa.Column("visibility", sa.String(16), nullable=False),
        sa.Column("shared_actions", sa.JSON(), nullable=False),
        sa.Column("project_actions", sa.JSON(), nullable=False),
        sa.Column("takeovers", sa.JSON(), nullable=False),
    )
    op.create_index("ix_thread_access_project_id", "thread_access", ["project_id"])
    op.create_index("ix_thread_access_owner_user_id", "thread_access", ["owner_user_id"])


def downgrade():
    op.drop_index("ix_thread_access_owner_user_id", table_name="thread_access")
    op.drop_index("ix_thread_access_project_id", table_name="thread_access")
    op.drop_table("thread_access")
