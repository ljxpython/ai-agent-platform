from __future__ import annotations

import logging
import unittest

from starlette.testclient import TestClient

from runtime_service.observability.context import (
    RuntimeTraceContext,
    parse_or_create_traceparent,
    reset_current_trace_context,
    set_current_trace_context,
)
from runtime_service.observability.diagnostics import trace_id_for
from runtime_service.observability.logging import RuntimeTraceLogFilter, format_log_line
from runtime_service.webapp import app


class TestRuntimeTracePropagation(unittest.TestCase):
    def test_parse_or_create_traceparent(self) -> None:
        upstream_trace = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        ctx = parse_or_create_traceparent(upstream_trace)

        self.assertEqual(ctx.trace_id, "4bf92f3577b34da6a3ce929d0e0e4736")
        self.assertEqual(ctx.parent_span_id, "00f067aa0ba902b7")
        self.assertEqual(len(ctx.span_id), 16)
        self.assertTrue(
            ctx.traceparent.startswith("00-4bf92f3577b34da6a3ce929d0e0e4736-")
        )

    def test_fallback_when_invalid(self) -> None:
        ctx = parse_or_create_traceparent("invalid-header")
        self.assertEqual(len(ctx.trace_id), 32)
        self.assertIsNone(ctx.parent_span_id)
        self.assertEqual(len(ctx.span_id), 16)

    def test_trace_id_for_prefers_platform_trace_id(self) -> None:
        upstream_trace = "a1b2c3d4e5f60718293a4b5c6d7e8f90"
        metadata = {
            "tenant_id": "t",
            "project_id": "p",
            "run_id": "11111111-1111-1111-1111-111111111111",
            "platform_trace_id": upstream_trace,
        }
        resolved = trace_id_for(metadata)
        self.assertEqual(resolved, upstream_trace)

    def test_logging_filter_enrichment(self) -> None:
        ctx = RuntimeTraceContext(
            trace_id="12345678901234567890123456789012",
            span_id="abcdef1234567890",
            parent_span_id=None,
            traceparent="00-12345678901234567890123456789012-abcdef1234567890-01",
        )
        token = set_current_trace_context(ctx)
        try:
            logger = logging.getLogger("test_rt_logger")
            record = logger.makeRecord(
                name="test",
                level=logging.INFO,
                fn="test.py",
                lno=1,
                msg="runtime run",
                args=(),
                exc_info=None,
            )
            f = RuntimeTraceLogFilter()
            f.filter(record)

            self.assertEqual(getattr(record, "service", ""), "runtime-service")
            self.assertEqual(getattr(record, "trace_id", ""), ctx.trace_id)
            self.assertEqual(getattr(record, "span_id", ""), ctx.span_id)

            formatted = format_log_line("Agent started", extra={"graph": "agent"})
            self.assertIn(
                "[runtime-service][trace_id=12345678901234567890123456789012]",
                formatted,
            )
            self.assertIn("graph=agent", formatted)
        finally:
            reset_current_trace_context(token)

    def test_middleware_traceparent_response_headers(self) -> None:
        client = TestClient(app)
        upstream_trace = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
        res = client.get("/metrics", headers={"traceparent": upstream_trace})
        self.assertEqual(res.status_code, 200)
        self.assertIn("traceparent", res.headers)
        self.assertTrue(
            res.headers["traceparent"].startswith(
                "00-4bf92f3577b34da6a3ce929d0e0e4736-"
            )
        )
        self.assertEqual(
            res.headers.get("x-trace-id"), "4bf92f3577b34da6a3ce929d0e0e4736"
        )


if __name__ == "__main__":
    unittest.main()
