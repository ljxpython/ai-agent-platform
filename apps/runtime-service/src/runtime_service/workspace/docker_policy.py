"""Shared immutable container isolation policy, independent of Agent execution."""

import os
from pathlib import Path

from runtime_service.errors import RuntimeWorkspaceError

MAX_OUTPUT = 128 * 1024


def runtime_backend() -> str:
    backend = os.getenv("RUNTIME_BACKEND", "docker")
    if backend not in {"local", "docker"}:
        raise RuntimeWorkspaceError("runtime.workspace.backend_invalid")
    return backend


def docker_workspace_args(
    workspace: Path,
    *,
    image: str,
    name: str,
    skills: Path | None = None,
    protected: bool = False,
    background: bool = False,
) -> list[str]:
    """Share the same mount and resource policy between commands and terminals."""
    if not workspace.is_dir() or workspace.is_symlink():
        raise RuntimeWorkspaceError("runtime.workspace.unavailable")
    if not image or image.startswith("-"):
        raise RuntimeWorkspaceError("runtime.workspace.image_invalid")
    args = [
        "docker",
        "create" if background else "run",
        *([] if background else ["--rm"]),
        "--pull=never",
        "--name",
        name,
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
        f"type=bind,src={workspace},dst=/workspace"
        + (",readonly" if protected else ""),
    ]
    if protected:
        args += ["--mount", f"type=bind,src={workspace / 'work'},dst=/workspace/work"]
        args += [
            "--env",
            "RUNTIME_WORKSPACE_ROOT=/workspace",
            "--env",
            "RUNTIME_SKILLS_ROOT=/skills",
        ]
    if skills is not None:
        args += ["--mount", f"type=bind,src={skills},dst=/skills,readonly"]
    return [*args, "--workdir", "/workspace/work" if protected else "/workspace", image]
