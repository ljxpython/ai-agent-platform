"""Bounded public research HTTP; no caller-provided host or credentials."""
import asyncio
from urllib.parse import urlsplit

import httpx
from langchain_core.tools import ToolException


async def get_public(url: str, params: dict | None = None) -> tuple[bytes, dict]:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not (parsed.netloc in {"api.github.com", "export.arxiv.org"} or url == "https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md"):
        raise ToolException("research_endpoint_denied")
    try:
        async with (
            asyncio.timeout(35),
            httpx.AsyncClient(timeout=30, follow_redirects=False, trust_env=False) as client,
            client.stream("GET", url, params=params,
                          headers={"Accept": "application/json, application/atom+xml", "User-Agent": "DearAgent-research/1.0"}) as response,
        ):
            if response.status_code in (403, 429):
                raise ToolException("research_rate_limited_or_forbidden")
            if response.status_code == 404:
                raise ToolException("research_not_found_or_private")
            response.raise_for_status()
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > 2 * 1024 * 1024:
                    raise ToolException("research_response_too_large")
            return bytes(data), dict(response.headers)
    except (httpx.HTTPError, TimeoutError) as exc:
        raise ToolException("research_provider_failed") from exc
