"""Usage DTO projection; no model payloads or credentials leave the ledger."""

import asyncio
import base64
import binascii
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from runtime_service.db.repositories import usage as repository
from runtime_service.observability.usage import (
    EXCLUDED_OPERATIONS,
    MAX_TOKEN,
    TOKEN_FIELDS,
    empty_tokens,
    usage_enabled,
)


def parse_limit(value) -> int:
    if (
        isinstance(value, bool)
        or not str(value).isascii()
        or not str(value).isdigit()
        or len(str(value)) > 3
        or not 1 <= int(value) <= 200
    ):
        raise ValueError("invalid_usage_limit")
    return int(value)


def _utc(value: str) -> datetime:
    timestamp = datetime.fromisoformat(value)
    if timestamp.utcoffset() != timedelta(0):
        raise ValueError("invalid_usage_window")
    return timestamp.astimezone(UTC)


def parse_window(created_from, created_to):
    if created_from is None and created_to is None:
        return None
    if not created_from or not created_to:
        raise ValueError("invalid_usage_window")
    start, end = _utc(created_from), _utc(created_to)
    if end <= start or end - start > timedelta(days=90):
        raise ValueError("invalid_usage_window")
    return start, end


def parse_cursor(value):
    if value is None:
        return None
    if not isinstance(value, str) or not 1 <= len(value) <= 512:
        raise ValueError("invalid_usage_cursor")
    try:
        decoded = json.loads(base64.b64decode(value, altchars=b"-_", validate=True))
        if (
            not isinstance(decoded, list)
            or len(decoded) != 2
            or not all(isinstance(v, str) for v in decoded)
        ):
            raise ValueError("invalid_usage_cursor")
        return _utc(decoded[0]), UUID(decoded[1])
    except (ValueError, TypeError, binascii.Error) as exc:
        raise ValueError("invalid_usage_cursor") from exc


def _cursor(call):
    return base64.urlsafe_b64encode(
        json.dumps(
            [call["started_at"].isoformat(), str(call["model_call_id"])]
        ).encode()
    ).decode()


def _integer(value):
    number = int(value)
    if not 0 <= number <= MAX_TOKEN:
        raise ValueError("unsafe_usage_total")
    return number


def _money(value):
    if value is None or not 0 <= Decimal(value) < Decimal("10000000000000000"):
        return None
    return format(Decimal(value), ".12f")


def _cost(total, known, priced, versions, *, complete):
    if complete and total == 0:
        status = "not_applicable"
    elif complete and priced == total:
        status = "estimated"
    else:
        status = "partial" if priced else "unknown"
    amount = _money(known)
    if known is not None and amount is None:
        status = "unknown"
    return {
        "status": status,
        "estimated_cost_usd": amount if status == "estimated" else None,
        "known_cost_usd": amount,
        "currency": "USD",
        "source": "configured_catalog" if priced else None,
        "unpriced_call_count": total - priced,
        "pricing_versions": versions[:50],
    }


def empty_summary(reason):
    return {
        "version": 1,
        "availability": "disabled" if reason == "disabled" else "unavailable",
        "unavailable_reason": None if reason == "disabled" else reason,
        "tokens": empty_tokens(),
        "known_tokens": empty_tokens(),
        "cost": _cost(0, None, 0, [], complete=False),
        "coverage": {
            "observed_call_count": 0,
            "reported_call_count": 0,
            "missing_usage_call_count": 0,
            "incomplete_call_count": 0,
            "collection_degraded": False,
            "excluded_operations": EXCLUDED_OPERATIONS,
        },
        "truncated": False,
    }


