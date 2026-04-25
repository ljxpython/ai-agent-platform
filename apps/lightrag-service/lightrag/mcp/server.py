from __future__ import annotations

import asyncio
import os
from functools import lru_cache
from typing import Any

from .config import ProjectKnowledgeMCPConfig, build_mcp_config
from .service import build_project_knowledge_service

try:
    from fastmcp import FastMCP
except ImportError:  # pragma: no cover - compatibility fallback
    from mcp.server.fastmcp import FastMCP  # type: ignore[no-redef]


@lru_cache(maxsize=1)
def build_mcp_server() -> FastMCP:
    service = build_project_knowledge_service()
    mcp = FastMCP("LightRAGProjectKnowledgeServer")

    @mcp.tool()
    async def query_project_knowledge(
        project_id: str,
        query: str,
        mode: str | None = None,
        top_k: int | None = None,
        metadata_filters: dict[str, Any] | None = None,
        metadata_boost: dict[str, Any] | None = None,
        strict_scope: bool | None = None,
    ) -> dict[str, Any]:
        """Query project-scoped knowledge and return an answer with citations."""

        return await service.query_project_knowledge(
            project_id=project_id,
            query=query,
            mode=mode,
            top_k=top_k,
            metadata_filters=metadata_filters,
            metadata_boost=metadata_boost,
            strict_scope=strict_scope,
        )

    @mcp.tool()
    async def list_project_knowledge_documents(
        project_id: str,
        status: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """List project-scoped indexed documents and their overall status."""

        return await service.list_project_knowledge_documents(
            project_id=project_id,
            status=status,
            limit=limit,
        )

    @mcp.tool()
    async def get_project_knowledge_document_status(
        project_id: str,
        document_id: str,
    ) -> dict[str, Any]:
        """Get the status of a single project-scoped knowledge document."""

        return await service.get_project_knowledge_document_status(
            project_id=project_id,
            document_id=document_id,
        )

    return mcp


def build_server_run_settings(
    config: ProjectKnowledgeMCPConfig | None = None,
) -> dict[str, Any]:
    config = config or build_mcp_config()
    run_settings: dict[str, Any] = {
        "transport": config.transport,
        "show_banner": config.show_banner,
    }

    if config.transport != "stdio":
        run_settings["host"] = config.host
        run_settings["port"] = config.port

        if config.path:
            run_settings["path"] = config.path
        if config.log_level:
            run_settings["log_level"] = config.log_level
        if config.message_path:
            os.environ["FASTMCP_MESSAGE_PATH"] = config.message_path

    return run_settings


def main() -> int:
    service = build_project_knowledge_service()
    server = build_mcp_server()
    run_settings = build_server_run_settings()
    try:
        try:
            server.run(**run_settings)
        except TypeError as exc:
            if "show_banner" not in str(exc):
                raise
            run_settings.pop("show_banner", None)
            server.run(**run_settings)
    except KeyboardInterrupt:  # pragma: no cover - normal shutdown path
        pass
    finally:
        asyncio.run(service.finalize())
    return 0
