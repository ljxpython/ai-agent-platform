from __future__ import annotations

import asyncio
import importlib
import sys
import types
from dataclasses import dataclass
from uuid import uuid4

import pytest

pytestmark = pytest.mark.offline


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


@dataclass
class FakeTemplateRAG:
    working_dir: str
    workspace: str
    initialize_calls: int = 0
    migrate_calls: int = 0

    async def initialize_storages(self) -> None:
        self.initialize_calls += 1

    async def check_and_migrate_data(self) -> None:
        self.migrate_calls += 1

    async def finalize_storages(self) -> None:
        return None


def test_project_rag_cache_maps_project_id_to_platform_workspace_and_shared_storage_root(
    service_module, config
):
    project_id = str(uuid4())
    expected_workspace = f"kb_{project_id.replace('-', '')}"
    template = FakeTemplateRAG(
        working_dir=str(config.storage_root),
        workspace="__lightrag_mcp_template__",
    )
    resolver = service_module.ProjectStorageResolver(config)
    cache = service_module.ProjectScopedRAGCache(
        config=config,
        template_rag=template,
        resolver=resolver,
    )

    rag = asyncio.run(cache.get_rag(project_id))

    assert rag.workspace == expected_workspace
    assert rag.working_dir == str(config.storage_root)
    assert resolver.workspace_input_dir(project_id) == config.input_root / expected_workspace
    assert rag.initialize_calls == 1
    assert rag.migrate_calls == 1


def test_project_rag_cache_reuses_cached_instance_for_same_project(service_module, config):
    project_id = str(uuid4())
    template = FakeTemplateRAG(
        working_dir=str(config.storage_root),
        workspace="__lightrag_mcp_template__",
    )
    cache = service_module.ProjectScopedRAGCache(
        config=config,
        template_rag=template,
        resolver=service_module.ProjectStorageResolver(config),
    )

    first = asyncio.run(cache.get_rag(project_id))
    second = asyncio.run(cache.get_rag(project_id))

    assert first is second
