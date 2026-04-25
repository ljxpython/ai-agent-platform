from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = pytest.mark.offline

EXPECTED_PHASE1_TOOLS = {
    "query_project_knowledge",
    "list_project_knowledge_documents",
    "get_project_knowledge_document_status",
}
FORBIDDEN_TOOL_NAMES = {
    "ingest_project_document",
    "ingest_project_content_list",
    "retry_project_document_ingest",
    "get_project_ingest_job_status",
    "list_failed_project_documents",
    "search_project_graph_labels",
    "get_project_knowledge_subgraph",
    "reindex_project_knowledge",
    "delete_project_document",
    "get_project_storage_stats",
}


def _load_server_ast() -> ast.Module:
    source = Path("lightrag/mcp/server.py").read_text(encoding="utf-8")
    return ast.parse(source)


def _collect_nested_tool_names(tree: ast.Module) -> set[str]:
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "build_mcp_server":
            return {
                child.name
                for child in node.body
                if isinstance(child, ast.AsyncFunctionDef)
            }
    pytest.fail("build_mcp_server() was not found in lightrag/mcp/server.py")


def test_mcp_server_registers_only_phase1_tools():
    tool_names = _collect_nested_tool_names(_load_server_ast())

    assert tool_names == EXPECTED_PHASE1_TOOLS
    assert FORBIDDEN_TOOL_NAMES.isdisjoint(tool_names)
