"""Parameterized analytics in one bounded, read-only database snapshot."""

import threading
import time
from contextlib import contextmanager
from datetime import timedelta
from zoneinfo import ZoneInfo

import psycopg

from runtime_service.db.repositories.usage_projection import (
    AGGREGATES,
    COUNTS,
    FIELDS,
    PURPOSE,
    SUMS,
)
from runtime_service.db.usage_connections import query_pool
from runtime_service.observability.usage import TOKEN_FIELDS

_read_slots = threading.BoundedSemaphore(1)
_GROUPS = {
    "project": "c.project_id",
    "model": "COALESCE(c.model_id::text,'unmapped')",
    "agent": "c.project_id || '/' || c.graph_id",
    "purpose": "CASE WHEN c.purpose IN ('agent','summarization','memory_extraction','vision') THEN c.purpose ELSE 'other' END",
    "scope": "c.scope",
}
_RANKS = {
    "known_total_tokens": "total_tokens",
    "known_cost_usd": "known_cost_usd",
    "observed_call_count": "observed_call_count",
}
_JOIN = "FROM runtime_usage_calls c JOIN runtime_usage_runs r USING (tenant_id,project_id,run_id,thread_id,graph_id)"
# A fixed 16-byte UUID suffix preserves the pair without slow text-collation sorts.
_RUN_KEY = "convert_to(c.project_id,'UTF8') || uuid_send(c.run_id)"
_METRICS = ",".join(
    [
        "count(*) AS observed_call_count",
        "count(*) FILTER (WHERE c.quality IN ('reported','derived_from_reported')) AS reported_call_count",
        "count(*) FILTER (WHERE c.quality NOT IN ('reported','derived_from_reported')) AS missing_usage_call_count",
        "count(*) FILTER (WHERE c.outcome='started') AS incomplete_call_count",
        "count(c.estimated_cost_usd) AS priced_call_count",
        "sum(c.estimated_cost_usd) AS known_cost_usd",
        f"count(DISTINCT {_RUN_KEY}) AS recorded_run_count",
        f"count(DISTINCT {_RUN_KEY}) FILTER (WHERE r.collection_ended_at IS NULL) AS open_run_count",
        "bool_or(r.degraded) AS degraded",
        "(array_agg(DISTINCT c.pricing_snapshot->>'version') FILTER (WHERE c.pricing_snapshot->>'version' IS NOT NULL))[1:51] AS pricing_versions",
        "count(*) FILTER (WHERE c.input_tokens IS NOT NULL AND c.cache_read_tokens IS NOT NULL AND c.outcome<>'started') AS ratio_sample_call_count",
        "sum(c.input_tokens) FILTER (WHERE c.input_tokens IS NOT NULL AND c.cache_read_tokens IS NOT NULL AND c.outcome<>'started') AS ratio_input_tokens",
        "sum(c.cache_read_tokens) FILTER (WHERE c.input_tokens IS NOT NULL AND c.cache_read_tokens IS NOT NULL AND c.outcome<>'started') AS ratio_cache_tokens",
        *[
            f"sum(c.{k}) AS {k}, count(c.{k}) FILTER (WHERE c.outcome<>'started') AS {k}_count"
            for k in TOKEN_FIELDS
        ],
    ]
)


@contextmanager
def _connection(deadline=None):
    deadline = deadline or time.monotonic() + 4.5
    if deadline <= time.monotonic():
        raise psycopg.errors.QueryCanceled("Usage query deadline exceeded")
    if not _read_slots.acquire(timeout=0.1):
        raise psycopg.OperationalError("Usage query capacity exhausted")
    try:
        with (
            query_pool().connection(
                timeout=min(0.1, max(0.001, deadline - time.monotonic()))
            ) as conn,
            conn.transaction(),
        ):
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            yield conn, deadline
    finally:
        _read_slots.release()


def _execute(conn, deadline, sql, values):
    remaining = int((deadline - time.monotonic()) * 1000)
    if remaining <= 0:
        raise psycopg.errors.QueryCanceled("Usage query deadline exceeded")
    conn.execute(
        "SELECT set_config('statement_timeout', %s, true)", (str(min(1000, remaining)),)
    )
    rows = conn.execute(sql, values).fetchall()
    for row in rows:
        if "pricing_versions" in row:
            row["pricing_versions"] = row["pricing_versions"] or []
    return rows


