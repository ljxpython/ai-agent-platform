import asyncio

from runtime_service.services.dearflow_agent.workspace.backend import DearWorkspaceBackend


def test_container_mounts_timeout_and_output_limit(monkeypatch, tmp_path):
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
