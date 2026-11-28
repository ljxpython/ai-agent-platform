"""Extract requested, executed, and blocked tool events from thread messages & diagnostics."""

from __future__ import annotations

import json
from typing import Any


def _message_role(msg: dict[str, Any]) -> str:
    return str(msg.get("role") or msg.get("type") or "").lower()


def _parse_args(raw_args: Any) -> dict[str, Any]:
    if isinstance(raw_args, dict):
        return raw_args
    if isinstance(raw_args, str):
        try:
            parsed = json.loads(raw_args)
            return parsed if isinstance(parsed, dict) else {"raw": raw_args}
        except json.JSONDecodeError:
            return {"raw": raw_args}
    return {}


def _extract_ai_tool_calls(msg: dict[str, Any]) -> list[dict[str, Any]]:
    calls = msg.get("tool_calls")
    if isinstance(calls, list) and calls:
        out = []
        for c in calls:
            if not isinstance(c, dict):
                continue
            fn = c.get("function") if isinstance(c.get("function"), dict) else None
            name = fn.get("name") if fn else c.get("name")
            args = fn.get("arguments") if fn else c.get("args")
            if isinstance(name, str) and name:
                out.append(
                    {
                        "id": str(c.get("id") or ""),
                        "name": name,
                        "args": _parse_args(args),
                    }
                )
        return out
    content = msg.get("content")
    if isinstance(content, list):
        out = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_call" and block.get("name"):
                out.append(
                    {
                        "id": str(block.get("id") or ""),
                        "name": str(block["name"]),
                        "args": _parse_args(block.get("args") or block.get("input")),
                    }
                )
        return out
    return []


def extract_tool_evidence(
    messages: list[dict[str, Any]],
    *,
    rejected_interrupts: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Return normalized tool events and whether every requested tool call has an outcome."""
    requested_by_id: dict[str, dict[str, Any]] = {}
    ordered_events: list[dict[str, Any]] = []
    settled_ids: set[str] = set()

    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = _message_role(msg)
        if role in {"assistant", "ai"}:
            for call in _extract_ai_tool_calls(msg):
                cid = call["id"]
                ev = {
                    "id": cid,
                    "name": call["name"],
                    "args": call["args"],
                    "status": "requested",
                }
                if cid:
                    requested_by_id[cid] = ev
                ordered_events.append(ev)
        elif role == "tool":
            cid = str(msg.get("tool_call_id") or "")
            tool_name = str(msg.get("name") or requested_by_id.get(cid, {}).get("name") or "")
            raw_status = str(msg.get("status") or "success").lower()
            if raw_status in {"error", "failed"}:
                final_status = "error"
            elif raw_status in {"blocked", "rejected"}:
                final_status = "blocked"
            else:
                final_status = "executed"
            if cid and cid in requested_by_id:
                requested_by_id[cid]["status"] = final_status
                requested_by_id[cid]["output_preview"] = str(msg.get("content") or "")[:500]
                settled_ids.add(cid)
            elif tool_name:
                ordered_events.append(
                    {
                        "id": cid,
                        "name": tool_name,
                        "args": {},
                        "status": final_status,
                        "output_preview": str(msg.get("content") or "")[:500],
                    }
                )

    for rej in rejected_interrupts or []:
        if not isinstance(rej, dict):
            continue
        for action in rej.get("action_requests") or []:
            if not isinstance(action, dict):
                continue
            aid = str(action.get("id") or "")
            aname = str(action.get("name") or "")
            aargs = _parse_args(action.get("args"))
            matched_ev: dict[str, Any] | None = None
            if aid and aid in requested_by_id:
                matched_ev = requested_by_id[aid]
            elif aname:
                for ev in reversed(ordered_events):
                    if ev.get("status") == "requested" and ev.get("name") == aname:
                        if not aargs or ev.get("args") == aargs:
                            matched_ev = ev
                            break
            if matched_ev is not None:
                matched_ev["status"] = "blocked"
                if matched_ev.get("id"):
                    settled_ids.add(str(matched_ev["id"]))
            else:
                ordered_events.append(
                    {
                        "id": aid,
                        "name": aname,
                        "args": aargs,
                        "status": "blocked",
                    }
                )

    complete = all(
        (ev.get("status") != "requested") or (ev.get("id") in settled_ids)
        for ev in ordered_events
        if ev.get("id")
    )
    return ordered_events, complete
