"""Bounded provider reads; no caller-controlled URL, scope or credentials."""

import asyncio
import json

import httpx

from platform_api.core.errors import NotFoundError, PlatformApiError


class KnowledgeClient:
    def __init__(self, http: httpx.AsyncClient):
        self.http = http

    async def get(self, connection, path: str, params: dict | None = None):
        try:
            async with (
                asyncio.timeout(10),
                self.http.stream(
                    "GET",
                    connection.base_url + "/internal/knowledge/" + path,
                    params=params,
                    headers={"Authorization": "Bearer " + connection.token},
                ) as response,
            ):
                if response.status_code == 404:
                    raise NotFoundError(
                        code="knowledge_not_found",
                        message="Knowledge resource not found",
                    )
                response.raise_for_status()
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 1024 * 1024:
                        raise ValueError("knowledge_response_too_large")
                return json.loads(raw)
        except (httpx.HTTPError, ValueError, TimeoutError) as exc:
            raise PlatformApiError(
                code="knowledge_unavailable",
                status_code=502,
                message="Knowledge service unavailable",
            ) from exc
