from __future__ import annotations

import asyncio
import json
import unittest
from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import patch

import anyio
import anyio.lowlevel
import pytest
from starlette.requests import Request

from platform_api.adapters.langgraph.sdk_client import redact_runtime_private_fields
from platform_api.core.runtime_contract import reject_private_runtime_state
from platform_api.modules.runtime_gateway.presentation.http import (
    RuntimeStreamingResponse,
    _redact_protocol_event_stream,
    _redact_runtime_private_fields,
    _redact_sse_frame,
    _runtime_sse_response,
)


async def _chunks(*values: bytes) -> AsyncIterator[bytes]:
    for value in values:
        yield value


def test_callback_source_is_private_in_nested_checkpoint_and_run_resources():
    value = {
        "kwargs": {"runtime_context_token": "SECRET", "input": {"x": 1}},
        "metadata": {
            "origin_ref": "PRIVATE",
            "callback_context": {"origin_ref": "PRIVATE"},
        },
        "config": {
            "configurable": {
                "langgraph_auth_user": {"callback_context": {"origin_ref": "PRIVATE"}}
            }
        },
    }
    safe = redact_runtime_private_fields(value)
    assert "SECRET" not in repr(safe) and "PRIVATE" not in repr(safe)
    assert safe["kwargs"]["input"] == {"x": 1}


@pytest.mark.parametrize("protocol", [False, True])
def test_stable_model_failure_survives_fragmented_stream_without_provider_text(
    protocol,
):
    async def run():
        code = "runtime.model.retry_exhausted"
        data = {
            "event": "lifecycle",
            "status": "error",
            "error": {
                "type": "RuntimeResolutionError",
                "message": code,
                "stack": "PRIVATE_PROVIDER_CANARY",
            },
        }
        payload = (
            {"method": "lifecycle", "params": {"namespace": [], "data": data}}
            if protocol
            else data
        )
        raw = ("event: lifecycle\ndata: " + json.dumps(payload) + "\n\n").encode()
        safe = b"".join(
            [
                part
                async for part in _redact_protocol_event_stream(
                    _chunks(raw[:19], raw[19:]), protocol=protocol
                )
            ]
        )
        assert code.encode() in safe and b"PRIVATE_PROVIDER_CANARY" not in safe
        unsafe = {
            "event": "lifecycle",
            "error": {"type": "RuntimeResolutionError", "message": code + " SECRET"},
        }
        assert "SECRET" not in str(redact_runtime_private_fields(unsafe))

    asyncio.run(run())


@pytest.mark.parametrize(
    "protocol,typed", [(False, False), (False, True), (True, True)]
)
def test_workspace_error_slots_survive_fragmented_native_events(protocol, typed):
    code = "runtime.workspace.execution_outcome_unknown"
    error = {
        "type": "RuntimeWorkspaceError",
        "message": code,
        "stack": "PRIVATE_CANARY",
    }
    original = {"error": "normal", "content": "USER_TEXT"}

    async def run():
        for method, data in (
            ("error", error),
            ("lifecycle", {"status": "error", "error": error}),
            ("tasks", {"id": "task", "error": error, "result": original}),
            (
                "debug",
                {
                    "type": "task_result",
                    "payload": {"error": error, "result": original},
                },
            ),
            (
                "checkpoints",
                {"tasks": [{"error": error}], "values": {"messages": [original]}},
            ),
        ):
            if method == "error" and typed:
                continue
            payload = (
                {
                    "method": method,
                    "seq": 3,
                    "params": {"namespace": ["tools:child"], "data": data},
                }
                if typed
                else data
            )
            raw = (
                f"event: {method}|child\nid: cursor-3\ndata: {json.dumps(payload)}\n\n"
            ).encode()
            result = b"".join(
                [
                    chunk
                    async for chunk in _redact_protocol_event_stream(
                        _chunks(raw[:17], raw[17:51], raw[51:]), protocol=protocol
                    )
                ]
            )
            assert code.encode() in result and b"PRIVATE_CANARY" not in result
            assert b"id: cursor-3" in result
            if method in {"tasks", "debug", "checkpoints"}:
                assert b"USER_TEXT" in result
            if typed:
                decoded = json.loads(result.decode().split("data: ")[1])
                assert decoded["seq"] == 3 and decoded["params"]["namespace"] == [
                    "tools:child"
                ]
        value = {
            "thread_id": "thread",
            "error": error,
            "tasks": [{"error": error}],
            "values": {"messages": [original]},
        }
        safe = _redact_runtime_private_fields([value, {"history": [value]}])
        assert "PRIVATE_CANARY" not in repr(safe) and safe[0]["values"]["messages"] == [
            original
        ]
        assert _redact_runtime_private_fields(safe) == safe

    asyncio.run(run())


