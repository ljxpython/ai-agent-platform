"""Service binding for a persistent, isolated thread workspace."""
from __future__ import annotations

import asyncio
import os
from importlib.resources import files
from pathlib import Path

from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from deepagents.backends.protocol import SandboxBackendProtocol, ExecuteResponse, WriteResult, EditResult
from langchain.agents.middleware import AgentMiddleware

from runtime_service.runtime import RuntimeAuthError, verified_delegation_from_user
from runtime_service.tools.images import ImageWorkspace
from runtime_service.workspace.scoped import resolve_thread_workspace, thread_scope_hash
from runtime_service.workspace.execution import execute_in_workspace

PACKAGE = "runtime_service.services.dearflow_agent"


class DearWorkspaceBackend(FilesystemBackend, SandboxBackendProtocol):
    def __init__(self, tenant: str, project: str, thread: str):
        self.scope = (tenant, project, thread)
        self.root = resolve_thread_workspace(tenant, project, thread, "dearflow_agent")
        super().__init__(root_dir=self.root.parent, virtual_mode=True)

    @property
    def id(self) -> str:
        return "dearflow-" + thread_scope_hash(*self.scope)

    def prepare(self):
        io = ImageWorkspace(self.root)
        for folder in ("uploads", "work", "outputs"):
            os.close(io._directory((folder,), create=True))

    def _can_write(self, path: str) -> bool:
        # Shell access is restricted by mounts; filesystem tools need their own guard.
        if not path.startswith("/workspace/work/") or ".." in path.split("/"):
            return False
        try:
            resolved = self._resolve_path(path)
            return resolved.is_relative_to(self.root / "work")
        except (ValueError, OSError, RuntimeError):
            return False

    def write(self, file_path: str, content: str) -> WriteResult:
        if not self._can_write(file_path):
            return WriteResult(error="workspace_write_denied")
        return super().write(file_path, content)

    def edit(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> EditResult:
        if not self._can_write(file_path):
            return EditResult(error="workspace_write_denied")
        return super().edit(file_path, old_string, new_string, replace_all)

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        return asyncio.run(self.aexecute(command, timeout=timeout))

    async def aexecute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        try:
            return await execute_in_workspace(
                self.root, command, timeout=timeout, protected=True,
                image=os.getenv("RUNTIME_WORKSPACE_IMAGE", "runtime-agent-workspace:p1"),
                skills=Path(str(files(PACKAGE).joinpath("skills"))),
            )
        except TimeoutError:
            return ExecuteResponse(output="Execution timed out.", exit_code=124)


def build_backend(workspace):
    return CompositeBackend(
        default=workspace if workspace is not None else StateBackend(),
        routes={
            "/skills/": FilesystemBackend(root_dir=str(files(PACKAGE).joinpath("skills")), virtual_mode=True),
            "/conversation_history/": StateBackend(),
            "/large_tool_results/": StateBackend(),
        },
    )


class WorkspaceMiddleware(AgentMiddleware):
    def __init__(self, workspace):
        self.workspace = workspace

    async def abefore_agent(self, state, runtime):
        if self.workspace is None:
            raise RuntimeAuthError("runtime.graph.probe_only")
        facts = verified_delegation_from_user(runtime.server_info.user)
        scope = (facts.principal.tenant_id, facts.principal.project_id, runtime.execution_info.thread_id)
        if scope != self.workspace.scope or facts.scope.assistant_id != "dearflow_agent":
            raise RuntimeAuthError("runtime.workspace.scope_mismatch")
        await asyncio.to_thread(self.workspace.prepare)
