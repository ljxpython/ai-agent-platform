"""Bounded short transactions and scoped SQL aggregation for usage facts."""

from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from runtime_service.db import normalize_dsn

TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cache_read_tokens",
    "cache_creation_tokens",
    "cache_creation_5m_tokens",
    "cache_creation_1h_tokens",
    "reasoning_tokens",
)


@contextmanager
def _connection(*, readonly=False):
    with psycopg.connect(
        normalize_dsn(),
        row_factory=dict_row,
        connect_timeout=1,
        options="-c statement_timeout=750 -c lock_timeout=250 -c timezone=UTC",
    ) as conn:
        if readonly:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        yield conn


def _begin(conn, identity, *, reopen=False):
    suffix = "DO UPDATE SET collection_ended_at=NULL" if reopen else "DO NOTHING"
    conn.execute(
        "INSERT INTO runtime_usage_runs (tenant_id,project_id,run_id,thread_id,graph_id) "
        "VALUES (%(tenant_id)s,%(project_id)s,%(run_id)s,%(thread_id)s,%(graph_id)s) "
        f"ON CONFLICT (tenant_id,project_id,run_id) {suffix}",
        identity,
    )


def begin_collection(identity):
    with _connection() as conn:
        _begin(conn, identity, reopen=True)


def finish_collection(identity, degraded):
    with _connection() as conn:
        conn.execute(
            "UPDATE runtime_usage_runs SET collection_ended_at=now(), degraded=degraded OR %(degraded)s "
            "WHERE tenant_id=%(tenant_id)s AND project_id=%(project_id)s AND run_id=%(run_id)s "
            "AND thread_id=%(thread_id)s AND graph_id=%(graph_id)s",
            {**identity, "degraded": degraded},
        )


def upsert_call(identity, call):
    values = {
        **identity,
        **{k: v for k, v in call.items() if k != "tokens"},
        **call["tokens"],
    }
    values["namespace"] = Jsonb(values["namespace"])
    values["token_details"] = Jsonb(values.get("token_details", {}))
    values["pricing_snapshot"] = (
        Jsonb(values["pricing_snapshot"]) if values["pricing_snapshot"] else None
    )
    columns = list(values)
    updates = [
        k for k in columns if k not in {*identity, "model_call_id", "started_at"}
    ]
    with _connection() as conn:
        _begin(conn, identity)
        conn.execute(
            f"INSERT INTO runtime_usage_calls ({','.join(columns)}) "
            f"VALUES ({','.join('%(' + k + ')s' for k in columns)}) "
            "ON CONFLICT (tenant_id,project_id,run_id,model_call_id) DO UPDATE SET "
            + ",".join(f"{k}=EXCLUDED.{k}" for k in updates)
            + " WHERE runtime_usage_calls.outcome='started' OR "
            "(runtime_usage_calls.quality IN ('missing','partial','invalid') "
            "AND EXCLUDED.quality IN ('reported','derived_from_reported'))",
            values,
        )


def _where(identity, window):
    values = dict(identity)
    conditions = [f"r.{k}=%({k})s" for k in identity]
    if window:
        values.update(created_from=window[0], created_to=window[1])
        conditions.extend(
            [
                "r.collection_started_at >= %(created_from)s",
                "r.collection_started_at < %(created_to)s",
            ]
        )
    return " AND ".join(conditions), values


def _summary(conn, where, values):
    runs = conn.execute(
        f"SELECT count(*) AS recorded_run_count, min(collection_started_at) AS first_recorded_at, "
        f"max(collection_started_at) AS last_recorded_at, bool_or(degraded) AS degraded, "
        f"count(*) FILTER (WHERE collection_ended_at IS NULL) AS open_run_count "
        f"FROM runtime_usage_runs r WHERE {where}",
        values,
    ).fetchone()
    tokens = ",".join(
        f"sum(c.{k}) AS {k}, count(c.{k}) FILTER (WHERE c.outcome <> 'started') AS {k}_count"
        for k in TOKEN_FIELDS
    )
    calls = conn.execute(
        "SELECT count(*) AS observed_call_count, "
        "count(*) FILTER (WHERE c.quality IN ('reported','derived_from_reported')) AS reported_call_count, "
        "count(*) FILTER (WHERE c.quality IN ('missing','invalid','partial')) AS missing_usage_call_count, "
        "count(*) FILTER (WHERE c.outcome='started') AS incomplete_call_count, "
        "count(c.estimated_cost_usd) AS priced_call_count, sum(c.estimated_cost_usd) AS known_cost_usd, "
        + tokens
        + " FROM runtime_usage_calls c JOIN runtime_usage_runs r "
        "USING(tenant_id,project_id,run_id,thread_id,graph_id) WHERE " + where,
        values,
    ).fetchone()
    versions = conn.execute(
        "SELECT DISTINCT c.pricing_snapshot->>'version' AS version FROM runtime_usage_calls c "
        "JOIN runtime_usage_runs r USING(tenant_id,project_id,run_id,thread_id,graph_id) "
        f"WHERE {where} AND c.pricing_snapshot IS NOT NULL ORDER BY version LIMIT 51",
        values,
    ).fetchall()
    return {**runs, **calls, "pricing_versions": [row["version"] for row in versions]}


def read_run_usage(identity, limit, cursor):
    where, values = _where(identity, None)
    with _connection(readonly=True) as conn:
        summary = _summary(conn, where, values)
        page_where = where
        if cursor:
            page_where += (
                " AND (c.started_at,c.model_call_id) > (%(cursor_at)s,%(cursor_id)s)"
            )
            values.update(cursor_at=cursor[0], cursor_id=cursor[1])
        rows = conn.execute(
            "SELECT c.* FROM runtime_usage_calls c JOIN runtime_usage_runs r "
            "USING(tenant_id,project_id,run_id,thread_id,graph_id) "
            f"WHERE {page_where} ORDER BY c.started_at,c.model_call_id LIMIT %(limit)s",
            {**values, "limit": limit + 1},
        ).fetchall()
        return summary, rows


def aggregate_thread_usage(identity, window):
    where, values = _where(identity, window)
    with _connection(readonly=True) as conn:
        return _summary(conn, where, values)
