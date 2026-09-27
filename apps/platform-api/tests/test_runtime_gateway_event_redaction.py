from __future__ import annotations

import asyncio
import unittest
from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import patch

import anyio
import anyio.lowlevel
from platform_api.modules.runtime_gateway.presentation.http import (
    RuntimeStreamingResponse,
    _redact_protocol_event_stream,
    _runtime_sse_response,
)
from starlette.requests import Request


async def _chunks(*values: bytes) -> AsyncIterator[bytes]:
    for value in values:
        yield value


class RuntimeGatewayEventRedactionTest(unittest.IsolatedAsyncioTestCase):
    async def test_disconnect_and_unknown_cancel_have_distinct_close_reasons(self):
        async def pending():
            yield b": heartbeat\n\n"
            await asyncio.Event().wait()

        for disconnected, expected in ((True, "client_disconnect"), (False, "unknown")):
            reasons = []
            response = RuntimeStreamingResponse(
                pending(), on_close=lambda reason, _: reasons.append(reason)
            )

            async def send(message):
                if message["type"] == "http.response.body":
                    if disconnected:
                        response._client_disconnected = True
                    raise asyncio.CancelledError()

            with self.assertRaises(asyncio.CancelledError):
                await response.stream_response(send)
            self.assertEqual(reasons, [expected])

    async def test_upstream_error_and_send_disconnect_close_once(self):
        async def broken():
            yield b"data: 1\n\n"
            raise RuntimeError("upstream failed")

        for send_error, expected in (
            (False, "upstream_error"),
            (True, "client_disconnect"),
        ):
            reasons = []
            response = RuntimeStreamingResponse(
                broken(), on_close=lambda reason, _: reasons.append(reason)
            )

            async def send(message):
                if send_error and message["type"] == "http.response.body":
                    raise BrokenPipeError()

            with self.assertRaises((RuntimeError, BrokenPipeError)):
                await response.stream_response(send)
            self.assertEqual(reasons, [expected])

    async def test_stream_callbacks_use_error_response_request_id(self):
        request = Request(
            {"type": "http", "method": "POST", "path": "/stream", "headers": []}
        )
        request.state.platform_context = SimpleNamespace(
            request=SimpleNamespace(request_id="request-1", trace_id="request-1"),
            project=SimpleNamespace(project_id="project-1"),
        )
        request.state.audit_metadata = {"run_id": "run-1"}
        events = []
        response = _runtime_sse_response(
            request,
            _chunks(b"data: invalid-json\n\n"),
            thread_id="thread-1",
            stream_kind="run",
            protocol=False,
        )

        async def send(message):
            return None

        with patch(
            "platform_api.modules.runtime_gateway.presentation.http.log_event",
            side_effect=lambda _logger, event, **fields: events.append((event, fields)),
        ):
            await response.stream_response(send)
        self.assertEqual(
            [event for event, _ in events],
            ["runtime.stream.opened", "runtime.stream.closed"],
        )
        self.assertEqual({fields["request_id"] for _, fields in events}, {"request-1"})
        self.assertEqual({fields["run_id"] for _, fields in events}, {"run-1"})
        self.assertEqual(events[-1][1]["close_reason"], "frame_rejected")

        events.clear()
        response = _runtime_sse_response(
            request,
            _chunks(b"data: 1\n\n"),
            thread_id="thread-1",
            stream_kind="thread",
            protocol=False,
        )

        async def reject_start(message):
            if message["type"] == "http.response.start":
                raise RuntimeError("send failed")

        with (
            patch(
                "platform_api.modules.runtime_gateway.presentation.http.log_event",
                side_effect=lambda _logger, event, **fields: events.append(
                    (event, fields)
                ),
            ),
            self.assertRaisesRegex(RuntimeError, "send failed"),
        ):
            await response.stream_response(reject_start)
        self.assertEqual(events, [])

    async def test_disconnect_closes_suspended_upstream_before_response_returns(self):
        closed = []

        async def upstream():
            try:
                yield b": heartbeat\n\n"
            finally:
                await anyio.lowlevel.checkpoint()
                closed.append(True)

        with anyio.CancelScope() as scope:

            async def send(message):
                if message["type"] == "http.response.body":
                    scope.cancel()
                    await anyio.lowlevel.checkpoint()

            response = RuntimeStreamingResponse(
                _redact_protocol_event_stream(upstream())
            )
            await response.stream_response(send)
        self.assertEqual(closed, [True])

    async def test_redacts_sensitive_fields_without_changing_protocol_shape(
        self,
    ) -> None:
        stream = _redact_protocol_event_stream(
            _chunks(
                b'data: {"seq":7,"method":"messages","params":{"data":{"token":"secret","x-runtime-run-read-authorization":"Bearer secret","text":"visible"}}}\n\n'
            )
        )

        result = [chunk async for chunk in stream]

        self.assertEqual(
            result,
            [
                b'data: {"seq":7,"method":"messages","params":{"data":{"token":"[REDACTED]","x-runtime-run-read-authorization":"[REDACTED]","text":"visible"}}}\n\n'
            ],
        )

    async def test_closes_on_non_json_without_leaking_payload(self) -> None:
        reasons = []
        stream = _redact_protocol_event_stream(
            _chunks(b"event: keep\ndata: fixture-secret", b"\n\n", b": heartbeat\n\n"),
            on_close=reasons.append,
        )

        result = [chunk async for chunk in stream]

        self.assertEqual(result, [])
        self.assertEqual(reasons, ["frame_rejected"])

    async def test_every_chunk_boundary_preserves_utf8_crlf_and_multiline_data(self):
        raw = (
            'id: 42\r\nevent: values\r\ndata: {"method":"values","params":{"namespace":[],"data":'
            '{"context":{"runtime_model_ref":"private"},\r\n'
            'data: "text":"金额 token 原文"}}}\r\n\r\n: heartbeat\r\n\r\n'
        ).encode()
        expected = (
            'id: 42\nevent: values\ndata: {"method":"values","params":{"namespace":[],"data":{"context":{},"text":"金额 token 原文"}}}\n\n'
            ": heartbeat\n\n"
        ).encode()
        for boundary in range(len(raw)):
            result = b"".join(
                [
                    part
                    async for part in _redact_protocol_event_stream(
                        _chunks(raw[:boundary], raw[boundary:])
                    )
                ]
            )
            self.assertEqual(result, expected, boundary)

    async def test_frame_limit_is_per_frame_and_run_scalars_are_allowed(self):
        payload = b"x" * (8 * 1024 * 1024 - len(b'data: ""'))
        valid = b'data: "' + payload + b'"\n\n'
        self.assertEqual(len(valid) - 2, 8 * 1024 * 1024)
        accepted = b"".join(
            [
                part
                async for part in _redact_protocol_event_stream(
                    _chunks(valid + b"data: 7\n\n"),
                    protocol=False,
                )
            ]
        )
        self.assertIn(b"data: 7\n\n", accepted)
        rejected = b"".join(
            [
                part
                async for part in _redact_protocol_event_stream(
                    _chunks(valid[:-2] + b"x\n\n"),
                    protocol=False,
                )
            ]
        )
        self.assertEqual(rejected, b"")

    async def test_rejects_truncated_utf8_and_protocol_array_but_keeps_run_array(self):
        for raw in (b'data: {"method":"values"}', b'data: "\xff"\n\n', b"data: []\n\n"):
            reasons = []
            result = b"".join(
                [
                    part
                    async for part in _redact_protocol_event_stream(
                        _chunks(raw),
                        on_close=reasons.append,
                    )
                ]
            )
            self.assertEqual(result, b"")
            self.assertEqual(reasons, ["frame_rejected"])
        reasons = []
        result = b"".join(
            [
                part
                async for part in _redact_protocol_event_stream(
                    _chunks(b'data: [{"token":"fixture-secret"}]\n\nevent: end\n\n'),
                    protocol=False,
                    on_close=reasons.append,
                )
            ]
        )
        self.assertEqual(result, b'data: [{"token":"[REDACTED]"}]\n\nevent: end\n\n')
        self.assertEqual(reasons, ["eof"])

    async def test_sanitizes_comment_and_closes_upstream_once_on_bad_frame(self):
        closes = []
        reasons = []

        async def upstream():
            try:
                yield b": fixture-secret\n\n"
                yield b"data: not-json\n\n"
            finally:
                closes.append(True)

        result = b"".join(
            [
                part
                async for part in _redact_protocol_event_stream(
                    upstream(),
                    on_close=reasons.append,
                )
            ]
        )
        self.assertEqual(result, b": heartbeat\n\n")
        self.assertEqual(closes, [True])
        self.assertEqual(reasons, ["frame_rejected"])
