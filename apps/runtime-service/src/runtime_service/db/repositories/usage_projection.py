"""Versioned, retryable projections of the canonical model-call ledger."""

import logging
import time

import psycopg
from psycopg.rows import dict_row

from runtime_service.db import normalize_dsn
from runtime_service.observability.usage import TOKEN_FIELDS

COUNTS = (
    "observed_call_count",
    "reported_call_count",
    "missing_usage_call_count",
    "incomplete_call_count",
    "priced_call_count",
    "ratio_sample_call_count",
    *(field + "_count" for field in TOKEN_FIELDS),
)
SUMS = (*TOKEN_FIELDS, "known_cost_usd", "ratio_input_tokens", "ratio_cache_tokens")
FIELDS = (*COUNTS, *SUMS, "run_ids", "pricing_versions")
PURPOSE = "CASE WHEN c.purpose IN ('agent','summarization','memory_extraction','vision') THEN c.purpose ELSE 'other' END"
AGGREGATES = ",".join(
    [
        "count(*) AS observed_call_count",
        "count(*) FILTER (WHERE c.quality IN ('reported','derived_from_reported')) AS reported_call_count",
        "count(*) FILTER (WHERE c.quality NOT IN ('reported','derived_from_reported')) AS missing_usage_call_count",
        "count(*) FILTER (WHERE c.outcome='started') AS incomplete_call_count",
        "count(c.estimated_cost_usd) AS priced_call_count",
        "count(*) FILTER (WHERE c.input_tokens IS NOT NULL AND c.cache_read_tokens IS NOT NULL AND c.outcome<>'started') AS ratio_sample_call_count",
        *[
            f"count(c.{field}) FILTER (WHERE c.outcome<>'started') AS {field}_count"
            for field in TOKEN_FIELDS
        ],
        *[f"sum(c.{field}) AS {field}" for field in TOKEN_FIELDS],
        "sum(c.estimated_cost_usd) AS known_cost_usd",
        "sum(c.input_tokens) FILTER (WHERE c.input_tokens IS NOT NULL AND c.cache_read_tokens IS NOT NULL AND c.outcome<>'started') AS ratio_input_tokens",
        "sum(c.cache_read_tokens) FILTER (WHERE c.input_tokens IS NOT NULL AND c.cache_read_tokens IS NOT NULL AND c.outcome<>'started') AS ratio_cache_tokens",
        "bit_or(set_bit(repeat('0',%(run_slots)s)::bit varying,r.usage_slot,1)) AS run_ids",
        "COALESCE((array_agg(DISTINCT c.pricing_snapshot->>'version') FILTER (WHERE c.pricing_snapshot->>'version' IS NOT NULL))[1:51],ARRAY[]::text[]) AS pricing_versions",
    ]
)
_LOCK = 746183211
logger = logging.getLogger(__name__)


def _connect():
    return psycopg.connect(
        normalize_dsn(),
        row_factory=dict_row,
        autocommit=True,
        connect_timeout=1,
        options="-c statement_timeout=2500 -c lock_timeout=250 -c timezone=UTC",
    )


def _replace_day(conn, job):
    conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
    values = {**job, "day": job["utc_day"]}
    values["run_slots"] = conn.execute(
        "SELECT COALESCE(max(usage_slot)+1,0) AS count FROM runtime_usage_runs WHERE tenant_id=%(tenant_id)s AND project_id=%(project_id)s",
        values,
    ).fetchone()["count"]
    conn.execute(
        "DELETE FROM runtime_usage_buckets WHERE generation=%(generation)s AND tenant_id=%(tenant_id)s AND project_id=%(project_id)s AND "
        "((grain IN (0,3) AND bucket >= %(day)s AND bucket < %(day)s + interval '1 day') OR "
        "(grain=1 AND bucket=%(day)s) OR (grain=2 AND bucket >= %(day)s - interval '8 hours' AND bucket <= %(day)s + interval '16 hours'))",
        values,
    )
    dimensions = (
        "generation,tenant_id,project_id,grain,bucket,graph_id,model_key,purpose,scope"
    )
    conn.execute(
        f"INSERT INTO runtime_usage_buckets ({dimensions},{','.join(FIELDS)}) "
        f"SELECT %(generation)s,c.tenant_id,c.project_id,b.grain,b.bucket,c.graph_id,COALESCE(c.model_id::text,'unmapped'),{PURPOSE},c.scope,{AGGREGATES} "
        "FROM runtime_usage_calls c JOIN runtime_usage_runs r USING(tenant_id,project_id,run_id,thread_id,graph_id) "
        "CROSS JOIN LATERAL (VALUES "
        "(0,date_trunc('hour',c.started_at)), "
        "(1,date_trunc('day',c.started_at)), "
        "(3,date_bin('8 hours',c.started_at,'1970-01-01T00:00:00Z'::timestamptz)), "
        "(2,date_trunc('day',c.started_at AT TIME ZONE 'Asia/Shanghai') AT TIME ZONE 'Asia/Shanghai')) b(grain,bucket) "
        "WHERE c.tenant_id=%(tenant_id)s AND c.project_id=%(project_id)s "
        "AND c.started_at >= %(day)s - interval '8 hours' AND c.started_at < %(day)s + interval '40 hours' "
        "AND (b.grain=2 OR (c.started_at >= %(day)s AND c.started_at < %(day)s + interval '1 day')) "
        "GROUP BY 1,2,3,4,5,6,7,8,9",
        values,
    )
    conn.execute(
        "DELETE FROM runtime_usage_projection_dirty WHERE generation=%(generation)s AND tenant_id=%(tenant_id)s "
        "AND project_id=%(project_id)s AND utc_day=%(utc_day)s AND version<=%(version)s",
        values,
    )


