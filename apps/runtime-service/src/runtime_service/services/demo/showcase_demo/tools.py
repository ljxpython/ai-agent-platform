"""Service-specific tools; filesystem, planning and execution come from Deep Agents."""

import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

import httpx
from langchain_core.tools import ToolException, tool

_ALLOWED_HOSTS = frozenset(
    {"docs.python.org", "docs.langchain.com", "reference.langchain.com"}
)
_MAX_BYTES = 128 * 1024
_SKIP_TAGS = frozenset(
    {"script", "style", "noscript", "svg", "head", "nav", "footer", "header"}
)


class _HTMLToMarkdownParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._pieces: list[str] = []
        self._skip_depth = 0
        self._in_pre = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()
        if tag_lower in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth > 0:
            return

        if tag_lower in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag_lower[1])
            self._pieces.append(f"\n\n{'#' * level} ")
        elif tag_lower in ("p", "div", "section", "article"):
            self._pieces.append("\n\n")
        elif tag_lower == "br":
            self._pieces.append("\n")
        elif tag_lower == "li":
            self._pieces.append("\n- ")
        elif tag_lower == "pre":
            self._in_pre = True
            self._pieces.append("\n\n```\n")
        elif tag_lower == "code" and not self._in_pre:
            self._pieces.append("`")

    def handle_endtag(self, tag: str) -> None:
        tag_lower = tag.lower()
        if tag_lower in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth > 0:
            return

        if tag_lower in (
            "h1", "h2", "h3", "h4", "h5", "h6", "p", "div", "section", "article"
        ):
            self._pieces.append("\n\n")
        elif tag_lower == "pre":
            self._in_pre = False
            self._pieces.append("\n```\n\n")
        elif tag_lower == "code" and not self._in_pre:
            self._pieces.append("`")

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        if not data:
            return
        self._pieces.append(data)

    def get_markdown(self) -> str:
        text = "".join(self._pieces)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def html_to_markdown(raw_html: str) -> str:
    """Extract clean Markdown text from HTML, stripping navigation/script noise."""
    parser = _HTMLToMarkdownParser()
    parser.feed(raw_html)
    parser.close()
    return parser.get_markdown()


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
                    break
            is_truncated = len(content) >= _MAX_BYTES
            decoded = content.decode("utf-8", errors="replace")

            if (
                media_type == "text/html"
                or "<html" in decoded.lower()
                or "<body" in decoded.lower()
            ):
                cleaned = html_to_markdown(decoded)
                if not cleaned:
                    cleaned = decoded
                if is_truncated:
                    return cleaned + "\n\n[Document truncated at 128 KiB]"
                return cleaned

            if is_truncated:
                return decoded + "\n[Document truncated at 128 KiB]"
            return decoded
    except httpx.HTTPError as exc:
        raise ToolException(
            "Documentation request failed; check the URL or retry later."
        ) from exc


fetch_documentation.handle_tool_error = True

__all__ = ["fetch_documentation", "html_to_markdown"]

