from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

import httpx
from anyio import CancelScope

from platform_api.adapters.langgraph.sdk_client import (
    create_runtime_upstream_error,
    raise_runtime_upstream_error,
)
from platform_api.core.errors import PlatformApiError, UpstreamServiceError
from platform_api.modules.runtime_gateway.application.ports import BinaryPayload


class LangGraphRuntimeClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        api_key: str | None = None,
        forwarded_headers: Mapping[str, str] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._api_key = api_key
        self._forwarded_headers = dict(forwarded_headers or {})

    def _headers(
        self,
        *,
        accept: str | None = None,
        forwarded_headers: Mapping[str, str] | None = None,
    ) -> dict[str, str]:
        headers = dict(self._forwarded_headers)
        headers.update(forwarded_headers or {})
        if self._api_key:
            headers["x-api-key"] = self._api_key
        if accept:
            headers["accept"] = accept
        return headers

    def _url(self, path: str) -> str:
        normalized_path = path if path.startswith("/") else f"/{path}"
        return f"{self._base_url}{normalized_path}"

    async def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return

        detail: Any
        if not response.content:
            detail = "langgraph_upstream_request_failed"
        else:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text or "langgraph_upstream_request_failed"

        raise create_runtime_upstream_error(
            status_code=response.status_code,
            detail=detail,
            fallback_code="langgraph_upstream_request_failed",
            upstream_path=response.request.url.path,
        )

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        payload: Any = None,
        params: Mapping[str, Any] | None = None,
        forwarded_headers: Mapping[str, str] | None = None,
    ) -> Any:
        json_payload = (
            dict(payload)
            if isinstance(payload, Mapping)
            else payload
        )
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.request(
                    method=method,
                    url=self._url(path),
                    json=json_payload,
                    params=dict(params) if params is not None else None,
                    headers=self._headers(
                        accept="application/json",
                        forwarded_headers=forwarded_headers,
                    ),
                )
        except httpx.TimeoutException as exc:
            raise UpstreamServiceError(
                upstream="langgraph",
                status_code=504,
                code="langgraph_upstream_timeout",
                message="LangGraph upstream timed out",
            ) from exc
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(
                upstream="langgraph",
                status_code=502,
                code="langgraph_upstream_unavailable",
                message="LangGraph upstream is unavailable",
            ) from exc

        await self._raise_for_status(response)

        if response.status_code == 204 or not response.content:
            return {}

        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    async def list_deployed_graphs(
        self, *, forwarded_headers: Mapping[str, str] | None = None,
    ) -> list[dict[str, str]]:
        graphs: dict[str, dict[str, str]] = {}
        offset = 0
        while True:
            rows = await self.request_json(
                "POST", "/assistants/search",
                payload={"metadata": {"created_by": "system"}, "limit": 1000, "offset": offset},
                forwarded_headers=forwarded_headers,
            )
            if not isinstance(rows, list) or any(
                not isinstance(row, dict) or not isinstance(row.get("graph_id"), str)
                or not row["graph_id"].strip() for row in rows
            ):
                raise PlatformApiError(
                    code="runtime_graph_catalog_invalid", status_code=502,
                    message="Runtime returned an invalid Assistant search response",
                )
            for row in rows:
                key = row["graph_id"]
                graphs[key] = {"graph_id": key, "description": row.get("description") or ""}
            if len(rows) < 1000:
                return list(graphs.values())
            offset += len(rows)

    async def stream(
        self,
        method: str,
        path: str,
        *,
        payload: Any = None,
        params: Mapping[str, Any] | None = None,
        forwarded_headers: Mapping[str, str] | None = None,
    ) -> AsyncIterator[bytes]:
        client = httpx.AsyncClient(timeout=httpx.Timeout(None, connect=self._timeout_seconds))
        response = None
        try:
            request = client.build_request(
                method, self._url(path), json=dict(payload) if isinstance(payload, Mapping) else payload,
                params=dict(params) if params is not None else None,
                headers=self._headers(accept="text/event-stream", forwarded_headers=forwarded_headers),
            )
            response = await client.send(request, stream=True)
            if response.status_code >= 400:
                await response.aread()
            await self._raise_for_status(response)
        except BaseException as exc:
            with CancelScope(shield=True):
                if response is not None:
                    await response.aclose()
                await client.aclose()
            if isinstance(exc, httpx.HTTPError):
                raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_stream_failed")
            raise

        async def iterator() -> AsyncIterator[bytes]:
            try:
                async for chunk in response.aiter_bytes():
                    if chunk:
                        yield chunk
            finally:
                with CancelScope(shield=True):
                    await response.aclose()
                    await client.aclose()
        return iterator()

    async def require_json(
        self,
        method: str,
        path: str,
        *,
        payload: Any = None,
        params: Mapping[str, Any] | None = None,
        forwarded_headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        value = await self.request_json(
            method,
            path,
            payload=payload,
            params=params,
            forwarded_headers=forwarded_headers,
        )
        if isinstance(value, dict):
            return value
        raise PlatformApiError(
            code="langgraph_upstream_invalid_response",
            status_code=502,
            message="LangGraph upstream returned an invalid object payload",
        )

    async def upload_image(
        self,
        path: str,
        *,
        body: AsyncIterator[bytes],
        content_type: str,
        content_length: int,
        forwarded_headers: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        headers = self._headers(
            accept="application/json",
            forwarded_headers=forwarded_headers,
        )
        headers["content-type"] = content_type
        headers["content-length"] = str(content_length)

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.request(
                    method="PUT",
                    url=self._url(path),
                    content=body,
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            raise UpstreamServiceError(
                upstream="langgraph",
                status_code=504,
                code="langgraph_upstream_timeout",
                message="LangGraph upstream timed out",
            ) from exc
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(
                upstream="langgraph",
                status_code=502,
                code="langgraph_upstream_unavailable",
                message="LangGraph upstream is unavailable",
            ) from exc

        await self._raise_for_status(response)

        try:
            return response.json()
        except ValueError:
            raise PlatformApiError(
                code="langgraph_upstream_invalid_response",
                status_code=502,
                message="LangGraph upstream returned an invalid JSON response",
            )

    async def read_image(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        forwarded_headers: Mapping[str, str] | None = None,
    ) -> BinaryPayload:
        client = httpx.AsyncClient(timeout=httpx.Timeout(None, connect=self._timeout_seconds))
        response = None
        try:
            request = client.build_request(
                "GET",
                self._url(path),
                params=dict(params) if params is not None else None,
                headers=self._headers(forwarded_headers=forwarded_headers),
            )
            response = await client.send(request, stream=True)
            if response.status_code >= 400:
                await response.aread()
                await self._raise_for_status(response)
        except BaseException as exc:
            with CancelScope(shield=True):
                if response is not None:
                    await response.aclose()
                await client.aclose()
            if isinstance(exc, (PlatformApiError, UpstreamServiceError)):
                raise
            if isinstance(exc, httpx.HTTPError):
                raise_runtime_upstream_error(exc, fallback_detail="langgraph_image_read_failed")
            raise

        content_type = response.headers.get("content-type", "")
        media_type = content_type.split(";")[0].strip().lower()
        if media_type not in {"image/png", "image/jpeg", "image/webp"}:
            with CancelScope(shield=True):
                await response.aclose()
                await client.aclose()
            raise PlatformApiError(
                code="runtime_invalid_image_response",
                status_code=502,
                message=f"Unsupported image content type: {content_type}",
            )

        content_length_str = response.headers.get("content-length")
        content_length = int(content_length_str) if content_length_str and content_length_str.isdigit() else None
        if content_length is not None and content_length > 20 * 1024 * 1024:
            with CancelScope(shield=True):
                await response.aclose()
                await client.aclose()
            raise PlatformApiError(
                code="runtime_invalid_image_response",
                status_code=502,
                message="Image content length exceeds 20 MiB limit",
            )

        etag = response.headers.get("etag")
        cache_control = response.headers.get("cache-control")
        max_bytes = 20 * 1024 * 1024

        async def body_stream() -> AsyncIterator[bytes]:
            total = 0
            try:
                async for chunk in response.aiter_bytes():
                    if chunk:
                        total += len(chunk)
                        if total > max_bytes:
                            raise PlatformApiError(
                                code="runtime_invalid_image_response",
                                status_code=502,
                                message="Image stream exceeded 20 MiB limit",
                            )
                        yield chunk
            finally:
                with CancelScope(shield=True):
                    await response.aclose()
                    await client.aclose()

        return BinaryPayload(
            body=body_stream(),
            content_type=content_type,
            content_length=content_length,
            etag=etag,
            cache_control=cache_control,
        )

