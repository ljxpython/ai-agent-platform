"""Real PostgreSQL, scoped only to an explicitly supplied Worktree test database."""

import asyncio
import json
import os
import signal
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest

from runtime_service.db import upgrade
from runtime_service.db.repositories import usage as ledger
from runtime_service.db.repositories.usage_analytics import (
    _connection,
    aggregate_usage,
)
from runtime_service.db.repositories.usage_projection import (
    _replace_day,
    begin_rebuild,
    project_pending,
)
from runtime_service.observability.usage import empty_tokens
from runtime_service.observability.usage_analytics import (
    AggregateQuery,
    RunsQuery,
    dashboard,
    query_aggregate,
    query_runs,
)
from tests.durable.usage_reference import aggregate_usage_raw


@pytest.fixture
def ledger_dsn(monkeypatch):
    dsn = os.getenv("USAGE_TEST_DSN")
    if not dsn:
        pytest.skip("USAGE_TEST_DSN must point to an isolated PostgreSQL database")
    monkeypatch.setenv("DATABASE_URI", dsn)
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "true")
    upgrade(dsn)
    upgrade(dsn)
    return dsn


def _call(*, at, model, total=30, incomplete=False):
    return {
        "model_call_id": str(uuid4()),
        "parent_call_id": None,
        "model_id": model,
        "provider": "openai",
        "model_name": "CANARY_MODEL_PRIVATE",
        "scope": "primary",
        "purpose": "agent",
        "namespace": ["CANARY_PROMPT_PRIVATE"],
        "pricing_snapshot": {"version": str(uuid4()), "api_key": "CANARY_SECRET"},
        "started_at": at,
        "ended_at": None if incomplete else at,
        "outcome": "started" if incomplete else "completed",
        "tokens": empty_tokens()
        if incomplete
        else {
            **empty_tokens(0),
            "input_tokens": total - 10,
            "output_tokens": 10,
            "total_tokens": total,
            "cache_read_tokens": 5,
            "reasoning_tokens": 2,
        },
        "token_details": {"CANARY_PAYLOAD": "private"},
        "quality": "missing" if incomplete else "reported",
        "usage_source": "missing" if incomplete else "usage_metadata",
        "estimated_cost_usd": None if incomplete else "0.002000000000",
        "cost_reason": None,
    }


