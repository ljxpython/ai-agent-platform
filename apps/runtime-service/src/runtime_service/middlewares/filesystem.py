"""Keep official file tools and eviction, with collision-safe result references."""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from copy import copy
from dataclasses import replace
from hashlib import sha256

from deepagents.backends.protocol import BackendProtocol
from deepagents.middleware._message_eviction import (
    _build_evicted_content,
    _extract_text_from_message,
)
from deepagents.middleware.filesystem import (
    NUM_CHARS_PER_TOKEN,
    TOOLS_EXCLUDED_FROM_EVICTION,
    FilesystemMiddleware,
)
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest
from langgraph.types import Command

from runtime_service.observability.logging import log_context_metric
from runtime_service.tools.knowledge import KNOWLEDGE_TOOL, fit_knowledge_message


def _record_view(message, result, *, stage, archived=False):
    try:
        log_context_metric(
            {
                "event": "runtime.tool_output.view",
                "tool_call_id": str(message.tool_call_id)[:128],
                "tool_name": str(message.name or "tool")[:80],
                "stage": stage,
                "input_chars": len(_extract_text_from_message(message)),
                "visible_chars": len(_extract_text_from_message(result)),
                "archived": archived,
            }
        )
    except Exception:
        pass  # Diagnostics must never replace a tool result.


def truncate_tool_output_text(
    content: str,
    *,
    head_lines: int = 50,
    tail_lines: int = 50,
    max_chars: int = 16000,
    tool_name: str = "",
) -> str:
    """Perform Head+Tail truncation on oversized tool outputs to prevent context blowup."""
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if len(content) <= max_chars:
        return content

    lines = content.splitlines(keepends=True)
    tool_desc = f"工具 '{tool_name}' " if tool_name else "工具"
    if len(lines) <= head_lines + tail_lines:
        notice = f"\n\n[... ⚠️ {tool_desc}输出单行超限 ({len(content)} 字符)，已自动截断中间部分 ...]\n\n"
        if len(notice) >= max_chars:
            return notice[:max_chars]
        half = (max_chars - len(notice)) // 2
        return content[:half] + notice + (content[-half:] if half else "")

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
        f"提示：此处并非完整结果。若需阅读特定区域，请{hint}。]\n\n"
    )
    if len(notice) >= max_chars:
        return notice[:max_chars]
    if len(head) + len(notice) + len(tail) > max_chars:
        budget = max_chars - len(notice)
        head = head[: budget // 2]
        tail = tail[-(budget - len(head)) :] if tail else ""
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
        content = _extract_text_from_message(message)
        if not content:
            return message

        limit_tokens = self._tool_token_limit_before_evict or 4000
        env_max = os.getenv("AGENT_TOOL_OUTPUT_MAX_CHARS")
        if env_max:
            try:
                max_chars = int(env_max.strip())
            except ValueError:
                max_chars = max(4000, min(24000, NUM_CHARS_PER_TOKEN * limit_tokens))
        else:
            max_chars = max(4000, min(24000, NUM_CHARS_PER_TOKEN * limit_tokens))

        # Guard excluded tools (e.g. read_file, grep) or execute / any tool that wasn't evicted
        # but exceeds safety threshold.
        threshold = max_chars
        if actual_name not in TOOLS_EXCLUDED_FROM_EVICTION:
            if self._tool_token_limit_before_evict is not None and not env_max:
                threshold = max(
                    max_chars, NUM_CHARS_PER_TOKEN * self._tool_token_limit_before_evict
                )

        if len(content) > threshold:
            truncated = truncate_tool_output_text(
                content,
                head_lines=50,
                tail_lines=50,
                max_chars=threshold,
                tool_name=actual_name,
            )
            guarded = message.model_copy(
                update={
                    "content": _build_evicted_content(message, truncated),
                }
            )
            _record_view(message, guarded, stage="display_cap")
            return guarded
        _record_view(message, message, stage="display")
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
        if tool_name in TOOLS_EXCLUDED_FROM_EVICTION and tool_name != "read_file":
            result = self._intercept_large_tool_result(result)
        return self._guard_result(result, tool_name)

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
        if tool_name in TOOLS_EXCLUDED_FROM_EVICTION and tool_name != "read_file":
            result = await self._aintercept_large_tool_result(result)
        return self._guard_result(result, tool_name)

    def _guard_result(self, result, tool_name):
        if isinstance(result, ToolMessage):
            return self._guard_message(result, tool_name)
        if isinstance(result, Command) and result.update is not None:
            messages, wrapped = self._unwrap_command_messages(result.update)
            guarded = [
                self._guard_message(message, tool_name)
                if isinstance(message, ToolMessage)
                else message
                for message in messages
            ]
            return replace(
                result,
                update={
                    **result.update,
                    "messages": self._rewrap_command_messages(guarded, wrapped=wrapped),
                },
            )
        return result

    def _process_large_message(
        self, message: ToolMessage, resolved_backend: BackendProtocol
    ) -> tuple[ToolMessage, bool]:
        if message.name == KNOWLEDGE_TOOL and self._tool_token_limit_before_evict:
            return fit_knowledge_message(
                message, NUM_CHARS_PER_TOKEN * self._tool_token_limit_before_evict
            ), False
        result, archived = FilesystemMiddleware._process_large_message(
            self._scoped(message), message, resolved_backend
        )
        _record_view(message, result, stage="spill", archived=archived)
        return result, archived

    async def _aprocess_large_message(
        self, message: ToolMessage, resolved_backend: BackendProtocol
    ) -> tuple[ToolMessage, bool]:
        if message.name == KNOWLEDGE_TOOL and self._tool_token_limit_before_evict:
            return fit_knowledge_message(
                message, NUM_CHARS_PER_TOKEN * self._tool_token_limit_before_evict
            ), False
        result, archived = await FilesystemMiddleware._aprocess_large_message(
            self._scoped(message), message, resolved_backend
        )
        _record_view(message, result, stage="spill", archived=archived)
        return result, archived
