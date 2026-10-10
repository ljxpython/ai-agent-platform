"""Existing Langfuse SDK masking applies at a real local OTLP HTTP export."""

import gzip
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from langfuse._client.span_processor import LangfuseSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider

from runtime_service.observability.langfuse import _mask, _mask_spans


def test_sdk_http_payload_deletes_raw_input_output_exception_and_status():
    received = []
    canary = "TRACE_CANARY alice@example.test sk-" + "A" * 24

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers["Content-Length"]))
            received.append(
                gzip.decompress(body)
                if self.headers.get("Content-Encoding") == "gzip"
                else body
            )
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    exporter = OTLPSpanExporter(
        endpoint=f"http://127.0.0.1:{server.server_port}/v1/traces", timeout=3
    )
    processor = LangfuseSpanProcessor(
        public_key="synthetic",
        secret_key="synthetic",
        base_url="http://fixture.invalid",
        span_exporter=exporter,
        should_export_span=lambda _: True,
        mask_otel_spans=_mask_spans,
        flush_at=16,
        flush_interval=60,
    )
    provider = TracerProvider()
    provider.add_span_processor(processor)
    try:
        span = provider.get_tracer("privacy-test").start_span("synthetic-run")
        for key in (
            "langfuse.observation.input",
            "langfuse.observation.output",
            "langfuse.trace.input",
            "langfuse.trace.output",
            "exception.message",
            "exception.stacktrace",
            "langfuse.observation.status_message",
        ):
            span.set_attribute(
                key,
                json.dumps(
                    {"messages": [{"content": canary, "artifact": {"raw": canary}}]}
                ),
            )
        assert _mask(data=canary) == "[REDACTED]"
        assert canary not in str(
            _mask(data={"metadata": {"request_id": "request", "secret": canary}})
        )
        span.set_attribute("service.name", "runtime-service")
        span.end()
        assert provider.force_flush(5000)
        assert received and all(canary.encode() not in body for body in received)
        assert b"runtime-service" in received[0]
    finally:
        provider.shutdown()
        server.shutdown()
        server.server_close()
        thread.join(5)
