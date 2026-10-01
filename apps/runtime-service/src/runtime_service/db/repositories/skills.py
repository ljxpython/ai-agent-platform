"""SQL-only helpers for user skill documents."""

from typing import Any

from psycopg import Connection
from psycopg.types.json import Jsonb

from runtime_service.db.schema import Scope


def get_document(
    db: Connection[dict[str, Any]], scope: Scope, slug: str
) -> dict | None:
    row = db.execute(
        "SELECT document FROM dear_skills WHERE tenant_id=%s AND project_id=%s AND user_id=%s AND slug=%s",
        (*scope, slug),
    ).fetchone()
    return row["document"] if row else None


def list_documents(db: Connection[dict[str, Any]], scope: Scope) -> list[dict]:
    return [
        row["document"]
        for row in db.execute(
            "SELECT document FROM dear_skills WHERE tenant_id=%s AND project_id=%s AND user_id=%s ORDER BY slug",
            scope,
        ).fetchall()
    ]


def list_slugs(db: Connection[dict[str, Any]], scope: Scope) -> list[str]:
    return [
        row["slug"]
        for row in db.execute(
            "SELECT slug FROM dear_skills WHERE tenant_id=%s AND project_id=%s AND user_id=%s",
            scope,
        ).fetchall()
    ]


def insert_document(
    db: Connection[dict[str, Any]], scope: Scope, document: dict
) -> None:
    db.execute(
        "INSERT INTO dear_skills VALUES (%s,%s,%s,%s,%s)",
        (*scope, document["slug"], Jsonb(document)),
    )


def update_document(
    db: Connection[dict[str, Any]], scope: Scope, document: dict
) -> None:
    db.execute(
        "UPDATE dear_skills SET document=%s WHERE tenant_id=%s AND project_id=%s AND user_id=%s AND slug=%s",
        (Jsonb(document), *scope, document["slug"]),
    )


def delete_document(db: Connection[dict[str, Any]], scope: Scope, slug: str) -> None:
    db.execute(
        "DELETE FROM dear_skills WHERE tenant_id=%s AND project_id=%s AND user_id=%s AND slug=%s",
        (*scope, slug),
    )
