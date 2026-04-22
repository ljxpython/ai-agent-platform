from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from app.core.context.models import ActorContext
from app.core.db import SqlAlchemyUnitOfWork
from app.core.errors import (
    BadRequestError,
    ForbiddenError,
    NotFoundError,
    PlatformApiError,
    ServiceUnavailableError,
)
from app.core.identifiers import parse_uuid
from app.core.normalization import clean_str, payload_to_dict
from app.modules.iam.application import AuthorizationRequest, IamPolicyEngine, PermissionCode
from app.modules.iam.domain import ProjectRole
from app.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository
from app.modules.testcase.application.contracts import (
    CreateTestcaseCaseCommand,
    ExportTestcaseCasesQuery,
    ExportTestcaseDocumentsQuery,
    GetTestcaseBatchDetailQuery,
    ListTestcaseBatchesQuery,
    ListTestcaseCasesQuery,
    ListTestcaseDocumentsQuery,
    UpdateTestcaseCaseCommand,
)
from app.modules.testcase.application.exporters import (
    MAX_TESTCASE_DOCUMENT_EXPORT_ROWS,
    MAX_TESTCASE_EXPORT_ROWS,
    TESTCASE_DOCUMENT_EXPORT_MEDIA_TYPE,
    TESTCASE_EXPORT_MEDIA_TYPE,
    build_testcase_cases_workbook,
    build_testcase_documents_workbook,
    resolve_testcase_export_columns,
)
from app.modules.testcase.application.ports import TestcaseDataPort
from app.modules.testcase.domain import (
    TestcaseBatchDetail,
    TestcaseBatchDetailCase,
    TestcaseBatchDetailCasePage,
    TestcaseBatchPage,
    TestcaseBatchSummary,
    TestcaseCase,
    TestcaseCasePage,
    TestcaseDocument,
    TestcaseDocumentPage,
    TestcaseDocumentRelationCase,
    TestcaseDocumentRelations,
    TestcaseOverview,
    TestcaseRoleView,
)

_DOCUMENTS_PATH = "/api/test-case-service/documents"
_TEST_CASES_PATH = "/api/test-case-service/test-cases"
_OVERVIEW_PATH = "/api/test-case-service/overview"
_BATCHES_PATH = "/api/test-case-service/batches"
_DEFAULT_EXPORT_PAGE_SIZE = 500
_ROLE_PRIORITY: tuple[tuple[str, str], ...] = (
    (ProjectRole.ADMIN.value, "admin"),
    (ProjectRole.EDITOR.value, "editor"),
    (ProjectRole.EXECUTOR.value, "executor"),
)


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for item in value:
        normalized = clean_str(item)
        if normalized and normalized not in seen:
            seen.add(normalized)
            items.append(normalized)
    return items


def _normalize_testcase_payload(payload: dict[str, Any]) -> dict[str, Any]:
    next_payload = dict(payload)
    for key in ("batch_id", "case_id", "module_name", "priority"):
        if key in next_payload:
            next_payload[key] = clean_str(next_payload.get(key))
    if "title" in next_payload:
        title = clean_str(next_payload.get("title"))
        if title is not None:
            next_payload["title"] = title
    if "description" in next_payload and next_payload.get("description") is None:
        next_payload["description"] = ""
    if "source_document_ids" in next_payload:
        next_payload["source_document_ids"] = _normalize_string_list(
            next_payload.get("source_document_ids")
        )
    return next_payload


