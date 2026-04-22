from __future__ import annotations

from collections import defaultdict
from threading import Lock


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
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
        status_family = f"{int(status_code / 100)}xx"
        failed = status_code >= 400

        with self._lock:
            self._requests_total += 1
            if failed:
                self._requests_failed += 1
            self._request_duration_total_ms += duration_ms
            self._request_duration_max_ms = max(self._request_duration_max_ms, duration_ms)
            self._status_buckets[status_family] += 1
            self._method_buckets[method.upper()] += 1

            path_metrics = self._path_buckets[path]
            path_metrics["count"] += 1
            path_metrics["duration_total_ms"] += duration_ms
            path_metrics["duration_max_ms"] = max(path_metrics["duration_max_ms"], duration_ms)
            if failed:
                path_metrics["failed"] += 1

    def snapshot_http_metrics(self, *, top_paths_limit: int = 10) -> dict[str, object]:
        with self._lock:
            total = self._requests_total
            failed = self._requests_failed
            avg_duration_ms = round(self._request_duration_total_ms / total, 2) if total else 0.0
            failure_rate = round(failed / total, 4) if total else 0.0

            top_paths = sorted(
                (
                    {
                        "path": path,
                        "count": int(metrics["count"]),
                        "failed": int(metrics["failed"]),
                        "failure_rate": round(
                            metrics["failed"] / metrics["count"], 4
                        )
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


metrics_registry = MetricsRegistry()
