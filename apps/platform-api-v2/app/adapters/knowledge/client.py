from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from app.core.errors import PlatformApiError, UpstreamServiceError


def _message_from_detail(detail: Any, fallback: str) -> str:
    if isinstance(detail, str) and detail.strip():
        return detail.strip()
    if isinstance(detail, dict):
        for key in ('message', 'detail', 'error'):
            value = detail.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return fallback


def create_knowledge_upstream_error(
    *,
    status_code: int,
    detail: Any,
    fallback_code: str,
    upstream_path: str | None = None,
) -> PlatformApiError:
    extra: dict[str, Any] = {
        'upstream': 'lightrag',
        'upstream_status_code': status_code,
    }
    if upstream_path:
        extra['upstream_path'] = upstream_path
    if detail not in (None, ''):
        extra['upstream_detail'] = detail
    return PlatformApiError(
        code=fallback_code,
        status_code=status_code,
        message=_message_from_detail(detail, fallback_code.replace('_', ' ')),
        extra=extra,
    )


class LightRagKnowledgeClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        api_key: str | None = None,
        forwarded_headers: Mapping[str, str] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip('/')
        self._timeout_seconds = timeout_seconds
        self._api_key = api_key
        self._forwarded_headers = {
            key: value
            for key, value in dict(forwarded_headers or {}).items()
            if value
        }

    def _url(self, path: str) -> str:
        normalized_path = path if path.startswith('/') else f'/{path}'
        return f'{self._base_url}{normalized_path}'

    def _headers(
        self,
        *,
        workspace_key: str,
        accept: str | None = 'application/json',
        content_type: str | None = None,
        extra: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        headers = dict(self._forwarded_headers)
        headers['LIGHTRAG-WORKSPACE'] = workspace_key
        if self._api_key:
            headers['x-api-key'] = self._api_key
        if accept:
            headers['accept'] = accept
        if content_type:
            headers['content-type'] = content_type
        if extra:
            headers.update({key: value for key, value in extra.items() if value})
        return headers

    async def _raise_for_status(self, response: httpx.Response, *, fallback_code: str) -> None:
        if response.status_code < 400:
            return
        if not response.content:
            detail: Any = fallback_code
        else:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text or fallback_code
        raise create_knowledge_upstream_error(
            status_code=response.status_code,
            detail=detail,
            fallback_code=fallback_code,
            upstream_path=response.request.url.path,
        )

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        workspace_key: str,
        payload: Any = None,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        json_payload = dict(payload) if isinstance(payload, Mapping) else payload
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.request(
                    method=method,
                    url=self._url(path),
                    json=json_payload,
                    params=dict(params) if params is not None else None,
                    headers=self._headers(workspace_key=workspace_key),
                )
        except httpx.TimeoutException as exc:
            raise UpstreamServiceError(
                upstream='lightrag',
                status_code=504,
                code='lightrag_upstream_timeout',
                message='LightRAG upstream timed out',
            ) from exc
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(
                upstream='lightrag',
                status_code=502,
                code='lightrag_upstream_unavailable',
                message='LightRAG upstream is unavailable',
            ) from exc

        await self._raise_for_status(response, fallback_code='lightrag_upstream_request_failed')
        if response.status_code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {'raw': response.text}

    async def upload_document(
        self,
        *,
        workspace_key: str,
        filename: str,
        content: bytes,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(
                    self._url('/documents/upload'),
                    files={
                        'file': (
                            filename,
                            content,
                            content_type or 'application/octet-stream',
                        )
                    },
                    headers=self._headers(
                        workspace_key=workspace_key,
                        accept='application/json',
                    ),
                )
        except httpx.TimeoutException as exc:
            raise UpstreamServiceError(
                upstream='lightrag',
                status_code=504,
                code='lightrag_upstream_timeout',
                message='LightRAG upstream timed out',
            ) from exc
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(
                upstream='lightrag',
                status_code=502,
                code='lightrag_upstream_unavailable',
                message='LightRAG upstream is unavailable',
            ) from exc

        await self._raise_for_status(response, fallback_code='lightrag_upload_failed')
        value = response.json()
        if isinstance(value, dict):
            return value
        raise PlatformApiError(
            code='lightrag_upstream_invalid_response',
            status_code=502,
            message='LightRAG upstream returned an invalid upload payload',
        )

    async def get_health(self, *, workspace_key: str) -> dict[str, Any]:
        value = await self.request_json('GET', '/health', workspace_key=workspace_key)
        if isinstance(value, dict):
            return value
        raise PlatformApiError(
            code='lightrag_upstream_invalid_response',
            status_code=502,
            message='LightRAG upstream returned an invalid health payload',
        )
