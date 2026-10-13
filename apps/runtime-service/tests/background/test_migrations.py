"""Both deployed application branches upgrade without losing receipts."""

import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from runtime_service import db


@pytest.fixture
def migration_database(monkeypatch):
    dsn = os.getenv("BACKGROUND_TEST_DSN")
    if not dsn:
        pytest.skip("BACKGROUND_TEST_DSN must point to an isolated database")
    schema = "background_migration_" + uuid4().hex
    with psycopg.connect(dsn) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    scoped = make_conninfo(dsn, options=f"-c search_path={schema}")
    monkeypatch.setenv("DATABASE_URI", scoped)
    try:
        yield scoped
    finally:
        with psycopg.connect(dsn) as connection:
            connection.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )


@pytest.mark.parametrize(
    "start",
    [
        "base",
        "0002_run_control",
        "0003_background_tasks",
        "0003_token_budget",
        "0004_background_token_budget",
        "0005_usage_projection",
        "head",
    ],
)
def test_merge_upgrades_each_branch_and_preserves_facts(migration_database, start):
    config = Config()
    config.set_main_option(
        "script_location", str(Path(db.__file__).with_name("migrations"))
    )
    engine = create_engine(
        "postgresql+psycopg://",
        creator=lambda: psycopg.connect(migration_database),
        poolclass=NullPool,
    )
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, start)
        before = {}
        if start != "base":
            with db.connect() as connection:
                run_id = uuid4()
                connection.execute(
                    "INSERT INTO runtime_usage_runs(tenant_id,project_id,run_id,thread_id,graph_id) VALUES('tenant','project',%s,%s,'showcase_demo')",
                    (run_id, uuid4()),
                )
                connection.execute(
                    "INSERT INTO runtime_stop_requests(stop_id,tenant_id,project_id,thread_id,actor_scope,idem_hash,auth_facts) VALUES(%s,'tenant','project','thread','owner','key','{}')",
                    (uuid4(),),
                )
                if start in {"0003_token_budget", "head"}:
                    connection.execute(
                        "UPDATE runtime_usage_runs SET token_budget_policy=%s,token_budget_stop_code='token_budget_exhausted'",
                        (Jsonb({"limit": 100000}),),
                    )
                if start in {"0003_background_tasks", "head"}:
                    from runtime_service.background_tasks.repository import reserve_task

                    reserve_task(
                        {
                            "tenant_id": "tenant",
                            "project_id": "project",
                            "owner_id": "owner",
                            "graph_id": "showcase_demo",
                            "thread_id": "thread",
                            "origin_run_id": str(run_id),
                            "checkpoint_ns": "",
                            "tool_call_id": "call",
                        },
                        "binding",
                        "request",
                        "migration-test",
                        60,
                    )
                for table in (
                    "runtime_usage_runs",
                    "runtime_stop_requests",
                    "runtime_background_tasks",
                ):
                    if connection.execute(
                        "SELECT to_regclass(%s) AS name", (table,)
                    ).fetchone()["name"]:
                        before[table] = connection.execute(
                            f"SELECT * FROM {table}"
                        ).fetchall()
        db.upgrade()
        db.upgrade()
        with db.connect() as connection:
            assert (
                connection.execute(
                    "SELECT version_num FROM runtime_app_alembic_version"
                ).fetchone()["version_num"]
                == "0008_sandbox_resource_binding"
            )
            for table in (
                "runtime_usage_calls",
                "runtime_background_tasks",
                "runtime_stop_requests",
            ):
                assert connection.execute(
                    "SELECT to_regclass(%s) AS name", (table,)
                ).fetchone()["name"]
            for table, rows in before.items():
                actual = connection.execute(f"SELECT * FROM {table}").fetchall()
                assert len(actual) == len(rows)
                assert all(
                    {key: new[key] for key in old} == old
                    for old, new in zip(rows, actual, strict=True)
                )
            connection.execute(
                "SELECT token_budget_policy,token_budget_stop_code FROM runtime_usage_runs"
            )
    finally:
        engine.dispose()
