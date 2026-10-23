from __future__ import annotations

import time
import unittest

from fastapi import FastAPI, Response
from prometheus_client import CONTENT_TYPE_LATEST
from starlette.testclient import TestClient

from runtime_service.observability.metrics import (
    RuntimeMetricsRegistry,
    runtime_metrics,
)
from runtime_service.webapp import app


class RuntimePrometheusMetricsTest(unittest.TestCase):
    def test_metrics_route_registered_on_webapp(self) -> None:
        route_paths = [getattr(route, "path", None) for route in app.routes]
        self.assertIn("/metrics", route_paths)

    def test_metrics_endpoint_exposed(self) -> None:
        application = FastAPI()

        @application.get("/metrics")
        async def metrics():
            return Response(
                content=runtime_metrics.render_prometheus_metrics(),
                media_type=CONTENT_TYPE_LATEST,
            )

        client = TestClient(application)
        response = client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/plain", response.headers.get("content-type", ""))
        body = response.text
        self.assertIn("runtime_agent_runs_total", body)
        self.assertIn("runtime_agent_run_duration_seconds", body)
        self.assertIn("runtime_model_calls_total", body)
        self.assertIn("runtime_loop_detection_tripped_total", body)
        self.assertIn("runtime_sandbox_containers_active", body)

    def test_record_agent_run(self) -> None:
        registry = RuntimeMetricsRegistry()
        registry.record_agent_run(
            graph_id="research_agent",
            outcome="success",
            duration_seconds=3.45,
        )
        rendered = registry.render_prometheus_metrics().decode()
        self.assertIn(
            'runtime_agent_runs_total{graph_id="research_agent",outcome="success"} 1.0',
            rendered,
        )
        self.assertIn(
            'runtime_agent_run_duration_seconds_count{graph_id="research_agent"} 1.0',
            rendered,
        )

    def test_record_model_call(self) -> None:
        registry = RuntimeMetricsRegistry()
        registry.record_model_call(
            provider="deepseek",
            model="deepseek-v4.1-flash",
            outcome="success",
        )
        registry.record_model_call(
            provider="deepseek",
            model="deepseek-v4.1-flash",
            outcome="failed",
        )
        rendered = registry.render_prometheus_metrics().decode()
        self.assertIn(
            'runtime_model_calls_total{model="deepseek-v4.1-flash",outcome="success",provider="deepseek"} 1.0',
            rendered,
        )
        self.assertIn(
            'runtime_model_calls_total{model="deepseek-v4.1-flash",outcome="failed",provider="deepseek"} 1.0',
            rendered,
        )

    def test_record_loop_detection(self) -> None:
        registry = RuntimeMetricsRegistry()
        registry.record_loop_detection(code="tool_loop_approaching")
        registry.record_loop_detection(code="tool_loop_reached")
        rendered = registry.render_prometheus_metrics().decode()
        self.assertIn(
            'runtime_loop_detection_tripped_total{code="tool_loop_approaching"} 1.0',
            rendered,
        )
        self.assertIn(
            'runtime_loop_detection_tripped_total{code="tool_loop_reached"} 1.0',
            rendered,
        )

    def test_set_active_sandboxes(self) -> None:
        registry = RuntimeMetricsRegistry()
        registry.set_active_sandboxes(4)
        rendered = registry.render_prometheus_metrics().decode()
        self.assertIn("runtime_sandbox_containers_active 4.0", rendered)

        registry.set_active_sandboxes(0)
        rendered = registry.render_prometheus_metrics().decode()
        self.assertIn("runtime_sandbox_containers_active 0.0", rendered)

    def test_fail_soft(self) -> None:
        registry = RuntimeMetricsRegistry()
        # Invalid inputs must not raise
        try:
            registry.record_agent_run(
                graph_id=None, outcome=None, duration_seconds="bad"
            )  # type: ignore
            registry.record_model_call(provider=None, model=None, outcome=None)  # type: ignore
            registry.record_loop_detection(code=None)  # type: ignore
            registry.set_active_sandboxes("invalid")  # type: ignore
        except Exception as exc:
            self.fail(f"runtime_metrics must be fail-soft, but raised {exc}")

    def test_performance(self) -> None:
        registry = RuntimeMetricsRegistry()
        count = 1000
        start = time.perf_counter()
        for _ in range(count):
            registry.record_agent_run(
                graph_id="agent", outcome="success", duration_seconds=1.2
            )
            registry.record_model_call(
                provider="openai", model="gpt-4o", outcome="success"
            )
        elapsed = time.perf_counter() - start
        avg_ms = (elapsed / (count * 2)) * 1000
        self.assertLess(
            avg_ms, 0.05, f"Avg call took {avg_ms:.4f}ms, expected < 0.05ms"
        )