def _where(query, *, previous=False):
    values = {
        "tenant": query.tenant_id,
        "projects": [str(p) for p in query.project_ids],
        "start": query.start - (query.end - query.start) if previous else query.start,
        "end": query.end,
    }
    conditions = [
        "c.tenant_id=%(tenant)s",
        "c.project_id=ANY(%(projects)s)",
        "c.started_at >= %(start)s",
        "c.started_at < %(end)s",
    ]
    for key in ("model_id", "graph_id", "scope"):
        value = getattr(query, key)
        if value is not None:
            values[key] = str(value)
            conditions.append(f"c.{key}=%({key})s")
    if query.model_mapping:
        conditions.append("c.model_id IS NULL")
    if query.purpose:
        values["purpose"] = query.purpose
        conditions.append(_GROUPS["purpose"] + "=%(purpose)s")
    return " AND ".join(conditions), values


def _segments(start, end, query, period):
    """Use complete local days, then complete hours, with at most two raw edges."""
    pieces = []
    cursor = start
    zone = ZoneInfo(query.timezone)
    while cursor < end:
        local = cursor.astimezone(zone)
        if (
            query.granularity == "day"
            and local.time() == local.time().min
            and cursor + timedelta(days=1) <= end
        ):
            grain, stop = (
                (1 if query.timezone == "UTC" else 2),
                cursor + timedelta(days=1),
            )
        elif (
            query.granularity == "day"
            and cursor.hour % 8
            == cursor.minute
            == cursor.second
            == cursor.microsecond
            == 0
            and cursor + timedelta(hours=8) <= end
        ):
            grain, stop = 3, cursor + timedelta(hours=8)
        elif (
            cursor.minute == cursor.second == cursor.microsecond == 0
            and cursor + timedelta(hours=1) <= end
        ):
            grain, stop = 0, cursor + timedelta(hours=1)
        else:
            grain, stop = (
                -1,
                min(
                    end,
                    cursor.replace(minute=0, second=0, microsecond=0)
                    + timedelta(hours=1),
                ),
            )
        if pieces and pieces[-1][0] == grain:
            pieces[-1] = (grain, pieces[-1][1], stop, period)
        else:
            pieces.append((grain, cursor, stop, period))
        cursor = stop
    return pieces


def _projection_sources(query, pieces, dirty, values):
    projected, raw = [], []
    filters = []
    for key in ("graph_id", "purpose", "scope"):
        if getattr(query, key):
            filters.append(f"b.{key}=%({key})s")
            values[key] = getattr(query, key)
    if query.model_id or query.model_mapping:
        filters.append("b.model_key=%(model_key)s")
        values["model_key"] = str(query.model_id) if query.model_id else "unmapped"
    for index, (grain, start, end, period) in enumerate(pieces):
        values.update({f"start{index}": start, f"end{index}": end})
        if grain == -1:
            raw.append((None, start, end, period))
            continue
        exclusions = []
        for job in dirty:
            day = job["utc_day"]
            lo = day - timedelta(hours=8) if grain == 2 else day
            hi = day + timedelta(hours=40) if grain == 2 else day + timedelta(days=1)
            lo, hi = max(start, lo), min(end, hi)
            if lo >= hi:
                continue
            number = len(raw)
            values.update(
                {
                    f"dirty_project{number}": job["project_id"],
                    f"dirty_start{number}": lo,
                    f"dirty_end{number}": hi,
                }
            )
            exclusions.append(
                f"(b.project_id=%(dirty_project{number})s AND b.bucket >= %(dirty_start{number})s AND b.bucket < %(dirty_end{number})s)"
            )
            raw.append((job["project_id"], lo, hi, period))
        condition = f"b.grain={grain} AND b.bucket >= %(start{index})s AND b.bucket < %(end{index})s"
        if exclusions:
            condition += " AND NOT (" + " OR ".join(exclusions) + ")"
        projected.append(
            f"SELECT '{period}' AS period,b.bucket,b.project_id,b.graph_id,b.model_key,b.purpose,b.scope,{','.join('b.' + f for f in FIELDS)} FROM runtime_usage_buckets b WHERE b.generation=%(generation)s AND b.tenant_id=%(tenant)s AND b.project_id=ANY(%(projects)s) AND "
            + condition
            + (" AND " + " AND ".join(filters) if filters else "")
        )
    ranges = []
    for project, lo, hi, period in sorted(raw, key=lambda r: (r[3], r[0] or "", r[1])):
        if (
            ranges
            and ranges[-1][0] == project
            and ranges[-1][3] == period
            and lo <= ranges[-1][2]
        ):
            ranges[-1] = (project, ranges[-1][1], max(hi, ranges[-1][2]), period)
        else:
            ranges.append((project, lo, hi, period))
    sources = []
    for number, (project, lo, hi, period) in enumerate(ranges):
        where, params = _where(query)
        params.update(
            start=lo, end=hi, projects=[project] if project else values["projects"]
        )
        for key, value in params.items():
            values[f"raw{number}_{key}"] = value
            where = where.replace(f"%({key})s", f"%(raw{number}_{key})s")
        sources.append(
            f"SELECT '{period}' AS period,c.*,r.usage_slot {_JOIN} WHERE {where}"
        )
    return projected, sources


