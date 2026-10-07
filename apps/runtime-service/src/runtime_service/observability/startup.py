"""Construction-local timing; no Thread cache or graph execution proxy."""

from __future__ import annotations

import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from runtime_service.observability.diagnostics import (
    diagnostic_metadata,
    log_diagnostic,
)
from runtime_service.observability.errors import error_type, execution_outcome
from runtime_service.observability.langfuse import record_diagnostic_event
from runtime_service.observability.otel import initialize_otel
from runtime_service.runtime.auth import VerifiedDelegation

PHASE_NAMES = frozenset(
    {
        "factory.context_resolution",
        "factory.memory_policy",
        "factory.mcp_tools",
        "factory.model_connection",
        "factory.model_build",
        "factory.workspace",
        "factory.agent_compile",
        "node.model_prepare",
    }
)


def _utc(ns: int) -> str:
    return (
        datetime.fromtimestamp(ns / 1_000_000_000, UTC)
        .isoformat()
        .replace("+00:00", "Z")
    )


class StartupDiagnostics:
    def __init__(self, graph_id: str) -> None:
        self.metadata: dict[str, Any] = {"graph_id": graph_id}
        self.phases: list[dict[str, Any]] = []
        self.started_ns = time.time_ns()
        self._started = time.monotonic_ns()
        self.ended_ns: int | None = None
        self.execution_span = None
        self._authorized = False
        self._finished = False
        self._ordinal = 0

    def __enter__(self) -> StartupDiagnostics:
        return self

    def __exit__(self, _kind, error, _tb) -> None:
        try:
            self.finish(error)
        except Exception:
            pass

    def authorize(self, config: Mapping[str, Any], facts: VerifiedDelegation) -> None:
        self.metadata.update(
            diagnostic_metadata(config, self.metadata["graph_id"], facts)
        )
        self.metadata["factory_id"] = str(uuid4())
        self._authorized = True

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        if name not in PHASE_NAMES:
            raise ValueError("unknown startup phase")
        started_ns, monotonic = time.time_ns(), time.monotonic_ns()
        ordinal = self._ordinal
        self._ordinal += 1
        error = None
        try:
            yield
        except BaseException as exc:
            error = exc
            raise
        finally:
            outcome = (
                "completed"
                if error is None
                else "cancelled"
                if execution_outcome(error) == "cancelled"
                else "failed"
            )
            record = {
                "phase": name,
                "ordinal": ordinal,
                "outcome": outcome,
                "started_at": _utc(started_ns),
                "ended_at": _utc(time.time_ns()),
                "duration_ms": max(0, time.monotonic_ns() - monotonic) / 1_000_000,
            }
            if error is not None:
                record["error_type"] = error_type(error)
            if ordinal < 16:
                if self._finished:
                    self._emit("runtime.node.phase_completed", record)
                else:
                    self.phases.append(record)

    def _emit(self, event: str, record: Mapping[str, Any]) -> None:
        fields = {**self.metadata, **record}
        try:
            log_diagnostic(event, fields)
            record_diagnostic_event(event, fields)
        except Exception:
            pass

    def finish(self, error: BaseException | None = None) -> None:
        if self._finished:
            return
        self._finished = True
        self.ended_ns = time.time_ns()
        if not self._authorized:
            if error is not None:
                log_diagnostic(
                    "runtime.startup.completed",
                    {
                        "graph_id": self.metadata["graph_id"],
                        "outcome": execution_outcome(error),
                        "error_type": error_type(error),
                    },
                )
            return
        total = {
            "duration_ms": max(0, time.monotonic_ns() - self._started) / 1_000_000,
            "started_at": _utc(self.started_ns),
            "ended_at": _utc(self.ended_ns),
            "outcome": execution_outcome(error),
        }
        for record in self.phases:
            self._emit("runtime.startup.phase_completed", record)
        self._emit("runtime.startup.completed", total)
        if error is not None:
            self.export_otel(error)

    def export_otel(self, error: BaseException | None = None) -> None:
        try:
            self._export_otel(error)
        except Exception:
            pass

    def _export_otel(self, error: BaseException | None) -> None:
        provider = initialize_otel()
        if provider is None or not self.metadata.get("run_id") or not self._authorized:
            return
        if self.execution_span is not None:
            return
        tracer = provider.get_tracer("runtime-service")
        attributes = {
            key: value for key, value in self.metadata.items() if isinstance(value, str)
        }
        context = None
        if error is None:
            self.execution_span = tracer.start_span(
                "runtime.execution", start_time=self.started_ns, attributes=attributes
            )
            context = trace.set_span_in_context(self.execution_span)
        startup = tracer.start_span(
            "runtime.startup",
            start_time=self.started_ns,
            context=context,
            attributes=attributes,
        )
        child_context = trace.set_span_in_context(startup)
        for record in self.phases:
            span = tracer.start_span(
                record["phase"],
                context=child_context,
                start_time=int(
                    datetime.fromisoformat(record["started_at"]).timestamp() * 1e9
                ),
                attributes={
                    "duration_ms": record["duration_ms"],
                    "outcome": record["outcome"],
                },
            )
            span.end(
                end_time=int(
                    datetime.fromisoformat(record["ended_at"]).timestamp() * 1e9
                )
            )
        startup.set_status(
            Status(
                StatusCode.OK if error is None else StatusCode.ERROR,
                None if error is None else error_type(error),
            )
        )
        startup.end(end_time=self.ended_ns)


__all__ = ["StartupDiagnostics"]
