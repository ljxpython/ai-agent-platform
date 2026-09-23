"""Service binding for a persistent, isolated thread workspace."""
from __future__ import annotations

import asyncio
import hashlib
import os
import shutil
import sys
import tempfile
from importlib.resources import files
from pathlib import Path

from deepagents.backends import (
    CompositeBackend,
    FilesystemBackend,
    LocalShellBackend,
    StateBackend,
)
from deepagents.backends.protocol import (
    DeleteResult,
    EditResult,
    ExecuteResponse,
    FileUploadResponse,
    SandboxBackendProtocol,
    WriteResult,
)
from langchain.agents.middleware import AgentMiddleware

from runtime_service.runtime import RuntimeAuthError, verified_delegation_from_user
from runtime_service.tools.images import ImageWorkspace
from runtime_service.workspace.execution import (
    MAX_OUTPUT,
    execute_in_workspace,
    runtime_backend,
)
from runtime_service.workspace.scoped import resolve_thread_workspace, thread_scope_hash

PACKAGE = "runtime_service.services.dearflow_agent"


def skills_hash(root=None) -> str:
    """Fingerprint packaged skill resources, including provenance and licenses."""
    root = Path(root) if root is not None else Path(str(files(PACKAGE).joinpath("skills")))
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise RuntimeAuthError("runtime.skill.snapshot_mismatch")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            digest.update(path.relative_to(root).as_posix().encode() + b"\0")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


class DearWorkspaceBackend(FilesystemBackend, SandboxBackendProtocol):
    def __init__(self, tenant: str, project: str, thread: str):
        self.scope = (tenant, project, thread)
        self.root = resolve_thread_workspace(tenant, project, thread, "dearflow_agent")
        self.skills_root = Path(str(files(PACKAGE).joinpath("skills")))
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
        if runtime_backend() == "local":
            if not isinstance(command, str) or not command.strip() or len(command) > 32768:
                raise ValueError("command must be non-empty and at most 32768 characters")
            if timeout is not None and (type(timeout) is not int or not 1 <= timeout <= 60):
                raise ValueError("timeout must be between 1 and 60 seconds")
            shell = LocalShellBackend(
                root_dir=self.root / "work", virtual_mode=True, inherit_env=False,
                env={
                    "PATH": os.pathsep.join((str(Path(sys.executable).parent), os.defpath)),
                    "HOME": str(self.root / "work"),
                    "GIT_CONFIG_GLOBAL": "/dev/null",
                    "RUNTIME_WORKSPACE_ROOT": str(self.root),
                    "RUNTIME_SKILLS_ROOT": str(self.skills_root),
                },
                timeout=30, max_output_bytes=MAX_OUTPUT,
            )
            return await asyncio.to_thread(shell.execute, command, timeout=timeout)
        try:
            return await execute_in_workspace(
                self.root, command, timeout=timeout, protected=True,
                image=os.getenv("RUNTIME_WORKSPACE_IMAGE", "runtime-agent-workspace:p5"),
                skills=self.skills_root,
            )
        except TimeoutError:
            return ExecuteResponse(output="Execution timed out.", exit_code=124)


def prepare_custom_skills(workspace, documents):
    workspace.prepare()
    public_root = Path(str(files(PACKAGE).joinpath("skills")))
    expected = {}
    for path in public_root.rglob("*"):
        if path.is_symlink():
            raise RuntimeAuthError("runtime.skill.snapshot_mismatch")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            expected[path.relative_to(public_root).as_posix()] = hashlib.sha256(path.read_bytes()).digest()
    for document in documents:
        for name, content in document["files"].items():
            expected[f"custom/{document['slug']}/{name}"] = hashlib.sha256(content.encode()).digest()
    digest = hashlib.sha256()
    for name, hashed in sorted(expected.items()):
        digest.update(name.encode() + b"\0")
        digest.update(hashed)
    fingerprint = digest.hexdigest()
    root = workspace.root.parent / ("skills-" + fingerprint)
    if root.is_symlink():
        raise RuntimeAuthError("runtime.skill.snapshot_mismatch")
    if not root.exists():
        with tempfile.TemporaryDirectory(prefix=".skills-", dir=workspace.root.parent) as staging:
            staged = Path(staging) / "snapshot"
            shutil.copytree(Path(str(files(PACKAGE).joinpath("skills"))), staged)
            for document in documents:
                directory = staged / "custom" / document["slug"]
                for name, content in document["files"].items():
                    path = directory / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content)
            try:
                staged.rename(root)
            except OSError:
                if not root.is_dir():
                    raise
    if skills_hash(root) != fingerprint:
        raise RuntimeAuthError("runtime.skill.snapshot_mismatch")
    workspace.skills_root = root


class ReadOnlySkillsBackend(FilesystemBackend):
    def delete(self, file_path):
        return DeleteResult(error="skill_resource_read_only")

    def write(self, file_path, content):
        return WriteResult(error="skill_resource_read_only")

    def edit(self, file_path, old_string, new_string, replace_all=False):
        return EditResult(error="skill_resource_read_only")

    def upload_files(self, files):
        return [FileUploadResponse(path=path, error="permission_denied") for path, _ in files]


def build_backend(workspace):
    return CompositeBackend(
        default=workspace if workspace is not None else StateBackend(),
        routes={
            "/skills/": ReadOnlySkillsBackend(root_dir=str(workspace.skills_root if workspace else files(PACKAGE).joinpath("skills")), virtual_mode=True),
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
