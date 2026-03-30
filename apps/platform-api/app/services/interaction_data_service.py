from __future__ import annotations

from typing import Any

from app.services.local_json_http_client import LocalJsonHttpClient
from fastapi import HTTPException, Request

_DOCUMENTS_PATH = "/api/test-case-service/documents"
_TEST_CASES_PATH = "/api/test-case-service/test-cases"
_OVERVIEW_PATH = "/api/test-case-service/overview"
_BATCHES_PATH = "/api/test-case-service/batches"
_DEFAULT_EXPORT_PAGE_SIZE = 200


class InteractionDataService:
    def __init__(self, request: Request) -> None:
        settings = request.app.state.settings
        self._client = LocalJsonHttpClient(
            request,
            base_url=settings.interaction_data_service_url,
            token=settings.interaction_data_service_token,
            timeout_seconds=settings.interaction_data_service_timeout_seconds,
            service_name="interaction_data_service",
        )

    @staticmethod
    def _project_params(project_id: str) -> dict[str, Any]:
        return {"project_id": project_id}

    @staticmethod
    def _ensure_project_match(payload: Any, project_id: str, *, detail: str) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="interaction_data_service_invalid_response")
        payload_project_id = str(payload.get("project_id") or "").strip()
        if payload_project_id != project_id:
            raise HTTPException(status_code=404, detail=detail)
        return payload

    async def get_overview(self, project_id: str) -> dict[str, Any]:
        payload = await self._client.get(_OVERVIEW_PATH, params=self._project_params(project_id))
        return self._ensure_project_match(payload, project_id, detail="testcase_overview_not_found")

    async def list_batches(self, project_id: str, *, limit: int, offset: int) -> dict[str, Any]:
        payload = await self._client.get(
            _BATCHES_PATH,
            params={**self._project_params(project_id), "limit": limit, "offset": offset},
        )
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="interaction_data_service_invalid_response")
        return payload

    async def list_cases(
        self,
        project_id: str,
        *,
        status: str | None,
        batch_id: str | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {**self._project_params(project_id), "limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if batch_id:
            params["batch_id"] = batch_id
        if query:
            params["query"] = query
        payload = await self._client.get(_TEST_CASES_PATH, params=params)
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="interaction_data_service_invalid_response")
        return payload

    async def get_case(self, project_id: str, case_id: str) -> dict[str, Any]:
        payload = await self._client.get(f"{_TEST_CASES_PATH}/{case_id}")
        return self._ensure_project_match(payload, project_id, detail="test_case_not_found")

    async def list_all_cases_for_export(
        self,
        project_id: str,
        *,
        status: str | None,
        batch_id: str | None,
        query: str | None,
        max_items: int,
    ) -> tuple[list[dict[str, Any]], int]:
        first_page = await self.list_cases(
            project_id,
            status=status,
            batch_id=batch_id,
            query=query,
            limit=min(_DEFAULT_EXPORT_PAGE_SIZE, max_items + 1),
            offset=0,
        )
        total = int(first_page.get("total") or 0)
        if total > max_items:
            raise HTTPException(
                status_code=400,
                detail=f"testcase_export_limit_exceeded:{total}>{max_items}",
            )
        items = list(first_page.get("items") or [])
        if len(items) >= total:
            return items[:total], total

        offset = len(items)
        while offset < total:
            page = await self.list_cases(
                project_id,
                status=status,
                batch_id=batch_id,
                query=query,
                limit=min(_DEFAULT_EXPORT_PAGE_SIZE, total - offset),
                offset=offset,
            )
            chunk = list(page.get("items") or [])
            items.extend(chunk)
            if not chunk:
                break
            offset = len(items)
        return items[:total], total

    async def create_case(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        next_payload = {**payload, "project_id": project_id}
        created = await self._client.post(_TEST_CASES_PATH, json_body=next_payload)
        return self._ensure_project_match(created, project_id, detail="test_case_not_found")

    async def update_case(self, project_id: str, case_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        await self.get_case(project_id, case_id)
        updated = await self._client.patch(f"{_TEST_CASES_PATH}/{case_id}", json_body=payload)
        return self._ensure_project_match(updated, project_id, detail="test_case_not_found")

    async def delete_case(self, project_id: str, case_id: str) -> dict[str, Any]:
        await self.get_case(project_id, case_id)
        payload = await self._client.delete(f"{_TEST_CASES_PATH}/{case_id}")
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="interaction_data_service_invalid_response")
        return payload

    async def list_documents(
        self,
        project_id: str,
        *,
        batch_id: str | None,
        parse_status: str | None,
        query: str | None,
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {**self._project_params(project_id), "limit": limit, "offset": offset}
        if batch_id:
            params["batch_id"] = batch_id
        if parse_status:
            params["parse_status"] = parse_status
        if query:
            params["query"] = query
        payload = await self._client.get(_DOCUMENTS_PATH, params=params)
        if not isinstance(payload, dict):
            raise HTTPException(status_code=502, detail="interaction_data_service_invalid_response")
        return payload

    async def get_document(self, project_id: str, document_id: str) -> dict[str, Any]:
        payload = await self._client.get(f"{_DOCUMENTS_PATH}/{document_id}")
        return self._ensure_project_match(payload, project_id, detail="document_not_found")
