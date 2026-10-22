from __future__ import annotations

import logging
import unittest

from starlette.requests import Request

from platform_api.adapters.langgraph.runtime_client import LangGraphRuntimeClient
from platform_api.core.context.runtime import (
    build_request_context,
    reset_current_request_context,
    set_current_request_context,
)
from platform_api.core.observability.logging import (
    PlatformTraceLogFilter,
    _build_context_fields,
)


class TestTracePropagation(unittest.TestCase):
    def _create_scope(self, headers_dict: dict[str, str]) -> dict:
        raw_headers = [
            (k.lower().encode("latin1"), v.encode("latin1"))
            for k, v in headers_dict.items()
        ]
        return {
            "type": "http",
            "method": "POST",
            "path": "/api/test",
            "headers": raw_headers,
            "query_string": b"",
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 80),
        }

    def test_generate_w3c_traceparent_when_missing(self) -> None:
        scope = self._create_scope({})
        req = Request(scope)
        context = build_request_context(req)

        self.assertIsNotNone(context.request.traceparent)
        self.assertTrue(context.request.traceparent.startswith("00-"))
        parts = context.request.traceparent.split("-")
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[0], "00")
        self.assertEqual(parts[1], context.request.trace_id)
        self.assertEqual(parts[2], context.request.span_id)
        self.assertEqual(parts[3], "01")

    def test_inherit_w3c_traceparent_when_present(self) -> None:
        upstream_trace_id = "4bf92f3577b34da6a3ce929d0e0e4736"
        upstream_span_id = "00f067aa0ba902b7"
        traceparent = f"00-{upstream_trace_id}-{upstream_span_id}-01"

        scope = self._create_scope({"traceparent": traceparent})
        req = Request(scope)
        context = build_request_context(req)

        self.assertEqual(context.request.trace_id, upstream_trace_id)
        # Should generate a new local span_id
        self.assertNotEqual(context.request.span_id, upstream_span_id)
        self.assertTrue(
            context.request.traceparent.startswith(f"00-{upstream_trace_id}-")
        )

    def test_logging_context_enrichment(self) -> None:
        scope = self._create_scope({})
        req = Request(scope)
        context = build_request_context(req)
        token = set_current_request_context(context)

        try:
            fields = _build_context_fields()
            self.assertEqual(fields.get("service"), "platform-api")
            self.assertEqual(fields.get("trace_id"), context.request.trace_id)
            self.assertEqual(fields.get("span_id"), context.request.span_id)

            logger = logging.getLogger("test_trace_logger")
            record = logger.makeRecord(
                name="test",
                level=logging.INFO,
                fn="test.py",
                lno=1,
                msg="test message",
                args=(),
                exc_info=None,
            )
            log_filter = PlatformTraceLogFilter()
            log_filter.filter(record)

            self.assertEqual(getattr(record, "service", ""), "platform-api")
            self.assertEqual(getattr(record, "trace_id", ""), context.request.trace_id)
            self.assertEqual(getattr(record, "span_id", ""), context.request.span_id)
        finally:
            reset_current_request_context(token)

    def test_runtime_client_headers_auto_injection(self) -> None:
        scope = self._create_scope({})
        req = Request(scope)
        context = build_request_context(req)
        token = set_current_request_context(context)

        try:
            client = LangGraphRuntimeClient(
                base_url="http://127.0.0.1:8123", timeout_seconds=5
            )
            headers = client._headers()
            self.assertEqual(headers.get("traceparent"), context.request.traceparent)
            self.assertEqual(headers.get("x-trace-id"), context.request.trace_id)
            self.assertEqual(headers.get("x-request-id"), context.request.request_id)
        finally:
            reset_current_request_context(token)


if __name__ == "__main__":
    unittest.main()
