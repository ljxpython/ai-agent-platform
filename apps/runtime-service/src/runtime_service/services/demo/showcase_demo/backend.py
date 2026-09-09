"""Official filesystem backend plus isolated Docker execution for one thread."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
from importlib.resources import files
from pathlib import Path
from uuid import uuid4

from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from deepagents.backends.protocol import ExecuteResponse, SandboxBackendProtocol
from langchain.agents.middleware import AgentMiddleware

from runtime_service.runtime import RuntimeAuthError, verified_delegation_from_user

_PACKAGE = "runtime_service.services.demo.showcase_demo"
_MAX_OUTPUT = 128 * 1024


class DockerWorkspaceBackend(FilesystemBackend, SandboxBackendProtocol):
    """File operations stay native; only shell execution crosses into Docker."""

    def __init__(self, tenant_id: str, project_id: str, thread_id: str) -> None:
        self.scope = (tenant_id, project_id, thread_id)
        self._id = hashlib.sha256(json.dumps(self.scope).encode()).hexdigest()
        base = Path(
            os.getenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", ".runtime/showcase")
        ).resolve()
        root = base / self._id
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
        if not isinstance(command, str) or not command.strip() or len(command) > 32_768:
            raise ValueError("command must be non-empty and at most 32768 characters")
        seconds = 30 if timeout is None else timeout
        if (
            not isinstance(seconds, int)
            or isinstance(seconds, bool)
            or not 1 <= seconds <= 60
        ):
            raise ValueError("timeout must be between 1 and 60 seconds")
        workspace = self.cwd / "workspace"
        if workspace.is_symlink() or not workspace.is_dir():
            raise RuntimeAuthError("runtime.workspace.not_ready")
        container = f"showcase-{uuid4().hex}"
        # Capture inside bounded tmpfs, not in an unbounded host-side PIPE.
        wrapper = (
            'timeout -s KILL "$1" sh -c "$2" > /tmp/output 2>&1; result=$?; '
            f'head -c {_MAX_OUTPUT} /tmp/output; exit "$result"'
        )
        args = [
            "docker",
            "run",
            "--rm",
            "--pull=never",
            "--name",
            container,
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--security-opt=no-new-privileges",
            "--pids-limit=64",
            "--memory=256m",
            "--cpus=1",
            "--ulimit",
            "fsize=8388608:8388608",
            "--tmpfs",
            "/tmp:rw,nosuid,nodev,size=16777216",
            "--mount",
            f"type=bind,src={workspace},dst=/workspace",
            "--workdir",
            "/workspace",
            os.getenv("RUNTIME_SHOWCASE_IMAGE", "python:3.13-slim"),
            "sh",
            "-c",
            wrapper,
            "showcase",
            str(seconds),
            command,
        ]
        try:
            result = subprocess.run(
                args, capture_output=True, timeout=seconds + 15, check=False
            )
        except FileNotFoundError as exc:
            raise RuntimeError("Docker CLI is required for showcase execution") from exc
        except subprocess.TimeoutExpired:
            subprocess.run(
                ["docker", "rm", "-f", container],
                capture_output=True,
                timeout=10,
                check=False,
            )
            return ExecuteResponse(output="Execution timed out.", exit_code=124)
        output = result.stdout + result.stderr
        return ExecuteResponse(
            output=output[:_MAX_OUTPUT].decode("utf-8", errors="replace"),
            exit_code=result.returncode,
            truncated=len(output) >= _MAX_OUTPUT,
        )


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
