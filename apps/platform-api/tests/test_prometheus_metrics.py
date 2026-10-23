from __future__ import annotations

import time
import unittest

from fastapi.testclient import TestClient

from platform_api.core.observability.metrics import (
    MetricsRegistry,
    metrics_registry,
    normalize_metric_path,
)
from platform_api.main import create_app


class PrometheusMetricsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app()
        settings = self.app.state.settings
        settings.platform_db_enabled = False
        settings.api_docs_enabled = False
        settings.auth_required = False
        self.client = TestClient(self.app)

    def test_normalize_metric_path(self) -> None:
        self.assertEqual(
            normalize_metric_path(
                "/api/projects/c0a80101-0000-0000-0000-000000000001/runs"
            ),
            "/api/projects/{id}/runs",
        )
        self.assertEqual(
            normalize_metric_path("/api/v1/threads/12345/messages/67890"),
            "/api/v1/threads/{id}/messages/{id}",
        )
        self.assertEqual(
            normalize_metric_path("/api/identity/session"),
            "/api/identity/session",
        )

    def test_metrics_endpoints_exposed_and_format_valid(self) -> None:
        # Trigger an API call so metrics are generated
        response = self.client.get("/_system/probes/live")
        self.assertEqual(response.status_code, 200)

        # 1. Test root /metrics endpoint
        metrics_resp = self.client.get("/metrics")
        self.assertEqual(metrics_resp.status_code, 200)
        self.assertIn("text/plain", metrics_resp.headers["content-type"])
        body = metrics_resp.text
        self.assertIn("platform_api_http_requests_total", body)
        self.assertIn("platform_api_http_request_duration_seconds", body)
        self.assertIn("platform_api_active_requests", body)
        self.assertIn('path="/_system/probes/live"', body)

        # 2. Test /_system/prometheus endpoint
        prom_resp = self.client.get("/_system/prometheus")
        self.assertEqual(prom_resp.status_code, 200)
        self.assertIn("platform_api_http_requests_total", prom_resp.text)

    def test_backward_compatible_system_metrics_json(self) -> None:
        self.client.get("/_system/probes/live")
        snapshot = metrics_registry.snapshot_http_metrics()
        self.assertIn("total", snapshot)
        self.assertIn("failed", snapshot)
        self.assertIn("avg_duration_ms", snapshot)
        self.assertIn("top_paths", snapshot)
        self.assertGreaterEqual(snapshot["total"], 1)

    def test_metrics_fail_soft(self) -> None:
        # Pass completely invalid types; record_http_request must catch and not raise
        registry = MetricsRegistry()
        try:
            registry.record_http_request(
                method="GET",
                path="/test",
                status_code=None,  # type: ignore[arg-type]
                duration_ms="invalid",  # type: ignore[arg-type]
            )
        except Exception as exc:
            self.fail(f"record_http_request should be fail-soft, but raised {exc}")

    def test_metrics_recording_performance(self) -> None:
        registry = MetricsRegistry()
        count = 1000
        start = time.perf_counter()
        for i in range(count):
            registry.record_http_request(
                method="GET",
                path=f"/api/items/{i}",
                status_code=200,
                duration_ms=1.5,
            )
        elapsed = time.perf_counter() - start
        avg_ms_per_call = (elapsed / count) * 1000
        # Single call must be significantly less than 0.05ms (usually < 0.01ms)
        self.assertLess(avg_ms_per_call, 0.05, f"Avg call took {avg_ms_per_call:.4f}ms")
