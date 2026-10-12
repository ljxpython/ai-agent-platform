"""Bounded analytics of recorded calls; collection and Run budgets stay unchanged."""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from runtime_service.observability.usage import (
    EXCLUDED_OPERATIONS,
    TOKEN_FIELDS,
    usage_enabled,
)
from runtime_service.observability.usage_query import _cost, _integer

Identifier = Annotated[
    str, Field(strict=True, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_:.-]+$")
]
Purpose = Literal["agent", "summarization", "memory_extraction", "vision", "other"]
Scope = Literal["primary", "subagent", "auxiliary"]
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="usage-query")
_inflight = threading.BoundedSemaphore(16)


async def _read(execute, query):
    if not _inflight.acquire(blocking=False):
        raise psycopg.OperationalError("Usage query capacity exhausted")
    deadline = time.monotonic() + 4.5
    future = _executor.submit(execute, query, deadline=deadline)
    future.add_done_callback(lambda _: _inflight.release())
    wrapped = asyncio.wrap_future(future)
    wrapped.add_done_callback(
        lambda done: None if done.cancelled() else done.exception()
    )
    try:
        return await asyncio.wait_for(asyncio.shield(wrapped), timeout=4.8)
    except TimeoutError as exc:
        raise psycopg.OperationalError("Usage query deadline exceeded") from exc


class AnalyticsQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: Literal[1] = 1
    actor_id: Identifier
    credential_id: Identifier | None = None
    tenant_id: Identifier
    project_ids: Annotated[list[UUID], Field(min_length=1, max_length=200)]
    request_id: Identifier
    start: datetime = Field(alias="from")
    end: datetime = Field(alias="to")
    model_id: UUID | None = None
    model_mapping: Literal["unmapped"] | None = None
    graph_id: Identifier | None = None
    purpose: Purpose | None = None
    scope: Scope | None = None

    @field_validator("version", mode="before")
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError("Integer version required")
        return value

    @field_validator("start", "end")
    @classmethod
    def utc_only(cls, value):
        if value.utcoffset() != timedelta(0):
            raise ValueError("UTC timestamp required")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def check_scope(self):
        if not timedelta(0) < self.end - self.start <= timedelta(days=90):
            raise ValueError("Window must be within 90 days")
        if len(set(self.project_ids)) != len(self.project_ids):
            raise ValueError("Duplicate project")
        if (
            self.model_id
            and self.model_mapping
            or self.graph_id
            and len(self.project_ids) != 1
        ):
            raise ValueError("Conflicting filter")
        return self

    def filters(self):
        return {
            key: self.model_dump(mode="json")[key]
            for key in ("model_id", "model_mapping", "graph_id", "purpose", "scope")
        }


class AggregateQuery(AnalyticsQuery):
    timezone: Literal["UTC", "Asia/Shanghai"] = "Asia/Shanghai"
    granularity: Literal["day", "hour"] = "day"
    group_by: Literal["project", "model", "agent", "purpose", "scope"] = "model"
    rank_by: Literal["known_total_tokens", "known_cost_usd", "observed_call_count"] = (
        "known_total_tokens"
    )
    top_n: Annotated[int, Field(strict=True, ge=1, le=50)] = 10

    @model_validator(mode="after")
    def check_buckets(self):
        if self.granularity == "hour" and self.end - self.start > timedelta(days=7):
            raise ValueError("Hourly window must be within 7 days")
        return self


class RunPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    at: datetime
    run_id: UUID

    @field_validator("at")
    @classmethod
    def utc_only(cls, value):
        return AnalyticsQuery.utc_only(value)


class RunsQuery(AnalyticsQuery):
    limit: Annotated[int, Field(strict=True, ge=1, le=200)] = 50
    cursor: RunPosition | None = None
    cutoff: datetime | None = None

    @model_validator(mode="after")
    def single_project(self):
        if len(self.project_ids) != 1:
            raise ValueError("Single project required")
        if self.cutoff is not None:
            self.cutoff = AnalyticsQuery.utc_only(self.cutoff)
        if self.cursor and self.cutoff is None:
            raise ValueError("Cursor requires cutoff")
        return self


def project_metrics(row, *, unknown=False):
    count = _integer(row.get("observed_call_count", 0))
    complete = (
        not unknown
        and not row.get("degraded", False)
        and not row.get("open_run_count", 0)
        and not row.get("incomplete_call_count", 0)
        and row.get("reported_call_count", 0) == count
    )
    tokens, known, counts = {}, {}, {}
    for field in TOKEN_FIELDS:
        counts[field] = _integer(row.get(field + "_count", 0))
        value = row.get(field)
        known[field] = (
            _integer(value)
            if value is not None
            else (0 if count == 0 and not unknown else None)
        )
        tokens[field] = known[field] if complete and counts[field] == count else None
    priced = _integer(row.get("priced_call_count", 0))
    cost = _cost(
        count,
        row.get("known_cost_usd"),
        priced,
        row.get("pricing_versions", []),
        complete=complete,
    )
    cache = row.get("ratio_cache_tokens", 0)
    inputs = row.get("ratio_input_tokens", 0)
    return {
        "tokens": tokens,
        "known_tokens": known,
        "cost": cost,
        "coverage": {
            **{
                k: _integer(row.get(k, 0))
                for k in (
                    "observed_call_count",
                    "reported_call_count",
                    "missing_usage_call_count",
                    "incomplete_call_count",
                )
            },
            "priced_call_count": priced,
            "field_call_counts": counts,
            "collection_degraded": bool(row.get("degraded", False)),
            "excluded_operations": EXCLUDED_OPERATIONS,
        },
        "recorded_run_count": _integer(row.get("recorded_run_count", 0)),
        "open_collection_run_count": _integer(row.get("open_run_count", 0)),
        "zero_call_manifest_count": row.get("zero_call_manifest_count"),
        "cache_read_ratio": float(Decimal(cache) / inputs) if inputs else None,
        "ratio_sample_call_count": _integer(row.get("ratio_sample_call_count", 0)),
        "average_tokens_per_recorded_run": float(
            Decimal(tokens["total_tokens"]) / row["recorded_run_count"]
        )
        if tokens["total_tokens"] is not None and row.get("recorded_run_count")
        else None,
        "pricing_versions_truncated": len(row.get("pricing_versions", [])) > 50,
    }


