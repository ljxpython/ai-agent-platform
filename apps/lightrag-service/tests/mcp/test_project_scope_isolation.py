from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from uuid import uuid4

import pytest

pytestmark = pytest.mark.offline


class FakeDocStatusPager:
    def __init__(self, pages):
        self.pages = pages

    async def get_docs_paginated(self, *, page: int, page_size: int, sort_field: str, sort_direction: str):
        index = min(page - 1, len(self.pages) - 1)
        return self.pages[index]


class FakeRAG:
    def __init__(self, answer: str, *, docs: dict[str, dict] | None = None):
        self.answer = answer
        self.docs = docs or {}
        self.query_calls = 0
        self.doc_status = FakeDocStatusPager([(list(self.docs.items()), len(self.docs))])

    async def aquery_llm(self, query: str, param=None, system_prompt=None):
        self.query_calls += 1
        return {
            "status": "success",
            "message": "ok",
            "data": {"references": [], "chunks": []},
            "metadata": {"query": query},
            "llm_response": {"content": self.answer, "response_iterator": None, "is_streaming": False},
        }

    async def get_docs_by_status(self, status):
        return {doc_id: doc for doc_id, doc in self.docs.items() if doc.get("status") == getattr(status, "value", status)}

    async def aget_docs_by_ids(self, document_id: str):
        return {document_id: self.docs.get(document_id)} if document_id in self.docs else {}


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


async def test_same_query_on_two_projects_does_not_cross_workspace(service_module, config):
    project_a = str(uuid4())
    project_b = str(uuid4())
    rag_cache = FakeRAGCache(
        {
            project_a: FakeRAG(
                "answer-a",
                docs={"a-doc": {"file_path": "a.md", "status": "processed", "updated_at": "2026-04-12T00:00:00Z"}},
            ),
            project_b: FakeRAG(
                "answer-b",
                docs={"b-doc": {"file_path": "b.md", "status": "processed", "updated_at": "2026-04-12T00:01:00Z"}},
            ),
        }
    )
    service = service_module.ProjectKnowledgeService(config=config, rag_cache=rag_cache, resolver=_Resolver(config))

    result_a = await service.query_project_knowledge(project_id=project_a, query="same question")
    result_b = await service.query_project_knowledge(project_id=project_b, query="same question")

    assert result_a["answer"] == "answer-a"
    assert result_b["answer"] == "answer-b"
    assert rag_cache.calls == [project_a, project_b]


async def test_list_documents_reads_only_target_project_workspace(service_module, config):
    project_a = str(uuid4())
    project_b = str(uuid4())
    rag_cache = FakeRAGCache(
        {
            project_a: FakeRAG("unused", docs={"a-doc": {"file_path": "a.md", "status": "processed", "updated_at": "2026-04-12T00:00:00Z"}}),
            project_b: FakeRAG("unused", docs={"b-doc": {"file_path": "b.md", "status": "processed", "updated_at": "2026-04-12T00:01:00Z"}}),
        }
    )
    service = service_module.ProjectKnowledgeService(config=config, rag_cache=rag_cache, resolver=_Resolver(config))

    result = await service.list_project_knowledge_documents(project_id=project_b, status="processed", limit=20)

    assert [doc["document_id"] for doc in result["documents"]] == ["b-doc"]
    assert rag_cache.calls == [project_b]


async def test_document_status_reads_only_target_project_workspace(service_module, config):
    project_a = str(uuid4())
    project_b = str(uuid4())
    rag_cache = FakeRAGCache(
        {
            project_a: FakeRAG("unused", docs={"a-doc": {"file_path": "a.md", "status": "processed", "track_id": "track-a"}}),
            project_b: FakeRAG("unused", docs={"b-doc": {"file_path": "b.md", "status": "processed", "track_id": "track-b"}}),
        }
    )
    service = service_module.ProjectKnowledgeService(config=config, rag_cache=rag_cache, resolver=_Resolver(config))

    result = await service.get_project_knowledge_document_status(project_id=project_a, document_id="a-doc")

    assert result["project_id"] == project_a
    assert result["document_id"] == "a-doc"
    assert result["track_id"] == "track-a"
    assert rag_cache.calls == [project_a]


def test_storage_isolation_uses_shared_storage_root_with_canonical_workspace_key(service_module, config):
    resolver = service_module.ProjectStorageResolver(config)
    project_a = str(uuid4())
    project_b = str(uuid4())

    expected_workspace_a = f"kb_{project_a.replace('-', '')}"
    expected_workspace_b = f"kb_{project_b.replace('-', '')}"

    assert resolver.storage_root == config.storage_root
    assert resolver.workspace_key(project_a) == expected_workspace_a
    assert resolver.workspace_key(project_b) == expected_workspace_b
    assert resolver.workspace_input_dir(project_a) == config.input_root / expected_workspace_a
    assert resolver.workspace_input_dir(project_b) == config.input_root / expected_workspace_b
    assert resolver.workspace_input_dir(project_a) != resolver.workspace_input_dir(project_b)
