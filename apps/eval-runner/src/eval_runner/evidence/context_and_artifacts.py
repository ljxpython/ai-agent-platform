"""Extract retrieved RAG contexts and normalize workspace artifact evidence."""

from __future__ import annotations

import json
from typing import Any, Literal

RETRIEVAL_TOOL_NAMES = frozenset(
    {
        "knowledge_search",
        "search_knowledge",
        "retrieve_knowledge",
        "query_knowledge",
        "lightrag_query",
        "rag_search",
        "rag_retrieve",
    }
)


def _is_retrieval_tool(name: str) -> bool:
    low = name.lower()
    if low in RETRIEVAL_TOOL_NAMES:
        return True
    return any(tok in low for tok in ("knowledge", "retrieve", "lightrag", "rag_"))


def _content_text(raw: Any) -> str:
    if isinstance(raw, str):
        return raw.strip()
    if isinstance(raw, list):
        parts = []
        for item in raw:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts).strip()
    if isinstance(raw, dict):
        return json.dumps(raw, ensure_ascii=False)
    return ""


def extract_retrieved_contexts(
    messages: list[dict[str, Any]],
) -> tuple[list[str], Literal["recorded", "recorded_empty", "not_recorded"]]:
    """Scan executed ToolMessages for RAG/Knowledge retrieval payloads."""
    contexts: list[str] = []
    saw_retrieval_call = False
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or msg.get("type") or "").lower()
        name = str(msg.get("name") or "")
        if role == "tool" and name and _is_retrieval_tool(name):
            saw_retrieval_call = True
            text = _content_text(msg.get("content"))
            if text and text not in contexts:
                contexts.append(text)
    if not saw_retrieval_call:
        return [], "not_recorded"
    if not contexts:
        return [], "recorded_empty"
    return contexts, "recorded"
