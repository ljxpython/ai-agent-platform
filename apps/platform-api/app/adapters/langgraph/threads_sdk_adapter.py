from __future__ import annotations

from typing import Any, Mapping

from app.adapters.langgraph.sdk_client import (
    get_langgraph_client,
    raise_runtime_upstream_error,
)


class LangGraphThreadsSdkAdapter:
    _CREATE_FIELDS = (
        "metadata",
        "thread_id",
        "if_exists",
        "supersteps",
        "graph_id",
        "ttl",
    )

    _SEARCH_FIELDS = (
        "metadata",
        "values",
        "ids",
        "status",
        "limit",
        "offset",
        "sort_by",
        "sort_order",
        "select",
        "extract",
    )

    _STATE_FIELDS = (
        "subgraphs",
        "checkpoint_id",
    )

    _HISTORY_FIELDS = (
        "limit",
        "before",
        "metadata",
        "checkpoint",
    )

    _COUNT_FIELDS = (
        "metadata",
        "values",
        "status",
    )

    _PRUNE_FIELDS = (
        "thread_ids",
        "strategy",
    )

    _UPDATE_FIELDS = (
        "metadata",
        "ttl",
    )

    _UPDATE_STATE_FIELDS = (
        "values",
        "as_node",
        "checkpoint",
        "checkpoint_id",
    )

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        forwarded_headers: Mapping[str, str] | None = None,
    ) -> None:
        self._client = get_langgraph_client(
            base_url=base_url,
            api_key=api_key,
            forwarded_headers=forwarded_headers,
            timeout_seconds=timeout_seconds,
        )

    async def get(self, thread_id: str) -> Any:
        try:
            return await self._client.threads.get(thread_id)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_thread_get_failed")

    async def create(self, payload: dict[str, Any] | None = None) -> Any:
        create_payload = {
            key: payload[key]
            for key in self._CREATE_FIELDS
            if payload is not None and key in payload
        }
        try:
            return await self._client.threads.create(**create_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_thread_create_failed")

    async def search(self, payload: dict[str, Any] | None = None) -> Any:
        search_payload = {
            key: payload[key]
            for key in self._SEARCH_FIELDS
            if payload is not None and key in payload
        }
        try:
            return await self._client.threads.search(**search_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_thread_search_failed")

    async def count(self, payload: dict[str, Any] | None = None) -> dict[str, int]:
        count_payload = {
            key: payload[key]
            for key in self._COUNT_FIELDS
            if payload is not None and key in payload
        }
        try:
            count = await self._client.threads.count(**count_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_thread_count_failed")
        return {"count": int(count)}

    async def prune(self, payload: dict[str, Any] | None = None) -> Any:
        prune_payload = {
            key: payload[key]
            for key in self._PRUNE_FIELDS
            if payload is not None and key in payload
        }
        try:
            return await self._client.threads.prune(**prune_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_thread_prune_failed")

    async def update(self, thread_id: str, payload: dict[str, Any] | None = None) -> Any:
        update_payload = {
            key: payload[key]
            for key in self._UPDATE_FIELDS
            if payload is not None and key in payload
        }
        try:
            return await self._client.threads.update(thread_id, **update_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_thread_update_failed")

    async def delete(self, thread_id: str) -> Any:
        try:
            return await self._client.threads.delete(thread_id)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_thread_delete_failed")

    async def copy(self, thread_id: str) -> Any:
        try:
            return await self._client.threads.copy(thread_id)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_thread_copy_failed")

    async def get_state(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        state_payload = {
            key: payload[key]
            for key in self._STATE_FIELDS
            if payload is not None and key in payload
        }
        try:
            return await self._client.threads.get_state(thread_id, **state_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_thread_state_failed")

    async def update_state(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        update_state_payload = {
            key: payload[key]
            for key in self._UPDATE_STATE_FIELDS
            if payload is not None and key in payload
        }
        try:
            return await self._client.threads.update_state(thread_id, **update_state_payload)
        except Exception as exc:
            raise_runtime_upstream_error(
                exc,
                fallback_detail="langgraph_thread_state_update_failed",
            )

    async def get_history(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        history_payload = {
            key: payload[key]
            for key in self._HISTORY_FIELDS
            if payload is not None and key in payload
        }
        try:
            return await self._client.threads.get_history(thread_id, **history_payload)
        except Exception as exc:
            raise_runtime_upstream_error(exc, fallback_detail="langgraph_thread_history_failed")
