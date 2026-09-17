from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class BinaryPayload:
    body: AsyncIterator[bytes]
    content_type: str
    content_length: int | None = None
    etag: str | None = None
    cache_control: str | None = None


class RuntimeGatewayUpstreamProtocol(Protocol):
    async def dear_governance(
        self, thread_id: str, resource: str, *, payload: dict | None = None, query: str = "",
    ) -> dict: ...

    async def get_info(self) -> dict[str, Any]: ...

    async def search_graphs(self, payload: dict[str, Any] | None = None) -> Any: ...

    async def count_graphs(self, payload: dict[str, Any] | None = None) -> Any: ...

    async def create_thread(self, payload: dict[str, Any] | None = None) -> Any: ...

    async def search_threads(self, payload: dict[str, Any] | None = None) -> Any: ...

    async def count_threads(self, payload: dict[str, Any] | None = None) -> Any: ...


    async def get_thread(self, thread_id: str) -> dict[str, Any]: ...


    async def delete_thread(self, thread_id: str) -> Any: ...

    async def update_thread(self, thread_id: str, payload: dict[str, Any]) -> Any: ...


    async def get_thread_state(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any: ...

    async def update_thread_state(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any: ...

    async def get_thread_history(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any: ...











    async def create_thread_run(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any: ...

    async def stream_thread_run(
        self,
        thread_id: str,
        payload: dict[str, Any] | None = None,
    ) -> AsyncIterator[bytes]: ...

    async def send_thread_command(
        self,
        thread_id: str,
        payload: dict[str, Any],
    ) -> Any: ...

    async def stream_thread_events(
        self,
        thread_id: str,
        payload: dict[str, Any],
    ) -> AsyncIterator[bytes]: ...


    async def get_graph_capabilities(self, graph_id: str) -> dict[str, Any]: ...

    async def get_thread_run(self, thread_id: str, run_id: str) -> Any: ...

    async def list_thread_runs(
        self,
        thread_id: str,
        params: dict[str, Any] | None = None,
    ) -> Any: ...

    async def delete_thread_run(self, thread_id: str, run_id: str) -> Any: ...

    async def join_thread_run(self, thread_id: str, run_id: str) -> Any: ...

    async def join_thread_run_stream(
        self,
        thread_id: str,
        run_id: str,
        params: dict[str, Any] | None = None,
    ) -> AsyncIterator[bytes]: ...


    async def cancel_thread_run(
        self,
        thread_id: str,
        run_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Any: ...

    async def upload_thread_image(
        self,
        *,
        graph_id: str,
        thread_id: str,
        sha256: str,
        content_type: str,
        content_length: int,
        body: AsyncIterator[bytes],
    ) -> dict[str, Any]: ...

    async def upload_thread_file(
        self,
        *,
        graph_id: str,
        thread_id: str,
        sha256: str,
        content_type: str,
        content_length: int,
        body: AsyncIterator[bytes],
        file_name: str | None = None,
    ) -> dict[str, Any]: ...

    async def read_thread_file(
        self,
        *,
        graph_id: str,
        thread_id: str,
        path: str,
    ) -> BinaryPayload: ...

    async def workspace_json(self, thread_id: str, resource: str, params: dict[str, Any]) -> dict[str, Any]: ...

    async def workspace_file(self, thread_id: str, resource: str, path: str) -> BinaryPayload: ...

    async def terminal_request(self, thread_id: str, action: str, *, terminal_id: str | None = None,
                               payload: dict | None = None, offset: int = 0) -> dict: ...