def _projected_metrics(conn, deadline, query, projected, sources, values):
    bucket = "date_trunc(%(granularity)s,bucket AT TIME ZONE %(timezone)s) AT TIME ZONE %(timezone)s"
    group = {
        "project": "project_id",
        "model": "model_key",
        "agent": "project_id || '/' || graph_id",
        "purpose": "purpose",
        "scope": "scope",
    }[query.group_by]
    values.update(
        granularity=query.granularity, timezone=query.timezone, top=query.top_n
    )
    raw_cte = ""
    if sources:
        raw_cte = (
            "raw_calls AS MATERIALIZED (SELECT * FROM ("
            + " UNION ALL ".join(sources)
            + ") bounded LIMIT 5001), raw_sized AS (SELECT *,max(usage_slot+1) OVER (PARTITION BY project_id) AS bitmap_size FROM raw_calls),"
        )
        raw_bucket = "date_trunc(%(granularity)s,c.started_at AT TIME ZONE %(timezone)s) AT TIME ZONE %(timezone)s"
        aggregates = AGGREGATES.replace(
            "repeat('0',%(run_slots)s)", "repeat('0',c.bitmap_size)"
        ).replace("r.usage_slot", "c.usage_slot")
        projected.append(
            f"SELECT c.period,{raw_bucket} AS bucket,c.project_id,c.graph_id,COALESCE(c.model_id::text,'unmapped') AS model_key,{PURPOSE} AS purpose,c.scope,{aggregates} FROM raw_sized c GROUP BY 1,2,3,4,5,6,7"
        )
    sums = ",".join(f"sum({field}) AS {field}" for field in (*COUNTS, *SUMS))
    rows = _execute(
        conn,
        deadline,
        "WITH " + raw_cte + "projected AS (" + " UNION ALL ".join(projected) + "),"
        f"cells AS MATERIALIZED (SELECT *,{bucket} AS point,{group} AS group_key,max(bit_length(run_ids)) OVER (PARTITION BY project_id) AS width FROM projected),"
        f"top_groups AS (SELECT group_key FROM cells WHERE period='current' GROUP BY 1 ORDER BY sum({_RANKS[query.rank_by]}) DESC NULLS LAST,group_key LIMIT %(top)s),"
        "states AS (SELECT r.project_id,"
        "bit_or(set_bit(repeat('0',s.width)::bit varying,r.usage_slot,1)) FILTER (WHERE r.collection_ended_at IS NULL) AS open_ids,"
        "bit_or(set_bit(repeat('0',s.width)::bit varying,r.usage_slot,1)) FILTER (WHERE r.degraded) AS degraded_ids "
        "FROM runtime_usage_runs r JOIN (SELECT project_id,max(width) AS width FROM cells GROUP BY 1) s ON r.project_id=s.project_id "
        "WHERE r.tenant_id=%(tenant)s AND r.usage_slot<s.width AND (r.collection_ended_at IS NULL OR r.degraded) GROUP BY 1),"
        "labeled AS (SELECT *,CASE WHEN group_key IN (SELECT group_key FROM top_groups) THEN group_key END AS label FROM cells),"
        "per_project AS (SELECT project_id,period,point,label,grouping(point) AS summary_row,grouping(label) AS series_row,"
        "bit_or(run_ids || repeat('0',width-bit_length(run_ids))::bit varying) AS run_ids,"
        "max(width) AS width FROM labeled GROUP BY GROUPING SETS ((project_id,period),(project_id,period,point),(project_id,period,label))),"
        "runs AS (SELECT period,point,label,summary_row,series_row,sum(bit_count(run_ids)) AS recorded_run_count,"
        "sum(COALESCE(bit_count(run_ids & open_ids),0)) AS open_run_count,bool_or(COALESCE(bit_count(run_ids & degraded_ids),0)>0) AS degraded,"
        "sum(bit_length(run_ids)) AS width FROM per_project p LEFT JOIN states USING(project_id) GROUP BY 1,2,3,4,5),"
        f"totals AS (SELECT period,point,label,grouping(point) AS summary_row,grouping(label) AS series_row,{sums},runtime_usage_versions(pricing_versions) AS pricing_versions "
        "FROM labeled GROUP BY GROUPING SETS ((period),(period,point),(period,label))) "
        "SELECT t.*,r.recorded_run_count,r.open_run_count,r.degraded,"
        + ("(SELECT count(*) FROM raw_calls)" if sources else "0")
        + " AS catchup_count,"
        "CASE WHEN t.period='current' AND t.summary_row=1 AND t.series_row=1 THEN (SELECT array_agg(model_key ORDER BY model_key) FROM (SELECT DISTINCT model_key FROM cells WHERE period='current' ORDER BY model_key LIMIT 201) f) END AS models,"
        "CASE WHEN t.period='current' AND t.summary_row=1 AND t.series_row=1 THEN (SELECT jsonb_agg(f) FROM (SELECT DISTINCT project_id,graph_id FROM cells WHERE period='current' ORDER BY project_id,graph_id LIMIT 201) f) END AS agents FROM totals t JOIN runs r ON "
        "t.period=r.period AND t.point IS NOT DISTINCT FROM r.point AND t.label IS NOT DISTINCT FROM r.label AND t.summary_row=r.summary_row AND t.series_row=r.series_row",
        values,
    )
    if rows and rows[0]["catchup_count"] > 5000:
        raise psycopg.OperationalError("Usage raw catch-up exceeds bounded capacity")
    return rows


