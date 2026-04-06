from __future__ import annotations

from typing import Any, Mapping

import httpx

from app.core.errors import PlatformApiError, UpstreamServiceError

FORWARDED_HEADER_KEYS = ("authorization", "x-tenant-id", "x-project-id", "x-request-id")


def build_forward_headers(
    headers: Mapping[str, str | None],
    *,
    request_id: str | None = None,
) -> dict[str, str]:
    forwarded: dict[str, str] = {}
    for key in FORWARDED_HEADER_KEYS:
        value = headers.get(key)
        if value:
            forwarded[key] = value
    if "x-request-id" not in forwarded and request_id:
        forwarded["x-request-id"] = request_id
    return forwarded


class LangGraphAssistantsClient:
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

    def _headers(self) -> dict[str, str]:
        headers = dict(self._forwarded_headers)
        if self._api_key:
            headers["x-api-key"] = self._api_key
        return headers

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, Any] | None = None,
    ) -> Any:
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    json=dict(payload) if payload is not None else None,
                    headers=self._headers(),
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

        if response.status_code >= 400:
            raise PlatformApiError(
                code="langgraph_upstream_request_failed",
                status_code=502,
                message=f"LangGraph upstream request failed ({response.status_code})",
                extra={
                    "upstream_status_code": response.status_code,
                    "upstream_path": path,
                },
            )

        if response.status_code == 204 or not response.content:
            return {}

        try:
            return response.json()
        except ValueError as exc:
            raise UpstreamServiceError(
                upstream="langgraph",
                status_code=502,
                code="langgraph_upstream_invalid_response",
                message="LangGraph upstream returned invalid JSON",
            ) from exc

    async def get_assistant(self, assistant_id: str) -> Any:
        return await self._request_json("GET", f"/assistants/{assistant_id}")

    async def create_assistant(self, payload: Mapping[str, Any]) -> Any:
        return await self._request_json("POST", "/assistants", payload=payload)

    async def update_assistant(self, assistant_id: str, payload: Mapping[str, Any]) -> Any:
        return await self._request_json(
            "PATCH",
            f"/assistants/{assistant_id}",
            payload=payload,
        )

    async def delete_assistant(
        self,
        assistant_id: str,
        *,
        delete_threads: bool = False,
    ) -> Any:
        suffix = "?delete_threads=true" if delete_threads else ""
        return await self._request_json(
            "DELETE",
            f"/assistants/{assistant_id}{suffix}",
        )