def test_real_aggregation_call_time_scope_distinct_top_other_and_late_upsert(
    ledger_dsn, monkeypatch
):
    tenant, p1, p2 = "analytics-" + uuid4().hex, str(uuid4()), str(uuid4())
    identity = {
        "tenant_id": tenant,
        "project_id": p1,
        "thread_id": str(uuid4()),
        "run_id": str(uuid4()),
        "graph_id": "agent",
    }
    model1, model2 = str(uuid4()), str(uuid4())
    ledger.begin_collection(identity)
    first = _call(at="2026-10-09T23:00:00Z", model=model1, total=20)
    second = _call(at="2026-10-10T17:00:00Z", model=model2, total=30)
    previous = _call(at="2026-10-08T17:00:00Z", model=model1, total=20)
    for call in (first, second, previous):
        ledger.upsert_call(identity, call)
    ledger.finish_collection(identity, False)
    other_identity = {**identity, "project_id": p2}
    ledger.upsert_call(
        other_identity, _call(at="2026-10-10T17:00:00Z", model=model1, total=40)
    )
    ledger.finish_collection(other_identity, False)
    unrelated = {**identity, "tenant_id": "other-" + tenant, "run_id": str(uuid4())}
    ledger.upsert_call(
        unrelated, _call(at="2026-10-10T17:00:00Z", model=model1, total=9999)
    )
    ledger.finish_collection(unrelated, False)
    base = {
        "actor_id": "actor",
        "tenant_id": tenant,
        "project_ids": [p1],
        "request_id": "test",
        "from": "2026-10-09T16:00:00Z",
        "to": "2026-10-11T16:00:00Z",
    }

    def report(**changes):
        return asyncio.run(
            query_aggregate(
                AggregateQuery.model_validate_json(json.dumps({**base, **changes}))
            )
        )

    result = report(top_n=1)
    assert result["summary"]["tokens"]["total_tokens"] == 50
    assert result["summary"]["recorded_run_count"] == 1
    assert [row["tokens"]["total_tokens"] for row in result["series"]] == [20, 30]
    assert result["previous_window"]["summary"]["tokens"]["total_tokens"] == 20
    assert result["previous_window"]["total_token_change_ratio"] == 1.5
    top, other = result["breakdown"]["items"][0], result["breakdown"]["other"]
    assert top["tokens"]["total_tokens"] + other["tokens"]["total_tokens"] == 50
    assert top["recorded_run_count"] == other["recorded_run_count"] == 1
    assert result["summary"]["cost"]["known_cost_usd"] == "0.004000000000"
    assert "CANARY" not in json.dumps(result)
    assert (
        report(project_ids=[p1, p2], group_by="agent")["summary"]["tokens"][
            "total_tokens"
        ]
        == 90
    )
    assert (
        len(report(project_ids=[p1, p2], group_by="agent")["breakdown"]["items"]) == 2
    )
    assert report(project_ids=[p1, p2])["summary"]["recorded_run_count"] == 2
    assert report(model_id=model1)["summary"]["tokens"]["total_tokens"] == 20
    assert report(model_id=model1)["summary"]["zero_call_manifest_count"] is None
    assert report(model_mapping="unmapped")["summary"]["tokens"]["total_tokens"] == 0
    pending = _call(at="2026-10-10T17:00:00Z", model=model2, incomplete=True)
    ledger.upsert_call(identity, pending)
    assert report()["summary"]["tokens"]["total_tokens"] is None
    assert report()["summary"]["known_tokens"]["total_tokens"] == 50
    completed = {
        **_call(at=pending["started_at"], model=model2, total=30),
        "model_call_id": pending["model_call_id"],
    }
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: ledger.upsert_call(identity, completed), range(2)))
    assert report()["summary"]["tokens"]["total_tokens"] == 80
    assert report()["summary"]["coverage"]["observed_call_count"] == 3
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "false")
    assert (
        report()["availability"] == "available"
        and not report()["collection"]["enabled_now"]
    )
    assert report(project_ids=[str(uuid4())])["availability"] == "disabled"
    with psycopg.connect(ledger_dsn) as conn:
        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT indexname FROM pg_indexes WHERE tablename IN ('runtime_usage_calls','runtime_usage_runs')"
            )
        }
        assert {
            "ix_runtime_usage_calls_project_time",
            "ix_runtime_usage_runs_project_time",
        } <= indexes
        revisions = conn.execute(
            "SELECT version_num FROM runtime_app_alembic_version"
        ).fetchall()
        assert revisions == [("0005_usage_projection",)]
    with (
        _connection() as (conn, _),
        pytest.raises(psycopg.errors.ReadOnlySqlTransaction),
    ):
        conn.execute(
            "INSERT INTO runtime_usage_runs (tenant_id,project_id,thread_id,run_id,graph_id) VALUES ('x','x',%s,%s,'x')",
            (uuid4(), uuid4()),
        )


