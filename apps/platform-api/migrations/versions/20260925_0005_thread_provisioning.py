"""Track platform thread reservations until Runtime creation is confirmed."""
from alembic import op
import sqlalchemy as sa

revision = "20260925_0005"
down_revision = "20260922_0004"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("thread_access") as batch_op:
        batch_op.add_column(sa.Column("provisioning_status", sa.String(16), nullable=False, server_default="ready"))
        batch_op.add_column(sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table("thread_access") as batch_op:
        batch_op.drop_column("reserved_at")
        batch_op.drop_column("provisioning_status")