class TestcaseService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session] | None,
        upstream: TestcaseDataPort,
        policy_engine: IamPolicyEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._upstream = upstream
        self._policy_engine = policy_engine or IamPolicyEngine()

    def _require_session_factory(self) -> sessionmaker[Session]:
        if self._session_factory is None:
            raise ServiceUnavailableError(
                code="platform_database_not_enabled",
                message="Platform database is not enabled",
            )
        return self._session_factory

    def _require_permission(self, *, actor: ActorContext, project_id: str, write: bool) -> None:
        self._policy_engine.require(
            actor=actor,
            authorization=AuthorizationRequest(
                permission=(
                    PermissionCode.PROJECT_TESTCASE_WRITE
                    if write
                    else PermissionCode.PROJECT_TESTCASE_READ
                ),
                project_id=project_id,
            ),
        )

    async def _prepare_project_scope(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        write: bool,
    ) -> None:
        session_factory = self._require_session_factory()
        self._require_permission(actor=actor, project_id=project_id, write=write)
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            project_uuid = parse_uuid(project_id, code="invalid_project_id")
            repository = SqlAlchemyProjectsRepository(uow.session)
            project = repository.get_project_by_id(project_uuid)
            if project is None or project.status == "deleted":
                raise NotFoundError(message="Project not found", code="project_not_found")

    @staticmethod
    def _ensure_object(payload: Any, *, code: str) -> dict[str, Any]:
        if isinstance(payload, dict):
            return payload
        raise PlatformApiError(
            code=code,
            status_code=502,
            message="Interaction-data-service returned an invalid object payload",
        )

    def _ensure_project_match(
        self,
        payload: Any,
        *,
        project_id: str,
        code: str,
    ) -> dict[str, Any]:
        payload_dict = self._ensure_object(payload, code="interaction_data_invalid_response")
        if clean_str(payload_dict.get("project_id")) != project_id:
            raise NotFoundError(message=code, code=code)
        return payload_dict

    @staticmethod
    def _normalize_total(payload: dict[str, Any], *, fallback_items: list[Any]) -> int:
        total = payload.get("total")
        if isinstance(total, int):
            return total
        return len(fallback_items)

    @staticmethod
    def _normalize_items(value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    def _resolve_role(self, *, actor: ActorContext, project_id: str) -> str:
        if actor.has_platform_role("platform_super_admin"):
            return "admin"

        role_set = set(actor.project_role_set(project_id))
        for role_value, label in _ROLE_PRIORITY:
            if role_value in role_set:
                return label

        raise ForbiddenError(code="project_role_missing", message="project_role_missing")

    async def _require_document(self, *, project_id: str, document_id: str) -> TestcaseDocument:
        payload = await self._upstream.require_json("GET", f"{_DOCUMENTS_PATH}/{document_id}")
        document = self._ensure_project_match(
            payload,
            project_id=project_id,
            code="document_not_found",
        )
        return TestcaseDocument.model_validate(document)

    async def _require_case(self, *, project_id: str, case_id: str) -> TestcaseCase:
        payload = await self._upstream.require_json("GET", f"{_TEST_CASES_PATH}/{case_id}")
        testcase = self._ensure_project_match(
            payload,
            project_id=project_id,
            code="test_case_not_found",
        )
        return TestcaseCase.model_validate(testcase)

    async def _list_all_cases_for_export(
        self,
        *,
        project_id: str,
        query: ExportTestcaseCasesQuery,
        max_items: int,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "project_id": project_id,
            "limit": min(_DEFAULT_EXPORT_PAGE_SIZE, max_items + 1),
            "offset": 0,
        }
        if clean_str(query.batch_id):
            params["batch_id"] = query.batch_id
        if clean_str(query.status):
            params["status"] = query.status
        if clean_str(query.query):
            params["query"] = query.query
        first_payload = self._ensure_object(
            await self._upstream.require_json("GET", _TEST_CASES_PATH, params=params),
            code="interaction_data_invalid_response",
        )
        first_items = self._normalize_items(first_payload.get("items"))
        total = self._normalize_total(first_payload, fallback_items=first_items)
        if total > max_items:
            raise BadRequestError(
                code="testcase_export_limit_exceeded",
                message=f"testcase_export_limit_exceeded:{total}>{max_items}",
            )
        items = list(first_items)
        if len(items) >= total:
            return items[:total]

        offset = len(items)
        while offset < total:
            page_payload = self._ensure_object(
                await self._upstream.require_json(
                    "GET",
                    _TEST_CASES_PATH,
                    params={**params, "limit": min(_DEFAULT_EXPORT_PAGE_SIZE, total - offset), "offset": offset},
                ),
                code="interaction_data_invalid_response",
            )
            chunk = self._normalize_items(page_payload.get("items"))
            items.extend(chunk)
            if not chunk:
                break
            offset = len(items)
        return items[:total]

    async def _list_all_documents_for_export(
        self,
        *,
        project_id: str,
        query: ExportTestcaseDocumentsQuery,
        max_items: int,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "project_id": project_id,
            "limit": min(_DEFAULT_EXPORT_PAGE_SIZE, max_items + 1),
            "offset": 0,
        }
        if clean_str(query.batch_id):
            params["batch_id"] = query.batch_id
        if clean_str(query.parse_status):
            params["parse_status"] = query.parse_status
        if clean_str(query.query):
            params["query"] = query.query
        first_payload = self._ensure_object(
            await self._upstream.require_json("GET", _DOCUMENTS_PATH, params=params),
            code="interaction_data_invalid_response",
        )
        first_items = self._normalize_items(first_payload.get("items"))
        total = self._normalize_total(first_payload, fallback_items=first_items)
        if total > max_items:
            raise BadRequestError(
                code="testcase_export_limit_exceeded",
                message=f"testcase_export_limit_exceeded:{total}>{max_items}",
            )
        items = list(first_items)
        if len(items) >= total:
            return items[:total]

        offset = len(items)
        while offset < total:
            page_payload = self._ensure_object(
                await self._upstream.require_json(
                    "GET",
                    _DOCUMENTS_PATH,
                    params={**params, "limit": min(_DEFAULT_EXPORT_PAGE_SIZE, total - offset), "offset": offset},
                ),
                code="interaction_data_invalid_response",
            )
            chunk = self._normalize_items(page_payload.get("items"))
            items.extend(chunk)
            if not chunk:
                break
            offset = len(items)
        return items[:total]

    async def get_overview(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> TestcaseOverview:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        payload = await self._upstream.require_json(
            "GET",
            _OVERVIEW_PATH,
            params={"project_id": project_id},
        )
        normalized = self._ensure_project_match(
            payload,
            project_id=project_id,
            code="testcase_overview_not_found",
        )
        return TestcaseOverview.model_validate(normalized)

    async def get_role(
        self,
        *,
        actor: ActorContext,
        project_id: str,
    ) -> TestcaseRoleView:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        role = self._resolve_role(actor=actor, project_id=project_id)
        return TestcaseRoleView(
            project_id=project_id,
            role=role,
            can_write_testcase=role in {"admin", "editor"},
        )

    async def list_batches(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        query: ListTestcaseBatchesQuery,
    ) -> TestcaseBatchPage:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        payload = self._ensure_object(
            await self._upstream.require_json(
                "GET",
                _BATCHES_PATH,
                params={
                    "project_id": project_id,
                    "limit": query.limit,
                    "offset": query.offset,
                },
            ),
            code="interaction_data_invalid_response",
        )
        items = [
            TestcaseBatchSummary.model_validate(item)
            for item in self._normalize_items(payload.get("items"))
        ]
        return TestcaseBatchPage(
            items=items,
            total=self._normalize_total(payload, fallback_items=items),
        )

    async def get_batch_detail(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        batch_id: str,
        query: GetTestcaseBatchDetailQuery,
    ) -> TestcaseBatchDetail:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        normalized_batch_id = clean_str(batch_id)
        if normalized_batch_id is None:
            raise BadRequestError(code="invalid_batch_id", message="invalid_batch_id")

        payload = self._ensure_object(
            await self._upstream.require_json(
                "GET",
                f"{_BATCHES_PATH}/{normalized_batch_id}",
                params={
                    "project_id": project_id,
                    "document_limit": query.document_limit,
                    "document_offset": query.document_offset,
                    "case_limit": query.case_limit,
                    "case_offset": query.case_offset,
                },
            ),
            code="interaction_data_invalid_response",
        )
        batch_payload = self._ensure_object(
            payload.get("batch"),
            code="interaction_data_invalid_response",
        )
        if clean_str(batch_payload.get("batch_id")) != normalized_batch_id:
            raise NotFoundError(code="testcase_batch_not_found", message="testcase_batch_not_found")

        document_page_payload = self._ensure_object(
            payload.get("documents"),
            code="interaction_data_invalid_response",
        )
        case_page_payload = self._ensure_object(
            payload.get("test_cases"),
            code="interaction_data_invalid_response",
        )
        document_items = [
            TestcaseDocument.model_validate(item)
            for item in self._normalize_items(document_page_payload.get("items"))
        ]
        case_items = [
            TestcaseBatchDetailCase.model_validate(item)
            for item in self._normalize_items(case_page_payload.get("items"))
        ]
        return TestcaseBatchDetail(
            batch=TestcaseBatchSummary.model_validate(batch_payload),
            documents=TestcaseDocumentPage(
                items=document_items,
                total=self._normalize_total(
                    document_page_payload,
                    fallback_items=document_items,
                ),
            ),
            test_cases=TestcaseBatchDetailCasePage(
                items=case_items,
                total=self._normalize_total(case_page_payload, fallback_items=case_items),
            ),
        )

    async def list_documents(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        query: ListTestcaseDocumentsQuery,
        skip_scope_check: bool = False,
    ) -> TestcaseDocumentPage:
        if not skip_scope_check:
            await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        params: dict[str, Any] = {
            "project_id": project_id,
            "limit": query.limit,
            "offset": query.offset,
        }
        if clean_str(query.batch_id):
            params["batch_id"] = query.batch_id
        if clean_str(query.parse_status):
            params["parse_status"] = query.parse_status
        if clean_str(query.query):
            params["query"] = query.query

        payload = self._ensure_object(
            await self._upstream.require_json("GET", _DOCUMENTS_PATH, params=params),
            code="interaction_data_invalid_response",
        )
        items = [
            TestcaseDocument.model_validate(item)
            for item in self._normalize_items(payload.get("items"))
        ]
        return TestcaseDocumentPage(
            items=items,
            total=self._normalize_total(payload, fallback_items=items),
        )

    async def get_document(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        document_id: str,
    ) -> TestcaseDocument:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        return await self._require_document(project_id=project_id, document_id=document_id)

    async def get_document_relations(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        document_id: str,
    ) -> TestcaseDocumentRelations:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        payload = self._ensure_object(
            await self._upstream.require_json(
                "GET",
                f"{_DOCUMENTS_PATH}/{document_id}/relations",
            ),
            code="interaction_data_invalid_response",
        )
        document = self._ensure_project_match(
            payload.get("document"),
            project_id=project_id,
            code="document_not_found",
        )
        related_cases = [
            TestcaseDocumentRelationCase.model_validate(item)
            for item in self._normalize_items(payload.get("related_cases"))
        ]
        related_cases_count = payload.get("related_cases_count")
        return TestcaseDocumentRelations(
            document=TestcaseDocument.model_validate(document),
            runtime_meta=payload.get("runtime_meta")
            if isinstance(payload.get("runtime_meta"), dict)
            else {},
            related_cases=related_cases,
            related_cases_count=(
                related_cases_count if isinstance(related_cases_count, int) else len(related_cases)
            ),
        )

    async def get_document_binary(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        document_id: str,
        inline: bool,
    ) -> tuple[bytes, dict[str, str]]:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        await self._require_document(project_id=project_id, document_id=document_id)
        suffix = "preview" if inline else "download"
        return await self._upstream.get_binary(f"{_DOCUMENTS_PATH}/{document_id}/{suffix}")

    async def export_documents(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        query: ExportTestcaseDocumentsQuery,
    ) -> tuple[str, str, bytes]:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        items = await self._list_all_documents_for_export(
            project_id=project_id,
            query=query,
            max_items=MAX_TESTCASE_DOCUMENT_EXPORT_ROWS,
        )
        enriched_items: list[dict[str, Any]] = []
        for item in items:
            document_id = clean_str(item.get("id"))
            related_cases_count = 0
            if document_id:
                relations_payload = self._ensure_object(
                    await self._upstream.require_json(
                        "GET",
                        f"{_DOCUMENTS_PATH}/{document_id}/relations",
                    ),
                    code="interaction_data_invalid_response",
                )
                document_payload = self._ensure_project_match(
                    relations_payload.get("document"),
                    project_id=project_id,
                    code="document_not_found",
                )
                if clean_str(document_payload.get("id")) == document_id:
                    related_cases_count = int(relations_payload.get("related_cases_count") or 0)
            enriched_items.append({**item, "related_cases_count": related_cases_count})

        filename, workbook_bytes = build_testcase_documents_workbook(
            project_id=project_id,
            documents=enriched_items,
            filters={
                "batch_id": query.batch_id,
                "parse_status": query.parse_status,
                "query": query.query,
            },
        )
        return filename, TESTCASE_DOCUMENT_EXPORT_MEDIA_TYPE, workbook_bytes

    async def list_cases(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        query: ListTestcaseCasesQuery,
        skip_scope_check: bool = False,
    ) -> TestcaseCasePage:
        if not skip_scope_check:
            await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        params: dict[str, Any] = {
            "project_id": project_id,
            "limit": query.limit,
            "offset": query.offset,
        }
        if clean_str(query.batch_id):
            params["batch_id"] = query.batch_id
        if clean_str(query.status):
            params["status"] = query.status
        if clean_str(query.query):
            params["query"] = query.query

        payload = self._ensure_object(
            await self._upstream.require_json("GET", _TEST_CASES_PATH, params=params),
            code="interaction_data_invalid_response",
        )
        items = [
            TestcaseCase.model_validate(item)
            for item in self._normalize_items(payload.get("items"))
        ]
        return TestcaseCasePage(
            items=items,
            total=self._normalize_total(payload, fallback_items=items),
        )

    async def get_case(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        case_id: str,
    ) -> TestcaseCase:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        testcase = await self._require_case(project_id=project_id, case_id=case_id)
        source_document_ids = _normalize_string_list(testcase.source_document_ids)

        async def load_document(document_id: str) -> tuple[str, TestcaseDocument | None]:
            try:
                document = await self._require_document(
                    project_id=project_id,
                    document_id=document_id,
                )
                return document_id, document
            except NotFoundError:
                return document_id, None

        source_documents: list[TestcaseDocument] = []
        missing_source_document_ids: list[str] = []
        if source_document_ids:
            loaded = await asyncio.gather(*(load_document(document_id) for document_id in source_document_ids))
            for document_id, document in loaded:
                if document is None:
                    missing_source_document_ids.append(document_id)
                else:
                    source_documents.append(document)

        payload = testcase.model_dump(mode="python")
        payload["source_document_ids"] = source_document_ids
        payload["source_documents"] = [document.model_dump(mode="python") for document in source_documents]
        payload["missing_source_document_ids"] = missing_source_document_ids
        return TestcaseCase.model_validate(payload)

    async def create_case(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        command: CreateTestcaseCaseCommand,
    ) -> TestcaseCase:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        payload = _normalize_testcase_payload(_payload_to_dict(command))
        payload["project_id"] = project_id
        created = await self._upstream.require_json("POST", _TEST_CASES_PATH, payload=payload)
        normalized = self._ensure_project_match(
            created,
            project_id=project_id,
            code="test_case_not_found",
        )
        return TestcaseCase.model_validate(normalized)

    async def update_case(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        case_id: str,
        command: UpdateTestcaseCaseCommand,
    ) -> TestcaseCase:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        await self._require_case(project_id=project_id, case_id=case_id)
        payload = _normalize_testcase_payload(_payload_to_dict(command))
        updated = await self._upstream.require_json(
            "PATCH",
            f"{_TEST_CASES_PATH}/{case_id}",
            payload=payload,
        )
        normalized = self._ensure_project_match(
            updated,
            project_id=project_id,
            code="test_case_not_found",
        )
        return TestcaseCase.model_validate(normalized)

    async def delete_case(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        case_id: str,
    ) -> None:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=True)
        await self._require_case(project_id=project_id, case_id=case_id)
        await self._upstream.require_json("DELETE", f"{_TEST_CASES_PATH}/{case_id}")

    async def export_cases(
        self,
        *,
        actor: ActorContext,
        project_id: str,
        query: ExportTestcaseCasesQuery,
    ) -> tuple[str, str, bytes]:
        await self._prepare_project_scope(actor=actor, project_id=project_id, write=False)
        items = await self._list_all_cases_for_export(
            project_id=project_id,
            query=query,
            max_items=MAX_TESTCASE_EXPORT_ROWS,
        )
        filename, workbook_bytes = build_testcase_cases_workbook(
            project_id=project_id,
            cases=items,
            filters={
                "batch_id": query.batch_id,
                "status": query.status,
                "query": query.query,
            },
            columns=resolve_testcase_export_columns(list(query.columns)),
        )
        return filename, TESTCASE_EXPORT_MEDIA_TYPE, workbook_bytes
