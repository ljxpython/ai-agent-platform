"""Runtime service monkey patches for upstream LangGraph quirks."""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from langgraph.errors import GraphBubbleUp

logger = logging.getLogger(__name__)


def apply_langgraph_patches() -> None:
    """Apply upstream fixes to LangGraph streaming and ToolNode error handling."""
    _patch_stream_tool_call_handler()
    _patch_tool_node_bubble_up()


def _patch_stream_tool_call_handler() -> None:
    try:
        from langgraph.pregel._tools import StreamToolCallHandler

        if getattr(StreamToolCallHandler, "_bubble_up_patched", False):
            return

        orig_error = StreamToolCallHandler._error

        def _patched_error(self: StreamToolCallHandler, error: BaseException, *, run_id: UUID) -> None:
            # GraphBubbleUp (including GraphInterrupt) is a control-flow interrupt signal,
            # not a failure of the tool execution. Do not emit a "tool-error" event to clients.
            if isinstance(error, GraphBubbleUp):
                info = self._run_to_call.pop(run_id, None)
                if info is not None:
                    _, _, token = info
                    self._reset_writer(token)
                return
            return orig_error(self, error, run_id=run_id)

        StreamToolCallHandler._error = _patched_error  # type: ignore[method-assign]
        StreamToolCallHandler._bubble_up_patched = True  # type: ignore[attr-defined]
    except Exception as exc:
        logger.warning("Failed to patch StreamToolCallHandler: %s", exc)


def _patch_tool_node_bubble_up() -> None:
    try:
        from langgraph.prebuilt.tool_node import ToolNode

        if getattr(ToolNode, "_bubble_up_patched", False):
            return

        orig_run_one = ToolNode._run_one
        orig_arun_one = ToolNode._arun_one

        def _patched_run_one(self: ToolNode, *args: Any, **kwargs: Any) -> Any:
            try:
                return orig_run_one(self, *args, **kwargs)
            except GraphBubbleUp:
                raise

        async def _patched_arun_one(self: ToolNode, *args: Any, **kwargs: Any) -> Any:
            try:
                return await orig_arun_one(self, *args, **kwargs)
            except GraphBubbleUp:
                raise

        ToolNode._run_one = _patched_run_one  # type: ignore[method-assign]
        ToolNode._arun_one = _patched_arun_one  # type: ignore[method-assign]
        ToolNode._bubble_up_patched = True  # type: ignore[attr-defined]
    except Exception as exc:
        logger.warning("Failed to patch ToolNode bubble up: %s", exc)