class RuntimeGatewayEventRedactionTest(unittest.IsolatedAsyncioTestCase):
    async def test_native_task_error_is_safe_in_both_streams(self):
        data = {
            "id": "task-1",
            "name": "tools",
            "error": "TASK_EXCEPTION_CANARY",
            "result": {},
            "interrupts": [],
        }
        for protocol in (False, True):
            payload = (
                {
                    "method": "tasks",
                    "params": {"namespace": ["tools:child"], "data": data},
                }
                if protocol
                else data
            )
            raw = ("event: tasks\ndata: " + json.dumps(payload) + "\n\n").encode()
            result = b"".join(
                [
                    chunk
                    async for chunk in _redact_protocol_event_stream(
                        _chunks(raw), protocol=protocol
                    )
                ]
            )
            self.assertNotIn(b"TASK_EXCEPTION_CANARY", result)
            self.assertIn(b"runtime.execution_failed", result)
            self.assertIn(b'"id":"task-1"', result)

    async def test_fatal_run_error_hides_original_exception_in_both_streams(self):
        for protocol in (False, True):
            with self.subTest(protocol=protocol):
                detail = "EXCEPTION_CANARY Authorization=secret /private/host/provider"
                data = {
                    "event": "failed" if protocol else "lifecycle",
                    "status": "error",
                    "error": detail
                    if protocol
                    else {"type": "RuntimeError", "message": detail},
                }
                payload = (
                    {
                        "method": "lifecycle",
                        "params": {"namespace": [], "run_id": "run-1", "data": data},
                    }
                    if protocol
                    else data
                )
                raw = (
                    "event: lifecycle\ndata: " + json.dumps(payload) + "\n\n"
                ).encode()
                result = b"".join(
                    [
                        chunk
                        async for chunk in _redact_protocol_event_stream(
                            _chunks(raw), protocol=protocol
                        )
                    ]
                )
                self.assertNotIn(b"EXCEPTION_CANARY", result)
                self.assertIn(b"runtime.execution_failed", result)
                self.assertIn(b'"status":"error"', result)

    async def test_safe_tool_error_survives_standard_and_protocol_streams(self):
        content = json.dumps(
            {
                "status": "error",
                "code": "tool.invalid_input",
                "error": "Safe input failure",
                "error_type": "ToolException",
                "name": "search_web",
                "recovery": "correct_input",
                "outcome": "not_started",
            }
        )
        message = {
            "type": "tool",
            "name": "search_web",
            "tool_call_id": "child-call",
            "status": "error",
            "content": content,
            "artifact": {
                "token": "ARTIFACT_SECRET_CANARY",
                "sources": [{"path": "/workspace/sources/source.txt"}],
            },
        }
        for protocol in (False, True):
            with self.subTest(protocol=protocol):
                data = {"tools": {"messages": [message]}}
                payload = (
                    {
                        "seq": 3,
                        "method": "updates",
                        "params": {"namespace": ["tools:child"], "data": data},
                    }
                    if protocol
                    else data
                )
                raw = (
                    "event: updates|tools:child\ndata: " + json.dumps(payload) + "\n\n"
                ).encode()
                result = b"".join(
                    [
                        chunk
                        async for chunk in _redact_protocol_event_stream(
                            _chunks(raw[:13], raw[13:39], raw[39:]), protocol=protocol
                        )
                    ]
                )
                decoded = json.loads(result.decode().split("data: ", 1)[1].strip())
                transported = decoded["params"]["data"] if protocol else decoded
                actual = transported["tools"]["messages"][0]
                self.assertEqual(
                    {
                        k: actual[k]
                        for k in ("name", "tool_call_id", "status", "content")
                    },
                    {
                        k: message[k]
                        for k in ("name", "tool_call_id", "status", "content")
                    },
                )
                self.assertEqual(actual["artifact"]["token"], "[REDACTED]")
                self.assertNotIn(b"SECRET_CANARY", result)
                if protocol:
                    self.assertEqual(decoded["params"]["namespace"], ["tools:child"])

    async def test_tool_error_event_is_distinct_from_run_failure(self):
        for event in ("tool-error", "failed"):
            with self.subTest(event=event):
                data = {
                    "event": event,
                    "tool_call_id": "call",
                    "message": "tool.execution_failed",
                }
                raw = (
                    "data: "
                    + json.dumps(
                        {
                            "seq": 1,
                            "method": "tools" if event == "tool-error" else "lifecycle",
                            "params": {"namespace": [], "data": data},
                        }
                    )
                    + "\n\n"
                ).encode()
                result = b"".join(
                    [
                        chunk
                        async for chunk in _redact_protocol_event_stream(_chunks(raw))
                    ]
                )
                actual = json.loads(result.decode().split("data: ", 1)[1])
                self.assertEqual(actual["params"]["data"], data)

    def test_offloading_capability_remains_boolean(self):
        for supported in (True, False):
            self.assertEqual(
                redact_runtime_private_fields({"conversation_offloading": supported}),
                {"conversation_offloading": supported},
            )

    def test_malformed_offloading_status_is_bounded_without_crashing(self):
        for value in (
            None,
            [],
            {"type": "conversation_offloading", "status": [], "trigger": {}},
        ):
            self.assertEqual(
                redact_runtime_private_fields({"conversation_offloading": value}),
                {"conversation_offloading": {}},
            )
        value = {
            "type": "conversation_offloading",
            "status": "failed",
            "trigger": "manual",
            "reason_code": ["private"],
            "operation_id": "x" * 129,
        }
        self.assertEqual(
            redact_runtime_private_fields(value),
            {
                "type": "conversation_offloading",
                "status": "failed",
                "trigger": "manual",
            },
        )

    def test_offloading_whitelist_applies_to_state_history_and_protocol_envelopes(self):
        public = {
            "type": "conversation_offloading",
            "operation_id": "operation",
            "status": "completed",
            "trigger": "automatic",
            "history_saved": True,
        }
        private = {
            **public,
            "summary": "PRIVATE",
            "file_path": "/private/history",
            "reason_code": "secret exception",
        }
        state = {
            "values": {
                "conversation_offloading": private,
                "_summarization_event": {"summary_message": "PRIVATE"},
                "_summarization_session_id": "private-id",
                "files": {
                    "/outputs/result.txt": "visible",
                    "/budget-large": {"content": "FULL_TOOL_RESULT"},
                    "/conversation_history/session_private.md": "PRIVATE",
                    "/session_" + "a" * 32 + ".md": "PRIVATE",
                    "/media/" + "b" * 16 + ".png": "PRIVATE",
                },
            }
        }
        redacted = redact_runtime_private_fields([state])[0]
        self.assertEqual(redacted["values"]["conversation_offloading"], public)
        self.assertEqual(
            redacted["values"]["files"],
            {
                "/outputs/result.txt": "visible",
                "/budget-large": {"content": "FULL_TOOL_RESULT"},
            },
        )
        for payload, protocol in (
            (private, False),
            (
                {
                    "method": "custom",
                    "params": {"namespace": ["child"], "data": private},
                },
                True,
            ),
            ({"method": "values", "params": {"namespace": [], "data": state}}, True),
        ):
            frame = b"data: " + json.dumps(payload).encode()
            cleaned = _redact_sse_frame(frame, protocol=protocol)
            self.assertNotIn(b"PRIVATE", cleaned)
            self.assertNotIn(b"file_path", cleaned)
            self.assertNotIn(b"private-id", cleaned)
        for key in (
            "conversation_offloading",
            "_summarization_event",
            "_summarization_session_id",
        ):
            with self.assertRaises(ValueError):
                reject_private_runtime_state({"nested": [{key: {}}]})
        for path in (
            "/conversation_history/session_private.md",
            "/session_" + "a" * 32 + ".md",
            "/media/" + "b" * 16 + ".png",
        ):
            with self.assertRaises(ValueError):
                reject_private_runtime_state({"nested": [{"files": {path: "fake"}}]})
        reject_private_runtime_state({"files": {"/outputs/result.txt": "visible"}})
        reject_private_runtime_state(
            {"files": {"/budget-large": {"content": "FULL_TOOL_RESULT"}}}
        )

    async def test_plain_stream_close_and_failed_observer_do_not_change_body(self):
        reasons = []
        sent = []
        response = RuntimeStreamingResponse(
            _chunks(b"data: 1\n\n"), on_close=lambda reason, _: reasons.append(reason)
        )

        async def send(message):
            sent.append(message)

        await response.stream_response(send)
        self.assertEqual(reasons, ["closed"])
        self.assertTrue(any(item.get("body") == b"data: 1\n\n" for item in sent))

        request = Request(
            {"type": "http", "method": "POST", "path": "/stream", "headers": []}
        )
        request.state.platform_context = SimpleNamespace(
            request=SimpleNamespace(request_id="request-1", trace_id="request-1"),
            project=SimpleNamespace(project_id="project-1"),
        )
        response = _runtime_sse_response(
            request,
            _chunks(b"data: 1\n\n"),
            thread_id="thread-1",
            stream_kind="run",
            protocol=False,
        )
        sent.clear()
        with patch(
            "platform_api.modules.runtime_gateway.presentation.http.log_event",
            side_effect=RuntimeError("observer unavailable"),
        ):
            await response.stream_response(send)
        self.assertTrue(any(item.get("body") == b"data: 1\n\n" for item in sent))

    async def test_eof_and_empty_stream_keep_one_log_pair(self):
        for values, expected in (((), "eof"), ((b"data: 1\n\n",), "eof")):
            request = Request(
                {"type": "http", "method": "POST", "path": "/stream", "headers": []}
            )
            request.state.platform_context = SimpleNamespace(
                request=SimpleNamespace(request_id="request-1", trace_id="request-1"),
                project=SimpleNamespace(project_id="project-1"),
            )
            events = []
            response = _runtime_sse_response(
                request,
                _chunks(*values),
                thread_id="thread-1",
                stream_kind="thread",
                protocol=False,
            )
            with patch(
                "platform_api.modules.runtime_gateway.presentation.http.log_event",
                side_effect=lambda _logger, event, _events=events, **fields: (
                    _events.append((event, fields))
                ),
            ):
                await response.stream_response(lambda _message: asyncio.sleep(0))
            self.assertEqual(
                [name for name, _ in events],
                ["runtime.stream.opened", "runtime.stream.closed"],
            )
            self.assertEqual(events[-1][1]["close_reason"], expected)
            self.assertNotIn("run_id", events[-1][1])

    async def test_disconnect_and_unknown_cancel_have_distinct_close_reasons(self):
        async def pending():
            yield b": heartbeat\n\n"
            await asyncio.Event().wait()

        for disconnected, expected in ((True, "client_disconnect"), (False, "unknown")):
            reasons = []
            response = RuntimeStreamingResponse(
                pending(),
                on_close=lambda reason, _, _reasons=reasons: _reasons.append(reason),
            )

            async def send(message, _disconnected=disconnected, _response=response):
                if message["type"] == "http.response.body":
                    if _disconnected:
                        _response._client_disconnected = True
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
                broken(),
                on_close=lambda reason, _, _reasons=reasons: _reasons.append(reason),
            )

            async def send(message, _send_error=send_error):
                if _send_error and message["type"] == "http.response.body":
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

    async def test_injects_heartbeat_when_upstream_is_idle(self):
        received_heartbeats = asyncio.Event()

        async def slow_upstream():
            yield b'data: {"seq":1,"method":"values","params":{"namespace":[],"data":{"step":"start"}}}\n\n'
            await received_heartbeats.wait()
            yield b'data: {"seq":2,"method":"values","params":{"namespace":[],"data":{"step":"end"}}}\n\n'

        parts = []
        async with asyncio.timeout(5):
            async for part in _redact_protocol_event_stream(
                slow_upstream(),
                heartbeat_seconds=0.04,
            ):
                parts.append(part)
                if parts.count(b": heartbeat\n\n") >= 2:
                    received_heartbeats.set()

        heartbeats = [p for p in parts if p == b": heartbeat\n\n"]
        self.assertGreaterEqual(len(heartbeats), 2)
        self.assertIn(
            b'data: {"seq":1,"method":"values","params":{"namespace":[],"data":{"step":"start"}}}\n\n',
            parts,
        )
        self.assertIn(
            b'data: {"seq":2,"method":"values","params":{"namespace":[],"data":{"step":"end"}}}\n\n',
            parts,
        )

    async def test_heartbeat_can_be_disabled(self):
        async def slow_upstream():
            yield b'data: {"seq":1,"method":"values","params":{"namespace":[],"data":{"step":"start"}}}\n\n'
            await asyncio.sleep(0.06)
            yield b'data: {"seq":2,"method":"values","params":{"namespace":[],"data":{"step":"end"}}}\n\n'

        parts = []
        async for part in _redact_protocol_event_stream(
            slow_upstream(),
            heartbeat_seconds=0.0,
        ):
            parts.append(part)

        self.assertEqual(
            parts,
            [
                b'data: {"seq":1,"method":"values","params":{"namespace":[],"data":{"step":"start"}}}\n\n',
                b'data: {"seq":2,"method":"values","params":{"namespace":[],"data":{"step":"end"}}}\n\n',
            ],
        )

    async def test_sse_frame_with_unicode_line_separators_is_not_split(self):
        # \u2028 (LINE SEPARATOR) and \u2029 (PARAGRAPH SEPARATOR) must not break SSE frames
        frame = b'data: {"seq":1,"method":"values","params":{"namespace":[],"data":{"content":"hello\\u2028world\\u2029test"}}}\n\n'
        parts = []
        async for part in _redact_protocol_event_stream(_chunks(frame)):
            parts.append(part)

        self.assertEqual(len(parts), 1)
        self.assertIn("hello\u2028world\u2029test".encode(), parts[0])
