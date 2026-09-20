import os
import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from cleanup_history import (
    HISTORY,
    clean,
    history_counts,
    local_url,
    validate_test_name,
)


class HistoryCleanupTest(unittest.TestCase):
    def test_target_guards(self):
        for name in (
            "postgres",
            "platform_api",
            "platform_migration_test_*",
            'x";DROP DATABASE postgres',
        ):
            with self.assertRaises(ValueError):
                validate_test_name(name, {"platform_api"})
        with self.assertRaises(ValueError):
            validate_test_name(
                "platform_migration_test_live", {"platform_migration_test_live"}
            )
        validate_test_name("platform_migration_test_old_20260920", {"platform_api"})
        with self.assertRaises(ValueError):
            local_url("postgresql://remote.example/db")

    @unittest.skipUnless(
        os.getenv("CLEANUP_TEST_DATABASE_URL"), "Explicit PG URL required"
    )
    def test_history_cleanup_preserves_active_tokens_and_rolls_back(self):
        engine = create_engine(os.environ["CLEANUP_TEST_DATABASE_URL"])
        try:
            with engine.connect() as c:
                for table in (*HISTORY, "crons", "run_requests", "audit_logs"):
                    c.execute(
                        text(
                            f'CREATE TEMP TABLE "{table}" (status text, enabled boolean)'
                        )
                    )
                c.execute(
                    text(
                        "CREATE TEMP TABLE refresh_tokens (expires_at timestamptz, revoked_at timestamptz)"
                    )
                )
                c.execute(
                    text(
                        "INSERT INTO refresh_tokens VALUES (now()+interval '1 day', NULL), (now()-interval '1 day', NULL), (now()+interval '1 day', now())"
                    )
                )
                c.execute(text("INSERT INTO runs (status) VALUES ('running')"))
                c.commit()
                with self.assertRaises(ValueError):
                    history_counts(c, runtime=True)
                c.execute(text("UPDATE runs SET status='interrupted'"))
                c.execute(text("INSERT INTO checkpoints (status) VALUES ('history')"))
                c.execute(text("INSERT INTO audit_logs (status) VALUES ('history')"))
                c.commit()
                self.assertEqual(
                    history_counts(c, runtime=False)["expired_or_revoked_tokens"], 2
                )
                clean(c, runtime=False)
                clean(c, runtime=True)
                self.assertEqual(
                    c.execute(text("SELECT count(*) FROM refresh_tokens")).scalar_one(),
                    1,
                )
                self.assertTrue(
                    all(
                        value == 0 for value in history_counts(c, runtime=True).values()
                    )
                )
                self.assertTrue(
                    all(
                        value == 0
                        for value in history_counts(c, runtime=False).values()
                    )
                )
                c.rollback()
                self.assertEqual(
                    history_counts(c, runtime=False)["expired_or_revoked_tokens"], 2
                )
                self.assertEqual(history_counts(c, runtime=True)["checkpoints"], 1)
        finally:
            engine.dispose()
