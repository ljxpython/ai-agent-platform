"""Resource failures through real thread backends, with no production resources."""

import asyncio
import errno
import os

import httpx
import pytest
from langchain_mcp_adapters.interceptors import MCPToolCallRequest

from runtime_service.runtime import RuntimeAuthError
from runtime_service.runtime.errors import RuntimeWorkspaceError
from runtime_service.services.dearflow_agent.tools import mcp
from runtime_service.services.dearflow_agent.workspace.backend import (
    DearWorkspaceBackend,
)
from runtime_service.tools.images import ImageWorkspace


def test_tool_write_does_not_recreate_a_missing_trusted_root(tmp_path):
    root = tmp_path / "missing"
    with pytest.raises(RuntimeWorkspaceError, match="runtime.workspace.unavailable"):
        ImageWorkspace(root)._directory(("generated",), create=True)
    assert not root.exists()
    os.close(ImageWorkspace(root)._directory(("work",), create=True, create_root=True))
    assert (root / "work").is_dir()


def test_root_failure_stops_without_replacing_workspace_or_existing_file(tmp_path):
    original = tmp_path / "original"
    original.mkdir()
    (original / "keep.txt").write_text("keep")
    root = tmp_path / "workspace"
    root.symlink_to(original, target_is_directory=True)
    with pytest.raises(RuntimeWorkspaceError, match="runtime.workspace.unavailable"):
        ImageWorkspace(root)._directory(("work",), create=True)
    assert root.is_symlink() and (original / "keep.txt").read_text() == "keep"
    assert not (original / "work").exists()


@pytest.mark.parametrize("failure", [errno.EACCES, errno.ENOSPC])
def test_root_resource_failure_preserves_existing_files(monkeypatch, tmp_path, failure):
    root = tmp_path / "workspace"
    root.mkdir()
    (root / "keep.txt").write_text("keep")
    original_open = os.open
    error = OSError(failure, "PRIVATE_RESOURCE_CANARY")

    def failing_open(path, *args, **kwargs):
        if path == root.name and kwargs.get("dir_fd") is not None:
            raise error
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(os, "open", failing_open)
    with pytest.raises(RuntimeWorkspaceError) as caught:
        ImageWorkspace(root)._directory(("work",), create=True)
    assert caught.value.__cause__ is error
    assert str(caught.value) == "runtime.workspace.unavailable"
    assert (root / "keep.txt").read_text() == "keep"
    assert not (root / "work").exists()


def test_execute_cli_start_failure_is_fatal_and_does_not_run_host_command(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("RUNTIME_BACKEND", "docker")
    backend = DearWorkspaceBackend("tenant", "project", "failed-start")
    backend.prepare()
    (backend.root / "work/keep.txt").write_text("keep")
    monkeypatch.setenv("PATH", "")
    with pytest.raises(
        RuntimeWorkspaceError, match="runtime.workspace.execution_outcome_unknown"
    ):
        asyncio.run(backend.aexecute("touch host-execution-must-not-happen"))
    assert (backend.root / "work/keep.txt").read_text() == "keep"
    assert not (backend.root / "work/host-execution-must-not-happen").exists()


@pytest.mark.parametrize(
    "error",
    [
        ValueError("conversion"),
        RuntimeAuthError("denied"),
        ExceptionGroup(
            "mixed", [httpx.ConnectError("CANARY"), ValueError("conversion")]
        ),
    ],
)
def test_mcp_interceptor_does_not_downgrade_conversion_or_security_failures(error):
    async def handler(request):
        raise error

    with pytest.raises(type(error)):
        asyncio.run(
            mcp._read_only_transport(
                MCPToolCallRequest(name="mcp_read", args={}, server_name="bound"),
                handler,
            )
        )


@pytest.mark.integration
def test_docker_preserves_nonzero_and_timeout_results_without_repeat(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("RUNTIME_BACKEND", "docker")
    monkeypatch.setenv("RUNTIME_WORKSPACE_IMAGE", "python:3.13-slim")
    backend = DearWorkspaceBackend("tenant", "project", "docker-test")
    backend.prepare()

    async def run():
        nonzero = await backend.aexecute(
            "printf first >> counter.txt; exit 7", timeout=5
        )
        assert nonzero.exit_code == 7
        timed_out = await backend.aexecute(
            "printf second >> counter.txt; sleep 5", timeout=1
        )
        assert timed_out.exit_code in (124, 137)
        assert (backend.root / "work/counter.txt").read_text() == "firstsecond"
        assert backend.root.is_dir()

    asyncio.run(run())
