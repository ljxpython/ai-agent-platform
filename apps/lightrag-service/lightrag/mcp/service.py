from __future__ import annotations

import asyncio
import time
from dataclasses import replace
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Any

from lightrag import QueryParam
from lightrag.base import DocProcessingStatus, DocStatus
from lightrag.lightrag import LightRAG
from lightrag.api.lightrag_server import create_app

from .config import ProjectKnowledgeMCPConfig, build_api_args_for_mcp, build_mcp_config
from .schemas import (
    CitationRecord,
    ListProjectKnowledgeDocumentsResponse,
    ProjectKnowledgeDocumentStatusResponse,
    ProjectKnowledgeDocumentSummary,
    QueryProjectKnowledgeResponse,
)
from .validators import (
    normalize_overall_status,
    normalize_status_filter,
    validate_document_id,
    validate_positive_int,
    validate_project_id,
    validate_query_mode,
    validate_query_text,
)

EMPTY_PROJECT_ANSWER = "No indexed project knowledge is available for this project yet."
EMPTY_QUERY_ANSWER = "No relevant project knowledge was found for the query."
NOT_FOUND_STATUS = "not_found"


class ProjectStorageResolver:
    def __init__(self, config: ProjectKnowledgeMCPConfig) -> None:
        self._config = config

    @property
    def storage_root(self) -> Path:
        return self._config.storage_root

    @property
    def input_root(self) -> Path:
        return self._config.input_root

    def workspace_key(self, project_id: str) -> str:
        return self._config.workspace_key(project_id)

    def workspace_input_dir(self, project_id: str) -> Path:
        return self._config.workspace_input_dir(project_id)


class ProjectScopedRAGCache:
    def __init__(
        self,
        *,
        config: ProjectKnowledgeMCPConfig,
        template_rag: LightRAG | None = None,
        resolver: ProjectStorageResolver | None = None,
    ) -> None:
        self._config = config
        self._template_rag = template_rag
        self._resolver = resolver or ProjectStorageResolver(config)
        self._cache: dict[str, LightRAG] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    async def get_rag(self, project_id: str) -> LightRAG:
        lock = await self._get_lock(project_id)
        async with lock:
            cached = self._cache.get(project_id)
            if cached is not None:
                return cached

            workspace_key = self._resolver.workspace_key(project_id)
            template_rag = self._template_rag or build_template_rag(self._config)
            self._template_rag = template_rag
            rag = replace(
                template_rag,
                working_dir=str(self._resolver.storage_root),
                workspace=workspace_key,
            )
            await rag.initialize_storages()
            await rag.check_and_migrate_data()
            self._cache[project_id] = rag
            return rag

    async def finalize_all(self) -> None:
        async with self._global_lock:
            cached_rags = list(self._cache.values())
            self._cache = {}
            self._locks = {}

        for rag in cached_rags:
            try:
                await rag.finalize_storages()
            except Exception:
                pass

    async def _get_lock(self, project_id: str) -> asyncio.Lock:
        async with self._global_lock:
            lock = self._locks.get(project_id)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[project_id] = lock
            return lock


