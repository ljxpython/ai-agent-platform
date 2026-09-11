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
