"""Bounded metadata-only Langfuse queries; execution state stays in GraphHarbor."""

from __future__ import annotations

import asyncio
import math
import os
import re
import time
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import httpx
from langfuse.api.client import AsyncLangfuseAPI

from runtime_service.observability.diagnostics import (
    loop_detection_fields,
    trace_id_for,
    workspace_execution_fields,
)
from runtime_service.observability.errors import MODEL_ERROR_CODES
from runtime_service.observability.startup import PHASE_NAMES
from runtime_service.runtime.errors import WORKSPACE_ERROR_CODES

_client: AsyncLangfuseAPI | None = None
_FIELDS = "core,basic,time,metadata"
_EVENTS = {
    "runtime.model_call.failed",
    "runtime.graph.completed",
    "runtime.startup.completed",
    "runtime.startup.phase_completed",
    "runtime.prepare.completed",
    "runtime.retry.completed",
    "runtime.workspace.execution_completed",
    "runtime.loop.transition",
}


@asynccontextmanager
async def diagnostics_client_lifespan() -> AsyncIterator[None]:
    global _client
    configured = os.getenv("LANGFUSE_ENABLED", "").lower() == "true" and all(
        os.getenv(key)
        for key in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL")
    )
    if not configured:
        yield
        return
    async with httpx.AsyncClient(
        timeout=2, trust_env=False, follow_redirects=False
    ) as transport:
        _client = AsyncLangfuseAPI(
            base_url=os.environ["LANGFUSE_BASE_URL"],
            username=os.environ["LANGFUSE_PUBLIC_KEY"],
            password=os.environ["LANGFUSE_SECRET_KEY"],
            httpx_client=transport,
            follow_redirects=False,
        )
        try:
            yield
        finally:
            _client = None


def _dict(value: Any) -> dict:
    if isinstance(value, Mapping):
        return dict(value)
    return value.model_dump() if hasattr(value, "model_dump") else {}


def _identifier(value: Any) -> str | None:
    return (
        value
        if isinstance(value, str)
        and re.fullmatch(r"[\w:.-]{1,128}", value, flags=re.ASCII)
        else None
    )


def _duration(value: Any) -> float | None:
    return (
        value
        if type(value) in (int, float) and math.isfinite(value) and value >= 0
        else None
    )


