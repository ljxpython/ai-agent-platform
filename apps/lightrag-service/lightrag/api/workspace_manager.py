from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from lightrag import LightRAG
from lightrag.api.raganything_integration import RAGAnythingProcessor

if TYPE_CHECKING:
    from lightrag.api.routers.document_routes import DocumentManager


@dataclass(slots=True)
class WorkspaceResources:
    workspace: str
    rag: LightRAG
    doc_manager: "DocumentManager"
    raganything_processor: RAGAnythingProcessor | None = None


class LightRAGWorkspaceManager:
    def __init__(
        self,
        *,
        default_workspace: str = "",
        rag_factory: Callable[[str], LightRAG],
        doc_manager_factory: Callable[[str], "DocumentManager"],
        raganything_factory: Callable[[LightRAG], RAGAnythingProcessor | None] | None = None,
    ) -> None:
        self._default_workspace = default_workspace
        self._rag_factory = rag_factory
        self._doc_manager_factory = doc_manager_factory
        self._raganything_factory = raganything_factory
        self._resources: dict[str, WorkspaceResources] = {}
        self._initialized: set[str] = set()
        self._locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

    @property
    def default_workspace(self) -> str:
        return self._default_workspace

    def resolve_workspace(self, workspace: str | None) -> str:
        normalized = (workspace or "").strip()
        return normalized or self._default_workspace

    async def register_resources(
        self,
        *,
        workspace: str,
        resources: WorkspaceResources,
    ) -> None:
        normalized = self.resolve_workspace(workspace)
        async with self._global_lock:
            self._resources[normalized] = resources

    async def get_resources(self, workspace: str | None) -> WorkspaceResources:
        normalized = self.resolve_workspace(workspace)
        lock = await self._get_lock(normalized)
        async with lock:
            resources = self._resources.get(normalized)
            if resources is None:
                rag = self._rag_factory(normalized)
                resources = WorkspaceResources(
                    workspace=normalized,
                    rag=rag,
                    doc_manager=self._doc_manager_factory(normalized),
                    raganything_processor=(
                        self._raganything_factory(rag)
                        if self._raganything_factory is not None
                        else None
                    ),
                )
                self._resources[normalized] = resources

            if normalized not in self._initialized:
                await resources.rag.initialize_storages()
                await resources.rag.check_and_migrate_data()
                self._initialized.add(normalized)

            return resources

    async def finalize_all(self) -> None:
        async with self._global_lock:
            resources_items = list(self._resources.items())
            self._resources = {}
            self._initialized.clear()
            self._locks = {}

        for _, resources in resources_items:
            try:
                await resources.rag.finalize_storages()
            except Exception:
                # Finalization is best-effort during shutdown.
                pass

    async def _get_lock(self, workspace: str) -> asyncio.Lock:
        async with self._global_lock:
            lock = self._locks.get(workspace)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[workspace] = lock
            return lock
