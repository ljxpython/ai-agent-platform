"""Real Docker runner gates; only disposable, explicitly labelled containers."""

import asyncio
import json
import os
import secrets
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import pytest

from runtime_service.workspace.background import (
    BackgroundBinding,
    create_task_container,
    decode_snapshots,
    inspect_task_container,
    read_task_output,
    read_task_receipt,
    remove_task_container,
    start_task_container,
    stop_task_container,
)
from runtime_service.workspace.background_runner import MAX_LOG_BYTES, Output


def test_output_binary_and_utf8_remain_bounded():
    for payload in (b"abc" * 4000000, b"\xff" * 4000000, "测试".encode() * 2000000):
        output = Output()
        for n in range(0, len(payload), 8192):
            output.add(payload[n : n + 8192])
        text, omitted, truncated = output.snapshot()
        assert len(text) <= MAX_LOG_BYTES and omitted > 0 and truncated
        text.decode()
    assert decode_snapshots(b'{"snapshot": 1, "part": 9}') is None


@pytest.mark.parametrize(
    "command,timeout,exit_code",
    [
        ("exit 124", 30, 1),
        ("exit 137", 30, 1),
        ("sleep 60", 1, 20),
        ('python3 -c \'import sys; sys.stdout.write("A"*10485760+"TAIL")\'', 30, 0),
    ],
)
def test_real_container_exit_deadline_and_bounded_output(
    tmp_path, monkeypatch, command, timeout, exit_code
):
    if os.getenv("BACKGROUND_DOCKER_TEST") != "1":
        pytest.skip("BACKGROUND_DOCKER_TEST=1 requires the managed test daemon")
    monkeypatch.setenv("RUNTIME_EXECUTION_HOST_ID", "background-test")
    monkeypatch.setenv("RUNTIME_BACKEND", "docker")
    task = uuid4()
    row = {
        "task_id": task,
        "execution_host_id": "background-test",
        "container_name": "runtime-bg-" + task.hex,
        "container_id": None,
        "binding_digest": "test-scope",
        "runner_secret": secrets.token_hex(32),
    }
    binding = BackgroundBinding(
        tmp_path, "python:3.13-slim", ("test", "test", "test"), "showcase_demo"
    )

    async def verify():
        try:
            state = await create_task_container(row, binding, command, timeout)
            row["container_id"] = state["id"]
            state = await start_task_container(row)
            deadline = time.monotonic() + 40
            while state["Running"] and time.monotonic() < deadline:
                await asyncio.sleep(0.1)
                state = await inspect_task_container(row)
            assert state["Status"] == "exited" and state["ExitCode"] == exit_code, state
            snapshot = await read_task_output(row)
            assert snapshot is not None
            assert len(snapshot[0].encode()) <= MAX_LOG_BYTES
            if "10485760" in command:
                assert snapshot[0].startswith("A") and snapshot[0].endswith("TAIL")
                assert snapshot[1] > 9000000 and snapshot[2]
                inspected = subprocess.run(
                    ["docker", "inspect", row["container_id"]],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=15,
                )
                facts = json.loads(inspected.stdout)[0]
                assert facts["HostConfig"]["LogConfig"] == {
                    "Type": "local",
                    "Config": {"max-size": "2m", "max-file": "2"},
                }
                root = subprocess.run(
                    ["docker", "info", "--format={{.DockerRootDir}}"],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=15,
                )
                log_directory = (
                    Path(root.stdout.strip())
                    / "containers"
                    / row["container_id"]
                    / "local-logs"
                )
                assert log_directory.is_absolute()
                usage = subprocess.run(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "--network=none",
                        "--memory=64m",
                        "--pids-limit=16",
                        "--label=runtime.background.verification=log-bytes",
                        "--mount",
                        f"type=bind,source={log_directory},target=/logs,readonly",
                        "--entrypoint=python3",
                        "python:3.13-slim",
                        "-I",
                        "-c",
                        "from pathlib import Path; print(sum(p.stat().st_size for p in Path('/logs').rglob('*') if p.is_file()))",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                    timeout=30,
                )
                assert 0 < int(usage.stdout) <= 4 * 1024 * 1024
            assert await remove_task_container(row)
        finally:
            await stop_task_container(row)
            await remove_task_container(row)

    asyncio.run(verify())


