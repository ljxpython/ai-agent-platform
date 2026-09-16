"""Dear-owned PostgreSQL connections and explicit schema deployment."""
from __future__ import annotations

import json
import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row


def connect(dsn: str | None = None):
    value = dsn or os.environ["DATABASE_URI"]
    return psycopg.connect(value.replace("postgresql+asyncpg://", "postgresql://").replace(
        "postgresql+psycopg://", "postgresql://"), row_factory=dict_row)


def lock_scope(db, scope: tuple[str, str, str], resource: str):
    if len(scope) != 3 or any(not isinstance(x, str) or not x or len(x) > 200 for x in scope):
        raise ValueError("invalid_governance_scope")
    db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
               (json.dumps([resource, *scope]),))


if __name__ == "__main__":
    with connect() as connection:
        connection.execute(Path(__file__).with_name("migrations").joinpath("002_governance.sql").read_text())
