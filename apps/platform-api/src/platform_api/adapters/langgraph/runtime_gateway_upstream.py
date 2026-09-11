from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from typing import Any

from platform_api.adapters.langgraph.graphs_sdk_adapter import LangGraphGraphsSdkAdapter
from platform_api.adapters.langgraph.runs_sdk_adapter import LangGraphRunsSdkAdapter
from platform_api.adapters.langgraph.runtime_client import LangGraphRuntimeClient
from platform_api.adapters.langgraph.threads_sdk_adapter import (
    LangGraphThreadsSdkAdapter,
)
from platform_api.core.errors import PlatformApiError


class LangGraphRuntimeGatewayUpstream:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        api_key: str | None = None,
        forwarded_headers: Mapping[str, str] | None = None,
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._forwarded_headers = dict(forwarded_headers or {})
        self._http = LangGraphRuntimeClient(
            base_url=base_url,
            timeout_seconds=timeout_seconds,
            api_key=api_key,
            forwarded_headers=forwarded_headers,
        )
        self._graphs = LangGraphGraphsSdkAdapter(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            forwarded_headers=forwarded_headers,
        )
        self._threads = LangGraphThreadsSdkAdapter(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            forwarded_headers=forwarded_headers,
        )
        self._runs = LangGraphRunsSdkAdapter(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            forwarded_headers=forwarded_headers,
        )

    def with_forwarded_headers(
        self, forwarded_headers: Mapping[str, str]
    ) -> LangGraphRuntimeGatewayUpstream:
        """Return a request-scoped upstream with a freshly minted delegation."""
        headers = dict(self._forwarded_headers)
        headers.update(forwarded_headers)
        return LangGraphRuntimeGatewayUpstream(
            base_url=self._base_url,
            api_key=self._api_key,
            timeout_seconds=self._timeout_seconds,
            forwarded_headers=headers,
        )

    async def get_info(self) -> dict[str, Any]:
        return await self._http.require_json("GET", "/info")

    async def search_graphs(self, payload: dict[str, Any] | None = None) -> Any:
        return await self._graphs.search(payload)

    async def count_graphs(self, payload: dict[str, Any] | None = None) -> Any:
        return await self._graphs.count(payload)

    async def create_thread(self, payload: dict[str, Any] | None = None) -> Any:
        return await self._threads.create(payload)

    async def search_threads(self, payload: dict[str, Any] | None = None) -> Any:
        return await self._threads.search(payload)

    async def count_threads(self, payload: dict[str, Any] | None = None) -> Any:
        return await self._threads.count(payload)

    async def enqueue_thread_message(self, thread_id: str, payload: dict[str, Any]) -> Any:
        """Forward a running-thread message through the scoped Runtime delegation."""
        return await self._http.require_json(
            "POST", f"/internal/threads/{thread_id}/messages", payload=payload
        )

    async def list_thread_messages(self, thread_id: str) -> Any:
        return await self._http.require_json("GET", f"/internal/threads/{thread_id}/messages")


    async def get_thread(self, thread_id: str) -> dict[str, Any]:
        value = await self._threads.get(thread_id)
        if isinstance(value, dict):
            return value
        raise PlatformApiError(
            code="langgraph_upstream_invalid_response",
            status_code=502,
            message="LangGraph upstream returned an invalid thread payload",
        )


    async def delete_thread(self, thread_id: str) -> Any:
        return await self._threads.delete(thread_id)


    async def get_thread_state(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        return await self._threads.get_state(thread_id, payload)

    async def update_thread_state(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        return await self._threads.update_state(thread_id, payload)

    async def get_thread_history(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        return await self._threads.get_history(thread_id, payload)











    async def create_thread_run(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        return await self._runs.create(thread_id, payload or {})

    async def stream_thread_run(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> AsyncIterator[bytes]:
        return await self._runs.stream(thread_id, payload or {})

    async def send_thread_command(
        self,
        thread_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return await self._http.request_json(
            "POST",
            f"/threads/{thread_id}/commands",
            payload=payload,
        )

    async def stream_thread_events(
        self,
        thread_id: str,
        payload: dict[str, Any],
    ) -> AsyncIterator[bytes]:
        return await self._http.stream(
            "POST",
            f"/threads/{thread_id}/stream/events",
            payload=payload,
        )


    async def get_thread_run(self, thread_id: str, run_id: str) -> Any:
        return await self._runs.get(thread_id, run_id)

    async def list_thread_runs(
        self,
        thread_id: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        return await self._runs.list(thread_id, params)

    async def delete_thread_run(self, thread_id: str, run_id: str) -> Any:
        return await self._runs.delete(thread_id, run_id)

    async def join_thread_run(self, thread_id: str, run_id: str) -> Any:
        return await self._runs.join(thread_id, run_id)

    async def join_thread_run_stream(
        self,
        thread_id: str,
        run_id: str,
        params: dict[str, Any] | None = None,
    ) -> AsyncIterator[bytes]:
        return await self._runs.join_stream(thread_id, run_id, params)


    async def cancel_thread_run(
        self,
        thread_id: str,
        run_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        return await self._runs.cancel(thread_id, run_id, payload)
