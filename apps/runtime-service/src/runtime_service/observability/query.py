"""Bounded metadata-only Langfuse queries; execution state stays in GraphHarbor."""

from __future__ import annotations

import asyncio
import json
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

from runtime_service.errors import WORKSPACE_ERROR_CODES
from runtime_service.observability.diagnostics import (
    loop_detection_fields,
    trace_id_for,
    workspace_execution_fields,
)
from runtime_service.observability.errors import MODEL_ERROR_CODES
from runtime_service.observability.startup import PHASE_NAMES

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
    from runtime_service.observability.mlflow_tracer import (
        initialize_mlflow,
        is_mlflow_enabled,
    )

    if is_mlflow_enabled() and os.getenv("MLFLOW_TRACKING_URI", "").strip():
        initialize_mlflow()

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
def _project(
    observations: list[dict],
    expected: dict,
    *,
    truncated: bool,
    provider_override: str | None = None,
) -> dict:
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
        if provider_override is not None:
            chosen_provider = provider_override
        else:
            from runtime_service.observability.mlflow_tracer import get_tracing_provider

            active_provider = get_tracing_provider()
            chosen_provider = "mlflow" if active_provider == "mlflow" else "langfuse"
        result["trace"] = {
            "provider": chosen_provider,
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


def _mlflow_configured() -> bool:
    from runtime_service.observability.mlflow_tracer import is_mlflow_enabled

    return is_mlflow_enabled() and bool(os.getenv("MLFLOW_TRACKING_URI", "").strip())


def _mlflow_trace_meta(trace_info: Any) -> dict[str, Any]:
    tags = dict(getattr(trace_info, "tags", None) or {})
    meta = dict(getattr(trace_info, "trace_metadata", None) or {})
    merged = {**tags, **meta}
    if "thread_id" not in merged:
        session = meta.get("mlflow.trace.session") or tags.get("mlflow.session_id")
        if session:
            merged["thread_id"] = session
    return merged


def _mlflow_trace_matches(trace_info: Any, expected: dict) -> bool:
    merged = _mlflow_trace_meta(trace_info)
    return _matches(merged, expected)


def _mlflow_trace_outcome(trace_info: Any) -> str | None:
    raw = getattr(trace_info, "state", None)
    text = str(getattr(raw, "value", raw) or "").strip().upper()
    if text in {"OK", "TRACESTATE.OK"}:
        return "success"
    if text in {"ERROR", "TRACESTATE.ERROR"}:
        return "failed"
    return None


def _mlflow_root_duration_ms(trace_info: Any, spans: list[Any]) -> float | None:
    dur = _duration(getattr(trace_info, "execution_duration", None))
    if dur is not None:
        return float(dur)
    if spans:
        root = spans[0]
        start_ns = getattr(root, "start_time_ns", None)
        end_ns = getattr(root, "end_time_ns", None)
        if isinstance(start_ns, int) and isinstance(end_ns, int) and end_ns >= start_ns:
            return round((end_ns - start_ns) / 1_000_000, 2)
    return None


def _mlflow_tag_observations(
    trace_info: Any, trace_id: str, trace_meta: dict[str, Any]
) -> tuple[list[dict], bool]:
    tags = dict(getattr(trace_info, "tags", None) or {})
    raw = tags.get("runtime.diag.events")
    if not isinstance(raw, str) or not raw:
        return [], False
    try:
        items = json.loads(raw)
    except (ValueError, TypeError):
        return [], False
    if not isinstance(items, list):
        return [], False
    observations: list[dict] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        meta = item.get("metadata")
        if name not in _EVENTS or not isinstance(meta, dict):
            continue
        if meta.get("schema_version") != 1:
            continue
        obs_id = (
            _identifier(meta.get("observation_id"))
            or _identifier(meta.get("event_id"))
            or _identifier(f"{trace_id}.tag.{idx}")
        )
        if not obs_id:
            continue
        observations.append(
            {
                "id": obs_id,
                "trace_id": trace_id,
                "name": name,
                "metadata": {
                    "tenant_id": trace_meta.get("tenant_id"),
                    "project_id": trace_meta.get("project_id"),
                    "graph_id": trace_meta.get("graph_id"),
                    "thread_id": trace_meta.get("thread_id"),
                    "run_id": trace_meta.get("run_id"),
                    "request_id": trace_meta.get("request_id"),
                    "platform_trace_id": trace_meta.get("platform_trace_id"),
                    **meta,
                    "event": name,
                },
            }
        )
    truncated = tags.get("runtime.diag.events_truncated") == "1"
    return observations, truncated


def _query_mlflow_sync(expected: dict) -> dict:
    import mlflow

    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "").strip()
    client = mlflow.tracking.MlflowClient(tracking_uri=tracking_uri)

    exp_names = [f"project-{expected['project_id']}"]
    default_exp = os.getenv(
        "MLFLOW_EXPERIMENT_NAME", "ai-agent-platform-traces"
    ).strip()
    if default_exp and default_exp not in exp_names:
        exp_names.append(default_exp)

    exp_ids: list[str] = []
    for name in exp_names:
        exp = client.get_experiment_by_name(name)
        if exp is not None and exp.experiment_id not in exp_ids:
            exp_ids.append(exp.experiment_id)
    if not exp_ids:
        return empty_diagnostics("not_recorded")

    thread_id = expected["thread_id"]
    filter_string = (
        f"metadata.`mlflow.trace.session` = '{thread_id}'"
        if _identifier(thread_id) and "'" not in thread_id
        else None
    )
    # Keep metadata search lightweight (include_spans=False) to avoid downloading huge span trees across sibling runs.
    try:
        page = client.search_traces(
            locations=exp_ids,
            filter_string=filter_string,
            order_by=["timestamp DESC"],
            max_results=50,
            include_spans=False,
        )
    except Exception:
        page = client.search_traces(
            locations=exp_ids,
            max_results=50,
            include_spans=False,
        )

    matched = [trace for trace in page if _mlflow_trace_matches(trace.info, expected)]
    if not matched:
        result = empty_diagnostics("not_recorded")
        result["truncated"] = bool(getattr(page, "token", None))
        return result

    observations: list[dict] = []
    loaded_traces: list[tuple[Any, list[Any], dict[str, Any]]] = []
    tag_truncated = False
    for trace in matched[:50]:
        trace_id = getattr(trace.info, "trace_id", None)
        trace_meta = _mlflow_trace_meta(trace.info)
        tag_obs, is_tag_trunc = (
            _mlflow_tag_observations(trace.info, trace_id, trace_meta)
            if trace_id
            else ([], False)
        )
        if tag_obs:
            tag_truncated |= is_tag_trunc
            observations.extend(tag_obs)
            loaded_traces.append((trace, [], trace_meta))
            continue

        spans = list(getattr(getattr(trace, "data", None), "spans", None) or [])
        if not spans and trace_id:
            try:
                full = client.get_trace(trace_id)
                trace = full
                spans = list(getattr(getattr(full, "data", None), "spans", None) or [])
            except Exception:
                # Fall back to TraceInfo-level projection when full span fetch times out or fails.
                spans = []
        loaded_traces.append((trace, spans, trace_meta))
        for span in spans:
            span_id = getattr(span, "span_id", None) or "sp"
            for idx, event in enumerate(getattr(span, "events", None) or ()):
                name = getattr(event, "name", None)
                if name not in _EVENTS:
                    continue
                attrs = dict(getattr(event, "attributes", None) or {})
                if attrs.get("schema_version") != 1:
                    continue
                obs_id = (
                    _identifier(attrs.get("observation_id"))
                    or _identifier(attrs.get("event_id"))
                    or _identifier(f"{span_id}.{idx}")
                )
                if not obs_id or not trace_id:
                    continue
                observations.append(
                    {
                        "id": obs_id,
                        "trace_id": trace_id,
                        "name": name,
                        "metadata": {
                            "tenant_id": trace_meta.get("tenant_id"),
                            "project_id": trace_meta.get("project_id"),
                            "graph_id": trace_meta.get("graph_id"),
                            "thread_id": trace_meta.get("thread_id"),
                            "run_id": trace_meta.get("run_id"),
                            "request_id": trace_meta.get("request_id"),
                            "platform_trace_id": trace_meta.get("platform_trace_id"),
                            **attrs,
                            "event": name,
                        },
                    }
                )

    truncated = (len(matched) > 50) or tag_truncated
    result = (
        _project(
            observations,
            expected,
            truncated=truncated,
            provider_override="mlflow",
        )
        if observations
        else {**empty_diagnostics("not_recorded"), "truncated": truncated}
    )

    if len(loaded_traces) == 1:
        trace, spans, trace_meta = loaded_traces[0]
        trace_id = _identifier(getattr(trace.info, "trace_id", None))
        if result["trace"] is None and trace_id:
            result["trace"] = {"provider": "mlflow", "trace_id": trace_id, "url": None}
        if result["correlation"]["execution_request_id"] is None:
            result["correlation"]["execution_request_id"] = _identifier(
                trace_meta.get("request_id")
            )
        if result["correlation"]["platform_trace_id"] is None:
            result["correlation"]["platform_trace_id"] = _identifier(
                trace_meta.get("platform_trace_id")
            )
        if not result["graph_executions"]:
            outcome = _mlflow_trace_outcome(trace.info)
            if outcome and trace_id:
                result["graph_executions"].append(
                    {
                        "observation_id": trace_id,
                        "duration_ms": _mlflow_root_duration_ms(trace.info, spans),
                        "outcome": outcome,
                        "error_code": None,
                    }
                )
        if not observations:
            result["availability"] = "partial"
            result["unavailable_reason"] = None

    return result


