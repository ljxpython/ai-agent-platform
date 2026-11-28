"""SSE stream parser to measure real end-to-end TTFT (Time To First Token)."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any


@dataclass
class SseProbeResult:
    ttft_ms: int | None
    duration_ms: int
    first_event_ms: int | None
    final_text: str
    terminal_status: str
    error_category: str = "none"
    run_id: str | None = None
    interrupts: list[dict[str, Any]] | None = None


def _text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def _extract_assistant_text(payload: Any) -> str:
    if isinstance(payload, list) and payload:
        # Handle LangGraph message arrays or [AIMessage, metadata] tuples
        chunks: list[str] = []
        for item in reversed(payload):
            if not isinstance(item, dict):
                continue
            role = item.get("role", item.get("type"))
            if role in {"assistant", "ai"}:
                text = _text_from_content(item.get("content"))
                if text:
                    return text
        for item in payload:
            if not isinstance(item, dict):
                continue
            if item.get("event") == "message-start":
                continue
            delta = item.get("delta")
            if isinstance(delta, dict) and delta.get("type") == "text" and isinstance(delta.get("text"), str):
                chunks.append(delta["text"])
            elif isinstance(delta, str):
                chunks.append(delta)
            elif isinstance(item.get("text"), str):
                chunks.append(item["text"])
            elif item.get("content") and item.get("role", item.get("type")) in {"assistant", "ai", None}:
                chunks.append(_text_from_content(item["content"]))
        if chunks:
            return "".join(chunks)
    if isinstance(payload, dict):
        delta = payload.get("delta")
        if isinstance(delta, dict) and isinstance(delta.get("text"), str):
            return delta["text"]
        if isinstance(delta, str):
            return delta
        if isinstance(payload.get("text"), str):
            return payload["text"]
        if payload.get("role", payload.get("type")) in {"assistant", "ai"}:
            return _text_from_content(payload.get("content"))
    return ""


def _unwrap_frame(raw_event_name: str, raw_payload: Any) -> tuple[str, Any]:
    event_name = raw_event_name.partition("|")[0]
    if (
        isinstance(raw_payload, dict)
        and isinstance(raw_payload.get("method"), str)
        and isinstance(raw_payload.get("params"), dict)
    ):
        method = str(raw_payload["method"])
        data = raw_payload["params"].get("data", raw_payload["params"])
        return (event_name or method), data
    return event_name, raw_payload


def probe_sse_stream(
    lines: Iterable[str],
    *,
    started_monotonic: float,
    clock: Callable[[], float] = time.monotonic,
) -> SseProbeResult:
    """Parse platform SSE lines and compute real TTFT on first non-empty assistant text."""
    event_name = ""
    ttft_ms: int | None = None
    first_event_ms: int | None = None
    final_text = ""
    terminal_status = "success"
    run_id: str | None = None
    interrupts: list[dict[str, Any]] | None = None

    for raw in lines:
        line = raw.rstrip("\r\n")
        if not line or line.startswith(":"):
            continue
        if line.startswith("event:"):
            event_name = line[6:].strip()
            continue
        if not line.startswith("data:"):
            continue
        raw_data = line[5:].strip()
        if not raw_data:
            continue
        now_ms = int(round((clock() - started_monotonic) * 1000))
        if first_event_ms is None:
            first_event_ms = now_ms
        try:
            parsed = json.loads(raw_data)
        except json.JSONDecodeError:
            continue

        method, payload = _unwrap_frame(event_name, parsed)
        if method == "metadata" and isinstance(payload, dict):
            run_id = payload.get("run_id") or run_id
            continue
        if method == "lifecycle" and isinstance(payload, dict):
            if payload.get("run_id"):
                run_id = run_id or str(payload["run_id"])
            if payload.get("event") == "failed":
                terminal_status = "error"
            continue
        if method == "error":
            terminal_status = "error"
            continue
        if method in {"messages/partial", "messages/metadata", "messages"}:
            text = _extract_assistant_text(payload)
            if text:
                if ttft_ms is None and text.strip():
                    ttft_ms = max(0, now_ms)
                final_text = text if method == "messages/partial" else final_text + text
        elif method == "values" and isinstance(payload, dict):
            if payload.get("__interrupt__"):
                interrupts = list(payload["__interrupt__"])
                terminal_status = "interrupted"
            msgs = payload.get("messages")
            if isinstance(msgs, list):
                text = _extract_assistant_text(msgs)
                if text.strip():
                    if ttft_ms is None:
                        ttft_ms = max(0, now_ms)
                    final_text = text

    duration_ms = max(0, int(round((clock() - started_monotonic) * 1000)))
    return SseProbeResult(
        ttft_ms=ttft_ms,
        duration_ms=duration_ms,
        first_event_ms=first_event_ms,
        final_text=final_text,
        terminal_status=terminal_status,
        run_id=run_id,
        interrupts=interrupts,
    )