def test_real_keyset_zero_call_manifest_and_lock_timeout(ledger_dsn):
    tenant, project = "analytics-" + uuid4().hex, str(uuid4())
    base = {
        "actor_id": "actor",
        "tenant_id": tenant,
        "project_ids": [project],
        "request_id": "test",
        "from": "2026-10-01T00:00:00Z",
        "to": "2026-10-02T00:00:00Z",
    }
    identities = [
        {
            "tenant_id": tenant,
            "project_id": project,
            "thread_id": str(uuid4()),
            "run_id": str(uuid4()),
            "graph_id": "agent",
        }
        for _ in range(5)
    ]
    for identity in identities:
        ledger.begin_collection(identity)
        ledger.finish_collection(identity, False)
    with psycopg.connect(ledger_dsn) as conn:
        conn.execute(
            "UPDATE runtime_usage_runs SET collection_started_at='2026-10-01T00:00:00Z' WHERE tenant_id=%s",
            (tenant,),
        )
        conn.execute(
            "UPDATE runtime_usage_runs SET collection_started_at=%s WHERE tenant_id=%s AND run_id=%s",
            (base["to"], tenant, identities[-1]["run_id"]),
        )
    for identity in identities[:3]:
        ledger.upsert_call(identity, _call(at="2026-10-01T12:00:00Z", model=None))
    summary = asyncio.run(
        query_aggregate(AggregateQuery.model_validate_json(json.dumps(base)))
    )
    assert summary["summary"]["zero_call_manifest_count"] == 1
    assert summary["summary"]["recorded_run_count"] == 3
    runs = asyncio.run(
        query_runs(RunsQuery.model_validate_json(json.dumps({**base, "limit": 2})))
    )
    assert len(runs["items"]) == 2 and runs["next_cursor"]
    next_page = asyncio.run(
        query_runs(
            RunsQuery.model_validate_json(
                json.dumps(
                    {
                        **base,
                        "limit": 2,
                        "cursor": runs["next_cursor"],
                        "cutoff": runs["cutoff"],
                    }
                )
            )
        )
    )
    assert len(next_page["items"]) == 1 and next_page["next_cursor"] is None
    assert not {r["run_id"] for r in runs["items"]} & {
        r["run_id"] for r in next_page["items"]
    }
    with psycopg.connect(ledger_dsn) as lock:
        lock.execute("LOCK TABLE runtime_usage_calls IN ACCESS EXCLUSIVE MODE")
        blocked = asyncio.run(
            query_aggregate(AggregateQuery.model_validate_json(json.dumps(base)))
        )
        assert blocked["unavailable_reason"] == "backend_unavailable"


def _drain(dsn):
    for _ in range(100):
        with psycopg.connect(dsn) as conn:
            conn.execute("UPDATE runtime_usage_projection_dirty SET retry_at=now()")
        project_pending(limit=16)
        with psycopg.connect(dsn) as conn:
            pending = conn.execute(
                "SELECT count(*) FROM runtime_usage_projection_dirty"
            ).fetchone()[0]
            building = conn.execute(
                "SELECT building_generation FROM runtime_usage_projection_state"
            ).fetchone()[0]
        if not pending and building is None:
            return
    raise AssertionError("projection did not catch up")


