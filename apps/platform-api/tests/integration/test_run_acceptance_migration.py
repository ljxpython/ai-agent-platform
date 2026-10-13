"""Acceptance facts are additive and survive a refused destructive rollback."""

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
def test_acceptance_upgrade_preserves_old_rows_and_receipt_facts(tmp_path, backend):
    url = (
        f"sqlite:///{tmp_path / 'migration.db'}"
        if backend == "sqlite"
        else os.getenv("ACCEPTANCE_TEST_PLATFORM_DATABASE_URL")
    )
    if not url:
        pytest.skip("ACCEPTANCE_TEST_PLATFORM_DATABASE_URL must be disposable")
    app = Path(__file__).resolve().parents[2]
    config = Config(str(app / "alembic.ini"))
    config.set_main_option("script_location", str(app / "migrations"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    scripts = ScriptDirectory.from_config(config)
    head = scripts.get_current_head()
    assert scripts.get_revision("20261009_0007") is not None
    assert scripts.get_revision("20261010_0007") is not None
    command.upgrade(config, "20261007_0006")
    engine = create_engine(url)
    try:
        old = Table("run_requests", MetaData(), autoload_with=engine)
        with engine.begin() as connection:
            connection.execute(
                old.insert().values(
                    id=uuid4().hex if backend == "sqlite" else uuid4(),
                    project_id="fixture-project",
                    thread_id=str(uuid4()),
                    agent_key="fixture-graph",
                    requested_by="fixture-owner",
                    idempotency_key="old-request",
                    request_digest="a" * 64,
                    context_snapshot={"fixture": True},
                    config_snapshot={},
                    context_hash="b" * 64,
                    run_id=str(uuid4()),
                    submission_status="accepted",
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                )
            )
            before = dict(connection.execute(select(old)).mappings().one())
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        current = Table("run_requests", MetaData(), autoload_with=engine)
        added = set(current.c.keys()) - set(old.c.keys())
        assert added == {
            "origin_ref",
            "upstream_idempotency_key",
            "upstream_body",
            "upstream_request_digest",
            "upstream_receipt_scope_id",
            "upstream_receipt_credential_id",
            "upstream_auth_snapshot",
        }
        assert all(
            c["nullable"]
            for c in inspect(engine).get_columns("run_requests")
            if c["name"] in added
        )
        assert {
            "run_completion_origins",
            "run_completion_events",
            "run_completion_receipts",
        }.issubset(inspect(engine).get_table_names())
        with engine.begin() as connection:
            assert dict(connection.execute(select(old)).mappings().one()) == before
            row = connection.execute(select(current)).mappings().one()
            assert all(row[k] is None for k in added)
            connection.execute(
                current.update().values(
                    upstream_idempotency_key="fixture-final-key",
                    upstream_body=b'{"assistant_id":"fixture-graph"}',
                    upstream_request_digest="sha256:" + "c" * 64,
                    upstream_receipt_scope_id="d" * 64,
                    upstream_receipt_credential_id="e" * 64,
                    upstream_auth_snapshot={"subject": "fixture-owner"},
                )
            )
            receipt = dict(connection.execute(select(current)).mappings().one())
        with pytest.raises(
            RuntimeError,
            match="(acceptance facts|completion history) (are|is) retained",
        ):
            command.downgrade(config, "20261007_0006")
        with engine.connect() as connection:
            revisions = set(
                connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalars()
            )
            # SQLite may commit the no-op merge downgrade before the destructive branch refuses.
            assert revisions in ({head}, {"20261009_0007", "20261010_0007"})
            assert dict(connection.execute(select(current)).mappings().one()) == receipt
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                == head
            )
            assert dict(connection.execute(select(current)).mappings().one()) == receipt
    finally:
        engine.dispose()
