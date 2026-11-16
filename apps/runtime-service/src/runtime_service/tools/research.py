"""Shared bounded public research transport; never contacts user-provided hosts."""

import asyncio
import ipaddress
import json
import os
from urllib.parse import urlsplit

import httpx
from langchain_core.tools import ToolException


async def public_url(url: str) -> str:
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 80, 443)
        ):
            raise ValueError()
        host = parsed.hostname.rstrip(".").lower()
        if "." not in host or host.endswith(
            (".localhost", ".local", ".internal", ".lan")
        ):
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError()
        # Only the fixed Tavily endpoint is contacted by Runtime. DNS and redirects
        # for extracted pages belong to Tavily; local DNS may use proxy fake IPs.
    except ValueError as exc:
        raise ToolException("research_url_denied") from exc
    return url


async def tavily(operation: str, payload: dict) -> dict:
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        raise ToolException("research_unavailable: TAVILY_API_KEY is not configured")
    try:
        async with (
            asyncio.timeout(30),
            httpx.AsyncClient(
                timeout=25, follow_redirects=False, trust_env=True
            ) as client,
        ):
            async with client.stream(
                "POST",
                "https://api.tavily.com/" + operation,
                headers={"Authorization": "Bearer " + key},
                json=payload,
            ) as response:
                response.raise_for_status()
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 1024 * 1024:
                        raise ToolException("research_response_too_large")
        result = json.loads(data)
        if not isinstance(result, dict) or not isinstance(result.get("results"), list):
            raise ToolException("research_provider_failed")
        for record in result["results"]:
            if not isinstance(record, dict) or not isinstance(record.get("url"), str):
                raise ToolException("research_provider_failed")
            if any(
                record.get(key) is not None and not isinstance(record[key], str)
                for key in ("title", "content", "raw_content")
            ):
                raise ToolException("research_provider_failed")
        return result
    except (
        httpx.HTTPError,
        json.JSONDecodeError,
        UnicodeDecodeError,
        TimeoutError,
    ) as exc:
        raise ToolException("research_provider_failed") from exc
