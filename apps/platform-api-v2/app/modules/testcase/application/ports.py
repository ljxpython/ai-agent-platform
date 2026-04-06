from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


class TestcaseDataPort(Protocol):
    async def require_json(
        self,
        method: str,
        path: str,
        *,
        payload: Any = None,
        params: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]: ...

    async def get_binary(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> tuple[bytes, dict[str, str]]: ...
