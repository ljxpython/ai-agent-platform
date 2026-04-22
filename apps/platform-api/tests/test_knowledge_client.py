from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

import httpx

from app.adapters.knowledge.client import LightRagKnowledgeClient
from app.core.errors import PlatformApiError, UpstreamServiceError


class _RecordingAsyncClient:
    def __init__(
        self,
        *,
        timeout: float,
        response: httpx.Response | None = None,
        request_exc: Exception | None = None,
        post_exc: Exception | None = None,
    ) -> None:
        self.timeout = timeout
        self.response = response
        self.request_exc = request_exc
        self.post_exc = post_exc
        self.request_calls: list[dict[str, Any]] = []
        self.post_calls: list[dict[str, Any]] = []

    async def __aenter__(self) -> _RecordingAsyncClient:
        return self

    async def __aexit__(self, exc_type, exc, tb) -> bool:  # type: ignore[no-untyped-def]
        return False

    async def request(self, **kwargs: Any) -> httpx.Response:
        self.request_calls.append(kwargs)
        if self.request_exc is not None:
            raise self.request_exc
        assert self.response is not None
        return self.response

    async def post(self, url: str, **kwargs: Any) -> httpx.Response:
        self.post_calls.append({'url': url, **kwargs})
        if self.post_exc is not None:
            raise self.post_exc
        assert self.response is not None
        return self.response


class _AsyncClientFactory:
    def __init__(
        self,
        *,
        response: httpx.Response | None = None,
        request_exc: Exception | None = None,
        post_exc: Exception | None = None,
    ) -> None:
        self.response = response
        self.request_exc = request_exc
        self.post_exc = post_exc
        self.instances: list[_RecordingAsyncClient] = []

    def __call__(self, *, timeout: float) -> _RecordingAsyncClient:
        client = _RecordingAsyncClient(
            timeout=timeout,
            response=self.response,
            request_exc=self.request_exc,
            post_exc=self.post_exc,
        )
        self.instances.append(client)
        return client


class LightRagKnowledgeClientTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.client = LightRagKnowledgeClient(
            base_url='http://knowledge.test/',
            timeout_seconds=3.5,
            api_key='secret-key',
            forwarded_headers={
                'x-request-id': 'req-1',
                'x-trace-id': 'trace-1',
                'x-empty': '',
            },
        )
        self.workspace_key = 'kb_project_a'

    async def test_request_json_injects_workspace_and_forwarded_headers(self) -> None:
        response = httpx.Response(
            200,
            json={'ok': True},
            request=httpx.Request('POST', 'http://knowledge.test/query'),
        )
        factory = _AsyncClientFactory(response=response)
        payload = {'query': 'hello'}
        params = {'top_k': 3}

        with patch('app.adapters.knowledge.client.httpx.AsyncClient', new=factory):
            result = await self.client.request_json(
                'POST',
                '/query',
                workspace_key=self.workspace_key,
                payload=payload,
                params=params,
            )

        self.assertEqual(result, {'ok': True})
        recorded = factory.instances[0]
        self.assertEqual(recorded.timeout, 3.5)
        self.assertEqual(len(recorded.request_calls), 1)
        request = recorded.request_calls[0]
        self.assertEqual(request['method'], 'POST')
        self.assertEqual(request['url'], 'http://knowledge.test/query')
        self.assertEqual(request['json'], payload)
        self.assertEqual(request['params'], params)
        self.assertEqual(
            request['headers'],
            {
                'x-request-id': 'req-1',
                'x-trace-id': 'trace-1',
                'LIGHTRAG-WORKSPACE': self.workspace_key,
                'x-api-key': 'secret-key',
                'accept': 'application/json',
            },
        )

    async def test_upload_document_uses_multipart_contract_without_overriding_content_type_header(self) -> None:
        response = httpx.Response(
            200,
            json={'id': 'doc-1'},
            request=httpx.Request('POST', 'http://knowledge.test/documents/upload'),
        )
        factory = _AsyncClientFactory(response=response)

        with patch('app.adapters.knowledge.client.httpx.AsyncClient', new=factory):
            result = await self.client.upload_document(
                workspace_key=self.workspace_key,
                filename='notes.txt',
                content=b'hello world',
            )

        self.assertEqual(result, {'id': 'doc-1'})
        recorded = factory.instances[0]
        self.assertEqual(recorded.timeout, 3.5)
        self.assertEqual(len(recorded.post_calls), 1)
        upload = recorded.post_calls[0]
        self.assertEqual(upload['url'], 'http://knowledge.test/documents/upload')
        self.assertEqual(
            upload['files'],
            {
                'file': ('notes.txt', b'hello world', 'application/octet-stream'),
            },
        )
        self.assertEqual(
            upload['headers'],
            {
                'x-request-id': 'req-1',
                'x-trace-id': 'trace-1',
                'LIGHTRAG-WORKSPACE': self.workspace_key,
                'x-api-key': 'secret-key',
                'accept': 'application/json',
            },
        )
        self.assertNotIn('content-type', upload['headers'])

    async def test_request_json_maps_upstream_error_payload_into_platform_api_error(self) -> None:
        response = httpx.Response(
            422,
            json={'detail': 'invalid query payload'},
            request=httpx.Request('POST', 'http://knowledge.test/query'),
        )
        factory = _AsyncClientFactory(response=response)

        with patch('app.adapters.knowledge.client.httpx.AsyncClient', new=factory):
            with self.assertRaises(PlatformApiError) as ctx:
                await self.client.request_json(
                    'POST',
                    '/query',
                    workspace_key=self.workspace_key,
                    payload={'query': ''},
                )

        self.assertEqual(ctx.exception.code, 'lightrag_upstream_request_failed')
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.message, 'invalid query payload')
        self.assertEqual(
            ctx.exception.extra,
            {
                'upstream': 'lightrag',
                'upstream_status_code': 422,
                'upstream_path': '/query',
                'upstream_detail': {'detail': 'invalid query payload'},
            },
        )

    async def test_request_json_maps_timeout_to_gateway_error(self) -> None:
        factory = _AsyncClientFactory(request_exc=httpx.ReadTimeout('timed out'))

        with patch('app.adapters.knowledge.client.httpx.AsyncClient', new=factory):
            with self.assertRaises(UpstreamServiceError) as ctx:
                await self.client.request_json('GET', '/health', workspace_key=self.workspace_key)

        self.assertEqual(ctx.exception.code, 'lightrag_upstream_timeout')
        self.assertEqual(ctx.exception.status_code, 504)
        self.assertEqual(ctx.exception.message, 'LightRAG upstream timed out')
        self.assertEqual(ctx.exception.extra, {'upstream': 'lightrag'})

    async def test_upload_document_maps_transport_errors_to_upstream_unavailable(self) -> None:
        factory = _AsyncClientFactory(post_exc=httpx.ConnectError('connect failed'))

        with patch('app.adapters.knowledge.client.httpx.AsyncClient', new=factory):
            with self.assertRaises(UpstreamServiceError) as ctx:
                await self.client.upload_document(
                    workspace_key=self.workspace_key,
                    filename='notes.txt',
                    content=b'hello world',
                    content_type='text/plain',
                )

        self.assertEqual(ctx.exception.code, 'lightrag_upstream_unavailable')
        self.assertEqual(ctx.exception.status_code, 502)
        self.assertEqual(ctx.exception.message, 'LightRAG upstream is unavailable')
        self.assertEqual(ctx.exception.extra, {'upstream': 'lightrag'})


if __name__ == '__main__':
    unittest.main()
