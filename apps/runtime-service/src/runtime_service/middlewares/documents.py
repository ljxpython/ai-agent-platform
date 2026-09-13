from __future__ import annotations

from pathlib import Path
from typing import Any, Awaitable, Callable

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import SystemMessage

from runtime_service.tools.documents import build_document_tools


class DocumentToolsMiddleware(AgentMiddleware):
    """Expose bounded document parsing as a reusable runtime capability."""

    def __init__(self, workspace: Path | None):
        self.workspace = workspace
        self.tools = build_document_tools(workspace)

    async def awrap_model_call(self, request: Any, handler: Callable[[Any], Awaitable[Any]]) -> Any:
        if self.workspace is None:
            return await handler(request)
        uploads = self.workspace / "uploads"
        files = []
        if uploads.is_dir():
            for path in sorted(uploads.iterdir()):
                if path.is_file() and not path.is_symlink():
                    files.append(f"- /workspace/uploads/{path.name} ({path.stat().st_size} bytes)")
        if not files:
            return await handler(request)
        context = SystemMessage(content="当前线程可用文档：\n" + "\n".join(files) + "\n需要内容时调用 parse_document。")
        current = getattr(request, "system_message", None)
        if current is not None and hasattr(current, "content_blocks"):
            content = list(current.content_blocks) + [{"type": "text", "text": str(context.content)}]
            clean = request.override(system_message=SystemMessage(content=content))
        else:
            clean = request
        return await handler(clean)


__all__ = ["DocumentToolsMiddleware"]