class ProjectKnowledgeService:
    def __init__(
        self,
        *,
        config: ProjectKnowledgeMCPConfig,
        rag_cache: ProjectScopedRAGCache | None = None,
        resolver: ProjectStorageResolver | None = None,
    ) -> None:
        self.config = config
        self._resolver = resolver or ProjectStorageResolver(config)
        self._rag_cache = rag_cache or ProjectScopedRAGCache(
            config=config,
            resolver=self._resolver,
        )

    async def finalize(self) -> None:
        await self._rag_cache.finalize_all()

    async def query_project_knowledge(
        self,
        *,
        project_id: str,
        query: str,
        mode: str | None = None,
        top_k: int | None = None,
        metadata_filters: dict[str, Any] | None = None,
        metadata_boost: dict[str, Any] | None = None,
        strict_scope: bool | None = None,
    ) -> dict[str, Any]:
        normalized_project_id = validate_project_id(project_id)
        normalized_query = validate_query_text(query)
        normalized_mode = validate_query_mode(mode, self.config.default_query_mode)
        normalized_top_k = validate_positive_int(
            top_k,
            field_name="top_k",
            default=self.config.default_top_k,
        )

        started = time.perf_counter()
        rag = await self._rag_cache.get_rag(normalized_project_id)
        existing_documents = await self._load_all_documents(rag)
        if not existing_documents:
            return QueryProjectKnowledgeResponse(
                project_id=normalized_project_id,
                query=normalized_query,
                mode=normalized_mode,
                answer=EMPTY_PROJECT_ANSWER,
                matched_document_ids=[],
                citations=[],
                timing_ms=_elapsed_ms(started),
            ).model_dump()

        result = await rag.aquery_llm(
            normalized_query,
            param=QueryParam(
                mode=normalized_mode,  # type: ignore[arg-type]
                top_k=normalized_top_k,
                chunk_top_k=normalized_top_k,
                include_references=True,
                stream=False,
                metadata_filters=metadata_filters,
                metadata_boost=metadata_boost,
                strict_scope=bool(strict_scope),
            ),
        )
        answer = _extract_query_answer(result)
        data = _coerce_dict(_coerce_dict(result).get("data"))
        citations, matched_document_ids = await self._build_citations(
            rag=rag,
            data=data,
        )

        return QueryProjectKnowledgeResponse(
            project_id=normalized_project_id,
            query=normalized_query,
            mode=normalized_mode,
            answer=str(answer),
            matched_document_ids=matched_document_ids,
            citations=citations,
            timing_ms=_elapsed_ms(started),
        ).model_dump()

    async def list_project_knowledge_documents(
        self,
        *,
        project_id: str,
        status: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        normalized_project_id = validate_project_id(project_id)
        normalized_limit = validate_positive_int(
            limit,
            field_name="limit",
            default=self.config.default_list_limit,
        )
        status_filter = normalize_status_filter(status)

        rag = await self._rag_cache.get_rag(normalized_project_id)
        documents = await self._load_documents(rag=rag, status_filter=status_filter)
        documents = documents[:normalized_limit]
        return ListProjectKnowledgeDocumentsResponse(
            project_id=normalized_project_id,
            count=len(documents),
            documents=documents,
        ).model_dump()

    async def get_project_knowledge_document_status(
        self,
        *,
        project_id: str,
        document_id: str,
    ) -> dict[str, Any]:
        normalized_project_id = validate_project_id(project_id)
        normalized_document_id = validate_document_id(document_id)

        rag = await self._rag_cache.get_rag(normalized_project_id)
        found = await rag.aget_docs_by_ids(normalized_document_id)
        doc = found.get(normalized_document_id)
        if doc is None:
            return self._not_found_document_response(
                project_id=normalized_project_id,
                document_id=normalized_document_id,
            ).model_dump()

        return self._document_status_response(
            project_id=normalized_project_id,
            document_id=normalized_document_id,
            doc=doc,
        ).model_dump()

    async def _build_citations(
        self,
        *,
        rag: LightRAG,
        data: dict[str, Any],
    ) -> tuple[list[CitationRecord], list[str]]:
        references = data.get("references", [])
        chunks = data.get("chunks", [])
        if not isinstance(references, list) or not references:
            return [], []

        documents = await self._load_all_documents(rag)
        path_mapping = _build_document_path_mapping(documents)
        chunks_by_reference: dict[str, list[dict[str, Any]]] = {}
        for chunk in chunks if isinstance(chunks, list) else []:
            if not isinstance(chunk, dict):
                continue
            reference_id = str(chunk.get("reference_id") or "").strip()
            if not reference_id:
                continue
            chunks_by_reference.setdefault(reference_id, []).append(chunk)

        citations: list[CitationRecord] = []
        matched_document_ids: list[str] = []
        seen_document_ids: set[str] = set()
        for reference in references:
            if not isinstance(reference, dict):
                continue
            reference_id = str(reference.get("reference_id") or "").strip()
            file_path = _coerce_text(reference.get("file_path"))
            mapped_document_id = _resolve_document_id(file_path, path_mapping)
            chunk_group = chunks_by_reference.get(reference_id, [])
            first_chunk = chunk_group[0] if chunk_group else {}
            snippet = _snippet_from_chunks(chunk_group)
            citation = CitationRecord(
                document_id=mapped_document_id,
                file_path=file_path,
                filename=_filename(file_path),
                chunk_id=_coerce_text(first_chunk.get("chunk_id"))
                if isinstance(first_chunk, dict)
                else None,
                page_index=_coerce_page_index(first_chunk if isinstance(first_chunk, dict) else {}),
                snippet=snippet,
            )
            citations.append(citation)
            if mapped_document_id and mapped_document_id not in seen_document_ids:
                seen_document_ids.add(mapped_document_id)
                matched_document_ids.append(mapped_document_id)

        return citations, matched_document_ids

    async def _load_all_documents(self, rag: LightRAG) -> list[ProjectKnowledgeDocumentSummary]:
        return await self._load_documents(rag=rag, status_filter=None)

    async def _load_documents(
        self,
        *,
        rag: LightRAG,
        status_filter: DocStatus | None,
    ) -> list[ProjectKnowledgeDocumentSummary]:
        if status_filter is not None:
            docs_by_id = await rag.get_docs_by_status(status_filter)
            items = list(docs_by_id.items())
        else:
            items = []
            page = 1
            page_size = 200
            while True:
                page_items, total_count = await rag.doc_status.get_docs_paginated(
                    page=page,
                    page_size=page_size,
                    sort_field="updated_at",
                    sort_direction="desc",
                )
                items.extend(page_items)
                if len(items) >= total_count or not page_items:
                    break
                page += 1

        summaries = [
            self._document_summary(document_id=document_id, doc=doc)
            for document_id, doc in items
        ]
        summaries.sort(key=lambda item: item.updated_at or "", reverse=True)
        return summaries

    def _document_summary(
        self,
        *,
        document_id: str,
        doc: DocProcessingStatus | dict[str, Any],
    ) -> ProjectKnowledgeDocumentSummary:
        payload = _doc_status_payload(doc)
        raw_status = payload.get("status") or ""
        return ProjectKnowledgeDocumentSummary(
            document_id=document_id,
            file_path=_coerce_text(payload.get("file_path")),
            filename=_filename(payload.get("file_path")),
            overall_status=normalize_overall_status(str(raw_status)),
            track_id=_coerce_text(payload.get("track_id")),
            chunks_count=_coerce_int(payload.get("chunks_count")),
            updated_at=_coerce_text(payload.get("updated_at")),
            last_error=_coerce_text(payload.get("error_msg")),
        )

    def _document_status_response(
        self,
        *,
        project_id: str,
        document_id: str,
        doc: DocProcessingStatus | dict[str, Any],
    ) -> ProjectKnowledgeDocumentStatusResponse:
        summary = self._document_summary(document_id=document_id, doc=doc)
        return ProjectKnowledgeDocumentStatusResponse(
            project_id=project_id,
            document_id=document_id,
            overall_status=summary.overall_status,
            file_path=summary.file_path,
            filename=summary.filename,
            track_id=summary.track_id,
            chunks_count=summary.chunks_count,
            updated_at=summary.updated_at,
            last_error=summary.last_error,
        )

    def _not_found_document_response(
        self,
        *,
        project_id: str,
        document_id: str,
    ) -> ProjectKnowledgeDocumentStatusResponse:
        return ProjectKnowledgeDocumentStatusResponse(
            project_id=project_id,
            document_id=document_id,
            overall_status=NOT_FOUND_STATUS,
            last_error=None,
        )


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _doc_status_payload(doc: DocProcessingStatus | dict[str, Any]) -> dict[str, Any]:
    if isinstance(doc, dict):
        return dict(doc)
    return {
        "file_path": doc.file_path,
        "status": doc.status.value if isinstance(doc.status, DocStatus) else str(doc.status),
        "track_id": doc.track_id,
        "chunks_count": doc.chunks_count,
        "updated_at": doc.updated_at,
        "error_msg": doc.error_msg,
    }


def _coerce_text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _coerce_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _extract_query_answer(result: Any) -> str:
    llm_response = _coerce_dict(_coerce_dict(result).get("llm_response"))
    return _coerce_text(llm_response.get("content")) or EMPTY_QUERY_ANSWER


def _coerce_page_index(chunk: dict[str, Any]) -> int | None:
    for key in ("page_index", "page", "page_number"):
        value = _coerce_int(chunk.get(key))
        if value is not None:
            return value
    return None


def _filename(file_path: Any) -> str | None:
    text = _coerce_text(file_path)
    if text is None:
        return None
    return Path(text).name or text


def _normalize_path(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip().replace("\\", "/")
    while "//" in text:
        text = text.replace("//", "/")
    try:
        return PurePosixPath(text).as_posix()
    except Exception:
        return text


def _build_document_path_mapping(
    documents: list[ProjectKnowledgeDocumentSummary],
) -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    for document in documents:
        for candidate in filter(
            None,
            {
                _normalize_path(document.file_path),
                _normalize_path(document.filename),
            },
        ):
            mapping.setdefault(candidate, set()).add(document.document_id)
    return mapping


def _resolve_document_id(
    file_path: str | None,
    mapping: dict[str, set[str]],
) -> str | None:
    normalized = _normalize_path(file_path)
    if normalized is None:
        return None
    matches = mapping.get(normalized)
    if matches and len(matches) == 1:
        return next(iter(matches))
    basename = _normalize_path(_filename(normalized))
    if basename is None:
        return None
    basename_matches = mapping.get(basename)
    if basename_matches and len(basename_matches) == 1:
        return next(iter(basename_matches))
    return None


def _snippet_from_chunks(chunks: list[dict[str, Any]]) -> str | None:
    for chunk in chunks:
        content = _coerce_text(chunk.get("content"))
        if content:
            return content[:280]
    return None


@lru_cache(maxsize=1)
def build_template_rag(config: ProjectKnowledgeMCPConfig) -> LightRAG:
    args = build_api_args_for_mcp(config)
    app = create_app(args)
    workspace_manager = app.state.workspace_manager
    rag_factory = getattr(workspace_manager, "_rag_factory", None)
    if rag_factory is None:
        raise RuntimeError("workspace_manager_rag_factory_unavailable")
    template_rag = rag_factory(args.workspace)
    if not isinstance(template_rag, LightRAG):
        raise RuntimeError("unexpected_rag_factory_result")
    return template_rag


@lru_cache(maxsize=1)
def build_project_knowledge_service() -> ProjectKnowledgeService:
    config = build_mcp_config()
    return ProjectKnowledgeService(config=config)