def aggregate_usage(query, *, deadline=None):
    pieces = _segments(
        query.start - (query.end - query.start), query.start, query, "previous"
    ) + _segments(query.start, query.end, query, "current")
    values = dict(
        tenant=query.tenant_id,
        projects=[str(p) for p in query.project_ids],
        current=query.start,
        previous=query.start - (query.end - query.start),
        end=query.end,
    )
    with _connection(deadline) as (conn, deadline):
        manifest_where = "tenant_id=%(tenant)s AND project_id=ANY(%(projects)s)"
        if query.graph_id:
            manifest_where += " AND graph_id=%(graph_id)s"
            values["graph_id"] = query.graph_id
        values.update(
            dirty_start=pieces[0][1] - timedelta(days=1),
            dirty_end=query.end + timedelta(days=1),
        )
        remaining = int((deadline - time.monotonic()) * 1000)
        if remaining <= 0:
            raise psycopg.errors.QueryCanceled("Usage query deadline exceeded")
        with conn.pipeline():
            conn.execute(
                "SELECT set_config('statement_timeout',%s,true)",
                (str(min(1000, remaining)),),
            )
            state_cursor = conn.execute(
                "SELECT transaction_timestamp() AS at,active_generation FROM runtime_usage_projection_state WHERE id=1"
            )
            collection_cursor = conn.execute(
                "SELECT count(*) AS manifest_count,min(collection_started_at) AS first_recorded_at,max(collection_started_at) AS last_recorded_at,"
                "count(*) FILTER (WHERE NOT has_calls AND collection_started_at >= %(current)s AND collection_started_at < %(end)s) AS current_zeros,"
                "count(*) FILTER (WHERE NOT has_calls AND collection_started_at >= %(previous)s AND collection_started_at < %(current)s) AS previous_zeros FROM runtime_usage_runs WHERE "
                + manifest_where,
                values,
            )
            dirty_cursor = conn.execute(
                "SELECT DISTINCT project_id,utc_day FROM runtime_usage_projection_dirty WHERE generation=(SELECT active_generation FROM runtime_usage_projection_state WHERE id=1) AND tenant_id=%(tenant)s AND project_id=ANY(%(projects)s) AND utc_day >= %(dirty_start)s AND utc_day < %(dirty_end)s LIMIT 9",
                values,
            )
        state = state_cursor.fetchone()
        as_of, values["generation"] = state["at"], state["active_generation"]
        collection = collection_cursor.fetchone()
        dirty = dirty_cursor.fetchall()
        if len(dirty) > 8:
            raise psycopg.OperationalError(
                "Usage projection backlog exceeds bounded catch-up"
            )
        projected, sources = _projection_sources(query, pieces, dirty, values)
        rows = _projected_metrics(conn, deadline, query, projected, sources, values)
        summaries = {
            row["period"]: row
            for row in rows
            if row["summary_row"] and row["series_row"]
        }
        for period in ("current", "previous"):
            summaries.setdefault(period, dict.fromkeys(COUNTS, 0))[
                "zero_call_manifest_count"
            ] = (
                None
                if any(
                    (query.model_id, query.model_mapping, query.purpose, query.scope)
                )
                else collection[period + "_zeros"]
            )
        groups = [
            dict(row, key=row["label"])
            for row in rows
            if row["period"] == "current"
            and row["summary_row"]
            and not row["series_row"]
            and row["label"] is not None
        ]
        groups.sort(
            key=lambda row: (
                row[_RANKS[query.rank_by]] is None,
                -(row[_RANKS[query.rank_by]] or 0),
                row["key"],
            )
        )
        models, agents = (
            summaries["current"].get("models") or [],
            summaries["current"].get("agents") or [],
        )
        return dict(
            as_of=as_of,
            collection=collection,
            summary=summaries["current"],
            previous=summaries["previous"],
            series=[
                dict(row, bucket=row["point"])
                for row in rows
                if row["period"] == "current"
                and not row["summary_row"]
                and row["series_row"]
            ],
            groups=groups,
            other=next(
                (
                    row
                    for row in rows
                    if row["period"] == "current"
                    and row["summary_row"]
                    and not row["series_row"]
                    and row["label"] is None
                ),
                None,
            ),
            facets={
                "models": {"items": models[:200], "truncated": len(models) > 200},
                "agents": {"items": agents[:200], "truncated": len(agents) > 200},
            },
        )


