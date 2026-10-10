"""Real PostgreSQL regression checks for selective Worktree baseline copies."""

import os
import shutil
import sys
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import psycopg
from local_stack_seed import copy_database, seed_environment
from local_stack_worktree import configs, destroy_environment, initialize, record
from psycopg.types.json import Jsonb
from sqlalchemy import create_engine

REPOSITORY = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY / "apps/platform-api/src"))

from platform_api.core.db.base import Base
from platform_api.core.db.init_db import import_core_models
from platform_api.core.security.passwords import hash_password, verify_password
from platform_api.modules.runtime_catalog.application.credentials import (
    decrypt_api_key,
    encrypt_api_key,
)


@unittest.skipUnless(
    os.environ.get("LOCAL_STACK_INTEGRATION") == "1",
    "Requires explicitly enabled local PostgreSQL integration",
)
class WorktreeSeedTest(unittest.TestCase):
    @contextmanager
    def fixture(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            common = base / "common"
            primary, root = base / "primary", base / "worktree"
            entries = []
            try:
                initialize(primary, common, REPOSITORY)
                primary_entry = record(primary, common)
                entries.append((primary, primary_entry))
                source_runtime, source_platform = configs(primary, primary_entry)
                for app, name in (
                    ("platform-api", "platform"),
                    ("runtime-service", "runtime"),
                ):
                    destination = primary / "apps" / app / ".env"
                    destination.parent.mkdir(parents=True)
                    shutil.copy2(primary / f".local-stack/{name}.env", destination)
                initialize(root, common, primary)
                entry = record(root, common)
                entries.append((root, entry))
                runtime, platform = configs(root, entry)
                import_core_models()
                for values in (source_platform, platform):
                    engine = create_engine(values["PLATFORM_API_DATABASE_URL"])
                    try:
                        Base.metadata.create_all(engine)
                    finally:
                        engine.dispose()
                for values in (source_runtime, runtime):
                    with psycopg.connect(values["DATABASE_URI"]) as connection:
                        connection.execute(
                            "CREATE TABLE assistants (assistant_id uuid PRIMARY KEY, graph_id text, context jsonb); "
                            "CREATE TABLE assistant_versions (assistant_id uuid REFERENCES assistants, version integer, config jsonb); "
                            "CREATE TABLE dear_skills (tenant_id text, project_id text, user_id text, slug text, document jsonb); "
                            "CREATE TABLE threads (id uuid PRIMARY KEY, messages jsonb); "
                            "CREATE TABLE runs (id uuid PRIMARY KEY); "
                            "CREATE TABLE crons (id uuid PRIMARY KEY); "
                            "CREATE TABLE dear_memory (document jsonb)"
                        )
                ids = self.populate(source_platform, source_runtime)
                yield (
                    root,
                    common,
                    primary,
                    entry,
                    source_platform,
                    source_runtime,
                    platform,
                    runtime,
                    ids,
                )
            finally:
                for directory, entry in reversed(entries):
                    with psycopg.connect(
                        os.environ.get("LOCAL_STACK_PG_ADMIN_DSN", "dbname=postgres"),
                        autocommit=True,
                    ) as admin:
                        for _ in range(50):
                            if not admin.execute(
                                "SELECT 1 FROM pg_stat_activity WHERE datname = ANY(%s)",
                                (list(entry["databases"].values()),),
                            ).fetchone():
                                break
                            time.sleep(0.1)
                    destroy_environment(directory, common, entry["id"])

    def populate(self, platform: dict, runtime: dict) -> dict:
        ids = {
            key: uuid4()
            for key in (
                "tenant",
                "user",
                "project",
                "model",
                "graph",
                "agent",
                "assistant",
            )
        }
        ciphertext = encrypt_api_key(
            "fixture-model-key",
            master_key=platform["PLATFORM_API_MODEL_CONFIG_MASTER_KEY"],
        )
        engine = create_engine(platform["PLATFORM_API_DATABASE_URL"])
        try:
            with engine.begin() as connection:
                rows = (
                    (
                        "tenants",
                        {
                            "id": ids["tenant"],
                            "name": "Reusable tenant",
                            "slug": "reusable",
                        },
                    ),
                    (
                        "users",
                        {
                            "id": ids["user"],
                            "external_subject": "admin",
                            "username": "admin",
                            "password_hash": hash_password("source-password"),
                            "status": "active",
                            "is_super_admin": True,
                            "platform_roles_json": ["platform_super_admin"],
                            "must_change_password": True,
                            "failed_login_attempts": 4,
                        },
                    ),
                    (
                        "projects",
                        {
                            "id": ids["project"],
                            "tenant_id": ids["tenant"],
                            "name": "Reusable project",
                        },
                    ),
                    (
                        "project_members",
                        {
                            "project_id": ids["project"],
                            "user_id": ids["user"],
                            "role": "admin",
                        },
                    ),
                    (
                        "runtime_catalog_models",
                        {
                            "id": ids["model"],
                            "display_name": "Reusable model",
                            "provider": "openai",
                            "base_url": "https://example.invalid/v1",
                            "protocol": "openai",
                            "model_name": "fixture-model",
                            "api_key_ciphertext": ciphertext,
                        },
                    ),
                    (
                        "runtime_catalog_graphs",
                        {
                            "id": ids["graph"],
                            "runtime_id": platform[
                                "PLATFORM_API_LANGGRAPH_UPSTREAM_URL"
                            ],
                            "graph_key": "reference_agent",
                            "raw_payload_json": {"graph_id": "reference_agent"},
                        },
                    ),
                    (
                        "agents",
                        {
                            "id": ids["agent"],
                            "project_id": ids["project"],
                            "name": "Reusable Agent",
                            "graph_id": "reference_agent",
                            "created_by": ids["user"],
                            "updated_by": ids["user"],
                        },
                    ),
                    (
                        "project_graph_policies",
                        {
                            "project_id": ids["project"],
                            "graph_catalog_id": ids["graph"],
                        },
                    ),
                    (
                        "thread_access",
                        {
                            "thread_id": str(uuid4()),
                            "project_id": str(ids["project"]),
                            "owner_user_id": str(ids["user"]),
                        },
                    ),
                )
                for name, values in rows:
                    connection.execute(Base.metadata.tables[name].insert(), values)
        finally:
            engine.dispose()
        with psycopg.connect(runtime["DATABASE_URI"]) as connection:
            connection.execute(
                "INSERT INTO assistants VALUES (%s, %s, %s)",
                (
                    ids["assistant"],
                    "reference_agent",
                    Jsonb({"model": str(ids["model"])}),
                ),
            )
            connection.execute(
                "INSERT INTO assistant_versions VALUES (%s, 1, %s)",
                (ids["assistant"], Jsonb({"temperature": 0.5})),
            )
            connection.execute(
                "INSERT INTO dear_skills VALUES (%s, %s, %s, 'reusable', %s)",
                (
                    str(ids["tenant"]),
                    str(ids["project"]),
                    str(ids["user"]),
                    Jsonb({"content": "Reusable skill"}),
                ),
            )
            connection.execute(
                "INSERT INTO threads VALUES (%s, %s)",
                (uuid4(), Jsonb(["private conversation"])),
            )
            connection.execute("INSERT INTO crons VALUES (%s)", (uuid4(),))
            connection.execute("INSERT INTO runs VALUES (%s)", (uuid4(),))
        ids["ciphertext"] = ciphertext
        return ids

    def test_seed_preserves_relations_reencrypts_credentials_and_never_overwrites(self):
        with self.fixture() as (
            root,
            common,
            primary,
            _entry,
            source_platform,
            source_runtime,
            platform,
            runtime,
            ids,
        ):
            report = seed_environment(root, common, primary)
            self.assertEqual(report["platform"]["status"], "seeded")
            self.assertEqual(report["runtime"]["status"], "seeded")
            with psycopg.connect(
                platform["PLATFORM_API_DATABASE_URL"].replace(
                    "postgresql+psycopg:", "postgresql:"
                )
            ) as target:
                user = target.execute(
                    "SELECT id, password_hash, must_change_password, failed_login_attempts FROM users WHERE username = 'admin'"
                ).fetchone()
                self.assertEqual(user[0], ids["user"])
                self.assertTrue(verify_password("admin123", user[1]))
                self.assertEqual(user[2:], (False, 0))
                ciphertext = target.execute(
                    "SELECT api_key_ciphertext FROM runtime_catalog_models"
                ).fetchone()[0]
                self.assertNotEqual(ciphertext, ids["ciphertext"])
                self.assertEqual(
                    decrypt_api_key(
                        ciphertext,
                        master_key=platform["PLATFORM_API_MODEL_CONFIG_MASTER_KEY"],
                    ),
                    "fixture-model-key",
                )
                self.assertEqual(
                    target.execute(
                        "SELECT runtime_id FROM runtime_catalog_graphs"
                    ).fetchone()[0],
                    platform["PLATFORM_API_LANGGRAPH_UPSTREAM_URL"],
                )
                self.assertEqual(
                    target.execute(
                        "SELECT project_id, user_id FROM project_members"
                    ).fetchone(),
                    (ids["project"], ids["user"]),
                )
                self.assertEqual(
                    target.execute("SELECT count(*) FROM thread_access").fetchone()[0],
                    0,
                )
                target.execute(
                    "UPDATE runtime_catalog_models SET display_name = 'Worktree edit'"
                )
                target.execute(
                    "UPDATE users SET password_hash = %s",
                    (hash_password("worktree-password"),),
                )
            with psycopg.connect(runtime["DATABASE_URI"]) as target:
                self.assertEqual(
                    target.execute("SELECT assistant_id FROM assistants").fetchone()[0],
                    ids["assistant"],
                )
                self.assertEqual(
                    target.execute("SELECT slug FROM dear_skills").fetchone()[0],
                    "reusable",
                )
                for table in ("threads", "runs", "crons", "dear_memory"):
                    self.assertEqual(
                        target.execute(f"SELECT count(*) FROM {table}").fetchone()[0], 0
                    )
            report = seed_environment(root, common, primary)
            self.assertTrue(
                all(item["status"] == "already-seeded" for item in report.values())
            )
            with psycopg.connect(
                platform["PLATFORM_API_DATABASE_URL"].replace(
                    "postgresql+psycopg:", "postgresql:"
                )
            ) as target:
                self.assertEqual(
                    target.execute(
                        "SELECT display_name FROM runtime_catalog_models"
                    ).fetchone()[0],
                    "Worktree edit",
                )
                self.assertTrue(
                    verify_password(
                        "worktree-password",
                        target.execute("SELECT password_hash FROM users").fetchone()[0],
                    )
                )
            with psycopg.connect(
                source_platform["PLATFORM_API_DATABASE_URL"].replace(
                    "postgresql+psycopg:", "postgresql:"
                )
            ) as source:
                self.assertEqual(
                    source.execute(
                        "SELECT api_key_ciphertext FROM runtime_catalog_models"
                    ).fetchone()[0],
                    ids["ciphertext"],
                )
                self.assertTrue(
                    verify_password(
                        "source-password",
                        source.execute("SELECT password_hash FROM users").fetchone()[0],
                    )
                )
                self.assertEqual(
                    source.execute("SELECT count(*) FROM thread_access").fetchone()[0],
                    1,
                )
            with psycopg.connect(source_runtime["DATABASE_URI"]) as source:
                self.assertEqual(
                    source.execute("SELECT count(*) FROM threads").fetchone()[0], 1
                )

    def test_bad_model_key_rolls_back_the_entire_platform_copy(self):
        with self.fixture() as (
            _root,
            _common,
            _primary,
            entry,
            source_platform,
            _source_runtime,
            platform,
            _runtime,
            _ids,
        ):
            source_platform["PLATFORM_API_MODEL_CONFIG_MASTER_KEY"] = platform[
                "PLATFORM_API_MODEL_CONFIG_MASTER_KEY"
            ]
            with self.assertRaisesRegex(ValueError, "cannot be decrypted"):
                copy_database(
                    source_platform["PLATFORM_API_DATABASE_URL"].replace(
                        "postgresql+psycopg:", "postgresql:"
                    ),
                    platform["PLATFORM_API_DATABASE_URL"].replace(
                        "postgresql+psycopg:", "postgresql:"
                    ),
                    entry,
                    "platform",
                    source_platform,
                    platform,
                )
            with psycopg.connect(
                platform["PLATFORM_API_DATABASE_URL"].replace(
                    "postgresql+psycopg:", "postgresql:"
                )
            ) as target:
                self.assertEqual(
                    target.execute("SELECT count(*) FROM users").fetchone()[0], 0
                )
                self.assertEqual(
                    target.execute(
                        "SELECT to_regclass('public._local_stack_seed')"
                    ).fetchone()[0],
                    None,
                )

    def test_nonempty_target_and_foreign_database_are_rejected(self):
        with self.fixture() as (
            root,
            common,
            primary,
            entry,
            _source_platform,
            source_runtime,
            platform,
            runtime,
            _ids,
        ):
            with psycopg.connect(runtime["DATABASE_URI"]) as target:
                target.execute(
                    "INSERT INTO threads VALUES (%s, %s)",
                    (uuid4(), Jsonb(["keep this history"])),
                )
            with self.assertRaisesRegex(ValueError, "not empty"):
                copy_database(
                    source_runtime["DATABASE_URI"],
                    runtime["DATABASE_URI"],
                    entry,
                    "runtime",
                    source_runtime,
                    runtime,
                )
            result = seed_environment(root, common, primary, if_empty=True)
            self.assertTrue(
                all(
                    item["status"] == "existing-data-retained"
                    for item in result.values()
                )
            )
            with psycopg.connect(
                platform["PLATFORM_API_DATABASE_URL"].replace(
                    "postgresql+psycopg:", "postgresql:"
                )
            ) as target:
                self.assertEqual(
                    target.execute("SELECT count(*) FROM users").fetchone()[0], 0
                )
            with self.assertRaisesRegex(ValueError, "not empty"):
                seed_environment(root, common, primary)
            with self.assertRaisesRegex(ValueError, "not owned"):
                copy_database(
                    source_runtime["DATABASE_URI"],
                    source_runtime["DATABASE_URI"],
                    entry,
                    "runtime",
                    source_runtime,
                    runtime,
                )
            with self.assertRaisesRegex(ValueError, "local server"):
                copy_database(
                    "postgresql://private@remote.invalid/db",
                    runtime["DATABASE_URI"],
                    entry,
                    "runtime",
                    source_runtime,
                    runtime,
                )
            with self.assertRaisesRegex(ValueError, "connection overrides"):
                copy_database(
                    "postgresql://private@127.0.0.1/db?host=remote.invalid",
                    runtime["DATABASE_URI"],
                    entry,
                    "runtime",
                    source_runtime,
                    runtime,
                )

    def test_schema_mismatch_rolls_back_and_can_be_retried(self):
        with self.fixture() as (
            _root,
            _common,
            _primary,
            entry,
            _source_platform,
            source_runtime,
            _platform,
            runtime,
            _ids,
        ):
            with psycopg.connect(runtime["DATABASE_URI"]) as target:
                target.execute("ALTER TABLE dear_skills ADD COLUMN unexpected text")
            with self.assertRaisesRegex(ValueError, "schema differs"):
                copy_database(
                    source_runtime["DATABASE_URI"],
                    runtime["DATABASE_URI"],
                    entry,
                    "runtime",
                    source_runtime,
                    runtime,
                )
            with psycopg.connect(runtime["DATABASE_URI"]) as target:
                self.assertEqual(
                    target.execute("SELECT count(*) FROM assistants").fetchone()[0], 0
                )
                target.execute("ALTER TABLE dear_skills DROP COLUMN unexpected")
            result = copy_database(
                source_runtime["DATABASE_URI"],
                runtime["DATABASE_URI"],
                entry,
                "runtime",
                source_runtime,
                runtime,
            )
            self.assertEqual(result["status"], "seeded")

    def test_partial_copy_retries_without_source_platform_and_adds_local_admin(self):
        with self.fixture() as (
            root,
            common,
            primary,
            _entry,
            source_platform,
            _source_runtime,
            platform,
            runtime,
            ids,
        ):
            with psycopg.connect(
                source_platform["PLATFORM_API_DATABASE_URL"].replace(
                    "postgresql+psycopg:", "postgresql:"
                )
            ) as source:
                source.execute("UPDATE users SET username = 'source-admin'")
            with psycopg.connect(runtime["DATABASE_URI"]) as target:
                target.execute("ALTER TABLE dear_skills ADD COLUMN unexpected text")
            with self.assertRaisesRegex(ValueError, "schema differs"):
                seed_environment(root, common, primary)
            with psycopg.connect(
                platform["PLATFORM_API_DATABASE_URL"].replace(
                    "postgresql+psycopg:", "postgresql:"
                )
            ) as target:
                self.assertEqual(
                    target.execute("SELECT count(*) FROM users").fetchone()[0], 2
                )
                self.assertTrue(
                    verify_password(
                        "admin123",
                        target.execute(
                            "SELECT password_hash FROM users WHERE username = 'admin'"
                        ).fetchone()[0],
                    )
                )
                self.assertEqual(
                    target.execute("SELECT user_id FROM project_members").fetchone()[0],
                    ids["user"],
                )
            with psycopg.connect(runtime["DATABASE_URI"]) as target:
                self.assertEqual(
                    target.execute("SELECT count(*) FROM assistants").fetchone()[0], 0
                )
                target.execute("ALTER TABLE dear_skills DROP COLUMN unexpected")
            (primary / "apps/platform-api/.env").unlink()
            report = seed_environment(root, common, primary)
            self.assertEqual(report["platform"]["status"], "already-seeded")
            self.assertEqual(report["runtime"]["status"], "seeded")
            (primary / "apps/runtime-service/.env").unlink()
            report = seed_environment(root, common, primary)
            self.assertTrue(
                all(item["status"] == "already-seeded" for item in report.values())
            )


if __name__ == "__main__":
    unittest.main()