def _switch_ready(conn):
    with conn.transaction():
        state = conn.execute(
            "SELECT * FROM runtime_usage_projection_state WHERE id=1 FOR UPDATE"
        ).fetchone()
        building = state["building_generation"]
        if (
            building is None
            or not state["seed_complete"]
            or conn.execute(
                "SELECT 1 FROM runtime_usage_projection_dirty WHERE generation=%s LIMIT 1",
                (building,),
            ).fetchone()
        ):
            return
        conn.execute(
            "UPDATE runtime_usage_projection_state SET active_generation=building_generation,building_generation=NULL,switched_at=now() WHERE id=1"
        )


def _seed_project(conn):
    state = conn.execute(
        "SELECT * FROM runtime_usage_projection_state WHERE id=1"
    ).fetchone()
    if state["building_generation"] is None or state["seed_complete"]:
        return
    project = conn.execute(
        "SELECT tenant_id,project_id FROM runtime_usage_runs "
        "WHERE %s::text IS NULL OR (tenant_id,project_id)>(%s,%s) "
        "GROUP BY tenant_id,project_id ORDER BY tenant_id,project_id LIMIT 1",
        (state["seed_tenant"], state["seed_tenant"], state["seed_project"]),
    ).fetchone()
    with conn.transaction():
        if project is None:
            conn.execute(
                "UPDATE runtime_usage_projection_state SET seed_complete=true WHERE id=1"
            )
            return
        conn.execute(
            "INSERT INTO runtime_usage_projection_dirty (generation,tenant_id,project_id,utc_day) "
            "SELECT %s,tenant_id,project_id,date_trunc('day',started_at) FROM runtime_usage_calls "
            "WHERE tenant_id=%s AND project_id=%s GROUP BY 2,3,4",
            (state["building_generation"], project["tenant_id"], project["project_id"]),
        )
    # Commit dirty rows before locking state: writers acquire these locks in reverse order.
    # Repeated seeding only queues a redundant replacement, never double-counts facts.
    conn.execute(
        "UPDATE runtime_usage_projection_state SET seed_tenant=%s,seed_project=%s WHERE id=1",
        (project["tenant_id"], project["project_id"]),
    )


def project_pending(*, limit=8):
    """One globally serialized, bounded batch; fact writers never wait for its scans."""
    with _connect() as conn:
        if not conn.execute(
            "SELECT pg_try_advisory_lock(%s) AS locked", (_LOCK,)
        ).fetchone()["locked"]:
            return 0
        processed, deadline = 0, time.monotonic() + 2
        try:
            _seed_project(conn)
            while processed < limit and time.monotonic() < deadline:
                job = conn.execute(
                    "SELECT d.generation,d.tenant_id,d.project_id,d.utc_day,max(d.version) AS version FROM runtime_usage_projection_dirty d CROSS JOIN runtime_usage_projection_state s "
                    "WHERE s.id=1 GROUP BY d.generation,d.tenant_id,d.project_id,d.utc_day,s.active_generation,s.building_generation HAVING max(d.retry_at)<=now() OR min(d.retry_at)<=now()-interval '5 seconds' "
                    "ORDER BY (d.generation=CASE WHEN %s THEN COALESCE(s.building_generation,s.active_generation) ELSE s.active_generation END) DESC,d.utc_day,d.tenant_id,d.project_id LIMIT 1",
                    (bool(processed % 2),),
                ).fetchone()
                if job is None:
                    break
                try:
                    with conn.transaction():
                        _replace_day(conn, job)
                except (
                    psycopg.errors.QueryCanceled,
                    psycopg.errors.LockNotAvailable,
                    psycopg.errors.SerializationFailure,
                ) as exc:
                    logger.warning("Usage projection retry kind=%s", type(exc).__name__)
                    conn.execute(
                        "UPDATE runtime_usage_projection_dirty SET retry_at=now()+interval '5 seconds' WHERE generation=%(generation)s AND tenant_id=%(tenant_id)s AND project_id=%(project_id)s AND utc_day=%(utc_day)s",
                        job,
                    )
                processed += 1
            _switch_ready(conn)
            return processed
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (_LOCK,))


def begin_rebuild():
    """Register a generation in a short transaction; background seeding is resumable."""
    with _connect() as conn, conn.transaction():
        state = conn.execute(
            "SELECT * FROM runtime_usage_projection_state WHERE id=1 FOR UPDATE"
        ).fetchone()
        if state["building_generation"] is not None:
            return state["building_generation"]
        generation = conn.execute(
            "SELECT nextval('runtime_usage_projection_generation') AS id"
        ).fetchone()["id"]
        conn.execute(
            "UPDATE runtime_usage_projection_state SET building_generation=%s,seed_complete=false,seed_tenant=NULL,seed_project=NULL WHERE id=1",
            (generation,),
        )
        return generation
