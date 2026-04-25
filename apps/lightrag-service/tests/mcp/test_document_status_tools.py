from __future__ import annotations

import importlib
import sys
import types
from uuid import uuid4

import pytest

pytestmark = pytest.mark.offline


class FakeDocStatusPager:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    async def get_docs_paginated(self, *, page: int, page_size: int, sort_field: str, sort_direction: str):
        self.calls.append({"page": page, "page_size": page_size})
        index = min(page - 1, len(self.pages) - 1)
        return self.pages[index]


class FakeRAG:
    def __init__(self, *, docs: dict[str, dict]):
        self.docs = docs
        self.doc_status = FakeDocStatusPager([(list(docs.items()), len(docs))])

    async def get_docs_by_status(self, status):
        value = getattr(status, "value", status)
        return {doc_id: doc for doc_id, doc in self.docs.items() if doc.get("status") == value}

    async def aget_docs_by_ids(self, document_id: str):
        return {document_id: self.docs[document_id]} if document_id in self.docs else {}


class FakeRAGCache:
    def __init__(self, mapping: dict[str, object | None]):
        self.mapping = mapping

    async def get_rag(self, project_id: str):
        return self.mapping.get(project_id)


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


async def test_list_documents_filters_by_status_and_honors_limit(service_module, config):
    project_id = str(uuid4())
    rag = FakeRAG(
        docs={
            "doc-1": {"file_path": "a.md", "status": "processed", "updated_at": "2026-04-12T00:00:00Z"},
            "doc-2": {"file_path": "b.md", "status": "failed", "updated_at": "2026-04-12T00:01:00Z"},
            "doc-3": {"file_path": "c.md", "status": "processed", "updated_at": "2026-04-12T00:02:00Z"},
        }
    )
    service = service_module.ProjectKnowledgeService(config=config, rag_cache=FakeRAGCache({project_id: rag}))

    result = await service.list_project_knowledge_documents(project_id=project_id, status="processed", limit=1)

    assert result["project_id"] == project_id
    assert result["count"] == 1
    assert len(result["documents"]) == 1
    assert result["documents"][0]["overall_status"] == "ready"


async def test_get_document_status_returns_chunks_count_track_id_and_error(service_module, config):
    project_id = str(uuid4())
    service = service_module.ProjectKnowledgeService(
        config=config,
        rag_cache=FakeRAGCache(
            {
                project_id: FakeRAG(
                    docs={
                        "doc-1": {
                            "status": "failed",
                            "track_id": "track-1",
                            "chunks_count": 7,
                            "updated_at": "2026-04-12T01:00:00Z",
                            "error_msg": "parse failure",
                            "file_path": "broken.md",
                        }
                    }
                )
            }
        ),
    )

    result = await service.get_project_knowledge_document_status(project_id=project_id, document_id="doc-1")

    assert result == {
        "project_id": project_id,
        "document_id": "doc-1",
        "overall_status": "failed",
        "file_path": "broken.md",
        "filename": "broken.md",
        "track_id": "track-1",
        "chunks_count": 7,
        "updated_at": "2026-04-12T01:00:00Z",
        "last_error": "parse failure",
    }


async def test_get_document_status_handles_unknown_document_id(service_module, config):
    project_id = str(uuid4())
    service = service_module.ProjectKnowledgeService(
        config=config,
        rag_cache=FakeRAGCache({project_id: FakeRAG(docs={})}),
    )

    result = await service.get_project_knowledge_document_status(project_id=project_id, document_id="missing-doc")

    assert result == {
        "project_id": project_id,
        "document_id": "missing-doc",
        "overall_status": "not_found",
        "file_path": None,
        "filename": None,
        "track_id": None,
        "chunks_count": None,
        "updated_at": None,
        "last_error": None,
    }


async def test_status_tool_rejects_non_uuid_project_id(service_module, config):
    project_id = str(uuid4())
    service = service_module.ProjectKnowledgeService(
        config=config,
        rag_cache=FakeRAGCache({project_id: FakeRAG(docs={})}),
    )

    with pytest.raises(ValueError, match="project_id_must_be_uuid"):
        await service.get_project_knowledge_document_status(project_id="not-a-uuid", document_id="doc-1")
