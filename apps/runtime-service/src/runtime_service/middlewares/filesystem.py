"""Keep official file tools and eviction, with collision-safe result references."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from copy import copy
from hashlib import sha256

from deepagents.backends.protocol import BackendProtocol
from deepagents.middleware._message_eviction import _extract_text_from_message
from deepagents.middleware.filesystem import (
    NUM_CHARS_PER_TOKEN,
    TOOLS_EXCLUDED_FROM_EVICTION,
    FilesystemMiddleware,
)
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from runtime_service.tools.knowledge import KNOWLEDGE_TOOL, fit_knowledge_message


def truncate_tool_output_text(
    content: str,
    *,
    head_lines: int = 50,
    tail_lines: int = 50,
    max_chars: int = 16000,
    tool_name: str = "",
) -> str:
    """Perform Head+Tail truncation on oversized tool outputs to prevent context blowup."""
    if len(content) <= max_chars:
        return content

    lines = content.splitlines(keepends=True)
    if len(lines) <= head_lines + tail_lines:
        half = max_chars // 2
        return (
            content[:half]
            + f"\n\n[... ⚠️ 工具输出单行超限 ({len(content)} 字符)，已自动截断中间部分 ...]\n\n"
            + content[-half:]
        )

    head = "".join(lines[:head_lines])
    tail = "".join(lines[-tail_lines:]) if tail_lines > 0 else ""
    truncated_lines = max(0, len(lines) - head_lines - tail_lines)
    truncated_chars = max(0, len(content) - len(head) - len(tail))

    hint = (
        "使用 read_file 配合 offset 和 limit 参数按需分页查看"
        if tool_name in ("read_file", "view")
        else "使用更精确的过滤条件 (如 grep / head / tail)"
    )
    tool_desc = f"工具 '{tool_name}' " if tool_name else "工具"
    notice = (
        f"\n\n[... ⚠️ {tool_desc}输出过长 ({len(content)} 字符)。已自动截断中间 {truncated_lines} 行 ({truncated_chars} 字符) ...\n"
        f"提示：完整结果已安全受限保护。若需阅读特定区域，请{hint}。]\n\n"
    )
    return head + notice + tail


# shortcut: uses DeepAgents 0.7.8 private eviction hooks; revalidate on upgrades.
class ResultFilesystemMiddleware(FilesystemMiddleware):
    @property
    def name(self) -> str:
        return "FilesystemMiddleware"

    def _scoped(self, message: ToolMessage) -> ResultFilesystemMiddleware:
        content = _extract_text_from_message(message)
        if (
            not self._tool_token_limit_before_evict
            or len(content) <= NUM_CHARS_PER_TOKEN * self._tool_token_limit_before_evict
        ):
            return self
        # Child graphs share files and may reuse call IDs; never mutate the shared instance.
        scoped = copy(self)
        digest = sha256(content.encode()).hexdigest()
        scoped._large_tool_results_prefix = (
            f"{self._large_tool_results_prefix}/{digest}"
        )
        return scoped

    def _guard_message(self, message: ToolMessage, tool_name: str = "") -> ToolMessage:
        actual_name = tool_name or getattr(message, "name", "")
        # Only guard tools that are excluded from normal eviction (e.g. read_file, grep)
        # to prevent oversized raw outputs from flooding the LLM context.
        if actual_name not in TOOLS_EXCLUDED_FROM_EVICTION:
            return message

        content = _extract_text_from_message(message)
        limit_tokens = self._tool_token_limit_before_evict or 4000
        max_chars = max(8000, min(24000, NUM_CHARS_PER_TOKEN * limit_tokens))
        if len(content) > max_chars:
            truncated = truncate_tool_output_text(
                content,
                head_lines=50,
                tail_lines=50,
                max_chars=max_chars,
                tool_name=actual_name,
            )
            return message.model_copy(update={"content": truncated})
        return message

    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], ToolMessage | Command],
    ) -> ToolMessage | Command:
        result = super().wrap_tool_call(request, handler)
        tool_name = (
            request.tool_call.get("name", "")
            if isinstance(request.tool_call, dict)
            else ""
        )
        if isinstance(result, ToolMessage):
            return self._guard_message(result, tool_name)
        return result

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[ToolMessage | Command]],
    ) -> ToolMessage | Command:
        result = await super().awrap_tool_call(request, handler)
        tool_name = (
            request.tool_call.get("name", "")
            if isinstance(request.tool_call, dict)
            else ""
        )
        if isinstance(result, ToolMessage):
            return self._guard_message(result, tool_name)
        return result

    def _process_large_message(
        self, message: ToolMessage, resolved_backend: BackendProtocol
    ) -> tuple[ToolMessage, bool]:
        if message.name == KNOWLEDGE_TOOL and self._tool_token_limit_before_evict:
            return fit_knowledge_message(
                message, NUM_CHARS_PER_TOKEN * self._tool_token_limit_before_evict
            ), False
        return FilesystemMiddleware._process_large_message(
            self._scoped(message), message, resolved_backend
        )

    async def _aprocess_large_message(
        self, message: ToolMessage, resolved_backend: BackendProtocol
    ) -> tuple[ToolMessage, bool]:
        if message.name == KNOWLEDGE_TOOL and self._tool_token_limit_before_evict:
            return fit_knowledge_message(
                message, NUM_CHARS_PER_TOKEN * self._tool_token_limit_before_evict
            ), False
        return await FilesystemMiddleware._aprocess_large_message(
            self._scoped(message), message, resolved_backend
        )
