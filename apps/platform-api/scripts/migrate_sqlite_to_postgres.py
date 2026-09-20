"""Copy the current Platform SQLite schema into an empty Alembic PostgreSQL database."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from database import check_database, configured_engine, migration_config
from platform_api.config import load_settings
from platform_api.core.db.base import Base
from platform_api.core.db.init_db import import_core_models
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    bindparam,
    create_engine,
    func,
    inspect,
    select,
    text,
)


def snapshot(source: Path, backup: Path) -> None:
    if not source.is_file():
        raise ValueError("Source SQLite file does not exist.")
    # Exclusive creation protects both existing backups and an accidentally identical source.
    fd = os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    with (
        closing(
            sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)
        ) as src,
        closing(sqlite3.connect(backup)) as dst,
    ):
        src.backup(dst)
        if dst.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("SQLite snapshot failed integrity validation.")
        if dst.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("SQLite snapshot contains foreign key violations.")


def normalize(value):
    if isinstance(value, datetime):
        return (
            value.replace(tzinfo=UTC).isoformat()
            if value.tzinfo is None
            else value.astimezone(UTC).isoformat()
        )
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    return value


def digest(connection, table):
    result = hashlib.sha256()
    count = 0
    for row in connection.execute(row_query(table)).mappings():
        payload = json.dumps(
            dict(row),
            default=normalize,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        result.update(payload.encode())
        result.update(b"\n")
        count += 1
    return {"rows": count, "sha256": result.hexdigest()}


def row_query(table):
    return select(
        table,
        *[
            col.is_(None).label(f"_sql_null_{col.name}")
            for col in table.c
            if isinstance(col.type, JSON)
        ],
    ).order_by(*table.primary_key.columns)


def copy_data(source_engine, target_engine, config, *, assume_naive_utc: bool):
    import_core_models()
    tables = Base.metadata.sorted_tables
    with source_engine.connect() as source, target_engine.begin() as target:
        check_database(target, config)
        if compare_metadata(MigrationContext.configure(target), Base.metadata):
            raise ValueError("Target schema differs from the current models.")
        inspector = inspect(source)
        if set(inspector.get_table_names()) - {
            "alembic_version",
            "sqlite_sequence",
        } != set(Base.metadata.tables):
            raise ValueError(
                "Source tables differ from the current baseline; explicit mapping required."
            )
        for table in tables:
            if {c["name"] for c in inspector.get_columns(table.name)} != set(
                table.c.keys()
            ):
                raise ValueError(f"Source columns differ: {table.name}")
        target.execute(text("SET LOCAL lock_timeout = '5s'"))
        target.execute(
            text(
                "LOCK TABLE "
                + ", ".join(f'"{t.name}"' for t in tables)
                + " IN ACCESS EXCLUSIVE MODE"
            )
        )
        if any(target.scalar(select(func.count()).select_from(t)) for t in tables):
            raise ValueError(
                "Target business tables must all be empty; refusing to overwrite."
            )
        report = {}
        for table in tables:
            # Reject invalid SQLite booleans before SQLAlchemy coerces arbitrary integers to True.
            for col in table.c:
                if isinstance(col.type, Boolean):
                    bad = source.execute(
                        text(
                            f'SELECT 1 FROM "{table.name}" WHERE "{col.name}" NOT IN (0, 1) LIMIT 1'
                        )
                    ).first()
                    if bad:
                        raise ValueError(f"Invalid boolean: {table.name}.{col.name}")
            rows = source.execute(row_query(table)).mappings()
            insert = table.insert().values(
                {
                    col.name: bindparam(col.name, type_=JSON(none_as_null=True))
                    for col in table.c
                    if isinstance(col.type, JSON)
                }
            )
            for batch in rows.partitions(500):
                values = []
                for row in batch:
                    item = dict(row)
                    for col in table.c:
                        value = item[col.name]
                        if (
                            isinstance(col.type, DateTime)
                            and value is not None
                            and value.tzinfo is None
                        ):
                            if not assume_naive_utc:
                                raise ValueError(
                                    "Naive SQLite timestamps require an explicit --assume-naive-utc decision."
                                )
                            item[col.name] = value.replace(tzinfo=UTC)
                        if isinstance(col.type, JSON):
                            is_sql_null = item.pop(f"_sql_null_{col.name}")
                            if value is None and not is_sql_null:
                                item[col.name] = JSON.NULL
                    values.append(item)
                target.execute(insert, values)
            before, after = digest(source, table), digest(target, table)
            if before != after:
                raise ValueError(f"Data verification failed: {table.name}")
            report[table.name] = after
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument(
        "--backup", required=True, type=Path, help="New file; never overwritten."
    )
    parser.add_argument("--confirm-database", required=True)
    parser.add_argument("--writers-stopped", action="store_true", required=True)
    parser.add_argument("--assume-naive-utc", action="store_true")
    args = parser.parse_args()
    target = source = None
    try:
        target = configured_engine()
        if target.url.database != args.confirm_database:
            raise ValueError("Target database confirmation does not match.")
        snapshot(args.source, args.backup)
        source = create_engine(
            "sqlite://",
            creator=lambda: sqlite3.connect(
                args.backup.resolve().as_uri() + "?mode=ro", uri=True
            ),
        )
        report = copy_data(
            source,
            target,
            migration_config(load_settings().database_url or ""),
            assume_naive_utc=args.assume_naive_utc,
        )
        print(json.dumps({"database": target.url.database, "tables": report}, indent=2))
    except Exception as exc:  # noqa: BLE001 - CLI boundary must redact data and credentials.
        message = str(exc) if type(exc) is ValueError else type(exc).__name__
        raise SystemExit(
            f"Migration failed; source and backup retained: {message}"
        ) from None
    finally:
        for engine in (source, target):
            if engine is not None:
                engine.dispose()


if __name__ == "__main__":
    main()
