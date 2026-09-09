"""Service-specific tools; filesystem, planning and execution come from Deep Agents."""

from urllib.parse import urlsplit

import httpx
from langchain_core.tools import ToolException, tool

_ALLOWED_HOSTS = frozenset(
    {"docs.python.org", "docs.langchain.com", "reference.langchain.com"}
)
_MAX_BYTES = 128 * 1024


@tool
async def fetch_documentation(url: str) -> str:
    """Fetch bounded text from official Python or LangChain documentation over HTTPS."""
    try:
        parsed = urlsplit(url)
        valid = (
            parsed.scheme == "https"
            and parsed.hostname in _ALLOWED_HOSTS
            and parsed.port in (None, 443)
            and parsed.username is None
            and parsed.password is None
        )
    except ValueError:
        valid = False
    if not valid:
        raise ToolException(
            "Use an HTTPS URL on docs.python.org, docs.langchain.com or reference.langchain.com."
        )
    try:
        async with (
            httpx.AsyncClient(
                timeout=15, follow_redirects=False, trust_env=False
            ) as client,
            client.stream("GET", url) as response,
        ):
            if response.is_redirect:
                raise ToolException(
                    "Redirects are not followed; use the final official documentation URL."
                )
            response.raise_for_status()
            media_type = response.headers.get("content-type", "").split(";", 1)[0]
            if not (media_type.startswith("text/") or media_type == "application/json"):
                raise ToolException("Only text documentation is supported.")
            content = bytearray()
            async for chunk in response.aiter_bytes(chunk_size=4096):
                remaining = _MAX_BYTES - len(content)
                content.extend(chunk[:remaining])
                if len(chunk) > remaining:
                    return (
                        content.decode("utf-8", errors="replace")
                        + "\n[Document truncated at 128 KiB]"
                    )
            return content.decode("utf-8", errors="replace")
    except httpx.HTTPError as exc:
        raise ToolException(
            "Documentation request failed; check the URL or retry later."
        ) from exc


fetch_documentation.handle_tool_error = True

__all__ = ["fetch_documentation"]
