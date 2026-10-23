from __future__ import annotations

import logging
import re
from collections import defaultdict
from threading import Lock

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

logger = logging.getLogger(__name__)

_UUID_OR_HEX_RE = re.compile(r"/[0-9a-fA-F-]{8,}(?=/|$)")
_NUMERIC_ID_RE = re.compile(r"/\d+(?=/|$)")


def normalize_metric_path(path: str) -> str:
    """Normalize dynamic IDs in path to prevent cardinality explosion in Prometheus."""
    if not path:
        return "/"
    normalized = _UUID_OR_HEX_RE.sub("/{id}", path)
    return _NUMERIC_ID_RE.sub("/{id}", normalized)


class MetricsRegistry:
    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self._lock = Lock()
        self._registry = registry or CollectorRegistry(auto_describe=True)

        # Standard Prometheus Metrics
        self.http_requests_total = Counter(
            "platform_api_http_requests_total",
            "Total HTTP requests processed by platform-api",
            ["method", "path", "status"],
            registry=self._registry,
        )
        self.http_request_duration_seconds = Histogram(
            "platform_api_http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "path"],
            buckets=(
                0.005,
                0.01,
                0.025,
                0.05,
                0.075,
                0.1,
                0.25,
                0.5,
                0.75,
                1.0,
                2.5,
                5.0,
                10.0,
            ),
            registry=self._registry,
        )
        self.active_requests = Gauge(
            "platform_api_active_requests",
            "Number of active HTTP requests currently being handled",
            ["method"],
            registry=self._registry,
        )

        # Backward-compatible in-memory snapshot counters for /_system/metrics JSON
        self._requests_total = 0
        self._requests_failed = 0
        self._request_duration_total_ms = 0.0
        self._request_duration_max_ms = 0.0
        self._status_buckets: dict[str, int] = defaultdict(int)
        self._method_buckets: dict[str, int] = defaultdict(int)
        self._path_buckets: dict[str, dict[str, float]] = defaultdict(
            lambda: {
                "count": 0,
                "failed": 0,
                "duration_total_ms": 0.0,
                "duration_max_ms": 0.0,
            }
        )

    def record_http_request(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        try:
            status_family = f"{int(status_code / 100)}xx"
            failed = status_code >= 400
            duration_seconds = max(0.0, duration_ms / 1000.0)
            norm_path = normalize_metric_path(path)
            method_upper = method.upper()

            # Record Prometheus metrics
            self.http_requests_total.labels(
                method=method_upper,
                path=norm_path,
                status=str(status_code),
            ).inc()
            self.http_request_duration_seconds.labels(
                method=method_upper,
                path=norm_path,
            ).observe(duration_seconds)

            # Record backward-compatible snapshot metrics
            with self._lock:
                self._requests_total += 1
                if failed:
                    self._requests_failed += 1
                self._request_duration_total_ms += duration_ms
                self._request_duration_max_ms = max(
                    self._request_duration_max_ms, duration_ms
                )
                self._status_buckets[status_family] += 1
                self._method_buckets[method_upper] += 1

                path_metrics = self._path_buckets[path]
                path_metrics["count"] += 1
                path_metrics["duration_total_ms"] += duration_ms
                path_metrics["duration_max_ms"] = max(
                    path_metrics["duration_max_ms"], duration_ms
                )
                if failed:
                    path_metrics["failed"] += 1
        except Exception:  # Fail-soft: Metrics must never crash the HTTP request
            logger.warning("Failed to record metric", exc_info=True)

    def snapshot_http_metrics(self, *, top_paths_limit: int = 10) -> dict[str, object]:
        with self._lock:
            total = self._requests_total
            failed = self._requests_failed
            avg_duration_ms = (
                round(self._request_duration_total_ms / total, 2) if total else 0.0
            )
            failure_rate = round(failed / total, 4) if total else 0.0

            top_paths = sorted(
                (
                    {
                        "path": path,
                        "count": int(metrics["count"]),
                        "failed": int(metrics["failed"]),
                        "failure_rate": round(metrics["failed"] / metrics["count"], 4)
                        if metrics["count"]
                        else 0.0,
                        "avg_duration_ms": round(
                            metrics["duration_total_ms"] / metrics["count"], 2
                        )
                        if metrics["count"]
                        else 0.0,
                        "max_duration_ms": round(metrics["duration_max_ms"], 2),
                    }
                    for path, metrics in self._path_buckets.items()
                ),
                key=lambda item: (-item["count"], item["path"]),
            )[:top_paths_limit]

            return {
                "total": total,
                "failed": failed,
                "failure_rate": failure_rate,
                "avg_duration_ms": avg_duration_ms,
                "max_duration_ms": round(self._request_duration_max_ms, 2),
                "by_method": dict(sorted(self._method_buckets.items())),
                "by_status_family": dict(sorted(self._status_buckets.items())),
                "top_paths": top_paths,
            }

    def render_prometheus_metrics(self) -> bytes:
        return generate_latest(self._registry)


metrics_registry = MetricsRegistry()