def list_usage_runs(query, *, deadline=None):
    where, values = _where(query)
    with _connection(deadline) as (conn, deadline):
        as_of = conn.execute("SELECT transaction_timestamp() AS at").fetchone()["at"]
        cutoff = query.cutoff or as_of
        where += " AND c.started_at <= %(cutoff)s"
        values.update(cutoff=cutoff, limit=query.limit + 1)
        cursor_where = ""
        if query.cursor:
            cursor_where = (
                "WHERE (last_matching_call_at,run_id) < (%(cursor_at)s,%(cursor_id)s)"
            )
            values.update(cursor_at=query.cursor.at, cursor_id=query.cursor.run_id)
        rows = _execute(
            conn,
            deadline,
            f"WITH candidates AS (SELECT c.project_id,c.thread_id,c.run_id,c.graph_id,min(c.started_at) AS first_matching_call_at,max(c.started_at) AS last_matching_call_at,{_METRICS} {_JOIN} WHERE {where} GROUP BY c.project_id,c.thread_id,c.run_id,c.graph_id) SELECT * FROM candidates {cursor_where} ORDER BY last_matching_call_at DESC,run_id DESC LIMIT %(limit)s",
            values,
        )
        page = rows[: query.limit]
        cursor = (
            {
                "at": page[-1]["last_matching_call_at"].isoformat(),
                "run_id": str(page[-1]["run_id"]),
            }
            if len(rows) > query.limit
            else None
        )
        return {"items": page, "next_cursor": cursor, "as_of": as_of, "cutoff": cutoff}
