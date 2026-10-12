"""Opt-in capacity evidence in a new, Worktree-owned native PostgreSQL database."""

import argparse
import asyncio
import json
import math
import os
import platform
import statistics
import sys
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import psycopg
from dotenv import dotenv_values
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

from runtime_service.db import upgrade
from runtime_service.db.repositories import usage as ledger
from runtime_service.db.repositories.usage_analytics import (
    aggregate_usage,
    list_usage_runs,
)
from runtime_service.db.repositories.usage_projection import project_pending
from runtime_service.observability.usage import empty_tokens
from runtime_service.observability.usage_analytics import (
    AggregateQuery,
    RunsQuery,
    query_aggregate,
)


def timings(values):
    ordered = sorted(values)
    return {
        "n": len(values),
        "p50_ms": round(statistics.median(values) * 1000, 2),
        "p95_ms": round(ordered[math.ceil(len(values) * 0.95) - 1] * 1000, 2),
        "p99_ms": round(ordered[math.ceil(len(values) * 0.99) - 1] * 1000, 2),
    }


def write_pair(dsn, identity, n, *, at="2026-09-10T00:00:00Z"):
    os.environ["DATABASE_URI"] = dsn

    def lane(index):
        scope = {**identity, "run_id": str(uuid4())}
        ledger.begin_collection(scope)
        samples, errors = [], []
        for _ in range(n):
            call = dict(
                model_call_id=str(uuid4()),
                parent_call_id=None,
                model_id=None,
                scope="primary",
                purpose="agent",
                namespace=[],
                pricing_snapshot=None,
                started_at=at,
                ended_at=at,
                outcome="completed",
                tokens={
                    **empty_tokens(0),
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "total_tokens": 15,
                },
                token_details={},
                quality="reported",
                usage_source="usage_metadata",
                estimated_cost_usd=None,
                cost_reason="unpriced",
            )
            pending = {
                **call,
                "ended_at": None,
                "outcome": "started",
                "tokens": empty_tokens(),
                "quality": "missing",
                "usage_source": "missing",
            }
            for fact in (pending, call):
                started = time.perf_counter()
                try:
                    ledger.upsert_call(scope, fact)
                except Exception as exc:
                    errors.append(type(exc).__name__)
                samples.append(time.perf_counter() - started)
        ledger.finish_collection(scope, False)
        return samples, errors

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lane, range(2)))
    return [v for samples, _ in results for v in samples], [
        e for _, errors in results for e in errors
    ]