def window(query, *, previous=False):
    delta = query.end - query.start if previous else timedelta(0)
    return {
        "from": (query.start - delta).isoformat(),
        "to": (query.end - delta).isoformat(),
        "timezone": query.timezone,
        "granularity": query.granularity,
        "time_basis": "model_call_started_at",
    }


def dashboard(query, facts=None, *, backend_unavailable=False):
    facts = facts or {}
    collection = facts.get("collection", {})
    history = bool(collection.get("manifest_count", 0))
    unknown = backend_unavailable or not history
    summary = project_metrics(facts.get("summary", {}), unknown=unknown)
    previous = project_metrics(facts.get("previous", {}), unknown=unknown)
    start = query.start.astimezone(ZoneInfo(query.timezone))
    bucket = start.replace(minute=0, second=0, microsecond=0)
    if query.granularity == "day":
        bucket = bucket.replace(hour=0)
    step = timedelta(days=1) if query.granularity == "day" else timedelta(hours=1)
    points = {row["bucket"]: row for row in facts.get("series", [])}
    series = []
    while bucket < query.end:
        series.append(
            {
                "from": max(bucket, query.start).isoformat(),
                "to": min(bucket + step, query.end).isoformat(),
                **project_metrics(points.get(bucket, {}), unknown=unknown),
            }
        )
        bucket += step
    if len(series) > 200:
        raise ValueError("invalid_usage_analytics_query")
    total, old = summary["tokens"]["total_tokens"], previous["tokens"]["total_tokens"]
    availability = (
        "unavailable"
        if backend_unavailable or not history and usage_enabled()
        else "disabled"
        if not history
        else "available"
        if total is not None
        else "partial"
    )
    return {
        "version": 1,
        "tenant_id": query.tenant_id,
        "scope": {
            "project_ids": sorted(str(p) for p in query.project_ids),
            "covered_project_count": len(query.project_ids),
        },
        "window": window(query),
        "filters": query.filters(),
        "as_of": facts.get("as_of", datetime.now(UTC)).isoformat(),
        "availability": availability,
        "unavailable_reason": "backend_unavailable"
        if backend_unavailable
        else "not_recorded"
        if availability == "unavailable"
        else None,
        "coverage_basis": "recorded_native_runs",
        "summary": summary,
        "previous_window": {
            "window": window(query, previous=True),
            "summary": previous,
            "total_token_change_ratio": float(Decimal(total - old) / old)
            if total is not None and old
            else None,
        },
        "series": series,
        "breakdown": {
            "group_by": query.group_by,
            "rank_by": query.rank_by,
            "items": [
                {"key": row["key"], **project_metrics(row)}
                for row in facts.get("groups", [])
            ],
            "other": project_metrics(facts["other"]) if facts.get("other") else None,
        },
        "facets": facts.get(
            "facets",
            {
                "models": {"items": [], "truncated": False},
                "agents": {"items": [], "truncated": False},
            },
        ),
        "collection": {
            "enabled_now": usage_enabled(),
            **{
                key: collection[key].isoformat() if collection.get(key) else None
                for key in ("first_recorded_at", "last_recorded_at")
            },
            "excluded_operations": EXCLUDED_OPERATIONS,
        },
        "request_id": query.request_id,
    }


async def query_aggregate(query):
    from runtime_service.db.repositories.usage_analytics import aggregate_usage

    try:
        return dashboard(query, await _read(aggregate_usage, query))
    except (
        psycopg.OperationalError,
        psycopg.errors.QueryCanceled,
        psycopg.errors.LockNotAvailable,
        KeyError,
    ):
        return dashboard(query, backend_unavailable=True)
    except ValueError as exc:
        if str(exc) == "unsafe_usage_total":
            raise ValueError("usage_aggregate_range_exceeded") from exc
        raise


async def query_runs(query):
    from runtime_service.db.repositories.usage_analytics import list_usage_runs

    facts = await _read(list_usage_runs, query)
    items = [
        {
            **{
                k: str(row[k])
                for k in ("project_id", "thread_id", "run_id", "graph_id")
            },
            "first_matching_call_at": row["first_matching_call_at"].isoformat(),
            "last_matching_call_at": row["last_matching_call_at"].isoformat(),
            **project_metrics(row),
        }
        for row in facts["items"]
    ]
    return {
        "version": 1,
        "tenant_id": query.tenant_id,
        "project_ids": [str(p) for p in query.project_ids],
        "filters": query.filters(),
        "from": query.start.isoformat(),
        "to": query.end.isoformat(),
        "items": items,
        "next_cursor": facts["next_cursor"],
        "cutoff": facts["cutoff"].isoformat(),
        "as_of": facts["as_of"].isoformat(),
        "request_id": query.request_id,
    }
