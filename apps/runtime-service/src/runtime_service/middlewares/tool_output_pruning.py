"""Ephemeral tool output pruning middleware.

Virtual context folding: dynamically prunes older ToolMessages in the ModelRequest
to lightweight placeholders before reaching the LLM, without mutating persistent checkpoints.
"""

from __future__ import annotations

import os
import re
from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import (
    ModelCallResult,
    ModelRequest,
    ModelResponse,
)
from langchain_core.messages import ToolMessage

_PATH_RE = re.compile(r"(/large_tool_results/[^\s\'\"]+)")


def _prune_tool_content(content: Any, name: str, min_chars: int) -> tuple[Any, bool]:
    """Prune content of an older ToolMessage if it exceeds min_chars."""
    if isinstance(content, str):
        if len(content) <= min_chars:
            return content, False

        match = _PATH_RE.search(content)
        if match:
            file_path = match.group(1)
            placeholder = (
                f"[Tool output reference: '{name}' offloaded to {file_path}. "
                f"Full result ({len(content)} chars) preserved; use read_file to inspect.]"
            )
        else:
            placeholder = (
                f"[Tool output collapsed: '{name}' returned {len(content)} chars. "
                f"Full result safely preserved in database checkpoint.]"
            )
        return placeholder, True

    if isinstance(content, list):
        new_blocks = []
        modified = False
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                if len(text) > min_chars:
                    match = _PATH_RE.search(text)
                    if match:
                        file_path = match.group(1)
                        replacement = (
                            f"[Tool output reference: '{name}' offloaded to {file_path}. "
                            f"Full result ({len(text)} chars) preserved; use read_file to inspect.]"
                        )
                    else:
                        replacement = (
                            f"[Tool output collapsed: '{name}' returned {len(text)} chars. "
                            f"Full result safely preserved in database checkpoint.]"
                        )
                    new_blocks.append({**block, "text": replacement})
                    modified = True
                else:
                    new_blocks.append(block)
            else:
                new_blocks.append(block)
        return new_blocks, modified

    return content, False


def prune_messages_for_model(
    messages: list[Any],
    *,
    keep_recent: int = 4,
    min_chars: int = 300,
) -> list[Any]:
    """Fold older ToolMessages while preserving latest tools and state intact."""
    tool_indices = [i for i, m in enumerate(messages) if isinstance(m, ToolMessage)]
    if len(tool_indices) <= keep_recent:
        return messages

    prune_indices = set(tool_indices[:-keep_recent])
    pruned_messages = []
    has_changes = False

    for idx, msg in enumerate(messages):
        if idx in prune_indices and isinstance(msg, ToolMessage):
            tool_name = getattr(msg, "name", "") or "tool"
            new_content, changed = _prune_tool_content(
                msg.content, tool_name, min_chars
            )
            if changed:
                has_changes = True
                pruned_messages.append(msg.model_copy(update={"content": new_content}))
            else:
                pruned_messages.append(msg)
        else:
            pruned_messages.append(msg)

    return pruned_messages if has_changes else messages


class ToolOutputPruningMiddleware(AgentMiddleware):
    """Dynamically prune older tool outputs before sending the prompt to the LLM."""

    @property
    def name(self) -> str:
        return "ToolOutputPruningMiddleware"

    def __init__(
        self,
        *,
        enabled: bool | None = None,
        keep_recent: int | None = None,
        min_chars: int | None = None,
    ) -> None:
        super().__init__()
        self._enabled = enabled
        self._keep_recent = keep_recent
        self._min_chars = min_chars

    def _resolve_settings(self) -> tuple[bool, int, int]:
        if self._enabled is not None:
            enabled = self._enabled
        else:
            enabled = os.getenv("AGENT_CONTEXT_TOOL_PRUNING_ENABLED", "1") in (
                "1",
                "true",
                "True",
            )

        if self._keep_recent is not None:
            keep_recent = self._keep_recent
        else:
            try:
                keep_recent = int(
                    os.getenv("AGENT_CONTEXT_TOOL_PRUNING_KEEP_COUNT", "4")
                )
            except ValueError:
                keep_recent = 4

        if self._min_chars is not None:
            min_chars = self._min_chars
        else:
            try:
                min_chars = int(
                    os.getenv("AGENT_CONTEXT_TOOL_PRUNING_MIN_CHARS", "300")
                )
            except ValueError:
                min_chars = 300

        return enabled, max(1, keep_recent), max(50, min_chars)

    def _filter_request(self, request: ModelRequest) -> ModelRequest:
        enabled, keep_recent, min_chars = self._resolve_settings()
        if not enabled:
            return request

        filtered_messages = prune_messages_for_model(
            request.messages,
            keep_recent=keep_recent,
            min_chars=min_chars,
        )
        if filtered_messages is request.messages:
            return request

        return request.override(messages=filtered_messages)

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelCallResult:
        return handler(self._filter_request(request))

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Awaitable[ModelResponse]],
    ) -> ModelCallResult:
        return await handler(self._filter_request(request))
