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
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.messages.utils import count_tokens_approximately

from runtime_service.observability.logging import log_context_metric

_PATH_RE = re.compile(r"(/large_tool_results/[^\s\'\"]+)")


def _prune_tool_content(content: Any, name: str, min_chars: int) -> tuple[Any, bool]:
    """Prune content of an older ToolMessage if it exceeds min_chars."""
    if isinstance(content, str):
        if len(content) <= min_chars:
            return content, False

        match = _PATH_RE.search(content)
        if match:
            file_path = match.group(1)
            notice = (
                f"\n[Earlier '{name}' result: omitted middle. Full text: {file_path}; "
                "use read_file with offset/limit.]\n"
            )
        else:
            notice = (
                f"\n[Earlier '{name}' result: omitted middle. No readable archive is "
                "available here; reread the original source for missing evidence.]\n"
            )
        limit = min(min_chars, 6000)
        if len(notice) >= limit:
            return content, False
        budget = min(5120, limit - len(notice))
        head = budget * 4 // 5
        tail = budget - head
        return content[:head] + notice + (content[-tail:] if tail else ""), True

    if isinstance(content, list):
        new_blocks = []
        modified = False
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text", "")
                if len(text) > min_chars:
                    replacement, changed = _prune_tool_content(text, name, min_chars)
                    new_blocks.append({**block, "text": replacement})
                    modified = modified or changed
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
    min_chars: int = 8192,
) -> list[Any]:
    """Fold older ToolMessages while preserving latest tools and state intact."""
    tool_indices = [i for i, m in enumerate(messages) if isinstance(m, ToolMessage)]
    if len(tool_indices) <= keep_recent:
        return messages

    latest_ai = next((m for m in reversed(messages) if isinstance(m, AIMessage)), None)
    protected_ids = (
        {call["id"] for call in latest_ai.tool_calls} if latest_ai else set()
    )
    turn_start = next(
        (
            i
            for i in range(len(messages) - 1, -1, -1)
            if isinstance(messages[i], HumanMessage)
        ),
        -1,
    )
    # Unconsumed batches and this turn's bounded delegation reports are working context.
    protected_ids.update(
        call["id"]
        for message in messages[turn_start + 1 :]
        if isinstance(message, AIMessage)
        for call in message.tool_calls
        if call["name"] == "task"
    )
    prune_indices = {
        i
        for i in tool_indices[:-keep_recent]
        if messages[i].tool_call_id not in protected_ids
    }
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
        trigger_tokens: int | None = None,
    ) -> None:
        super().__init__()
        self._enabled = enabled
        self._keep_recent = keep_recent
        self._min_chars = min_chars
        if trigger_tokens is not None and trigger_tokens <= 0:
            raise ValueError("pruning trigger must be positive")
        self.trigger_tokens = trigger_tokens

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
                    os.getenv("AGENT_CONTEXT_TOOL_PRUNING_MIN_CHARS", "8192")
                )
            except ValueError:
                min_chars = 8192

        return enabled, max(1, keep_recent), max(50, min_chars)

    def filter_messages(
        self, messages: list[Any], system_message=None, tools=None
    ) -> list[Any]:
        enabled, keep_recent, min_chars = self._resolve_settings()
        if not enabled:
            return messages
        counted = (
            [system_message, *messages] if system_message is not None else messages
        )
        if (
            self.trigger_tokens is not None
            and count_tokens_approximately(counted, tools=tools) < self.trigger_tokens
        ):
            return messages

        return prune_messages_for_model(
            messages,
            keep_recent=keep_recent,
            min_chars=min_chars,
        )

    def _filter_request(self, request: ModelRequest) -> ModelRequest:
        filtered_messages = self.filter_messages(
            request.messages, request.system_message, request.tools
        )
        if filtered_messages is request.messages:
            return request

        try:
            log_context_metric(
                {
                    "event": "runtime.tool_output.pruned",
                    "changed_messages": sum(
                        a is not b
                        for a, b in zip(
                            request.messages, filtered_messages, strict=True
                        )
                    ),
                    "estimated_tokens_before": count_tokens_approximately(
                        request.messages
                    ),
                    "estimated_tokens_after": count_tokens_approximately(
                        filtered_messages
                    ),
                }
            )
        except Exception:
            pass  # Diagnostics must not affect the model view.
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
