from __future__ import annotations

from typing import Any, Mapping

from platform_api.adapters.langgraph.runtime_client import LangGraphRuntimeClient


class LangGraphGraphsSdkAdapter:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
        forwarded_headers: Mapping[str, str] | None = None,
    ) -> None:
        self._client = LangGraphRuntimeClient(
            base_url=base_url,
            api_key=api_key,
            forwarded_headers=forwarded_headers,
            timeout_seconds=timeout_seconds if timeout_seconds is not None else 30.0,
        )

    async def search(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        normalized_payload = payload if isinstance(payload, dict) else {}
        limit = self._as_non_negative_int(normalized_payload.get("limit"), default=50)
        offset = self._as_non_negative_int(normalized_payload.get("offset"), default=0)
        query = self._as_string(normalized_payload.get("query")).strip().lower()
        sort_order = (
            self._as_string(normalized_payload.get("sort_order")).strip().lower() or "asc"
        )
        if sort_order not in {"asc", "desc"}:
            sort_order = "asc"

        graphs = await self._collect_graphs(normalized_payload)
        if query:
            graphs = [
                item
                for item in graphs
                if query in item["graph_id"].lower()
                or query in self._as_string(item.get("description")).strip().lower()
            ]

        reverse = sort_order == "desc"
        graphs.sort(key=lambda item: item["graph_id"].lower(), reverse=reverse)

        total = len(graphs)
        paginated_items = graphs[offset : offset + limit]
        return {
            "items": paginated_items,
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    async def count(self, payload: dict[str, Any] | None = None) -> dict[str, int]:
        normalized_payload = payload if isinstance(payload, dict) else {}
        query = self._as_string(normalized_payload.get("query")).strip().lower()
        graphs = await self._collect_graphs(normalized_payload)
        if query:
            graphs = [
                item
                for item in graphs
                if query in item["graph_id"].lower()
                or query in self._as_string(item.get("description")).strip().lower()
            ]
        return {"count": len(graphs)}

    async def _collect_graphs(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        return await self._client.list_deployed_graphs()

    @staticmethod
    def _as_non_negative_int(value: Any, *, default: int) -> int:
        if isinstance(value, bool):
            return default
        if isinstance(value, int):
            return max(0, value)
        if isinstance(value, str) and value.isdigit():
            return int(value)
        return default

    @staticmethod
    def _as_string(value: Any) -> str:
        return value if isinstance(value, str) else ""
