"""Persist the exact upstream acceptance request before sending it."""

import sqlalchemy as sa
from alembic import op

revision = "20261010_0007"
down_revision = "20261007_0006"
branch_labels = None
depends_on = None


def upgrade():
    for name, kind in (
        ("upstream_idempotency_key", sa.String(256)),
        ("upstream_body", sa.LargeBinary()),
        ("upstream_request_digest", sa.String(71)),
        ("upstream_receipt_scope_id", sa.String(64)),
        ("upstream_receipt_credential_id", sa.String(64)),
        ("upstream_auth_snapshot", sa.JSON()),
    ):
        op.add_column("run_requests", sa.Column(name, kind, nullable=True))


def downgrade():
    raise RuntimeError(
        "Upstream acceptance facts are retained; destructive downgrade is not supported"
    )
