"""Run against PostgreSQL using session-local temporary tables only."""

import os
import sys
import unittest
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from database import clean_projects


class ProjectCleanupTest(unittest.TestCase):
    @unittest.skipUnless(
        os.getenv("CLEANUP_TEST_DATABASE_URL"), "Explicit PG URL required"
    )
    def test_preview_guards_execute_idempotence_and_rollback(self):
        engine = create_engine(os.environ["CLEANUP_TEST_DATABASE_URL"])
        try:
            with engine.connect() as connection:
                connection.execute(
                    text(
                        "CREATE TEMP TABLE projects (id uuid PRIMARY KEY, name text, "
                        "status text, deleted_at timestamptz, updated_at timestamptz)"
                    )
                )
                keep, other, deleted = [str(uuid4()) for _ in range(3)]
                for id_, status in [
                    (keep, "active"),
                    (other, "active"),
                    (deleted, "deleted"),
                ]:
                    connection.execute(
                        text(
                            "INSERT INTO projects (id, name, status) VALUES (:id, 'test', :status)"
                        ),
                        {"id": id_, "status": status},
                    )
                connection.commit()
                with self.assertRaises(ValueError):
                    clean_projects(connection, "invalid", execute=True)
                for invalid in [str(uuid4()), deleted]:
                    with self.assertRaises(ValueError):
                        clean_projects(connection, invalid, execute=True)
                preview = clean_projects(connection, keep, execute=False)
                self.assertEqual(preview["soft_deleted_count"], 1)
                self.assertEqual(
                    connection.execute(
                        text("SELECT count(*) FROM projects WHERE status = 'active'")
                    ).scalar_one(),
                    2,
                )
                self.assertEqual(
                    clean_projects(connection, keep, execute=True), preview
                )
                self.assertEqual(
                    clean_projects(connection, keep, execute=True)[
                        "soft_deleted_count"
                    ],
                    0,
                )
                self.assertEqual(
                    connection.execute(
                        text(
                            "SELECT count(*) FROM projects WHERE deleted_at IS NOT NULL"
                        )
                    ).scalar_one(),
                    1,
                )
                connection.rollback()
                self.assertEqual(
                    clean_projects(connection, keep, execute=False), preview
                )
        finally:
            engine.dispose()
