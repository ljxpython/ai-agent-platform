"""SQL-only helpers for the Runtime memory document."""

from typing import Any

from psycopg import Connection
from psycopg.types.json import Jsonb

from runtime_service.db.schema import Scope


def load_document(db: Connection[dict[str, Any]], scope: Scope) -> dict | None:
    row = db.execute(
        "SELECT document FROM dear_memory WHERE tenant_id=%s AND project_id=%s AND user_id=%s",
        scope,
    ).fetchone()
    return row["document"] if row else None


def save_document(db: Connection[dict[str, Any]], scope: Scope, document: dict) -> None:
    db.execute(
        """INSERT INTO dear_memory VALUES (%s,%s,%s,%s)
        ON CONFLICT (tenant_id,project_id,user_id) DO UPDATE SET document=EXCLUDED.document""",
        (*scope, Jsonb(document)),
    )
