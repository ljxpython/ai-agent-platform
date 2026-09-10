from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from typing import Any

from fastapi.encoders import jsonable_encoder

from platform_api.adapters.langgraph.runtime_client import LangGraphRuntimeClient
from platform_api.adapters.langgraph.sdk_client import (
    get_langgraph_client,
    raise_runtime_upstream_error,
)


def _to_sse_chunk(event: Any) -> bytes:
    if isinstance(event, bytes):
        if event.endswith(b"\n\n"):
            return event
        if event.endswith(b"\n"):
            return event + b"\n"
        return event + b"\n\n"

    if isinstance(event, str):
        if event.startswith(("data:", "event:", "id:", "retry:", ":")):
            if event.endswith("\n\n"):
                return event.encode("utf-8")
            if event.endswith("\n"):
                return f"{event}\n".encode()
            return f"{event}\n\n".encode()
        return f"data: {event}\n\n".encode()

    if isinstance(event, (list, tuple)):
        if len(event) >= 2 and isinstance(event[0], str):
            event_name = event[0]
            event_data = event[1]
            event_id = event[2] if len(event) >= 3 else None
            encoded_data = json.dumps(
                jsonable_encoder(event_data),
                separators=(",", ":"),
                ensure_ascii=False,
            )
            chunks = [f"event: {event_name}\n", f"data: {encoded_data}\n"]
            if event_id is not None:
                chunks.append(f"id: {event_id}\n")
            chunks.append("\n")
            return "".join(chunks).encode("utf-8")

    encoded = json.dumps(
        jsonable_encoder(event),
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return f"data: {encoded}\n\n".encode()


async def _sse_stream(events: Any) -> AsyncIterator[bytes]:
    if hasattr(events, "__aiter__"):
        async for event in events:
            yield _to_sse_chunk(event)
        return

    for event in events:
        yield _to_sse_chunk(event)


class LangGraphRunsSdkAdapter:
    _CREATE_FIELDS = (
        "input",
        "command",
        "stream_mode",
        "stream_subgraphs",
        "stream_resumable",
        "metadata",
        "config",
        "context",
        "checkpoint",
        "checkpoint_id",
        "checkpoint_during",
        "interrupt_before",
        "interrupt_after",
        "webhook",
        "multitask_strategy",
        "if_not_exists",
        "on_completion",
        "after_seconds",
        "durability",
    )

    _STREAM_FIELDS = _CREATE_FIELDS + (
        "version",
        "feedback_keys",
        "on_disconnect",
    )

    _WAIT_FIELDS = _CREATE_FIELDS + (
        "raise_error",
        "on_disconnect",
    )

    _CANCEL_FIELDS = (
        "wait",
        "action",
    )


    _LIST_FIELDS = (
        "limit",
        "offset",
        "status",
        "select",
    )


    _JOIN_STREAM_FIELDS = (
        "cancel_on_disconnect",
        "stream_mode",
        "last_event_id",
    )

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        forwarded_headers: Mapping[str, str] | None = None,
    ) -> None:
        self._http = LangGraphRuntimeClient(
            base_url=base_url, api_key=api_key, timeout_seconds=timeout_seconds or 30,
            forwarded_headers=forwarded_headers,
        )
        self._client = get_langgraph_client(
            base_url=base_url,
            api_key=api_key,
            forwarded_headers=forwarded_headers,
            timeout_seconds=timeout_seconds,
        )

    async def create(self, thread_id: str, payload: dict[str, Any]) -> Any:
        assistant_id = payload["assistant_id"]
        create_payload = {
            key: payload[key] for key in self._CREATE_FIELDS if key in payload
        }
        if payload.get("idempotency_key"):
            create_payload["headers"] = {"Idempotency-Key": payload["idempotency_key"]}
        try:
            return await self._client.runs.create(thread_id, assistant_id, **create_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_request_failed")


    async def stream(self, thread_id: str, payload: dict[str, Any]) -> AsyncIterator[bytes]:
        assistant_id = payload["assistant_id"]
        stream_payload = {
            key: payload[key] for key in self._STREAM_FIELDS if key in payload
        }
        try:
            event_iter = self._client.runs.stream(thread_id, assistant_id, **stream_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_stream_failed")
        return _sse_stream(event_iter)


    async def wait(self, thread_id: str, payload: dict[str, Any]) -> Any:
        assistant_id = payload["assistant_id"]
        wait_payload = {
            key: payload[key] for key in self._WAIT_FIELDS if key in payload
        }
        try:
            return await self._client.runs.wait(thread_id, assistant_id, **wait_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_request_failed")


    async def get(self, thread_id: str, run_id: str) -> Any:
        try:
            return await self._client.runs.get(thread_id, run_id)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_request_failed")

    async def cancel(
        self,
        thread_id: str,
        run_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        cancel_payload = {
            key: payload[key]
            for key in self._CANCEL_FIELDS
            if payload is not None and key in payload
        }
        try:
            return await self._client.runs.cancel(thread_id, run_id, **cancel_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_request_failed")


    async def list(self, thread_id: str, payload: dict[str, Any] | None = None) -> Any:
        list_payload = {
            key: payload[key]
            for key in self._LIST_FIELDS
            if payload is not None and key in payload
        }
        try:
            return await self._client.runs.list(thread_id, **list_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_request_failed")

    async def delete(self, thread_id: str, run_id: str) -> Any:
        try:
            return await self._client.runs.delete(thread_id, run_id)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_request_failed")

    async def join(self, thread_id: str, run_id: str) -> Any:
        try:
            return await self._client.runs.join(thread_id, run_id)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_run_request_failed")

    async def join_stream(
        self,
        thread_id: str,
        run_id: str,
        payload: dict[str, Any] | None = None,
    ) -> AsyncIterator[bytes]:
        if payload is not None and payload.get("cancel_on_disconnect") is True:
            raise ValueError("cancel_on_disconnect=true is not supported")
        join_stream_payload = {
            key: payload[key]
            for key in self._JOIN_STREAM_FIELDS
            if payload is not None and key in payload
        }
        join_stream_payload["cancel_on_disconnect"] = "false"
        last_event_id = join_stream_payload.pop("last_event_id", None)
        return await self._http.stream(
            "GET", f"/threads/{thread_id}/runs/{run_id}/stream",
            params=join_stream_payload,
            forwarded_headers={"Last-Event-ID": str(last_event_id)} if last_event_id is not None else None,
        )