def test_projection_matches_facts_for_time_edges_filters_prices_and_run_sets(
    ledger_dsn,
):
    tenant, projects = "projection-" + uuid4().hex, [str(uuid4()), str(uuid4())]
    identities = [
        dict(
            tenant_id=tenant,
            project_id=project,
            run_id=str(uuid4()),
            thread_id=str(uuid4()),
            graph_id="agent",
        )
        for project in projects
    ]
    models = [str(uuid4()), str(uuid4()), None]
    times = [
        "2026-09-30T23:59:59Z",
        "2026-10-01T00:00:00Z",
        "2026-10-01T15:59:59Z",
        "2026-10-01T16:00:00Z",
        "2026-10-02T03:15:30Z",
        "2026-10-02T16:00:00Z",
    ]
    for i in range(66):
        call = _call(
            at=times[i % len(times)],
            model=models[i % 3],
            total=i + 20,
            incomplete=i == 65,
        )
        call.update(
            purpose="custom" if i % 5 == 0 else "agent",
            scope="subagent" if i % 7 == 0 else "primary",
        )
        ledger.upsert_call(identities[i % 2], call)
    for identity in identities:
        ledger.finish_collection(identity, False)
    base = dict(
        actor_id="test",
        tenant_id=tenant,
        project_ids=projects,
        request_id="test",
        **{"from": "2026-10-01T00:00:00Z", "to": "2026-10-03T00:00:00Z"},
    )
    cases = [
        dict(timezone=zone, group_by=group, top_n=1, rank_by=rank)
        for zone in ("UTC", "Asia/Shanghai")
        for group in ("model", "agent", "project", "purpose", "scope")
        for rank in ("known_total_tokens", "known_cost_usd", "observed_call_count")
    ]
    cases += [
        dict(granularity="hour"),
        dict(**{"from": "2026-10-01T00:10:17Z", "to": "2026-10-02T03:15:30Z"}),
        dict(model_id=models[0]),
        dict(model_mapping="unmapped"),
        dict(purpose="other"),
        dict(scope="subagent"),
        dict(project_ids=[projects[0]], graph_id="agent"),
    ]

    def compare():
        for changes in cases:
            query = AggregateQuery.model_validate_json(json.dumps({**base, **changes}))
            projected = dashboard(query, aggregate_usage(query))
            reference = dashboard(query, aggregate_usage_raw(query))
            projected.pop("as_of")
            reference.pop("as_of")
            assert projected == reference, changes

    compare()
    _drain(ledger_dsn)
    compare()
    with psycopg.connect(ledger_dsn) as conn:
        conn.execute(
            "UPDATE runtime_usage_runs SET degraded=true,collection_ended_at=NULL WHERE tenant_id=%s AND project_id=%s",
            (tenant, projects[0]),
        )
    compare()
    generation = begin_rebuild()
    assert begin_rebuild() == generation
    ledger.upsert_call(
        identities[0], _call(at="2026-10-02T03:15:30Z", model=models[0], total=123)
    )
    compare()
    _drain(ledger_dsn)
    compare()
    with psycopg.connect(ledger_dsn) as conn:
        assert conn.execute(
            "SELECT active_generation FROM runtime_usage_projection_state"
        ).fetchone() == (generation,)
        assert (
            conn.execute(
                "SELECT count(DISTINCT generation) FROM runtime_usage_buckets"
            ).fetchone()[0]
            >= 2
        )


def test_projection_dirty_cas_delete_and_failed_batch_recovery(ledger_dsn):
    from psycopg.rows import dict_row

    tenant, project = "cas-" + uuid4().hex, str(uuid4())
    identity = dict(
        tenant_id=tenant,
        project_id=project,
        run_id=str(uuid4()),
        thread_id=str(uuid4()),
        graph_id="agent",
    )
    call = _call(at="2026-10-02T12:00:00Z", model=None, incomplete=True)
    ledger.upsert_call(identity, call)
    with psycopg.connect(ledger_dsn, row_factory=dict_row) as conn:
        job = conn.execute(
            "SELECT * FROM runtime_usage_projection_dirty WHERE tenant_id=%s", (tenant,)
        ).fetchone()
    ledger.upsert_call(
        identity,
        {
            **_call(at=call["started_at"], model=None, total=77),
            "model_call_id": call["model_call_id"],
        },
    )
    with psycopg.connect(ledger_dsn) as lock:
        with psycopg.connect(ledger_dsn) as ready:
            ready.execute("UPDATE runtime_usage_projection_dirty SET retry_at=now()")
        lock.execute("LOCK TABLE runtime_usage_buckets IN ACCESS EXCLUSIVE MODE")
        project_pending(limit=1)
    with psycopg.connect(ledger_dsn) as conn:
        assert conn.execute(
            "SELECT retry_at>now() FROM runtime_usage_projection_dirty WHERE tenant_id=%s",
            (tenant,),
        ).fetchone()[0]
        conn.execute(
            "UPDATE runtime_usage_projection_dirty SET retry_at=now() WHERE tenant_id=%s",
            (tenant,),
        )
    with psycopg.connect(ledger_dsn, row_factory=dict_row) as conn:
        _replace_day(conn, job)
        assert (
            conn.execute(
                "SELECT max(version) AS version FROM runtime_usage_projection_dirty WHERE tenant_id=%s",
                (tenant,),
            ).fetchone()["version"]
            > job["version"]
        )
    _drain(ledger_dsn)
    ledger.finish_collection(identity, False)
    base = dict(
        actor_id="test",
        tenant_id=tenant,
        project_ids=[project],
        request_id="test",
        timezone="UTC",
        **{"from": "2026-10-02T00:00:00Z", "to": "2026-10-03T00:00:00Z"},
    )
    query = AggregateQuery.model_validate_json(json.dumps(base))
    assert aggregate_usage(query)["summary"]["total_tokens"] == 77
    with psycopg.connect(ledger_dsn) as conn:
        conn.execute("DELETE FROM runtime_usage_calls WHERE tenant_id=%s", (tenant,))
    assert aggregate_usage(query)["summary"]["observed_call_count"] == 0


