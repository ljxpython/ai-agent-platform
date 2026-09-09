from __future__ import annotations

import shutil
import subprocess
from importlib.resources import files

import pytest

from runtime_service.runtime import RuntimeAuthError
from runtime_service.services.demo.showcase_demo.backend import (
    DockerWorkspaceBackend,
    build_backend,
)


def test_workspace_isolation_and_portable_skills(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path))
    first = DockerWorkspaceBackend("tenant", "project", "first")
    second = DockerWorkspaceBackend("tenant", "project", "second")
    assert not first.cwd.exists()
    first.prepare()
    second.prepare()
    assert first.cwd != second.cwd
    first.write("/workspace/private.txt", "thread one")
    assert second.read("/workspace/private.txt").error
    first.edit(
        "/workspace/report.py",
        'Decimal(row["unit_price"])',
        'Decimal(row["unit_price"]) * int(row["quantity"])',
    )
    first.prepare()
    assert 'int(row["quantity"])' in (first.cwd / "workspace/report.py").read_text()
    skill = build_backend(first).read("/skills/showcase-notes/SKILL.md")
    assert skill.error is None
    assert "43.50" in str(skill.file_data["content"])
    assert (
        files("runtime_service.services.demo.showcase_demo")
        .joinpath("examples/sales.csv")
        .is_file()
    )
    with pytest.raises(ValueError):
        first.read("/../../outside")


def test_workspace_rejects_symlink_root(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path / "data"))
    workspace = DockerWorkspaceBackend("tenant", "project", "thread")
    workspace.cwd.parent.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    workspace.cwd.symlink_to(outside, target_is_directory=True)
    with pytest.raises(RuntimeAuthError):
        workspace.prepare()
    with pytest.raises(RuntimeAuthError):
        DockerWorkspaceBackend("tenant", "project", "thread")


@pytest.mark.integration
def test_docker_executes_real_files_and_enforces_limits(monkeypatch, tmp_path):
    if not shutil.which("docker"):
        pytest.skip("Docker CLI is unavailable")
    ready = subprocess.run(
        ["docker", "info"], capture_output=True, timeout=15, check=False
    )
    if ready.returncode:
        pytest.skip("Docker daemon is unavailable")
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path))
    workspace = DockerWorkspaceBackend("tenant", "project", "docker-thread")
    workspace.prepare()
    initial = workspace.execute("python report.py")
    assert initial.exit_code == 0, initial.output
    assert "27.00" in initial.output
    assert not workspace.edit(
        "/workspace/report.py",
        'Decimal(row["unit_price"])',
        'Decimal(row["unit_price"]) * int(row["quantity"])',
    ).error
    result = workspace.execute("python report.py > result.txt && cat result.txt")
    assert result.exit_code == 0, result.output
    assert "43.50" in result.output
    assert "43.50" in (workspace.cwd / "workspace/result.txt").read_text()
    assert workspace.execute("exit 7").exit_code == 7
    assert workspace.execute("sleep 5", timeout=1).exit_code in (124, 137)
    assert workspace.execute("echo blocked > /outside.txt").exit_code != 0
    assert workspace.execute("test ! -e /var/run/docker.sock").exit_code == 0
    assert workspace.execute("test ! -e /workspace/.env").exit_code == 0
    assert workspace.execute("python -c 'print(\"x\" * 200000)'").truncated
    with pytest.raises(ValueError):
        workspace.execute("true", timeout=0)
    monkeypatch.setenv("RUNTIME_SHOWCASE_IMAGE", "showcase-missing-image:never")
    assert workspace.execute("echo must-not-succeed").exit_code != 0
