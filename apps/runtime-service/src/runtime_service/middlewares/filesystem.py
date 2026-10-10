"""Keep official file tools and eviction, with collision-safe result references."""

from __future__ import annotations

from copy import copy
from hashlib import sha256

from deepagents.backends.protocol import BackendProtocol
from deepagents.middleware._message_eviction import _extract_text_from_message
from deepagents.middleware.filesystem import NUM_CHARS_PER_TOKEN, FilesystemMiddleware
from langchain_core.messages import ToolMessage


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

    def _process_large_message(
        self, message: ToolMessage, resolved_backend: BackendProtocol
    ) -> tuple[ToolMessage, bool]:
        return FilesystemMiddleware._process_large_message(
            self._scoped(message), message, resolved_backend
        )

    async def _aprocess_large_message(
        self, message: ToolMessage, resolved_backend: BackendProtocol
    ) -> tuple[ToolMessage, bool]:
        return await FilesystemMiddleware._aprocess_large_message(
            self._scoped(message), message, resolved_backend
        )
