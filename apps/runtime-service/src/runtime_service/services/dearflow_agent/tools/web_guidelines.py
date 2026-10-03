"""Fixed-source web review rules with verifiable version evidence."""

import hashlib
from datetime import UTC, datetime

from langchain_core.tools import ToolException, tool

from runtime_service.services.dearflow_agent.tools.research_http import get_public

GUIDELINES_URL = "https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md"


@tool
async def fetch_web_guidelines() -> dict:
    """Fetch public web review rules for explicit static audit tasks only; never call during normal page creation or creative tasks. Return exact source, SHA256 and time."""
    data, headers = await get_public(GUIDELINES_URL)
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        raise ToolException("invalid_guidelines_encoding") from exc
    if (
        len(text) > 100000
        or "# " not in text
        or "text/html" in headers.get("content-type", "")
    ):
        raise ToolException("invalid_guidelines_response")
    return {
        "source_url": GUIDELINES_URL,
        "sha256": hashlib.sha256(data).hexdigest(),
        "fetched_at": datetime.now(UTC).isoformat(),
        "etag": headers.get("etag"),
        "content": text,
        "review_scope": "static_only",
    }


fetch_web_guidelines.handle_tool_error = True
