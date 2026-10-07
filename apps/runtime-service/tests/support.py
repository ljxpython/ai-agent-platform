from __future__ import annotations

import time
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from langchain_core.language_models.fake_chat_models import (
    FakeListChatModel,
    FakeMessagesListChatModel,
)
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool


class BindableFakeChatModel(FakeListChatModel):
    """Small test model that accepts tools without simulating tool calls."""

    def bind_tools(
        self,
        tools: Sequence[BaseTool | dict[str, object] | object],
        *,
        tool_choice: str | None = None,
        **kwargs: object,
    ) -> Runnable:
        return self


class BindableFakeMessagesChatModel(FakeMessagesListChatModel):
    """Test model that emits a fixed message through the real agent path."""

    def bind_tools(
        self,
        tools: Sequence[BaseTool | dict[str, object] | object],
        *,
        tool_choice: str | None = None,
        **kwargs: object,
    ) -> Runnable:
        return self


__all__ = ["BindableFakeChatModel", "BindableFakeMessagesChatModel"]


def with_run_budget(
    config: dict, *, timeout: float = 300, remaining: float | None = None
) -> dict:
    """Explicit Worker snapshot for graph tests; never a production fallback."""
    run_id = str(uuid4())
    configurable = dict(config.get("configurable") or {})
    now = datetime.now(UTC)
    configurable["__graphharbor_run_budget"] = {
        "version": 1,
        "run_id": run_id,
        "thread_id": configurable.get("thread_id"),
        "started_at": now.isoformat(),
        "deadline_at": (now + timedelta(seconds=timeout)).isoformat(),
        "timeout_seconds": timeout,
        "deadline_monotonic": time.monotonic()
        + (timeout if remaining is None else remaining),
    }
    return {
        **config,
        "configurable": configurable,
        "metadata": {**config.get("metadata", {}), "run_id": run_id},
    }
