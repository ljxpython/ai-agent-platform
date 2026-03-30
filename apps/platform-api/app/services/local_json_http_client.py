from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException, Request


class LocalJsonHttpClient:
    def __init__(
        self,
        request: Request,
        *,
        base_url: str | None,
        token: str | None,
        timeout_seconds: float,
        service_name: str,
    ) -> None:
        self._request = request
        self._client: httpx.AsyncClient = request.app.state.client
        self._base_url = (base_url or "").rstrip("/")
        self._token = (token or "").strip() or None
        self._timeout_seconds = max(1.0, timeout_seconds)
        self._service_name = service_name

    @property
    def is_configured(self) -> bool:
        return bool(self._base_url)

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"accept": "application/json"}
        request_id = getattr(self._request.state, "request_id", None)
        if request_id:
            headers["x-request-id"] = str(request_id)
        if self._token:
            headers["authorization"] = (
                self._token
                if self._token.lower().startswith("bearer ")
                else f"Bearer {self._token}"
            )
        return headers

    def _require_configured(self) -> None:
        if not self.is_configured:
            raise HTTPException(
                status_code=503,
                detail=f"{self._service_name}_not_configured",
            )

    def _url(self, path: str) -> str:
        normalized_path = path if path.startswith("/") else f"/{path}"
        return f"{self._base_url}{normalized_path}"

    async def _handle_response(self, response: httpx.Response) -> Any:
        if response.status_code < 400:
            return response.json()
        try:
            payload = response.json()
        except Exception:
            payload = response.text
        detail = payload.get("detail") if isinstance(payload, dict) else payload
        raise HTTPException(status_code=response.status_code, detail=detail)

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        self._require_configured()
        try:
            response = await self._client.get(
                self._url(path),
                headers=self._build_headers(),
                params=params,
                timeout=self._timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=504,
                detail=f"{self._service_name}_timeout: {exc}",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"{self._service_name}_unavailable: {exc}",
            ) from exc
        return await self._handle_response(response)

    async def post(self, path: str, *, json_body: dict[str, Any]) -> Any:
        self._require_configured()
        try:
            response = await self._client.post(
                self._url(path),
                headers={"content-type": "application/json", **self._build_headers()},
                json=json_body,
                timeout=self._timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=504,
                detail=f"{self._service_name}_timeout: {exc}",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"{self._service_name}_unavailable: {exc}",
            ) from exc
        return await self._handle_response(response)

    async def patch(self, path: str, *, json_body: dict[str, Any]) -> Any:
        self._require_configured()
        try:
            response = await self._client.patch(
                self._url(path),
                headers={"content-type": "application/json", **self._build_headers()},
                json=json_body,
                timeout=self._timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=504,
                detail=f"{self._service_name}_timeout: {exc}",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"{self._service_name}_unavailable: {exc}",
            ) from exc
        return await self._handle_response(response)

    async def delete(self, path: str) -> Any:
        self._require_configured()
        try:
            response = await self._client.delete(
                self._url(path),
                headers=self._build_headers(),
                timeout=self._timeout_seconds,
            )
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=504,
                detail=f"{self._service_name}_timeout: {exc}",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=502,
                detail=f"{self._service_name}_unavailable: {exc}",
            ) from exc
        return await self._handle_response(response)
