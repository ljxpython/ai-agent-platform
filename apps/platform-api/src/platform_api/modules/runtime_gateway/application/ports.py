from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol


class RuntimeGatewayUpstreamProtocol(Protocol):
    async def get_info(self) -> dict[str, Any]: ...

    async def search_graphs(self, payload: dict[str, Any] | None = None) -> Any: ...

    async def count_graphs(self, payload: dict[str, Any] | None = None) -> Any: ...

    async def create_thread(self, payload: dict[str, Any] | None = None) -> Any: ...

    async def search_threads(self, payload: dict[str, Any] | None = None) -> Any: ...

    async def count_threads(self, payload: dict[str, Any] | None = None) -> Any: ...


    async def get_thread(self, thread_id: str) -> dict[str, Any]: ...


    async def delete_thread(self, thread_id: str) -> Any: ...


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
