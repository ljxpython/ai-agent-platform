from __future__ import annotations

import logging
from threading import Lock

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

logger = logging.getLogger(__name__)


class RuntimeMetricsRegistry:
    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self._lock = Lock()
        self._registry = registry or CollectorRegistry(auto_describe=True)

        self.agent_runs_total = Counter(
            "runtime_agent_runs_total",
            "Total agent graph executions",
            ["graph_id", "outcome"],
            registry=self._registry,
        )
        self.agent_run_duration_seconds = Histogram(
            "runtime_agent_run_duration_seconds",
            "Agent graph execution duration in seconds",
            ["graph_id"],
            buckets=(
                0.5,
                1.0,
                2.5,
                5.0,
                10.0,
                15.0,
                30.0,
                60.0,
                120.0,
                300.0,
            ),
            registry=self._registry,
        )
        self.model_calls_total = Counter(
            "runtime_model_calls_total",
            "Total LLM invocations",
            ["provider", "model", "outcome"],
            registry=self._registry,
        )
        self.loop_detection_tripped_total = Counter(
            "runtime_loop_detection_tripped_total",
            "Total loop detection triggers",
            ["code"],
            registry=self._registry,
        )
        self.sandbox_containers_active = Gauge(
            "runtime_sandbox_containers_active",
            "Active sandbox docker containers count",
            registry=self._registry,
        )

    def record_agent_run(
        self,
        *,
        graph_id: str,
        outcome: str,
        duration_seconds: float | None = None,
    ) -> None:
        try:
            self.agent_runs_total.labels(
                graph_id=graph_id or "unknown",
                outcome=outcome or "unknown",
            ).inc()
            if duration_seconds is not None and duration_seconds >= 0:
                self.agent_run_duration_seconds.labels(
                    graph_id=graph_id or "unknown",
                ).observe(duration_seconds)
        except Exception:
            logger.warning("Failed to record agent run metric", exc_info=True)

    def record_model_call(
        self,
        *,
        provider: str,
        model: str,
        outcome: str,
    ) -> None:
        try:
            self.model_calls_total.labels(
                provider=provider or "unknown",
                model=model or "unknown",
                outcome=outcome or "unknown",
            ).inc()
        except Exception:
            logger.warning("Failed to record model call metric", exc_info=True)

    def record_loop_detection(self, *, code: str) -> None:
        try:
            self.loop_detection_tripped_total.labels(
                code=code or "unknown",
            ).inc()
        except Exception:
            logger.warning("Failed to record loop detection metric", exc_info=True)

    def set_active_sandboxes(self, count: int) -> None:
        try:
            self.sandbox_containers_active.set(max(0, count))
        except Exception:
            logger.warning("Failed to set active sandboxes metric", exc_info=True)

    def render_prometheus_metrics(self) -> bytes:
        return generate_latest(self._registry)


runtime_metrics = RuntimeMetricsRegistry()
