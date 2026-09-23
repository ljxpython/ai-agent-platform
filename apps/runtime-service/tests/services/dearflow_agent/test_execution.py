import asyncio
import shutil
import subprocess

import pytest
from runtime_service.services.dearflow_agent.workspace.backend import (
    DearWorkspaceBackend,
)


def test_local_execute_uses_thread_workspace_without_service_secrets(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_BACKEND", "local")
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", "must-not-enter-shell")
    backend = DearWorkspaceBackend("tenant", "project", "thread")
    backend.prepare()
    backend.write("/workspace/work/input.txt", "hello")

    result = asyncio.run(backend.aexecute(
        'cat "$RUNTIME_WORKSPACE_ROOT/work/input.txt" > output.txt; '
        'test -z "$PLATFORM_RUNTIME_DELEGATION_SECRET"; '
        'test -f "$RUNTIME_SKILLS_ROOT/runtime-smoke/SKILL.md"'
    ))
    assert result.exit_code == 0, result.output
    assert backend.read("/workspace/work/output.txt").file_data["content"] == "hello"
    assert asyncio.run(backend.aexecute("exit 7")).exit_code == 7
    assert asyncio.run(backend.aexecute("sleep 2", timeout=1)).exit_code == 124
    for timeout in (0, 61, True):
        with pytest.raises(ValueError):
            asyncio.run(backend.aexecute("true", timeout=timeout))


def test_local_skill_scripts_use_thread_root(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_BACKEND", "local")
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path))
    backend = DearWorkspaceBackend("tenant", "project", "thread")
    backend.prepare()
    backend.write("/workspace/work/input.csv", "name,value\nitem,1\n")
    backend.write("/workspace/work/plan.json", '{"slides":[{"title":"test"}]}')

    async def run():
        analysis = await backend.aexecute(
            'python "$RUNTIME_SKILLS_ROOT/data-analysis/scripts/analyze.py" '
            '--files "$RUNTIME_WORKSPACE_ROOT/work/input.csv" --action inspect'
        )
        assert analysis.exit_code == 0, analysis.output
        image = await backend.aexecute(
            "python -c 'from PIL import Image; Image.new(\"RGB\", (10, 10)).save(\"slide.png\")'"
        )
        assert image.exit_code == 0, image.output
        slides = await backend.aexecute(
            'python "$RUNTIME_SKILLS_ROOT/ppt-generation/scripts/generate.py" '
            '--plan-file "$RUNTIME_WORKSPACE_ROOT/work/plan.json" '
            '--slide-images "$RUNTIME_WORKSPACE_ROOT/work/slide.png" '
            '--output-file "$RUNTIME_WORKSPACE_ROOT/work/deck.pptx"'
        )
        assert slides.exit_code == 0, slides.output

    asyncio.run(run())
    assert (backend.root / "work/deck.pptx").is_file()


@pytest.mark.integration
def test_container_mounts_timeout_and_output_limit(monkeypatch, tmp_path):
    if not shutil.which("docker") or subprocess.run(
        ["docker", "info"], capture_output=True, timeout=15, check=False
    ).returncode:
        pytest.skip("Docker daemon is unavailable")
    monkeypatch.setenv("RUNTIME_BACKEND", "docker")
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path))
    backend = DearWorkspaceBackend("tenant", "project", "thread")
    backend.prepare()
    async def run():
        for path in ("/workspace/uploads/bad.txt", "/workspace/outputs/bad.txt", "/skills/bad.txt", "/etc/bad.txt"):
            result = await backend.aexecute(f"echo bad > {path}")
            assert result.exit_code != 0
        result = await backend.aexecute("sleep 5", timeout=1)
        assert result.exit_code != 0
        result = await backend.aexecute("python -c 'print(chr(120)*200000)'")
        assert len(result.output.encode()) <= 128 * 1024
        assert result.truncated
        # A process cannot keep running after cancellation.
        task = asyncio.create_task(backend.aexecute("sleep 3; echo leaked > cancelled.txt"))
        await asyncio.sleep(0.5)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await asyncio.sleep(3)
        assert not (backend.root / "work/cancelled.txt").exists()
    asyncio.run(run())
