import tempfile
import unittest
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from platform_api.core.db.base import Base
from platform_api.core.db.init_db import import_core_models
from sqlalchemy import create_engine, inspect


class PlatformBaselineTest(unittest.TestCase):
    def test_empty_database_upgrade_matches_models_and_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            url = f"sqlite:///{Path(directory) / 'platform.db'}"
            config.set_main_option("sqlalchemy.url", url)
            command.upgrade(config, "head")
            command.upgrade(config, "head")
            import_core_models()
            engine = create_engine(url)
            try:
                with engine.connect() as connection:
                    self.assertEqual(
                        compare_metadata(
                            MigrationContext.configure(connection), Base.metadata
                        ),
                        [],
                    )
                tables = inspect(engine).get_table_names()
                self.assertIn("agents", tables)
                self.assertNotIn("agent_profiles", tables)
                self.assertNotIn("assistant_profiles", tables)
                columns = {
                    column["name"] for column in inspect(engine).get_columns("agents")
                }
                self.assertTrue(
                    {"status", "context", "created_by", "updated_by"}
                    <= columns
                )
                self.assertFalse({"config", "metadata_json", "runtime_base_url"} & columns)
                model_columns = {c["name"] for c in inspect(engine).get_columns("runtime_catalog_models")}
                self.assertFalse({"runtime_id", "model_key", "sync_status", "is_default_runtime", "raw_payload_json"} & model_columns)
                self.assertIn("config_snapshot", {c["name"] for c in inspect(engine).get_columns("run_requests")})
                command.downgrade(config, "base")
                self.assertEqual(inspect(engine).get_table_names(), ["alembic_version"])
                command.upgrade(config, "head")
                self.assertIn("agents", inspect(engine).get_table_names())
            finally:
                engine.dispose()
