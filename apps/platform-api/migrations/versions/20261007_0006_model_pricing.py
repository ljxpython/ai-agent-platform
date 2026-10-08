"""Optional configured prices; existing models retain unknown pricing."""

from alembic import op
import sqlalchemy as sa

revision = "20261007_0006"
down_revision = "20260925_0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "runtime_catalog_models", sa.Column("pricing_json", sa.JSON(), nullable=True)
    )


def downgrade():
    raise RuntimeError(
        "Price snapshots are retained; destructive downgrade is not supported"
    )
