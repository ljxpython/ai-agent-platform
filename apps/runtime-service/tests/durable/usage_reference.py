"""Frozen pre-projection SQL oracle, used only by real PostgreSQL comparisons."""

from runtime_service.db.repositories.usage_analytics import (
    _GROUPS,
    _JOIN,
    _METRICS,
    _RANKS,
    _connection,
    _execute,
    _where,
)


def _collection(conn, deadline, query):
    where = "r.tenant_id=%(tenant)s AND r.project_id=ANY(%(projects)s)"
    values = {
        "tenant": query.tenant_id,
        "projects": [str(p) for p in query.project_ids],
        "start": query.start,
        "end": query.end,
        "previous": query.start - (query.end - query.start),
    }
    if query.graph_id:
        where += " AND r.graph_id=%(graph_id)s"
        values["graph_id"] = query.graph_id
    result = _execute(
        conn,
        deadline,
        "SELECT count(*) AS manifest_count, min(r.collection_started_at) AS first_recorded_at, max(r.collection_started_at) AS last_recorded_at FROM runtime_usage_runs r WHERE "
        + where,
        values,
    )[0]
    zeros = {"current": None, "previous": None}
    if not any((query.model_id, query.model_mapping, query.purpose, query.scope)):
        rows = _execute(
            conn,
            deadline,
            "SELECT CASE WHEN r.collection_started_at >= %(start)s THEN 'current' ELSE 'previous' END AS period, count(*) AS count FROM runtime_usage_runs r WHERE "
            + where
            + " AND r.collection_started_at >= %(previous)s AND r.collection_started_at < %(end)s AND NOT EXISTS (SELECT 1 FROM runtime_usage_calls c WHERE c.tenant_id=r.tenant_id AND c.project_id=r.project_id AND c.run_id=r.run_id) GROUP BY 1",
            values,
        )
        zeros = {"current": 0, "previous": 0} | {r["period"]: r["count"] for r in rows}
    return result, zeros


def aggregate_usage_raw(query, *, deadline=None):
    where, values = _where(query, previous=True)
    values.update(
        current=query.start,
        timezone=query.timezone,
        granularity=query.granularity,
        top=query.top_n,
    )
    period = "CASE WHEN c.started_at >= %(current)s THEN 'current' ELSE 'previous' END"
    bucket = "date_trunc(%(granularity)s,c.started_at AT TIME ZONE %(timezone)s) AT TIME ZONE %(timezone)s"
    group = _GROUPS[query.group_by]
    rank = _RANKS[query.rank_by]
    with _connection(deadline) as (conn, deadline):
        as_of = conn.execute("SELECT transaction_timestamp() AS at").fetchone()["at"]
        collection, zeros = _collection(conn, deadline, query)
        rows = _execute(
            conn,
            deadline,
            f"SELECT {period} AS period, {bucket} AS bucket, {_METRICS} {_JOIN} WHERE {where} GROUP BY GROUPING SETS (({period}),({period},{bucket}))",
            values,
        )
        summaries = {r["period"]: r for r in rows if r["bucket"] is None}
        for key in ("current", "previous"):
            summaries.setdefault(key, {})["zero_call_manifest_count"] = zeros[key]
        current_where, current_values = _where(query)
        current_values.update(
            timezone=query.timezone, granularity=query.granularity, top=query.top_n
        )
        groups = _execute(
            conn,
            deadline,
            f"SELECT {group} AS key, {_METRICS} {_JOIN} WHERE {current_where} GROUP BY 1 ORDER BY {rank} DESC NULLS LAST,key LIMIT %(top)s",
            current_values,
        )
        other = None
        if len(groups) == query.top_n:
            other_rows = _execute(
                conn,
                deadline,
                f"SELECT {_METRICS} {_JOIN} WHERE {current_where} AND {group} <> ALL(%(keys)s)",
                {**current_values, "keys": [r["key"] for r in groups]},
            )
            if other_rows[0]["observed_call_count"]:
                other = other_rows[0]
        models = _execute(
            conn,
            deadline,
            f"SELECT DISTINCT COALESCE(c.model_id::text,'unmapped') AS key {_JOIN} WHERE {current_where} ORDER BY key LIMIT 201",
            current_values,
        )
        agents = _execute(
            conn,
            deadline,
            f"SELECT DISTINCT c.project_id,c.graph_id {_JOIN} WHERE {current_where} ORDER BY c.project_id,c.graph_id LIMIT 201",
            current_values,
        )
        return {
            "as_of": as_of,
            "collection": collection,
            "summary": summaries["current"],
            "previous": summaries["previous"],
            "series": [
                r for r in rows if r["period"] == "current" and r["bucket"] is not None
            ],
            "groups": groups,
            "other": other,
            "facets": {
                "models": {
                    "items": [r["key"] for r in models[:200]],
                    "truncated": len(models) > 200,
                },
                "agents": {"items": agents[:200], "truncated": len(agents) > 200},
            },
        }
