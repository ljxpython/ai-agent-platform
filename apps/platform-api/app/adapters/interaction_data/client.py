from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import httpx

from app.core.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotAuthenticatedError,
    NotFoundError,
    PlatformApiError,
    ServiceUnavailableError,
    UpstreamServiceError,
)


class InteractionDataClient:
    def __init__(
        self,
        *,
        base_url: str | None,
        timeout_seconds: float,
        token: str | None = None,
        forwarded_headers: Mapping[str, str] | None = None,
    ) -> None:
        self._base_url = (base_url or "").rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._token = (token or "").strip() or None
        self._forwarded_headers = dict(forwarded_headers or {})

    def _require_configured(self) -> None:
        if self._base_url:
            return
        raise ServiceUnavailableError(
            code="interaction_data_service_not_configured",
            message="Interaction-data-service is not configured",
        )

    def _url(self, path: str) -> str:
        normalized_path = path if path.startswith("/") else f"/{path}"
        return f"{self._base_url}{normalized_path}"

    def _headers(self, *, accept: str | None = None) -> dict[str, str]:
        headers = dict(self._forwarded_headers)
        if self._token:
            headers["authorization"] = (
                self._token
                if self._token.lower().startswith("bearer ")
                else f"Bearer {self._token}"
            )
        if accept:
            headers["accept"] = accept
        return headers

    @staticmethod
    def _extract_detail(response: httpx.Response) -> Any:
        if not response.content:
            return "interaction_data_upstream_request_failed"
        try:
            payload = response.json()
        except ValueError:
            return response.text or "interaction_data_upstream_request_failed"
        if isinstance(payload, dict) and "detail" in payload:
            return payload.get("detail")
        return payload

    @staticmethod
    def _error_code(detail: Any, *, default: str) -> str:
        if not isinstance(detail, str):
            return default
        normalized = detail.strip()
        if not normalized:
            return default
        return normalized.split(":", 1)[0].strip() or default

    @staticmethod
    def _error_message(detail: Any, *, fallback: str) -> str:
        if isinstance(detail, str):
            normalized = detail.strip()
            if normalized:
                return normalized
            return fallback
        if detail is None:
            return fallback
        try:
            return json.dumps(detail, ensure_ascii=False)
        except TypeError:
            return fallback

    async def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return

        detail = self._extract_detail(response)
        code = self._error_code(detail, default="interaction_data_upstream_rejected")
        message = self._error_message(
            detail,
            fallback="Interaction-data-service request failed",
        )

        if response.status_code == 400:
            raise BadRequestError(code=code, message=message)
        if response.status_code == 401:
            raise NotAuthenticatedError(message=message)
        if response.status_code == 403:
            raise ForbiddenError(code=code, message=message)
        if response.status_code == 404:
            raise NotFoundError(code=code, message=message)
        if response.status_code == 409:
            raise ConflictError(code=code, message=message)

        raise PlatformApiError(
            code=code,
            status_code=response.status_code,
            message=message,
            extra={"upstream": "interaction_data"},
        )

    async def request_json(
        self,
        method: str,
        path: str,
        *,
        payload: Any = None,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        self._require_configured()
        json_payload = dict(payload) if isinstance(payload, Mapping) else payload
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.request(
                    method=method,
                    url=self._url(path),
                    json=json_payload,
                    params=dict(params) if params is not None else None,
                    headers=self._headers(accept="application/json"),
                )
        except httpx.TimeoutException as exc:
            raise UpstreamServiceError(
                upstream="interaction_data",
                status_code=504,
                code="interaction_data_upstream_timeout",
                message="Interaction-data-service timed out",
            ) from exc
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(
                upstream="interaction_data",
                status_code=502,
                code="interaction_data_upstream_unavailable",
                message="Interaction-data-service is unavailable",
            ) from exc

        await self._raise_for_status(response)

        if response.status_code == 204 or not response.content:
            return {}

        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    async def require_json(
        self,
        method: str,
        path: str,
        *,
        payload: Any = None,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        value = await self.request_json(method, path, payload=payload, params=params)
        if isinstance(value, dict):
            return value
        raise PlatformApiError(
            code="interaction_data_upstream_invalid_response",
            status_code=502,
            message="Interaction-data-service returned an invalid object payload",
        )

    async def get_binary(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> tuple[bytes, dict[str, str]]:
        self._require_configured()
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(
                    self._url(path),
                    params=dict(params) if params is not None else None,
                    headers=self._headers(),
                )
        except httpx.TimeoutException as exc:
            raise UpstreamServiceError(
                upstream="interaction_data",
                status_code=504,
                code="interaction_data_upstream_timeout",
                message="Interaction-data-service timed out",
            ) from exc
        except httpx.HTTPError as exc:
            raise UpstreamServiceError(
                upstream="interaction_data",
                status_code=502,
                code="interaction_data_upstream_unavailable",
                message="Interaction-data-service is unavailable",
            ) from exc

        await self._raise_for_status(response)
        return response.content, dict(response.headers)