def test_projection_sparse_high_cardinality_and_read_snapshot(ledger_dsn):
    tenant, project = "sparse-" + uuid4().hex, str(uuid4())
    with psycopg.connect(ledger_dsn) as conn:
        conn.execute(
            "INSERT INTO runtime_usage_runs(tenant_id,project_id,run_id,thread_id,graph_id,collection_ended_at) SELECT %s,%s,md5(i::text)::uuid,md5(i::text)::uuid,'agent-' || i,now() FROM generate_series(0,255) i",
            (tenant, project),
        )
        conn.execute(
            "INSERT INTO runtime_usage_calls(tenant_id,project_id,run_id,thread_id,graph_id,model_call_id,model_id,purpose,scope,outcome,quality,usage_source,input_tokens,output_tokens,total_tokens,started_at,ended_at) SELECT %s,%s,md5(i::text)::uuid,md5(i::text)::uuid,'agent-' || i,md5('call-' || i)::uuid,md5('model-' || i)::uuid,'agent','primary','completed','reported','usage_metadata',1,1,2,'2026-10-01T12:00:00Z','2026-10-01T12:00:00Z' FROM generate_series(0,255) i",
            (tenant, project),
        )
    _drain(ledger_dsn)
    query = AggregateQuery.model_validate_json(
        json.dumps(
            dict(
                actor_id="test",
                tenant_id=tenant,
                project_ids=[project],
                request_id="test",
                **{"from": "2026-10-01T00:00:00Z", "to": "2026-10-03T00:00:00Z"},
            )
        )
    )
    result = aggregate_usage(query)
    assert (
        result["summary"]["recorded_run_count"] == 256
        and result["summary"]["total_tokens"] == 512
    )
    assert len(result["groups"]) == 10 and result["other"]["recorded_run_count"] == 246
    assert (
        result["facets"]["models"]["truncated"]
        and result["facets"]["agents"]["truncated"]
    )
    # A later fact write must neither enter a read snapshot nor disappear after catch-up.
    with _connection() as (snapshot, _):
        before = snapshot.execute(
            "SELECT sum(total_tokens) AS tokens FROM runtime_usage_buckets WHERE tenant_id=%s AND grain=1",
            (tenant,),
        ).fetchone()["tokens"]
        scope = dict(
            tenant_id=tenant,
            project_id=project,
            run_id=str(uuid4()),
            thread_id=str(uuid4()),
            graph_id="late",
        )
        ledger.upsert_call(
            scope, _call(at="2026-10-01T12:00:00Z", model=None, total=11)
        )
        project_pending(limit=1)
        assert (
            snapshot.execute(
                "SELECT sum(total_tokens) AS tokens FROM runtime_usage_buckets WHERE tenant_id=%s AND grain=1",
                (tenant,),
            ).fetchone()["tokens"]
            == before
        )
    _drain(ledger_dsn)
    assert aggregate_usage(query)["summary"]["total_tokens"] == 523


