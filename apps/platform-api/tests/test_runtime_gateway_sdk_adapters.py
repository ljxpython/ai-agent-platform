from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
from platform_api.adapters.langgraph.runs_sdk_adapter import LangGraphRunsSdkAdapter
from platform_api.adapters.langgraph.runtime_client import LangGraphRuntimeClient
from platform_api.adapters.langgraph.runtime_gateway_upstream import (
    LangGraphRuntimeGatewayUpstream,
)
from platform_api.adapters.langgraph.threads_sdk_adapter import (
    LangGraphThreadsSdkAdapter,
)
from platform_api.core.errors import PlatformApiError
from platform_api.modules.runtime_gateway.presentation.http import router, _normalize_ack


async def _collect_chunks(stream):
    chunks: list[bytes] = []
    async for chunk in stream:
        chunks.append(chunk)
    return chunks


async def _stream_events(*events):
    for event in events:
        yield event


class RuntimeGatewaySdkAdaptersTest(unittest.IsolatedAsyncioTestCase):
    async def test_dear_memory_upstream_error_does_not_echo_fact_text(self):
        marker = "SENSITIVE_MEMORY_BODY"
        adapter = LangGraphRuntimeGatewayUpstream(base_url="http://runtime", timeout_seconds=10)
        for status, code in ((503, "memory_storage_unavailable"),
                             (504, "langgraph_upstream_timeout")):
            adapter._http = SimpleNamespace(require_json=AsyncMock(side_effect=PlatformApiError(
                code=code, status_code=status, message=marker,
                extra={"upstream_detail": marker})))
            with self.assertRaises(PlatformApiError) as caught:
                await adapter.dear_memory()
            self.assertEqual(caught.exception.code, code)
            self.assertNotIn(marker, str(caught.exception.to_payload(request_id="request-1")))
            self.assertEqual(caught.exception.to_payload(request_id="request-1")["request_id"], "request-1")

    async def test_dear_memory_uses_threadless_private_route(self):
        adapter = LangGraphRuntimeGatewayUpstream(base_url="http://runtime", timeout_seconds=10)
        adapter._http = SimpleNamespace(require_json=AsyncMock(return_value={"status": "ready"}))
        await adapter.dear_memory(payload={"action": "clear", "expected_revision": 1})
        adapter._http.require_json.assert_awaited_once_with(
            "POST", "/internal/dear/memory", payload={"action": "clear", "expected_revision": 1})

    async def test_dear_governance_is_runtime_private_route(self):
        adapter = LangGraphRuntimeGatewayUpstream(base_url="http://runtime", timeout_seconds=10)
        adapter._http = SimpleNamespace(require_json=AsyncMock(return_value={"revision": 1}))
        await adapter.dear_governance("thread-1", "memory", payload={"action": "clear", "expected_revision": 1})
        adapter._http.require_json.assert_awaited_once_with(
            "POST", "/internal/threads/thread-1/dear/memory",
            payload={"action": "clear", "expected_revision": 1}, params=None)

    async def test_explicit_v3_create_preserves_idempotency_and_payload(self):
        adapter = LangGraphRunsSdkAdapter(base_url="http://runtime")
        adapter._http = SimpleNamespace(request_json=AsyncMock(return_value={"run_id": "run-1"}))
        result = await adapter.create("thread-1", {
            "assistant_id": "agent-1", "version": "v3", "input": {"x": 1},
            "idempotency_key": "request-1", "untrusted_extra": "ignored",
        })
        self.assertEqual(result, {"run_id": "run-1"})
        adapter._http.request_json.assert_awaited_once_with(
            "POST", "/threads/thread-1/runs",
            payload={"assistant_id": "agent-1", "input": {"x": 1}, "version": "v3"},
            forwarded_headers={"Idempotency-Key": "request-1"},
        )

    async def test_threads_count_wraps_integer_into_count_object(self) -> None:
        fake_client = SimpleNamespace(
            threads=SimpleNamespace(
                count=AsyncMock(return_value=7),
            )
        )
        with patch(
            "platform_api.adapters.langgraph.threads_sdk_adapter.get_langgraph_client",
            return_value=fake_client,
        ):
            adapter = LangGraphThreadsSdkAdapter(base_url="http://example.com")
            payload = await adapter.count({"metadata": {"project_id": "p-1"}})

        self.assertEqual(payload, {"count": 7})

    async def test_runs_stream_encodes_tuple_events_as_sse(self) -> None:
        fake_client = SimpleNamespace(
            runs=SimpleNamespace(
                stream=Mock(
                    return_value=_stream_events(
                        ("values", {"ok": True}, "evt-1"),
                        {"hello": "world"},
                    )
                )
            )
        )
        with patch(
            "platform_api.adapters.langgraph.runs_sdk_adapter.get_langgraph_client",
            return_value=fake_client,
        ):
            adapter = LangGraphRunsSdkAdapter(base_url="http://example.com")
            stream = await adapter.stream("thread-1",
                {"assistant_id": "assistant-1", "version": "v2"}
            )
            chunks = await _collect_chunks(stream)

        body = b"".join(chunks).decode("utf-8")
        fake_client.runs.stream.assert_called_once_with(
            "thread-1",
            "assistant-1",
            version="v2",
        )
        self.assertIn("event: values", body)
        self.assertIn('data: {"ok":true}', body)
        self.assertIn("id: evt-1", body)
        self.assertIn('data: {"hello":"world"}', body)

    async def test_runs_join_stream_preflights_http_and_preserves_resume_headers(self):
        adapter = LangGraphRunsSdkAdapter(base_url="http://runtime")
        stream = _stream_events(b"event: values\ndata: {}\n\n")
        adapter._http = SimpleNamespace(stream=AsyncMock(return_value=stream))
        actual = await adapter.join_stream("thread-1", "run-1", {
            "stream_mode": "values", "last_event_id": "event-2",
        })
        self.assertEqual(await _collect_chunks(actual), [b"event: values\ndata: {}\n\n"])
        adapter._http.stream.assert_awaited_once_with(
            "GET", "/threads/thread-1/runs/run-1/stream",
            params={"stream_mode": "values", "cancel_on_disconnect": "false"},
            forwarded_headers={"Last-Event-ID": "event-2"},
        )
        adapter._http.stream.side_effect = PlatformApiError(code="denied", message="denied", status_code=403)
        with self.assertRaises(PlatformApiError):
            await adapter.join_stream("thread-1", "run-1")

    async def test_runs_join_stream_rejects_disconnect_cancellation(self) -> None:
        fake_client = SimpleNamespace(runs=SimpleNamespace(join_stream=Mock()))
        with patch(
            "platform_api.adapters.langgraph.runs_sdk_adapter.get_langgraph_client",
            return_value=fake_client,
        ):
            adapter = LangGraphRunsSdkAdapter(base_url="http://example.com")
            with self.assertRaisesRegex(ValueError, "cancel_on_disconnect=true"):
                await adapter.join_stream(
                    "thread-1",
                    "run-1",
                    {"cancel_on_disconnect": True},
                )

        fake_client.runs.join_stream.assert_not_called()



    async def test_protocol_v2_upstream_uses_exact_standard_paths(self) -> None:
        upstream = LangGraphRuntimeGatewayUpstream(
            base_url="http://example.com",
            timeout_seconds=1.0,
        )
        stream = object()
        upstream._http = SimpleNamespace(  # type: ignore[assignment]
            request_json=AsyncMock(return_value={"type": "success", "id": 1}),
            stream=AsyncMock(return_value=stream),
        )
        command = {"id": 1, "method": "input.respond", "params": {}}
        subscription = {"channels": ["messages"], "since": 3}

        response = await upstream.send_thread_command("thread-1", command)
        event_stream = await upstream.stream_thread_events("thread-1", subscription)

        self.assertEqual(response, {"type": "success", "id": 1})
        self.assertIs(event_stream, stream)
        upstream._http.request_json.assert_awaited_once_with(  # type: ignore[attr-defined]
            "POST",
            "/threads/thread-1/commands",
            payload=command,
        )
        upstream._http.stream.assert_awaited_once_with(  # type: ignore[attr-defined]
            "POST",
            "/threads/thread-1/stream/events",
            payload=subscription,
        )


