"""Opt-in integration against the explicitly prepared Worktree read-only fixture."""

import json
import os
from pathlib import Path

import psycopg
import pytest

from platform_api.core.errors import BadRequestError
from platform_api.modules.platform_assistant.contracts import AssistantDatabase
from platform_api.modules.platform_assistant.database import query, schema


@pytest.fixture
def pg_source():
    if os.getenv("ASSISTANT_LOCAL_POSTGRES_TEST") != "1":
        pytest.skip("Set ASSISTANT_LOCAL_POSTGRES_TEST=1 with this Worktree fixture")
    root = Path(__file__).resolve().parents[3]
    state = json.loads((root / ".local-stack/environment.json").read_text())
    assert Path(state["root"]) == root
    data = json.loads((root / ".local-stack/assistant-fixture.json").read_text())
    assert (
        psycopg.conninfo.conninfo_to_dict(data["dsn"])["dbname"]
        == state["databases"]["platform"]
    )
    return AssistantDatabase(
        dsn=data["dsn"],
        project_id=data["project_id"],
        schema_name="assistant_data",
        revision="local-synthetic-v1",
    )


def test_real_schema_join_aggregate_and_row_scope(pg_source):
    assert schema(pg_source)["tables"] == ["agents", "runs"]
    assert {c["table_name"] for c in schema(pg_source, ["runs"])["columns"]} == {"runs"}
    from platform_api.core.errors import ForbiddenError

    with pytest.raises(ForbiddenError):
        schema(pg_source, ["secrets"])
    result = query(
        pg_source,
        "SELECT a.name, count(*) AS total, sum(r.cost) AS cost FROM runs r JOIN agents a ON a.id=r.agent_id GROUP BY a.name",
    )
    assert result["rows"] == [{"name": "Demo", "total": 2, "cost": "4.00"}]
    assert query(pg_source, "SELECT * FROM runs WHERE status='secret'")["rows"] == []
    with pytest.raises(BadRequestError):
        query(pg_source, "SELECT * FROM assistant_fixture.runs")


def test_database_itself_refuses_mutations(pg_source):
    with psycopg.connect(pg_source.dsn, autocommit=True) as conn:
        assert conn.execute("SHOW default_transaction_read_only").fetchone()[0] == "on"
        with pytest.raises(psycopg.Error):
            conn.execute("DELETE FROM assistant_data.runs")
        conn.execute("SET default_transaction_read_only=off")
        with pytest.raises(psycopg.Error):
            conn.execute(
                "INSERT INTO assistant_data.agents VALUES (999,'forbidden','other')"
            )
        with pytest.raises(psycopg.Error):
            conn.execute("SELECT * FROM assistant_fixture.runs")


def test_result_truncation_and_query_timeout(pg_source):
    result = query(
        pg_source,
        "SELECT a.id FROM runs a CROSS JOIN runs b CROSS JOIN runs c CROSS JOIN runs d CROSS JOIN runs e CROSS JOIN runs f CROSS JOIN runs g",
    )
    assert result["truncated"] and result["row_count"] == 100
    # The generated query is valid SELECT, but its exponential join must time out.
    from platform_api.core.errors import ServiceUnavailableError

    with pytest.raises(ServiceUnavailableError):
        query(
            pg_source,
            "SELECT count(*) FROM "
            + " CROSS JOIN ".join("runs r" + str(i) for i in range(40)),
        )
