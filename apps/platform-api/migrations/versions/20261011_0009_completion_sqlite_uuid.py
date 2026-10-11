"""Align legacy SQLite completion UUID storage without removing history."""

import sqlalchemy as sa
from alembic import op

revision = "20261011_0009"
down_revision = "20261011_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name != "sqlite":
        return
    columns = {
        "run_completion_events": ("event_id",),
        "run_completion_receipts": ("id", "event_id"),
    }
    for table, names in columns.items():
        for name in names:
            if connection.exec_driver_sql(
                f"SELECT 1 FROM {table} WHERE typeof({name}) != 'text' LIMIT 1"
            ).first():
                raise RuntimeError(
                    "Non-text completion UUIDs require identity recovery before migration"
                )
    for table, names in columns.items():
        with op.batch_alter_table(table) as batch:
            for name in names:
                batch.alter_column(
                    name, existing_type=sa.Numeric(), type_=sa.Uuid(as_uuid=True)
                )


def downgrade() -> None:
    raise RuntimeError(
        "Run acceptance facts are retained; destructive downgrade is unsupported"
    )
