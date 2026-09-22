"""Exercise the new migration without touching the configured application tables."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text


def migration():
    path = Path(__file__).resolve().parents[1] / "migrations/versions/20260922_0003_thread_access.py"
    spec = importlib.util.spec_from_file_location("thread_acl_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ThreadAclMigrationTest(unittest.TestCase):
    def round_trip(self, connection):
        change = migration()
        with Operations.context(MigrationContext.configure(connection)):
            change.upgrade()
            self.assertIn("thread_access", inspect(connection).get_table_names())
            self.assertEqual({column["name"] for column in inspect(connection).get_columns("thread_access")},
                             {"thread_id", "project_id", "owner_user_id", "visibility", "shared_actions", "project_actions", "takeovers"})
            connection.execute(text("INSERT INTO thread_access VALUES ('thread', 'project', 'owner', 'private', '{}', '[]', '{}')"))
            self.assertEqual(connection.execute(text("SELECT owner_user_id FROM thread_access")).scalar_one(), "owner")
            change.downgrade()
            self.assertNotIn("thread_access", inspect(connection).get_table_names())
            change.upgrade()
            self.assertEqual(connection.execute(text("SELECT count(*) FROM thread_access")).scalar_one(), 0)
            change.downgrade()

    def test_sqlite_upgrade_and_downgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = create_engine(f"sqlite:///{Path(directory) / 'migration.db'}")
            try:
                with engine.begin() as connection:
                    self.round_trip(connection)
            finally:
                engine.dispose()

    @unittest.skipUnless(os.environ.get("RUN_LOCAL_GOVERNANCE_CONTRACT") == "1", "Explicit local PostgreSQL contract opt-in")
    def test_postgres_upgrade_and_downgrade_in_rolled_back_schema(self):
        from platform_api.config import Settings
        url = Settings().database_url
        self.assertTrue(url and url.startswith("postgresql"), "Local PostgreSQL configuration required")
        engine = create_engine(url)
        schema = "governance_test_" + uuid4().hex
        try:
            with engine.connect() as connection:
                transaction = connection.begin()
                try:
                    connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                    connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                    self.round_trip(connection)
                finally:
                    transaction.rollback()
                self.assertFalse(connection.execute(text("SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name=:schema)"), {"schema": schema}).scalar())
        finally:
            engine.dispose()
