from __future__ import annotations

from pathlib import Path

from langchain.agents.middleware import AgentMiddleware

from runtime_service.tools.documents import build_document_tools


class DocumentToolsMiddleware(AgentMiddleware):
    """Expose bounded document parsing as a reusable runtime capability."""

    def __init__(self, workspace: Path | None, *, execution_image: str | None = None):
        self.workspace = workspace
        self.tools = build_document_tools(workspace, execution_image=execution_image)


__all__ = ["DocumentToolsMiddleware"]
