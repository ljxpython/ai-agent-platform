from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from uuid import uuid4

import pytest

pytestmark = pytest.mark.offline


class FakeDocStatusPager:
    def __init__(self, pages: list[tuple[list[tuple[str, dict]], int]] | None = None):
        self.pages = pages or [([], 0)]
        self.calls: list[dict] = []

    async def get_docs_paginated(
        self,
        *,
        page: int,
        page_size: int,
        sort_field: str,
        sort_direction: str,
    ):
        self.calls.append(
            {
                "page": page,
                "page_size": page_size,
                "sort_field": sort_field,
                "sort_direction": sort_direction,
            }
        )
        index = min(page - 1, len(self.pages) - 1)
        return self.pages[index]


class FakeRAG:
    def __init__(self, query_result: dict, *, all_documents: list[tuple[str, dict]] | None = None):
        self.query_result = query_result
        self.query_calls: list[dict] = []
        self.doc_status = FakeDocStatusPager([(all_documents or [], len(all_documents or []))])

    async def aquery_llm(self, query: str, param=None, system_prompt=None):
        self.query_calls.append({"query": query, "param": param, "system_prompt": system_prompt})
        return self.query_result

    async def aquery_data(self, *_args, **_kwargs):  # pragma: no cover - sentinel
        raise AssertionError("Phase-1 service must not call aquery_data()")


class FakeRAGCache:
    def __init__(self, mapping: dict[str, object | None]):
        self.mapping = mapping
        self.calls: list[str] = []

    async def get_rag(self, project_id: str):
        self.calls.append(project_id)
        return self.mapping.get(project_id)


class _Resolver:
    def __init__(self, config):
        self.storage_root = config.storage_root
        self.input_root = config.input_root
        self._config = config

    def workspace_key(self, project_id: str) -> str:
        return self._config.workspace_key(project_id)

    def workspace_input_dir(self, project_id: str) -> Path:
        return self._config.workspace_input_dir(project_id)


def _install_fastmcp_stub():
    fastmcp_module = types.ModuleType("fastmcp")

    class _DummyFastMCP:
        def __init__(self, *_args, **_kwargs):
            pass

        def tool(self):
            def decorator(fn):
                return fn

            return decorator

    fastmcp_module.FastMCP = _DummyFastMCP
    sys.modules.setdefault("fastmcp", fastmcp_module)
    mcp_pkg = sys.modules.setdefault("mcp", types.ModuleType("mcp"))
    server_pkg = sys.modules.setdefault("mcp.server", types.ModuleType("mcp.server"))
    fastmcp_pkg = types.ModuleType("mcp.server.fastmcp")
    fastmcp_pkg.FastMCP = _DummyFastMCP
    sys.modules.setdefault("mcp.server.fastmcp", fastmcp_pkg)
    setattr(mcp_pkg, "server", server_pkg)


def _load_service_module():
    argv = sys.argv[:]
    try:
        sys.argv = [sys.argv[0]]
        _install_fastmcp_stub()
        return importlib.import_module("lightrag.mcp.service")
    finally:
        sys.argv = argv


@pytest.fixture
def service_module():
    return _load_service_module()


@pytest.fixture
def config(service_module, tmp_path):
    return service_module.ProjectKnowledgeMCPConfig(
        storage_root=tmp_path / "rag_storage",
        input_root=tmp_path / "inputs",
    )


@pytest.fixture
def sample_project_id() -> str:
    return str(uuid4())


@pytest.fixture
def sample_query_result() -> dict:
    return {
        "status": "success",
        "message": "ok",
        "data": {
            "references": [
                {
                    "reference_id": "ref-1",
                    "file_path": "docs/guide.md",
                }
            ],
            "chunks": [
                {
                    "reference_id": "ref-1",
                    "chunk_id": "chunk-1",
                    "page_index": 3,
                    "content": "Useful detail from guide",
                }
            ],
        },
        "metadata": {"mode": "mix", "top_k": 8},
        "llm_response": {
            "content": "Grounded answer",
            "response_iterator": None,
            "is_streaming": False,
        },
    }


async def test_query_tool_rejects_non_uuid_project_id(service_module, config):
    service = service_module.ProjectKnowledgeService(config=config, rag_cache=FakeRAGCache({}))

    with pytest.raises(ValueError, match="project_id_must_be_uuid"):
        await service.query_project_knowledge(project_id="not-a-uuid", query="hello")


