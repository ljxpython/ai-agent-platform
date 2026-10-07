"""Add the optional trusted model context window capacity."""

import sqlalchemy as sa
from alembic import op

revision = "20261006_0006"
down_revision = "20260925_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("runtime_catalog_models") as batch_op:
        batch_op.add_column(
            sa.Column("context_window_tokens", sa.Integer(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("runtime_catalog_models") as batch_op:
        batch_op.drop_column("context_window_tokens")
