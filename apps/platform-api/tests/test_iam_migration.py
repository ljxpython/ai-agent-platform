import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session

from platform_api.core.db.base import Base
from platform_api.core.db.init_db import import_core_models
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    RunCompletionEventRecord,
    RunCompletionReceiptRecord,
)


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
                    {"status", "context", "created_by", "updated_by"} <= columns
                )
                self.assertFalse(
                    {"config", "metadata_json", "runtime_base_url"} & columns
                )
                model_columns = {
                    c["name"]
                    for c in inspect(engine).get_columns("runtime_catalog_models")
                }
                self.assertFalse(
                    {
                        "runtime_id",
                        "model_key",
                        "sync_status",
                        "is_default_runtime",
                        "raw_payload_json",
                    }
                    & model_columns
                )
                self.assertIn(
                    "config_snapshot",
                    {c["name"] for c in inspect(engine).get_columns("run_requests")},
                )
                self.assertIn("runtime_tool_restrictions", tables)
                self.assertNotIn("project_tool_policies", tables)
                with self.assertRaisesRegex(
                    RuntimeError, "not recoverable|retained|migration history"
                ):
                    command.downgrade(config, "base")
                command.upgrade(config, "head")
                self.assertIn("agents", inspect(engine).get_table_names())
            finally:
                engine.dispose()


@pytest.mark.parametrize("numeric_identifier", [False, True])
def test_completion_merge_preserves_uuid_history_or_refuses_lost_ids(
    tmp_path, numeric_identifier
):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    url = f"sqlite:///{tmp_path / 'completion.db'}"
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "20261009_0007")
    event_id, receipt_id = uuid4(), uuid4()
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            connection.execute(
                RunCompletionEventRecord.__table__.insert().values(
                    event_id=event_id,
                    runtime_id="default",
                    origin_ref="fixture-origin",
                    run_id="fixture-run",
                    project_id="fixture-project",
                    status="success",
                    agent_key="fixture-agent",
                    suppressed=False,
                    detail_expires_at=datetime.now(UTC),
                    dedup_expires_at=datetime.now(UTC),
                    sequence=1,
                    occurred_at=datetime.now(UTC),
                    body_digest="a" * 64,
                    payload={"fixture": True},
                )
            )
            connection.execute(
                RunCompletionReceiptRecord.__table__.insert().values(
                    id=receipt_id, event_id=event_id, actor_user_id="fixture-user"
                )
            )
            if numeric_identifier:
                connection.execute(
                    text("UPDATE run_completion_events SET event_id=123456")
                )
        if numeric_identifier:
            with pytest.raises(RuntimeError, match="contain numeric values"):
                command.upgrade(config, "head")
            with engine.connect() as connection:
                assert (
                    connection.execute(
                        text("SELECT event_id FROM run_completion_events")
                    ).scalar_one()
                    == 123456
                )
        else:
            command.upgrade(config, "head")
            command.upgrade(config, "head")
            with Session(engine) as session:
                event = session.get(RunCompletionEventRecord, event_id)
                receipt = session.get(RunCompletionReceiptRecord, receipt_id)
                assert event.payload == {"fixture": True}
                assert event.run_id == "fixture-run"
                assert receipt.event_id == event_id
                assert receipt.actor_user_id == "fixture-user"
    finally:
        engine.dispose()