def run(output, existing_database=None, calls=1000000):
    root = Path(__file__).resolve().parents[3]
    env = json.loads((root / ".local-stack/environment.json").read_text())
    runtime = dotenv_values(root / ".local-stack/runtime.env")
    original = runtime["DATABASE_URI"]
    parameters = conninfo_to_dict(original)
    if not parameters["dbname"].startswith(env["id"]):
        raise ValueError("Worktree database identity mismatch")
    database = existing_database or env["id"] + "_usage_capacity_" + uuid4().hex[:8]
    if not database.startswith(env["id"] + "_usage_capacity_"):
        raise ValueError("Capacity database must belong to this Worktree")
    with psycopg.connect(
        os.getenv("LOCAL_STACK_PG_ADMIN_DSN", "dbname=postgres"), autocommit=True
    ) as admin:
        if existing_database:
            comment = admin.execute(
                "SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=%s",
                (database,),
            ).fetchone()
            if comment != ("local-stack:" + env["id"],):
                raise ValueError("Capacity database ownership marker mismatch")
        else:
            admin.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(database), sql.Identifier(parameters["user"])
                )
            )
            admin.execute(
                sql.SQL("COMMENT ON DATABASE {} IS {}").format(
                    sql.Identifier(database), sql.Literal("local-stack:" + env["id"])
                )
            )
    parameters["dbname"] = database
    dsn = psycopg.conninfo.make_conninfo(**parameters)
    os.environ["DATABASE_URI"] = dsn
    os.environ["RUNTIME_USAGE_ENABLED"] = "true"
    upgrade()
    report = {
        "database": database,
        "platform": platform.platform(),
        "cpu": platform.processor(),
        "dataset": {"calls": calls, "projects": 50, "runs": 10000, "window_days": 30},
        "errors": [],
        "queries": {},
    }
    if not existing_database:
        with psycopg.connect(dsn) as conn:
            report["postgres"] = conn.execute("SELECT version()").fetchone()[0]
            started = time.perf_counter()
            conn.execute("""INSERT INTO runtime_usage_runs (tenant_id,project_id,run_id,thread_id,graph_id,collection_started_at,collection_ended_at)
        SELECT '__default', md5('project-' || (i % 50)::text)::uuid::text, md5('run-' || i::text)::uuid, md5('thread-' || i::text)::uuid, 'agent-' || (i % 5)::text, '2026-09-01T00:00:00Z'::timestamptz, '2026-10-01T00:00:00Z'::timestamptz FROM generate_series(0,9999) i""")
            conn.execute(
                """INSERT INTO runtime_usage_calls (tenant_id,project_id,run_id,thread_id,graph_id,model_call_id,model_id,scope,purpose,outcome,quality,usage_source,input_tokens,output_tokens,total_tokens,cache_read_tokens,cache_creation_tokens,cache_creation_5m_tokens,cache_creation_1h_tokens,reasoning_tokens,estimated_cost_usd,started_at,ended_at)
        SELECT '__default',md5('project-' || (i %% 50)::text)::uuid::text,md5('run-' || (i %% 10000)::text)::uuid,md5('thread-' || (i %% 10000)::text)::uuid,'agent-' || (i %% 5)::text,md5('call-' || i::text)::uuid,md5('model-' || (i %% 10)::text)::uuid,'primary','agent','completed','reported','usage_metadata',100,20,120,10,0,0,0,2,0.00012,'2026-09-01T00:00:00Z'::timestamptz + floor(i * 2592000.0 / %(calls)s) * interval '1 second','2026-09-01T00:00:00Z'::timestamptz + floor(i * 2592000.0 / %(calls)s) * interval '1 second' FROM generate_series(0,%(calls)s-1) i""",
                {"calls": calls},
            )
            report["seed_seconds"] = round(time.perf_counter() - started, 2)
    with psycopg.connect(dsn, autocommit=True) as conn:
        report["postgres"] = conn.execute("SELECT version()").fetchone()[0]
        conn.execute("ANALYZE runtime_usage_calls")
        conn.execute("ANALYZE runtime_usage_runs")
        dataset = conn.execute(
            "SELECT count(*),min(started_at),max(started_at) FROM runtime_usage_calls WHERE tenant_id='__default'"
        ).fetchone()
        report["dataset"].update(
            calls=dataset[0],
            first_call_at=dataset[1].isoformat(),
            last_call_at=dataset[2].isoformat(),
        )
        expected_tokens = conn.execute(
            "SELECT sum(total_tokens) FROM runtime_usage_calls WHERE tenant_id='__default' AND started_at >= '2026-09-01T00:00:00Z' AND started_at < '2026-10-01T00:00:00Z'"
        ).fetchone()[0]
        report["dataset"]["expected_window_total_tokens"] = int(expected_tokens)
        projects = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT project_id FROM runtime_usage_runs ORDER BY project_id"
            )
        ]
        report["plan"] = conn.execute(
            "EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) SELECT sum(total_tokens) FROM runtime_usage_calls WHERE tenant_id='__default' AND project_id=%s AND started_at >= '2026-09-01T00:00:00Z' AND started_at < '2026-10-01T00:00:00Z'",
            (projects[0],),
        ).fetchone()[0]
    base = {
        "version": 1,
        "actor_id": "capacity",
        "tenant_id": "__default",
        "project_ids": projects,
        "request_id": "capacity",
        "from": "2026-09-01T00:00:00Z",
        "to": "2026-10-01T00:00:00Z",
    }
    started = time.perf_counter()
    pending = True
    while pending:
        project_pending(limit=16)
        with psycopg.connect(dsn) as conn:
            pending = conn.execute(
                "SELECT count(*) FROM runtime_usage_projection_dirty"
            ).fetchone()[0]
        print(json.dumps({"projection_pending": pending}), flush=True)
    with psycopg.connect(dsn) as conn:
        report["projection"] = {
            "build_seconds": round(time.perf_counter() - started, 2),
            "rows": conn.execute(
                "SELECT count(*) FROM runtime_usage_buckets"
            ).fetchone()[0],
            "bytes": conn.execute(
                "SELECT pg_total_relation_size('runtime_usage_buckets')"
            ).fetchone()[0],
        }
    for group in ("model", "project", "agent", "purpose", "scope"):
        query = AggregateQuery.model_validate_json(
            json.dumps({**base, "group_by": group})
        )
        durations = []
        for _ in range(3):
            start = time.perf_counter()
            try:
                result = aggregate_usage(query)
                assert result["summary"]["total_tokens"] == expected_tokens
            except Exception as exc:
                report["errors"].append(
                    {"scenario": group, "error": type(exc).__name__}
                )
            durations.append(time.perf_counter() - start)
        report["queries"][group] = timings(durations)
    identity = {
        "tenant_id": "usage-capacity-writes",
        "project_id": projects[0],
        "run_id": str(uuid4()),
        "thread_id": str(uuid4()),
        "graph_id": "writer",
    }
    ledger.begin_collection(identity)

    def writes(n=50):
        samples = []
        for _ in range(n):
            call = {
                "model_call_id": str(uuid4()),
                "parent_call_id": None,
                "model_id": None,
                "scope": "primary",
                "purpose": "agent",
                "namespace": [],
                "pricing_snapshot": None,
                "started_at": "2026-09-10T00:00:00Z",
                "ended_at": "2026-09-10T00:00:00Z",
                "outcome": "completed",
                "tokens": {
                    **empty_tokens(0),
                    "input_tokens": 10,
                    "output_tokens": 5,
                    "total_tokens": 15,
                },
                "token_details": {},
                "quality": "reported",
                "usage_source": "usage_metadata",
                "estimated_cost_usd": None,
                "cost_reason": "unpriced",
            }
            start = time.perf_counter()
            try:
                ledger.upsert_call(identity, call)
            except Exception as exc:
                report["errors"].append(
                    {"scenario": "writer", "error": type(exc).__name__}
                )
            samples.append(time.perf_counter() - start)
        return samples

    report["writes_idle_single"] = timings(writes())
    with ProcessPoolExecutor(max_workers=1) as pool:
        samples, errors = pool.submit(write_pair, dsn, identity, 50).result()
        report["writes_idle"] = timings(samples)
        report["errors"].extend({"scenario": "writer", "error": e} for e in errors)
    report["writer_concurrency"] = 2
    query = AggregateQuery.model_validate_json(json.dumps(base))

    async def reads():
        durations, availabilities = [], []

        async def one():
            start = time.perf_counter()
            result = await query_aggregate(query)
            durations.append(time.perf_counter() - start)
            availabilities.append(result["availability"])

        for _ in range(3):
            await asyncio.gather(*(one() for _ in range(10)))
        return timings(durations), {
            a: availabilities.count(a) for a in set(availabilities)
        }

    with ProcessPoolExecutor(max_workers=1) as pool:
        pool.submit(write_pair, dsn, identity, 0).result()
        writer = pool.submit(write_pair, dsn, identity, 50)
        report["reads_concurrent"], report["availability_concurrent"] = asyncio.run(
            reads()
        )
        samples, errors = writer.result()
        report["writes_under_reads"] = timings(samples)
        report["errors"].extend({"scenario": "writer", "error": e} for e in errors)
    report["write_p95_change_ratio"] = round(
        report["writes_under_reads"]["p95_ms"] / report["writes_idle"]["p95_ms"] - 1,
        4,
    )
    boundary = {
        **base,
        "from": "2026-07-03T00:00:00Z",
        "project_ids": projects + [str(uuid4()) for _ in range(200 - len(projects))],
    }
    start = time.perf_counter()
    result = asyncio.run(
        query_aggregate(AggregateQuery.model_validate_json(json.dumps(boundary)))
    )
    report["boundary_200_projects_90_days"] = {
        "elapsed_ms": round((time.perf_counter() - start) * 1000, 2),
        "availability": result["availability"],
        "series_count": len(result["series"]),
        "project_count": len(result["scope"]["project_ids"]),
    }
    if result["availability"] == "unavailable":
        report["errors"].append({"scenario": "boundary", "error": "unavailable"})
    run_query = RunsQuery.model_validate_json(
        json.dumps({**base, "project_ids": [projects[0]]})
    )
    samples = []
    for _ in range(5):
        start = time.perf_counter()
        try:
            result = list_usage_runs(run_query)
            assert result["items"]
        except Exception as exc:
            report["errors"].append({"scenario": "runs", "error": type(exc).__name__})
        samples.append(time.perf_counter() - start)
    report["runs"] = timings(samples)
    report["gates"] = {
        "queries_complete": not report["errors"]
        and report["availability_concurrent"] == {"available": 30},
        "concurrent_latency": report["reads_concurrent"]["p95_ms"] <= 1500
        and report["reads_concurrent"]["p99_ms"] <= 3000,
        "write_impact": report["write_p95_change_ratio"] <= 0.2
        and not any(e["scenario"] == "writer" for e in report["errors"]),
        "runs_latency": report["runs"]["p95_ms"] <= 1500,
        "boundary_available": report["boundary_200_projects_90_days"]["availability"]
        == "available",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {key: value for key, value in report.items() if key not in {"plan"}},
            ensure_ascii=False,
        )
    )
    return 0 if all(report["gates"].values()) else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--database", help="Reuse this Worktree's existing capacity dataset"
    )
    parser.add_argument("--calls", type=int, choices=[100000, 1000000], default=1000000)
    args = parser.parse_args()
    sys.exit(run(args.output, args.database, args.calls))
