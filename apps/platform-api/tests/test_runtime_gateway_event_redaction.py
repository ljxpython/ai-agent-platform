from __future__ import annotations

import unittest
from collections.abc import AsyncIterator

from platform_api.modules.runtime_gateway.presentation.http import (
    _redact_protocol_event_stream,
)


async def _chunks(*values: bytes) -> AsyncIterator[bytes]:
    for value in values:
        yield value


class RuntimeGatewayEventRedactionTest(unittest.IsolatedAsyncioTestCase):
    async def test_redacts_sensitive_fields_without_changing_protocol_shape(
        self,
    ) -> None:
        stream = _redact_protocol_event_stream(
            _chunks(
                b'data: {"seq":7,"method":"messages","params":{"data":{"token":"secret","text":"visible"}}}\n\n'
            )
        )

        result = [chunk async for chunk in stream]

        self.assertEqual(
            result,
            [
                b'data: {"seq":7,"method":"messages","params":{"data":{"token":"[REDACTED]","text":"visible"}}}\n\n'
            ],
        )

    async def test_preserves_fragmented_and_non_json_sse_frames(self) -> None:
        stream = _redact_protocol_event_stream(
            _chunks(b"event: keep\ndata: not-json", b"\n\n", b": heartbeat\n\n")
        )

        result = [chunk async for chunk in stream]

        self.assertEqual(
            result, [b"event: keep\ndata: not-json\n\n", b": heartbeat\n\n"]
        )

    async def test_every_chunk_boundary_preserves_utf8_crlf_and_multiline_data(self):
        raw = (
            'id: 42\r\nevent: values\r\ndata: {"context":{"runtime_model_ref":"private"},\r\n'
            'data: "text":"金额 token 原文"}\r\n\r\n: heartbeat\r\n\r\n'
        ).encode()
        expected = (
            'id: 42\nevent: values\ndata: {"context":{},"text":"金额 token 原文"}\n\n'
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