def test_projection_writer_during_snapshot_keeps_dirty_and_catches_up(ledger_dsn):
    from psycopg.rows import dict_row

    identity = dict(
        tenant_id="racing-" + uuid4().hex,
        project_id=str(uuid4()),
        run_id=str(uuid4()),
        thread_id=str(uuid4()),
        graph_id="agent",
    )
    pending = _call(at="2026-10-01T15:59:59Z", model=None, incomplete=True)
    ledger.upsert_call(identity, pending)
    completed = {
        **_call(at=pending["started_at"], model=None, total=77),
        "model_call_id": pending["model_call_id"],
    }
    with psycopg.connect(ledger_dsn, row_factory=dict_row) as conn:
        job = conn.execute(
            "SELECT * FROM runtime_usage_projection_dirty WHERE tenant_id=%s",
            (identity["tenant_id"],),
        ).fetchone()

    class RacingConnection:
        def execute(self, statement, *args):
            if statement.startswith("DELETE FROM runtime_usage_projection_dirty"):
                ledger.upsert_call(identity, completed)
            return conn.execute(statement, *args)

    with psycopg.connect(ledger_dsn, row_factory=dict_row) as conn:
        with conn.transaction():
            _replace_day(RacingConnection(), job)
        assert (
            conn.execute(
                "SELECT max(version) AS version FROM runtime_usage_projection_dirty WHERE tenant_id=%s",
                (identity["tenant_id"],),
            ).fetchone()["version"]
            > job["version"]
        )
    _drain(ledger_dsn)
    ledger.finish_collection(identity, False)
    for zone in ("UTC", "Asia/Shanghai"):
        query = AggregateQuery.model_validate_json(
            json.dumps(
                dict(
                    actor_id="test",
                    tenant_id=identity["tenant_id"],
                    project_ids=[identity["project_id"]],
                    request_id="test",
                    timezone=zone,
                    **{"from": "2026-10-01T00:00:00Z", "to": "2026-10-03T00:00:00Z"},
                )
            )
        )
        assert aggregate_usage(query)["summary"]["total_tokens"] == 77


def test_query_pool_rolls_back_and_readonly_transaction_does_not_leak(ledger_dsn):
    identity = dict(
        tenant_id="pool-" + uuid4().hex,
        project_id=str(uuid4()),
        run_id=str(uuid4()),
        thread_id=str(uuid4()),
        graph_id="agent",
    )
    with pytest.raises(RuntimeError), _connection() as (conn, _):
        conn.execute("SELECT 1")
        raise RuntimeError("rollback fixture")
    with _connection() as (conn, _):
        assert (
            conn.execute(
                "SELECT count(*) AS count FROM runtime_usage_runs WHERE tenant_id=%s",
                (identity["tenant_id"],),
            ).fetchone()["count"]
            == 0
        )
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction), conn.transaction():
            ledger._begin(conn, identity)
    ledger.begin_collection(identity)
    ledger.upsert_call(identity, _call(at="2026-10-01T12:00:00Z", model=None))
    ledger.finish_collection(identity, False)
    assert ledger.read_budget(identity)["used_tokens"] == 30