async def _query_langfuse_run_diagnostics(expected: dict) -> dict:
    if _client is None:
        return empty_diagnostics("not_configured")
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
                    session_id=expected["thread_id"],
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
            return _project(
                observations,
                expected,
                truncated=truncated,
                provider_override="langfuse",
            )
    except Exception:
        return empty_diagnostics("backend_unavailable")


async def _query_mlflow_run_diagnostics(expected: dict) -> dict:
    if not _mlflow_configured():
        return empty_diagnostics("not_configured")
    try:
        async with asyncio.timeout(8):
            return await asyncio.to_thread(_query_mlflow_sync, expected)
    except Exception:
        return empty_diagnostics("backend_unavailable")


async def query_run_diagnostics(
    *, tenant_id: str, project_id: str, graph_id: str, thread_id: str, run_id: str
) -> dict:
    expected = {
        "tenant_id": tenant_id,
        "project_id": project_id,
        "graph_id": graph_id,
        "thread_id": thread_id,
        "run_id": run_id,
    }
    from runtime_service.observability.mlflow_tracer import get_tracing_provider

    provider = get_tracing_provider()
    if provider == "mlflow":
        return await _query_mlflow_run_diagnostics(expected)
    if provider == "none":
        return empty_diagnostics("not_configured")
    if provider == "both":
        langfuse_result = (
            await _query_langfuse_run_diagnostics(expected)
            if _client is not None
            else empty_diagnostics("not_configured")
        )
        if langfuse_result["availability"] in {"available", "partial"}:
            return langfuse_result
        if _mlflow_configured():
            mlflow_result = await _query_mlflow_run_diagnostics(expected)
            if mlflow_result["availability"] != "not_configured":
                return mlflow_result
        return langfuse_result
    return await _query_langfuse_run_diagnostics(expected)


__all__ = ["diagnostics_client_lifespan", "query_run_diagnostics"]
