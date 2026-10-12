"""Join migration heads and align SQLite completion UUID storage."""

import sqlalchemy as sa
from alembic import op

revision = "20261011_0008"
down_revision = ("20261009_0007", "20261010_0007")
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    if connection.dialect.name != "sqlite":
        return
    # The old PostgreSQL-only UUID type gives SQLite numeric affinity.
    for table, columns in (
        ("run_completion_events", ("event_id",)),
        ("run_completion_receipts", ("id", "event_id")),
    ):
        for column in columns:
            if connection.execute(
                sa.text(
                    f"SELECT 1 FROM {table} WHERE typeof({column}) <> 'text' LIMIT 1"
                )
            ).first():
                raise RuntimeError(
                    "SQLite completion UUIDs contain numeric values; "
                    "restore the original identifiers before upgrading"
                )
        with op.batch_alter_table(table) as batch:
            for column in columns:
                batch.alter_column(
                    column, existing_type=sa.Numeric(), type_=sa.Uuid(as_uuid=True)
                )


def downgrade():
    raise RuntimeError(
        "Retain the migration history; roll back application code instead"
    )