class RuntimeGatewayRouterSmokeTest(unittest.TestCase):
    def test_global_run_surface_is_not_public(self) -> None:
        paths = {route.path for route in router.routes}
        self.assertNotIn("/api/langgraph/runs", paths)
        self.assertNotIn("/api/langgraph/runs/cancel", paths)

    def test_chat_allowlist_keeps_thread_run_and_protocol_surfaces(self) -> None:
        paths = {route.path for route in router.routes}
        for path in (
            "/api/langgraph/info",
            "/api/langgraph/graphs/search",
            "/api/langgraph/graphs/count",
            "/api/langgraph/threads",
            "/api/langgraph/threads/search",
            "/api/langgraph/threads/count",
            "/api/langgraph/threads/{thread_id}",
            "/api/langgraph/threads/{thread_id}/state",
            "/api/langgraph/threads/{thread_id}/history",
            "/api/langgraph/threads/{thread_id}/runs",
            "/api/langgraph/threads/{thread_id}/runs/stream",
            "/api/langgraph/threads/{thread_id}/commands",
            "/api/langgraph/threads/{thread_id}/stream/events",
            "/api/langgraph/threads/{thread_id}/runs/{run_id}",
            "/api/langgraph/threads/{thread_id}/runs/{run_id}/join",
            "/api/langgraph/threads/{thread_id}/runs/{run_id}/stream",
            "/api/langgraph/threads/{thread_id}/runs/{run_id}/cancel",
        ):
            self.assertIn(path, paths)


