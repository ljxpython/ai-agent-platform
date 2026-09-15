"""Official filesystem backend plus isolated Docker execution for one thread."""

from __future__ import annotations

import asyncio
import os
from importlib.resources import files

from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from deepagents.backends.protocol import ExecuteResponse, SandboxBackendProtocol
from langchain.agents.middleware import AgentMiddleware

from runtime_service.runtime import RuntimeAuthError, verified_delegation_from_user
from runtime_service.workspace.scoped import hashed_thread_root, thread_scope_hash

_PACKAGE = "runtime_service.services.demo.showcase_demo"


class DockerWorkspaceBackend(FilesystemBackend, SandboxBackendProtocol):
    """File operations stay native; only shell execution crosses into Docker."""

    def __init__(self, tenant_id: str, project_id: str, thread_id: str) -> None:
        self.scope = (tenant_id, project_id, thread_id)
        self._id = thread_scope_hash(tenant_id, project_id, thread_id)
        base = os.getenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", ".runtime/showcase")
        root = hashed_thread_root(base, tenant_id, project_id, thread_id)
        if root.is_symlink():
            raise RuntimeAuthError("runtime.workspace.invalid_path")
        super().__init__(root_dir=root, virtual_mode=True)

    @property
    def id(self) -> str:
        return self._id

    def prepare(self) -> None:
        """Seed a new workspace once, without overwriting the user's changes."""
        workspace = self.cwd / "workspace"
        if self.cwd.is_symlink() or workspace.is_symlink():
            raise RuntimeAuthError("runtime.workspace.invalid_path")
        workspace.mkdir(parents=True, exist_ok=True)
        marker = self.cwd / ".initialized"
        if marker.exists():
            return
        for resource in files(_PACKAGE).joinpath("examples").iterdir():
            if resource.is_file():
                try:
                    with (workspace / resource.name).open("xb") as destination:
                        destination.write(resource.read_bytes())
                except FileExistsError:
                    pass
        marker.touch()

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        return asyncio.run(self.aexecute(command, timeout=timeout))

    async def aexecute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        from runtime_service.workspace.execution import execute_in_workspace
        try:
            return await execute_in_workspace(
                self.cwd / "workspace", command,
                image=os.getenv("RUNTIME_SHOWCASE_IMAGE", "python:3.13-slim"), timeout=timeout,
            )
        except TimeoutError:
            return ExecuteResponse(output="Execution timed out.", exit_code=124)


def build_backend(workspace: DockerWorkspaceBackend | None) -> CompositeBackend:
    """Resource paths are package-relative; model-visible paths stay portable."""
    return CompositeBackend(
        default=workspace
        if workspace is not None
        else DockerWorkspaceBackend("probe", "probe", "probe"),
        routes={
            "/skills/": FilesystemBackend(
                root_dir=str(files(_PACKAGE).joinpath("skills")), virtual_mode=True
            ),
            "/conversation_history/": StateBackend(),
        },
    )


class WorkspaceMiddleware(AgentMiddleware):
    """Check the bound scope before initializing any thread-owned resources."""

    def __init__(self, workspace: DockerWorkspaceBackend | None) -> None:
        self.workspace = workspace

    async def abefore_agent(self, state, runtime) -> None:
        if self.workspace is None:
            raise RuntimeAuthError("runtime.graph.probe_only")
        facts = verified_delegation_from_user(runtime.server_info.user)
        scope = (
            facts.principal.tenant_id,
            facts.principal.project_id,
            runtime.execution_info.thread_id,
        )
        if scope != self.workspace.scope:
            raise RuntimeAuthError("runtime.workspace.scope_mismatch")
        await asyncio.to_thread(self.workspace.prepare)