def test_projection_late_commit_below_marker_watermark_is_not_lost(ledger_dsn):
    from psycopg.rows import dict_row

    identity = dict(
        tenant_id="late-commit-" + uuid4().hex,
        project_id=str(uuid4()),
        run_id=str(uuid4()),
        thread_id=str(uuid4()),
        graph_id="agent",
    )
    ledger.begin_collection(identity)
    ledger.upsert_call(identity, _call(at="2026-10-02T12:00:00Z", model=None))
    _drain(ledger_dsn)
    with psycopg.connect(ledger_dsn, row_factory=dict_row) as writer:
        writer.execute(
            "INSERT INTO runtime_usage_calls(tenant_id,project_id,run_id,thread_id,graph_id,model_call_id,purpose,scope,outcome,quality,usage_source,total_tokens,started_at,ended_at) "
            "VALUES (%(tenant_id)s,%(project_id)s,%(run_id)s,%(thread_id)s,%(graph_id)s,%(call_id)s,'agent','primary','completed','reported','usage_metadata',11,'2026-10-01T12:00:00Z','2026-10-01T12:00:00Z')",
            {**identity, "call_id": uuid4()},
        )
        low = writer.execute(
            "SELECT min(version) AS version FROM runtime_usage_projection_dirty WHERE tenant_id=%s",
            (identity["tenant_id"],),
        ).fetchone()["version"]
        ledger.upsert_call(
            identity, _call(at="2026-10-01T12:00:00Z", model=None, total=17)
        )
        with psycopg.connect(ledger_dsn, row_factory=dict_row) as conn:
            job = conn.execute(
                "SELECT * FROM runtime_usage_projection_dirty WHERE tenant_id=%s ORDER BY version DESC LIMIT 1",
                (identity["tenant_id"],),
            ).fetchone()
            assert low < job["version"]
            conn.commit()

            class LateCommit:
                def execute(self, statement, *args):
                    if statement.startswith(
                        "DELETE FROM runtime_usage_projection_dirty"
                    ):
                        writer.commit()
                    return conn.execute(statement, *args)

            _replace_day(LateCommit(), job)
        with psycopg.connect(ledger_dsn) as check:
            assert (
                check.execute(
                    "SELECT min(version) FROM runtime_usage_projection_dirty WHERE tenant_id=%s",
                    (identity["tenant_id"],),
                ).fetchone()[0]
                == low
            )
    _drain(ledger_dsn)
    with psycopg.connect(ledger_dsn) as conn:
        assert (
            conn.execute(
                "SELECT sum(total_tokens) FROM runtime_usage_buckets WHERE tenant_id=%s AND grain=1 AND bucket='2026-10-01T00:00:00Z'",
                (identity["tenant_id"],),
            ).fetchone()[0]
            == 28
        )


def test_projection_process_crash_rolls_back_and_rebuild_resumes(ledger_dsn):
    identity = dict(
        tenant_id="projection-crash-" + uuid4().hex,
        project_id=str(uuid4()),
        run_id=str(uuid4()),
        thread_id=str(uuid4()),
        graph_id="agent",
    )
    ledger.upsert_call(identity, _call(at="2026-10-01T12:00:00Z", model=None))
    _drain(ledger_dsn)
    generation = begin_rebuild()
    child = """import json,os,signal,sys,psycopg
from psycopg.rows import dict_row
from runtime_service.db.repositories.usage_projection import _replace_day
identity=json.load(sys.stdin)
with psycopg.connect(os.environ['DATABASE_URI'],row_factory=dict_row) as conn:
    job=conn.execute('SELECT * FROM runtime_usage_projection_dirty WHERE tenant_id=%s ORDER BY version DESC LIMIT 1',(identity['tenant_id'],)).fetchone()
    conn.commit()
    class Crash:
        def execute(self,statement,*args):
            result=conn.execute(statement,*args)
            if statement.startswith('DELETE FROM runtime_usage_buckets'):
                os.kill(os.getpid(),signal.SIGKILL)
            return result
    _replace_day(Crash(),job)
"""
    ledger.upsert_call(identity, _call(at="2026-10-01T12:00:00Z", model=None, total=17))
    killed = subprocess.run(
        ["rtk", "proxy", sys.executable, "-c", child],
        input=json.dumps(identity),
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert killed.returncode in {-signal.SIGKILL, 128 + signal.SIGKILL}
    assert begin_rebuild() == generation
    _drain(ledger_dsn)
    with psycopg.connect(ledger_dsn) as conn:
        assert conn.execute(
            "SELECT active_generation FROM runtime_usage_projection_state"
        ).fetchone() == (generation,)
        assert (
            conn.execute(
                "SELECT sum(total_tokens) FROM runtime_usage_buckets WHERE tenant_id=%s AND generation=%s AND grain=1",
                (identity["tenant_id"], generation),
            ).fetchone()[0]
            == 47
        )