def _utc(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 64:
        return None
    try:
        parsed = datetime.fromisoformat(value)
        return (
            parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
            if parsed.utcoffset() is not None
            else None
        )
    except ValueError:
        return None


def _matches(metadata: dict, expected: dict) -> bool:
    return all(metadata.get(key) == value for key, value in expected.items())


def empty_diagnostics(reason: str) -> dict:
    return {
        "version": 1,
        "availability": "disabled" if reason == "not_configured" else "unavailable",
        "unavailable_reason": reason,
        "correlation": {"execution_request_id": None, "platform_trace_id": None},
        "trace": None,
        "graph_executions": [],
        "model_errors": [],
        "workspace_executions": [],
        "loop_detections": [],
        "startup": None,
        "preparations": [],
        "retries": [],
        "truncated": False,
    }


def _reliability(metadata: dict, common: dict) -> tuple[str, dict] | None:
    if metadata.get("scope") not in {"primary", "subagent"}:
        return None
    namespace = metadata.get("namespace", [])
    fields = {
        **common,
        "scope": metadata["scope"],
        "namespace": [part for value in namespace[:8] if (part := _identifier(value))]
        if isinstance(namespace, list)
        else [],
    }
    if metadata["event"] == "runtime.prepare.completed":
        if metadata.get("component") != "workspace" or metadata.get("outcome") not in {
            "prepared",
            "reused",
            "repaired",
            "failed",
        }:
            return None
        return "preparations", {
            **fields,
            "component": "workspace",
            "outcome": metadata["outcome"],
            "error_code": metadata.get("error_code")
            if metadata.get("error_code") in {"prepare_failed", "resource_unavailable"}
            else None,
        }
    unit, attempts, role = (
        metadata.get("unit"),
        metadata.get("attempts"),
        metadata.get("role"),
    )
    if (
        unit not in {"model", "task"}
        or type(attempts) is not int
        or not 1 <= attempts <= 2
        or metadata.get("outcome")
        not in {"success", "exhausted", "failed", "cancelled", "interrupted"}
        or unit == "task"
        and (not _identifier(role) or len(role) > 64)
    ):
        return None
    return "retries", {
        **fields,
        "unit": unit,
        "role": role if unit == "task" else None,
        "attempts": attempts,
        "outcome": metadata["outcome"],
        "code": metadata.get("code")
        if metadata.get("code") in MODEL_ERROR_CODES
        else None,
    }


# Keep event schemas together so scope and response limits agree.
def _project(observations: list[dict], expected: dict, *, truncated: bool) -> dict:
    result = empty_diagnostics("not_recorded")
    records = [
        item for item in observations if _matches(_dict(item.get("metadata")), expected)
    ]
    if not records:
        result["truncated"] = truncated
        return result
    traces = {_identifier(item.get("trace_id")) for item in records} - {None}
    if len(traces) > 50:
        truncated = True
        accepted = list(dict.fromkeys(item.get("trace_id") for item in records))[:50]
        records = [item for item in records if item.get("trace_id") in accepted]
    if len(traces) == 1:
        result["trace"] = {
            "provider": "langfuse",
            "trace_id": next(iter(traces)),
            "url": None,
        }
    for target, source in (
        ("execution_request_id", "request_id"),
        ("platform_trace_id", "platform_trace_id"),
    ):
        values = {
            _identifier(_dict(item.get("metadata")).get(source)) for item in records
        } - {None}
        result["correlation"][target] = next(iter(values)) if len(values) == 1 else None
    phases, totals, factories, seen = [], [], set(), set()
    for item in records:
        metadata = _dict(item.get("metadata"))
        event = metadata.get("event")
        identifier = _identifier(item.get("id"))
        if (
            metadata.get("schema_version") != 1
            or event not in _EVENTS
            or item.get("name") != event
            or identifier is None
            or identifier in seen
        ):
            continue
        seen.add(identifier)
        common = {
            "observation_id": identifier,
            "duration_ms": _duration(metadata.get("duration_ms")),
        }
        error_code = metadata.get("error_code")
        error_code = (
            error_code
            if isinstance(error_code, str)
            and error_code
            in MODEL_ERROR_CODES | WORKSPACE_ERROR_CODES | {"runtime.loop.detected"}
            else None
        )
        if event in {"runtime.prepare.completed", "runtime.retry.completed"}:
            projected = _reliability(metadata, common)
            if projected is not None:
                target, fields = projected
                result[target].append(fields)
        elif event == "runtime.loop.transition":
            summary = loop_detection_fields(metadata)
            if summary is not None:
                result["loop_detections"].append(
                    {"observation_id": identifier, **summary}
                )
        elif event == "runtime.model_call.failed" and metadata.get("scope") in {
            "primary",
            "subagent",
        }:
            code = metadata.get("code")
            if code not in MODEL_ERROR_CODES:
                continue
            namespace = metadata.get("namespace", [])
            namespace = (
                [_identifier(part) for part in namespace[:8]]
                if isinstance(namespace, list)
                else []
            )
            status = metadata.get("provider_status")
            result["model_errors"].append(
                {
                    **common,
                    "scope": metadata["scope"],
                    "namespace": [part for part in namespace if part],
                    "code": code,
                    "error_type": _identifier(metadata.get("error_type")),
                    "provider_status": status
                    if type(status) is int and 100 <= status <= 599
                    else None,
                }
            )
        elif event == "runtime.graph.completed" and metadata.get("outcome") in {
            "success",
            "failed",
            "timeout",
            "cancelled",
            "interrupted",
        }:
            result["graph_executions"].append(
                {**common, "outcome": metadata["outcome"], "error_code": error_code}
            )
        elif event == "runtime.workspace.execution_completed":
            summary = workspace_execution_fields(metadata)
            if summary is not None:
                result["workspace_executions"].append({**common, **summary})
        elif event.startswith("runtime.startup.") and _identifier(
            metadata.get("factory_id")
        ):
            factories.add(metadata["factory_id"])
            if event == "runtime.startup.completed":
                totals.append(metadata)
            elif (
                metadata.get("phase") in PHASE_NAMES
                and metadata.get("outcome")
                in {"completed", "failed", "cancelled", "incomplete"}
                and type(metadata.get("ordinal")) is int
                and 0 <= metadata["ordinal"] < 16
            ):
                phases.append(
                    {
                        "name": metadata["phase"],
                        "ordinal": metadata["ordinal"],
                        "outcome": metadata["outcome"],
                        "started_at": _utc(metadata.get("started_at")),
                        "ended_at": _utc(metadata.get("ended_at")),
                        "duration_ms": common["duration_ms"],
                        "error_code": error_code,
                    }
                )
    if len(factories) == 1 and len(totals) == 1:
        result["startup"] = {
            "duration_ms": _duration(totals[0].get("duration_ms")),
            "phases": sorted(phases, key=lambda phase: phase["ordinal"])[:16],
        }
    for key, limit in (
        ("model_errors", 20),
        ("graph_executions", 10),
        ("workspace_executions", 20),
        ("loop_detections", 20),
        ("preparations", 20),
        ("retries", 20),
    ):
        truncated |= len(result[key]) > limit
        result[key] = result[key][:limit]
    truncated |= len(phases) > 16
    result.update(
        availability="available"
        if result["graph_executions"]
        and result["startup"]
        and len(traces) == 1
        and not truncated
        else "partial",
        unavailable_reason=None,
        truncated=truncated,
    )
    return result


async def query_run_diagnostics(
    *, tenant_id: str, project_id: str, graph_id: str, thread_id: str, run_id: str
) -> dict:
    if _client is None:
        return empty_diagnostics("not_configured")
    expected = {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "graph_id": graph_id,
        "thread_id": thread_id,
        "run_id": run_id,
    }
    deadline = time.monotonic() + 2
    try:
        async with asyncio.timeout(2):
            page = await _client.observations.get_many(
                trace_id=trace_id_for(expected),
                fields=_FIELDS,
                limit=100,
                expand_metadata="namespace",
                request_options={
                    "timeout_in_seconds": max(0.001, deadline - time.monotonic()),
                    "max_retries": 0,
                },
            )
            rows = _dict(page)
            observations = [_dict(item) for item in rows.get("data", [])[:100]]
            if not observations:
                # Legacy traces have random IDs; keep this fallback bounded and metadata-only.
                page = await _client.observations.get_many(
                    session_id=thread_id,
                    fields=_FIELDS,
                    limit=100,
                    expand_metadata="namespace",
                    request_options={
                        "timeout_in_seconds": max(0.001, deadline - time.monotonic()),
                        "max_retries": 0,
                    },
                )
                rows = _dict(page)
                observations = [_dict(item) for item in rows.get("data", [])[:100]]
            meta = _dict(rows.get("meta"))
            truncated = (
                bool(
                    meta.get("cursor")
                    or meta.get("next_cursor")
                    or meta.get("nextCursor")
                )
                or len(rows.get("data", [])) > 100
            )
            return _project(observations, expected, truncated=truncated)
    except Exception:
        return empty_diagnostics("backend_unavailable")


__all__ = ["diagnostics_client_lifespan", "query_run_diagnostics"]
