"""Acceptance facts are additive and survive a refused destructive rollback."""

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.engine import make_url

from platform_api.core.db import Base, import_core_models
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    RunCompletionEventRecord,
    RunCompletionReceiptRecord,
)


@pytest.fixture
def migration_url(tmp_path, backend):
    if backend == "sqlite":
        yield f"sqlite:///{tmp_path / 'migration.db'}"
        return
    value = os.getenv("ACCEPTANCE_TEST_PLATFORM_DATABASE_URL")
    if not value:
        pytest.skip("ACCEPTANCE_TEST_PLATFORM_DATABASE_URL must be disposable")
    schema = "acceptance_migration_" + uuid4().hex
    engine = create_engine(value)
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    try:
        yield (
            make_url(value)
            .update_query_dict({"options": f"-csearch_path={schema}"})
            .render_as_string(hide_password=False)
        )
    finally:
        with engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        engine.dispose()


@pytest.mark.parametrize("backend", ["sqlite", "postgres"])
@pytest.mark.parametrize(
    "start",
    ["20261007_0006", "20261009_0007", "20261010_0007", "20261011_0008", "head"],
)
def test_acceptance_upgrade_preserves_old_rows_and_receipt_facts(
    migration_url, backend, start
):
    url = migration_url
    app = Path(__file__).resolve().parents[2]
    config = Config(str(app / "alembic.ini"))
    config.set_main_option("script_location", str(app / "migrations"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, start)
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
        acceptance_columns = {
            "upstream_idempotency_key",
            "upstream_body",
            "upstream_request_digest",
            "upstream_receipt_scope_id",
            "upstream_receipt_credential_id",
            "upstream_auth_snapshot",
        }
        assert added == (acceptance_columns | {"origin_ref"}) - set(old.c.keys())
        assert {
            "run_completion_origins",
            "run_completion_events",
            "run_completion_receipts",
        } <= set(inspect(engine).get_table_names())
        assert all(
            c["nullable"]
            for c in inspect(engine).get_columns("run_requests")
            if c["name"] in acceptance_columns
        )
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
            RuntimeError, match="acceptance facts are retained|migration history"
        ):
            command.downgrade(config, "20261007_0006")
        with engine.connect() as connection:
            assert (
                connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                == "20261011_0009"
            )
            assert dict(connection.execute(select(current)).mappings().one()) == receipt
    finally:
        engine.dispose()


@pytest.mark.parametrize("corrupt", [False, True])
def test_sqlite_completion_uuid_rebuild_preserves_history_and_metadata(
    tmp_path, corrupt
):
    app = Path(__file__).resolve().parents[2]
    url = f"sqlite:///{tmp_path / 'completion-history.db'}"
    config = Config(str(app / "alembic.ini"))
    config.set_main_option("script_location", str(app / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "20261011_0008")
    engine = create_engine(url)
    event_id, receipt_id = uuid4(), uuid4()
    now = datetime.now(UTC)
    try:
        with engine.begin() as connection:
            connection.execute(
                RunCompletionEventRecord.__table__.insert().values(
                    event_id=event_id,
                    runtime_id="default",
                    origin_ref="source",
                    run_id="original-run",
                    project_id="project",
                    status="success",
                    agent_key="showcase_demo",
                    suppressed=False,
                    detail_expires_at=now,
                    dedup_expires_at=now,
                    sequence=1,
                    occurred_at=now,
                    body_digest="a" * 64,
                    payload={"retained": "原完成记录"},
                    accepted_at=now,
                )
            )
            connection.execute(
                RunCompletionReceiptRecord.__table__.insert().values(
                    id=receipt_id,
                    event_id=event_id,
                    actor_user_id="owner",
                    read_at=now,
                )
            )
            if corrupt:
                connection.exec_driver_sql(
                    "UPDATE run_completion_events SET event_id=42"
                )
            before = {
                table: connection.exec_driver_sql(f"SELECT * FROM {table}").fetchall()
                for table in ("run_completion_events", "run_completion_receipts")
            }
        if corrupt:
            with pytest.raises(RuntimeError, match="identity recovery"):
                command.upgrade(config, "head")
            with engine.connect() as connection:
                assert (
                    connection.exec_driver_sql(
                        "SELECT version_num FROM alembic_version"
                    ).scalar_one()
                    == "20261011_0008"
                )
                assert {
                    table: connection.exec_driver_sql(
                        f"SELECT * FROM {table}"
                    ).fetchall()
                    for table in before
                } == before
            return
        command.upgrade(config, "head")
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert {
                table: connection.exec_driver_sql(f"SELECT * FROM {table}").fetchall()
                for table in before
            } == before
            assert (
                connection.execute(
                    select(RunCompletionEventRecord.event_id)
                ).scalar_one()
                == event_id
            )
            assert (
                connection.execute(select(RunCompletionReceiptRecord.id)).scalar_one()
                == receipt_id
            )
            import_core_models()
            assert (
                compare_metadata(MigrationContext.configure(connection), Base.metadata)
                == []
            )
    finally:
        engine.dispose()
