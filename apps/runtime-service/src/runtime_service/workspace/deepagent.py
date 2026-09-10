"""Thread-scoped DeepAgent workspace helpers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


@dataclass(frozen=True, slots=True)
class DeepAgentWorkspace:
    root: Path
    backend: Any


def _workspace_component(value: str, name: str) -> str:
    component = str(value).strip()
    if (
        not component
        or component in {".", ".."}
        or "/" in component
        or "\\" in component
        or "\x00" in component
    ):
        raise ValueError(f"{name} must be one path component")
    return component


def build_deepagent_workspace(
    base_dir: Path,
    *,
    tenant_id: str,
    project_id: str,
    thread_id: str,
) -> DeepAgentWorkspace:
    tenant = _workspace_component(tenant_id, "tenant_id")
    project = _workspace_component(project_id, "project_id")
    thread = _workspace_component(thread_id, "thread_id")
    base = base_dir.resolve()
    current = base
    for component in (tenant, project, thread):
        current /= component
        if current.is_symlink():
            raise ValueError("workspace path must not contain symlinks")
    root = current.resolve()
    if not root.is_relative_to(base):
        raise ValueError(f"workspace root escapes base directory: {root}")
    root.mkdir(parents=True, exist_ok=True)
    root = root.resolve()
    if not root.is_relative_to(base):
        raise ValueError(f"workspace root escapes base directory: {root}")
    from deepagents.backends.filesystem import FilesystemBackend

    return DeepAgentWorkspace(
        root=root, backend=FilesystemBackend(root_dir=root, virtual_mode=True)
    )


def resolve_workspace_virtual_path(workspace_root: Path, path_text: str) -> Path:
    root = workspace_root.resolve()
    path = str(path_text).strip()
    if not path.startswith("/"):
        raise ValueError(f"workspace path must start with '/': {path_text!r}")
    parts = PurePosixPath(path).parts
    if ".." in parts or "~" in parts or "\\" in path:
        raise ValueError(f"workspace path contains a forbidden component: {path_text!r}")
    resolved = (root / path.lstrip("/")).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"path escapes workspace root: {resolved}")
    return resolved


def resolve_skill_sources(workspace_root: Path, sources: Sequence[str]) -> list[str]:
    root = workspace_root.resolve()
    resolved_sources: list[str] = []
    for source in sources:
        skill_dir = resolve_workspace_virtual_path(root, source)
        if not skill_dir.is_dir():
            raise FileNotFoundError(f"skill source does not exist: {skill_dir}")
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            raise FileNotFoundError(f"skill source missing SKILL.md: {skill_file}")
        relative = skill_dir.relative_to(root).as_posix().rstrip("/")
        if not relative:
            raise ValueError("skill source must resolve below the workspace root")
        resolved_sources.append(f"/{relative}/")
    return resolved_sources


__all__ = [
    "DeepAgentWorkspace",
    "build_deepagent_workspace",
    "resolve_skill_sources",
    "resolve_workspace_virtual_path",
]
