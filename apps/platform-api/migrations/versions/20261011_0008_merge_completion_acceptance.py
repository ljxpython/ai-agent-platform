"""Join completion ownership and immutable acceptance facts."""

revision = "20261011_0008"
down_revision = ("20261009_0007", "20261010_0007")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    # Refuse before a sibling downgrade can delete completion ownership on SQLite.
    raise RuntimeError(
        "Upstream acceptance facts are retained; destructive downgrade is not supported"
    )
