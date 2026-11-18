"""Retained control-plane budget rules and reliable notification state."""

import sqlalchemy as sa
from alembic import op

revision = "20261118_0015"
down_revision = "20261117_0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "runtime_budget_tenants",
        sa.Column("tenant_id", sa.String(128), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("synced_revision", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_error", sa.String(128)),
    )
    op.create_table(
        "runtime_budget_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_runtime_budget_policies_tenant_id", "runtime_budget_policies", ["tenant_id"]
    )
    op.create_table(
        "runtime_budget_nonces",
        sa.Column("nonce", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "runtime_budget_event_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
    )
    op.create_table(
        "runtime_budget_deliveries",
        sa.Column("event_id", sa.String(36), primary_key=True),
        sa.Column("channel_id", sa.String(36), primary_key=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(128)),
    )


def downgrade():
    raise RuntimeError("Budget history is retained; roll back application compatibly")