async def test_query_tool_uses_single_pass_query_result_for_answer_and_citations(
    service_module, config, sample_project_id, sample_query_result
):
    rag = FakeRAG(
        sample_query_result,
        all_documents=[
            (
                "doc-1",
                {
                    "file_path": "docs/guide.md",
                    "status": "processed",
                    "updated_at": "2026-04-12T00:00:00Z",
                },
            )
        ],
    )
    service = service_module.ProjectKnowledgeService(
        config=config,
        rag_cache=FakeRAGCache({sample_project_id: rag}),
        resolver=_Resolver(config),
    )

    result = await service.query_project_knowledge(
        project_id=sample_project_id,
        query="How does this work?",
        mode="mix",
        top_k=8,
    )

    assert len(rag.query_calls) == 1
    assert result["project_id"] == sample_project_id
    assert result["query"] == "How does this work?"
    assert result["answer"] == "Grounded answer"
    assert result["matched_document_ids"] == ["doc-1"]
    assert result["citations"] == [
        {
            "document_id": "doc-1",
            "file_path": "docs/guide.md",
            "filename": "guide.md",
            "chunk_id": "chunk-1",
            "page_index": 3,
            "snippet": "Useful detail from guide",
        }
    ]


async def test_query_tool_returns_empty_project_response_when_workspace_has_no_documents(
    service_module, config, sample_project_id
):
    rag = FakeRAG({"llm_response": {"content": "should not be used"}})
    service = service_module.ProjectKnowledgeService(
        config=config,
        rag_cache=FakeRAGCache({sample_project_id: rag}),
        resolver=_Resolver(config),
    )

    result = await service.query_project_knowledge(project_id=sample_project_id, query="Any docs?")

    assert result["project_id"] == sample_project_id
    assert result["matched_document_ids"] == []
    assert result["citations"] == []
    assert "no indexed project knowledge" in result["answer"].lower()
    assert rag.query_calls == []


async def test_query_tool_keeps_file_path_when_document_id_cannot_be_resolved(
    service_module, config, sample_project_id, sample_query_result
):
    rag = FakeRAG(
        sample_query_result,
        all_documents=[
            (
                "doc-1",
                {
                    "file_path": "docs/other.md",
                    "status": "processed",
                    "updated_at": "2026-04-12T00:00:00Z",
                },
            )
        ],
    )
    service = service_module.ProjectKnowledgeService(
        config=config,
        rag_cache=FakeRAGCache({sample_project_id: rag}),
        resolver=_Resolver(config),
    )

    result = await service.query_project_knowledge(project_id=sample_project_id, query="Need source")

    assert result["matched_document_ids"] == []
    assert result["citations"][0]["file_path"] == "docs/guide.md"
    assert result["citations"][0]["document_id"] is None


async def test_query_tool_marks_ambiguous_document_mapping_as_null(
    service_module, config, sample_project_id, sample_query_result
):
    rag = FakeRAG(
        sample_query_result,
        all_documents=[
            ("doc-1", {"file_path": "docs/guide.md", "status": "processed", "updated_at": "2026-04-12T00:00:00Z"}),
            ("doc-2", {"file_path": "docs/guide.md", "status": "processed", "updated_at": "2026-04-12T00:00:01Z"}),
        ],
    )
    service = service_module.ProjectKnowledgeService(
        config=config,
        rag_cache=FakeRAGCache({sample_project_id: rag}),
        resolver=_Resolver(config),
    )

    result = await service.query_project_knowledge(project_id=sample_project_id, query="Need source")

    assert result["matched_document_ids"] == []
    assert result["citations"][0]["document_id"] is None
    assert result["citations"][0]["file_path"] == "docs/guide.md"


async def test_query_tool_allows_sparse_or_empty_citations_without_crashing(
    service_module, config, sample_project_id
):
    rag = FakeRAG(
        {
            "status": "success",
            "message": "ok",
            "data": {"references": [], "chunks": []},
            "metadata": {"mode": "mix"},
            "llm_response": {
                "content": "Answer without citations",
                "response_iterator": None,
                "is_streaming": False,
            },
        },
        all_documents=[
            (
                "doc-1",
                {
                    "file_path": "docs/guide.md",
                    "status": "processed",
                    "updated_at": "2026-04-12T00:00:00Z",
                },
            )
        ],
    )
    service = service_module.ProjectKnowledgeService(
        config=config,
        rag_cache=FakeRAGCache({sample_project_id: rag}),
        resolver=_Resolver(config),
    )

    result = await service.query_project_knowledge(project_id=sample_project_id, query="Need summary")

    assert result["answer"] == "Answer without citations"
    assert result["citations"] == []
    assert result["matched_document_ids"] == []