def test_release_image_two_controllers_share_daemon_and_absolute_mount(
    tmp_path, monkeypatch
):
    image = os.getenv("BACKGROUND_RUNTIME_IMAGE")
    if not image:
        pytest.skip("BACKGROUND_RUNTIME_IMAGE must name the locked release image")
    host = "background-image-test"
    monkeypatch.setenv("RUNTIME_EXECUTION_HOST_ID", host)
    task = uuid4()
    row = {
        "task_id": str(task),
        "execution_host_id": host,
        "container_name": "runtime-bg-" + task.hex,
        "container_id": None,
        "binding_digest": "image-shared-scope",
        "runner_secret": secrets.token_hex(32),
    }
    workspace = str(tmp_path.resolve())
    prefix = "import asyncio,json,sys,time; from pathlib import Path; from runtime_service.workspace.background import *; row=json.load(sys.stdin); "
    scripts = [
        prefix
        + f"binding=BackgroundBinding(Path({workspace!r}), 'python:3.13-slim', ('test','test','test'), 'showcase_demo')\n"
        + """
async def run():
    started = time.monotonic()
    state = await create_task_container(row, binding, 'printf SHARED > proof.txt; printf SHARED; sleep 600', 900)
    row['container_id'] = state['id']
    state = await start_task_container(row)
    print(json.dumps({'running': state['Running'], 'ack_seconds': time.monotonic()-started}))
asyncio.run(run())
""",
        prefix
        + """
async def run():
    state = await inspect_task_container(row)
    assert state['Running']
    output = await read_task_output(row)
    assert output and output[0] == 'SHARED'
    await stop_task_container(row)
    assert await remove_task_container(row)
    print(json.dumps({'shared_mount': True, 'cleanup': True}))
asyncio.run(run())
""",
    ]
    results = []
    try:
        for script in scripts:
            result = subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--interactive",
                    "--label",
                    "runtime.background.verification=20261009",
                    "--entrypoint=python",
                    "--env",
                    "RUNTIME_BACKEND=docker",
                    "--env",
                    "RUNTIME_EXECUTION_HOST_ID=" + host,
                    "--volume",
                    workspace + ":" + workspace,
                    "--volume",
                    "/var/run/docker.sock:/var/run/docker.sock",
                    image,
                    "-c",
                    script,
                ],
                input=json.dumps(row),
                text=True,
                capture_output=True,
                timeout=120,
            )
            assert result.returncode == 0, result.stderr[-2000:]
            results.append(json.loads(result.stdout.strip().splitlines()[-1]))
        assert results[0]["running"] and results[1]["cleanup"]
        assert (tmp_path / "proof.txt").read_text() == "SHARED"
        print(json.dumps({"image": image, "controllers": 2, "results": results}))
    finally:
        asyncio.run(stop_task_container(row))
        asyncio.run(remove_task_container(row))


@pytest.mark.parametrize("scenario", ["forged-result-and-env", "oom", "missing"])
def test_real_runner_trust_boundary_oom_and_external_removal(
    tmp_path, monkeypatch, scenario
):
    if os.getenv("BACKGROUND_DOCKER_TEST") != "1":
        pytest.skip("BACKGROUND_DOCKER_TEST=1 requires the managed test daemon")
    monkeypatch.setenv("RUNTIME_EXECUTION_HOST_ID", "background-boundary-test")
    task = uuid4()
    row = {
        "task_id": task,
        "execution_host_id": "background-boundary-test",
        "container_name": "runtime-bg-" + task.hex,
        "container_id": None,
        "binding_digest": "boundary-test",
        "runner_secret": secrets.token_hex(32),
    }
    commands = {
        "forged-result-and-env": """python3 -c 'import os; from pathlib import Path; assert not Path("/var/run/docker.sock").exists(); assert not any(k.startswith(("PLATFORM_", "GRAPHHARBOR_", "OPENAI_", "RUNTIME_BACKGROUND_RECEIPT_SECRET")) for k in os.environ); Path("state.json").write_text("succeeded"); print("<script>succeeded</script>")'; exit 7""",
        "oom": "python3 -c 'x=bytearray(512*1024*1024)'",
        "missing": "sleep 60",
    }
    binding = BackgroundBinding(
        tmp_path, "python:3.13-slim", ("test", "test", "test"), "showcase_demo"
    )

    async def verify():
        try:
            state = await create_task_container(row, binding, commands[scenario], 45)
            row["container_id"] = state["id"]
            state = await start_task_container(row)
            if scenario == "missing":
                result = subprocess.run(
                    ["docker", "rm", "-f", row["container_id"]],
                    capture_output=True,
                    timeout=15,
                )
                assert result.returncode == 0
                assert await inspect_task_container(row) is None
                return
            deadline = time.monotonic() + 50
            while state["Running"] and time.monotonic() < deadline:
                await asyncio.sleep(0.1)
                state = await inspect_task_container(row)
            assert not state["Running"]
            if scenario == "oom":
                assert state["OOMKilled"]
            else:
                assert state["ExitCode"] == 1
                receipt = await read_task_receipt(row)
                assert receipt == {"outcome": 1, "exit_code": 7}
                assert (tmp_path / "state.json").read_text() == "succeeded"
                assert (await read_task_output(row))[
                    0
                ].strip() == "<script>succeeded</script>"
        finally:
            await stop_task_container(row)
            await remove_task_container(row)

    asyncio.run(verify())
