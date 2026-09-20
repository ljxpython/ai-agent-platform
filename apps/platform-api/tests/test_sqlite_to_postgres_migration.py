import os
import sqlite3
import sys
import tempfile
import unittest
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from alembic import command
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Integer,
    Numeric,
    String,
    Uuid,
    create_engine,
    func,
    select,
    text,
)
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DataError, DBAPIError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from database import (
    check_database,
    clean_ledgers,
    configured_engine,
    migration_config,
)
from migrate_sqlite_to_postgres import copy_data, digest, snapshot
from platform_api.config import Settings
from platform_api.core.db.base import Base
from platform_api.core.db.init_db import import_core_models


class MigrationSafetyTest(unittest.TestCase):
    def test_backup_includes_wal_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            source, backup = (
                Path(directory) / "source.db",
                Path(directory) / "backup.db",
            )
            with closing(sqlite3.connect(source)) as db:
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("CREATE TABLE example (id INTEGER)")
                db.execute("INSERT INTO example VALUES (1)")
                db.commit()
                snapshot(source, backup)
                with closing(sqlite3.connect(backup)) as copied:
                    self.assertEqual(
                        copied.execute("SELECT id FROM example").fetchall(), [(1,)]
                    )
                with self.assertRaises(FileExistsError):
                    snapshot(source, backup)
                with self.assertRaises(FileExistsError):
                    snapshot(source, source)
                self.assertEqual(backup.stat().st_mode & 0o777, 0o600)

    def test_config_guards_and_percent_encoded_password(self):
        for url, enabled, auto in (
            ("sqlite:///test.db", True, False),
            ("postgresql+psycopg://localhost/postgres", True, False),
            ("postgresql+psycopg://localhost/platform_api", False, False),
            ("postgresql+psycopg://localhost/platform_api", True, True),
        ):
            settings = Settings(
                _env_file=None,
                database_url=url,
                platform_db_enabled=enabled,
                platform_db_auto_create=auto,
            )
            with (
                patch("database.load_settings", return_value=settings),
                self.assertRaises(ValueError),
            ):
                configured_engine()
        url = "postgresql+psycopg://user:a%25b%40c@localhost/platform_api"
        self.assertEqual(migration_config(url).get_main_option("sqlalchemy.url"), url)


@unittest.skipUnless(
    os.environ.get("PLATFORM_MIGRATION_TEST_URL"),
    "Requires dedicated PostgreSQL test database",
)
class PostgreSQLMigrationTest(unittest.TestCase):
    def test_full_copy_rollback_restart_and_cleanup(self):
        url = os.environ["PLATFORM_MIGRATION_TEST_URL"]
        self.assertTrue(
            (make_url(url).database or "").startswith("platform_migration_test_")
        )
        config = migration_config(url)
        target = create_engine(url)
        import_core_models()
        with target.connect() as conn:
            self.assertEqual(
                conn.execute(
                    text(
                        "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name <> 'alembic_version'"
                    )
                ).scalar_one(),
                0,
            )
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        try:
            with tempfile.TemporaryDirectory() as directory:
                source = create_engine(f"sqlite:///{Path(directory) / 'source.db'}")
                Base.metadata.create_all(source)
                values = {}
                for table in Base.metadata.sorted_tables:
                    row = {}
                    for col in table.c:
                        if col.foreign_keys:
                            fk = next(iter(col.foreign_keys)).column
                            value = values[fk.table.name][fk.name]
                        elif isinstance(col.type, Uuid):
                            value = uuid.uuid4()
                        elif isinstance(col.type, Boolean):
                            value = True
                        elif isinstance(col.type, DateTime):
                            value = datetime(2026, 9, 20, 1, 2, 3, tzinfo=UTC)
                        elif isinstance(col.type, JSON):
                            value = {"中文": [True, None, 123]}
                        elif isinstance(col.type, Integer):
                            value = 1
                        elif isinstance(col.type, Numeric):
                            value = 0.5
                        elif isinstance(col.type, String):
                            value = (table.name + "_" + col.name)[: col.type.length]
                        else:
                            self.fail(f"Uncovered column: {table.name}.{col.name}")
                        row[col.name] = value
                    values[table.name] = row
                    with source.begin() as conn:
                        conn.execute(table.insert().values(**row))
                # SQLite accepts oversized values that PostgreSQL rejects, after earlier tables copied.
                with source.begin() as conn:
                    conn.execute(
                        text("UPDATE users SET username=:value"), {"value": "x" * 65}
                    )
                with self.assertRaises(DataError):
                    copy_data(source, target, config, assume_naive_utc=True)
                with target.connect() as conn:
                    self.assertTrue(
                        all(
                            conn.scalar(select(func.count()).select_from(t)) == 0
                            for t in Base.metadata.sorted_tables
                        )
                    )
                with source.begin() as conn:
                    conn.execute(text("UPDATE users SET username='migrated-user'"))
                with self.assertRaisesRegex(ValueError, "Naive"):
                    copy_data(source, target, config, assume_naive_utc=False)
                report = copy_data(source, target, config, assume_naive_utc=True)
                self.assertEqual(len(report), 20)
                self.assertTrue(all(entry["rows"] == 1 for entry in report.values()))
                with self.assertRaisesRegex(ValueError, "empty"):
                    copy_data(source, target, config, assume_naive_utc=True)
                target.dispose()
                with target.begin() as conn:
                    check_database(conn, config)
                    before = {
                        t.name: digest(conn, t) for t in Base.metadata.sorted_tables
                    }
                    self.assertEqual(
                        clean_ledgers(conn, execute=False),
                        {"run_requests": 1, "audit_logs": 1},
                    )
                    protection = conn.begin_nested()
                    conn.execute(
                        text(
                            "CREATE TABLE cleanup_dependency (request_id uuid REFERENCES run_requests(id))"
                        )
                    )
                    conn.execute(
                        text(
                            "INSERT INTO cleanup_dependency SELECT id FROM run_requests"
                        )
                    )
                    with self.assertRaises(DBAPIError), conn.begin_nested():
                        clean_ledgers(conn, execute=True)
                    self.assertEqual(
                        clean_ledgers(conn, execute=False),
                        {"run_requests": 1, "audit_logs": 1},
                    )
                    protection.rollback()
                    self.assertEqual(
                        clean_ledgers(conn, execute=True),
                        {"run_requests": 1, "audit_logs": 1},
                    )
                    for table in Base.metadata.sorted_tables:
                        if table.name not in {"run_requests", "audit_logs"}:
                            self.assertEqual(before[table.name], digest(conn, table))
                source.dispose()
        finally:
            target.dispose()
            command.downgrade(config, "base")


if __name__ == "__main__":
    unittest.main()