def project_summary(summary):
    count = _integer(summary["observed_call_count"])
    complete = (
        not summary["degraded"]
        and not summary["open_run_count"]
        and not summary["incomplete_call_count"]
        and summary["reported_call_count"] == count
    )
    tokens, known = {}, {}
    for field in TOKEN_FIELDS:
        value = (
            _integer(summary[field])
            if summary[field] is not None
            else 0
            if count == 0
            else None
        )
        known[field] = value
        tokens[field] = (
            value if complete and summary[field + "_count"] == count else None
        )
    coverage = {
        key: _integer(summary[key])
        for key in (
            "observed_call_count",
            "reported_call_count",
            "missing_usage_call_count",
            "incomplete_call_count",
        )
    }
    coverage.update(
        collection_degraded=bool(summary["degraded"]),
        excluded_operations=EXCLUDED_OPERATIONS,
    )
    versions = summary["pricing_versions"]
    return {
        "version": 1,
        "availability": "available" if complete else "partial",
        "unavailable_reason": None,
        "tokens": tokens,
        "known_tokens": known,
        "coverage": coverage,
        "cost": _cost(
            count,
            summary["known_cost_usd"],
            summary["priced_call_count"],
            versions,
            complete=complete,
        ),
        "truncated": len(versions) > 50,
    }


def project_call(call):
    result = {
        key: call[key]
        for key in (
            "provider",
            "model_name",
            "scope",
            "purpose",
            "namespace",
            "outcome",
            "quality",
        )
    }
    result.update(
        model_call_id=str(call["model_call_id"]),
        model_id=str(call["model_id"]) if call["model_id"] else None,
        started_at=call["started_at"].isoformat(),
        ended_at=call["ended_at"].isoformat() if call["ended_at"] else None,
    )
    result["tokens"] = {
        key: _integer(call[key]) if call[key] is not None else None
        for key in TOKEN_FIELDS
    }
    price = call["pricing_snapshot"] or {}
    amount = call["estimated_cost_usd"]
    result["cost"] = _cost(
        1,
        amount,
        int(amount is not None),
        [price["version"]] if price else [],
        complete=call["outcome"] != "started",
    )
    return result


async def query_run_usage(identity, *, limit=50, cursor=None):
    limit, cursor = parse_limit(limit), parse_cursor(cursor)
    base = {
        "thread_id": identity["thread_id"],
        "run_id": identity["run_id"],
        "finalized": False,
        "calls": {"items": [], "next_cursor": None},
    }
    try:
        summary, rows = await asyncio.to_thread(
            repository.read_run_usage, identity, limit, cursor
        )
        if not summary["recorded_run_count"]:
            return {
                **empty_summary("not_recorded" if usage_enabled() else "disabled"),
                **base,
            }
        page = rows[:limit]
        return {
            **project_summary(summary),
            **base,
            "finalized": not summary["open_run_count"]
            and not summary["incomplete_call_count"]
            and not summary["degraded"],
            "calls": {
                "items": [project_call(row) for row in page],
                "next_cursor": _cursor(page[-1]) if len(rows) > limit else None,
            },
        }
    except Exception:
        return {**empty_summary("backend_unavailable"), **base}


async def query_thread_usage(identity, *, created_from=None, created_to=None):
    window = parse_window(created_from, created_to)
    base = {
        "thread_id": identity["thread_id"],
        "coverage_basis": "recorded_native_runs",
        "created_from": window[0].isoformat() if window else None,
        "created_to": window[1].isoformat() if window else None,
        "recorded_run_count": 0,
        "first_recorded_at": None,
        "last_recorded_at": None,
    }
    try:
        summary = await asyncio.to_thread(
            repository.aggregate_thread_usage, identity, window
        )
        if not summary["recorded_run_count"]:
            return {
                **empty_summary("not_recorded" if usage_enabled() else "disabled"),
                **base,
            }
        return {
            **project_summary(summary),
            **base,
            "recorded_run_count": _integer(summary["recorded_run_count"]),
            **{
                key: summary[key].isoformat() if summary[key] else None
                for key in ("first_recorded_at", "last_recorded_at")
            },
        }
    except Exception:
        return {**empty_summary("backend_unavailable"), **base}