class RuntimeGatewayErrorMappingTest(unittest.IsolatedAsyncioTestCase):
    async def test_file_stream_limits_and_cleanup(self):
        original = httpx.AsyncClient
        runtime = LangGraphRuntimeClient(base_url="http://runtime", timeout_seconds=1)

        class Stream(httpx.AsyncByteStream):
            closed = False

            def __init__(self, mode):
                self.mode = mode

            async def __aiter__(self):
                yield b"start"
                if self.mode == "overflow":
                    yield b"x" * (20 * 1024 * 1024)
                if self.mode == "disconnect":
                    raise httpx.ReadError("connection lost")

            async def aclose(self):
                self.closed = True

        for mode in ("success", "bad_mime", "bad_length", "overflow", "disconnect", "cancel"):
            with self.subTest(mode=mode):
                stream = Stream(mode)
                headers = {"content-type": "text/plain"}
                if mode == "bad_mime":
                    headers["content-type"] = "application/x-unsupported"
                if mode == "bad_length":
                    headers["content-length"] = str(20 * 1024 * 1024 + 1)
                transport = httpx.MockTransport(lambda request: httpx.Response(200, headers=headers, stream=stream))
                client = original(transport=transport)
                with patch("platform_api.adapters.langgraph.runtime_client.httpx.AsyncClient", return_value=client):
                    try:
                        if mode in {"bad_mime", "bad_length"}:
                            with self.assertRaises(PlatformApiError) as error:
                                await runtime.read_file("/internal/threads/t/workspace/content")
                            self.assertEqual(error.exception.status_code, 502)
                        else:
                            payload = await runtime.read_file("/internal/threads/t/workspace/content")
                            if mode == "cancel":
                                self.assertEqual(await anext(payload.body), b"start")
                                await payload.body.aclose()
                            elif mode in {"overflow", "disconnect"}:
                                with self.assertRaises(PlatformApiError if mode == "overflow" else httpx.ReadError):
                                    _ = b"".join([chunk async for chunk in payload.body])
                            else:
                                self.assertEqual(b"".join([chunk async for chunk in payload.body]), b"start")
                        self.assertTrue(stream.closed)
                        self.assertTrue(client.is_closed)
                    finally:
                        await client.aclose()

    async def test_file_adapter_accepts_all_delivered_formats(self):
        original = httpx.AsyncClient
        runtime = LangGraphRuntimeClient(base_url="http://runtime", timeout_seconds=1)
        for mime in ("text/x-bibtex", "application/zip", "application/vnd.ms-excel",
                     "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     "text/html", "text/css", "text/javascript", "application/yaml", "text/yaml", "application/toml",
                     "application/xml", "application/sql", "image/svg+xml", "image/png", "image/jpeg", "image/webp",
                     "text/x-python", "text/x-shellscript", "text/typescript", "text/x-java-source", "text/x-c",
                     "text/x-c++src", "text/x-rust", "text/jsx", "text/tsx", "application/octet-stream"):
            transport = httpx.MockTransport(lambda request: httpx.Response(
                200, content=b"fixture", headers={"content-type": mime}, request=request))
            with patch("platform_api.adapters.langgraph.runtime_client.httpx.AsyncClient",
                       side_effect=lambda **kwargs: original(transport=transport, **kwargs)) as factory:
                payload = await runtime.read_file("/internal/threads/t/files/content")
                self.assertEqual(payload.content_type, mime)
                self.assertEqual(b"".join([chunk async for chunk in payload.body]), b"fixture")
                self.assertIs(factory.call_args.kwargs["trust_env"], False)

    async def test_protocol_stream_rejects_before_returning_iterator(self):
        client = LangGraphRuntimeClient(base_url="http://runtime", timeout_seconds=1)
        response = httpx.Response(403, json={"detail": "denied"},
                                  request=httpx.Request("POST", "http://runtime/events"))
        fake = SimpleNamespace(build_request=Mock(return_value=response.request),
                               send=AsyncMock(return_value=response), aclose=AsyncMock())
        with patch("platform_api.adapters.langgraph.runtime_client.httpx.AsyncClient", return_value=fake) as factory:
            with self.assertRaises(PlatformApiError) as error:
                await client.stream("POST", "/events", payload={})
        self.assertEqual(error.exception.status_code, 403)
        self.assertIs(factory.call_args.kwargs["trust_env"], False)
        fake.aclose.assert_awaited_once()


    async def test_stream_connect_timeout_is_504_before_returning_iterator(self):
        from platform_api.core.errors import UpstreamServiceError
        client = LangGraphRuntimeClient(base_url="http://runtime", timeout_seconds=1)
        fake = SimpleNamespace(build_request=Mock(return_value=httpx.Request("GET", "http://runtime/events")),
                               send=AsyncMock(side_effect=httpx.ConnectTimeout("timeout")), aclose=AsyncMock())
        with patch("platform_api.adapters.langgraph.runtime_client.httpx.AsyncClient", return_value=fake) as factory:
            with self.assertRaises(UpstreamServiceError) as error:
                await client.stream("GET", "/events")
        self.assertEqual(error.exception.status_code, 504)
        self.assertIs(factory.call_args.kwargs["trust_env"], False)
        fake.aclose.assert_awaited_once()

    async def test_cancel_ack_filters_internal_run_config(self):
        self.assertEqual(_normalize_ack({"run_id": "r", "kwargs": {"config": {
            "configurable": {"runtime_model_ref": "secret", "_runtime_auth": "secret"}}}}),
            {"run_id": "r", "kwargs": {"config": {"configurable": {}}}})

    async def test_upstream_error_removes_nested_internal_fields(self) -> None:
        client = LangGraphRuntimeClient(base_url="http://runtime", timeout_seconds=1)
        response = httpx.Response(
            400,
            json={"detail": {"message": "invalid input", "items": [
                {"runtime_model_ref": "secret", "_runtime_auth": "secret",
                 "text": "ordinary runtime_model_ref text"}]}},
            request=httpx.Request("POST", "http://runtime/runs"),
        )
        with self.assertRaises(PlatformApiError) as error:
            await client._raise_for_status(response)
        self.assertEqual(error.exception.extra["upstream_detail"], {
            "detail": {"message": "invalid input", "items": [
                {"text": "ordinary runtime_model_ref text"}]}})

    async def test_runtime_client_raises_platform_api_error_for_upstream_status(self) -> None:
        client = LangGraphRuntimeClient(
            base_url="http://example.com",
            timeout_seconds=1.0,
        )
        response = httpx.Response(
            404,
            json={"detail": "thread missing"},
            request=httpx.Request("GET", "http://example.com/threads/thread-1"),
        )

        with self.assertRaises(PlatformApiError) as ctx:
            await client._raise_for_status(response)

        self.assertEqual(ctx.exception.code, "langgraph_upstream_request_failed")
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.message, "thread missing")
        self.assertEqual(ctx.exception.extra["upstream_status_code"], 404)
        self.assertEqual(ctx.exception.extra["upstream_path"], "/threads/thread-1")


if __name__ == "__main__":
    unittest.main()
