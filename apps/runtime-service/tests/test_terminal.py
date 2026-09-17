import base64
import os
import shutil
import subprocess
import time
from uuid import uuid4

import pytest
from runtime_service.workspace.documents import DocumentError
from runtime_service.workspace.terminal import TerminalManager

OWNER = ("tenant", "project", "thread", "showcase_demo", "user")


@pytest.fixture
def manager(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("RUNTIME_SHOWCASE_BACKEND", "local")
    monkeypatch.setenv("RUNTIME_TERMINAL_ENABLED", "1")
    monkeypatch.setenv("SHOULD_NOT_LEAK", "private-marker")
    manager = TerminalManager()
    yield manager
    manager.shutdown()


def wait_output(session, expected, offset=0):
    deadline = time.monotonic() + 15
    output = bytearray()
    while time.monotonic() < deadline:
        response = session.read(offset)
        output.extend(base64.b64decode(response["data_base64"]))
        offset = response["next_offset"]
        if expected in output:
            return bytes(output), offset
        time.sleep(0.05)
    pytest.fail(f"Missing {expected!r} in {bytes(output)!r}")


def test_local_interactive_resize_replay_and_idempotency(manager):
    request = str(uuid4())
    ref = manager.create(OWNER, request, 24, 80)
    assert manager.create(OWNER, request, 24, 80)["terminal_id"] == ref["terminal_id"]
    session = manager.get(OWNER, ref["terminal_id"])
    data = b"printf 'hello-terminal\\n'; test -t 0 && echo tty-ok; echo ${SHOULD_NOT_LEAK-unset}\n"
    result = session.write(data, 0)
    assert session.write(data, 0) == result
    output, offset = wait_output(session, b"tty-ok\r\nunset")
    assert b"hello-terminal" in output
    assert base64.b64decode(session.read(0)["data_base64"]) == output
    with pytest.raises(DocumentError, match="input_conflict"):
        session.write(b"other", 0)
    with pytest.raises(DocumentError, match="input_sequence"):
        session.write(b"other", 3)
    session.resize(40, 120)
    session.write(b"stty size\n", 1)
    _, offset = wait_output(session, b"40 120", offset)
    session.write(b"sleep 30\n", 2)
    time.sleep(0.2)
    session.write(b"\x03", 3)
    session.write(b"printf 'after-interrupt\\n'\n", 4)
    wait_output(session, b"after-interrupt\r\n", offset)
    session.write(b"exit 7\n", 5)
    deadline = time.monotonic() + 3
    while session.finished is None and time.monotonic() < deadline:
        time.sleep(0.05)
    assert session.describe()["status"] == "exited"
    assert session.describe()["exit_code"] == 7


def test_scope_quota_expiry_and_shutdown(manager):
    sessions = [manager.create(OWNER, str(uuid4()), 24, 80) for _ in range(4)]
    with pytest.raises(DocumentError, match="session_limit"):
        manager.create(OWNER, str(uuid4()), 24, 80)
    identifier = sessions[0]["terminal_id"]
    for owner in ((*OWNER[:-1], "other-user"), ("tenant", "other", *OWNER[2:])):
        with pytest.raises(DocumentError, match="not_found"):
            manager.get(owner, identifier)
        assert manager.list(owner)["items"] == []
    session = manager.get(OWNER, identifier)
    session.last_input -= 901
    manager.sweep()
    assert session.describe()["reason"] == "idle_expired"
    assert session.process.poll() is not None
    session.finished -= 301
    manager.sweep()
    with pytest.raises(DocumentError, match="not_found"):
        manager.get(OWNER, identifier)
    manager.shutdown()
    with pytest.raises(DocumentError, match="instance_changed"):
        manager.get(OWNER, identifier)


def test_bounded_replay_and_ahead_cursor(manager, monkeypatch):
    import runtime_service.workspace.terminal as module

    monkeypatch.setattr(module, "BUFFER_BYTES", 128)
    session = manager.get(
        OWNER, manager.create(OWNER, str(uuid4()), 24, 80)["terminal_id"]
    )
    session.write(b"python -c 'print(\"x\" * 2000)'\n", 0)
    deadline = time.monotonic() + 5
    while session.offset == 0 and time.monotonic() < deadline:
        time.sleep(0.05)
    response = session.read(0)
    assert response["truncated"] and response["offset"] > 0
    assert len(base64.b64decode(response["data_base64"])) <= 128
    with pytest.raises(DocumentError, match="offset_ahead"):
        session.read(10000000)


def test_close_foreground_job_and_lifetime(manager, monkeypatch):
    session = manager.get(
        OWNER, manager.create(OWNER, str(uuid4()), 24, 80)["terminal_id"]
    )
    session.write(b"sleep 300\n", 0)
    deadline = time.monotonic() + 5
    foreground = session.process.pid
    while (
        foreground <= 0 or foreground == session.process.pid
    ) and time.monotonic() < deadline:
        time.sleep(0.05)
        foreground = os.tcgetpgrp(session.fd)
    assert foreground > 0 and foreground != session.process.pid
    session.created -= 3601
    manager.sweep()
    assert session.reason == "lifetime_expired"
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            os.kill(foreground, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        pytest.fail("foreground process survived terminal close")
    with pytest.raises(DocumentError, match="exited"):
        session.write(b"x", 1)
    second = manager.get(
        OWNER, manager.create(OWNER, str(uuid4()), 24, 80)["terminal_id"]
    )
    monkeypatch.setenv("RUNTIME_TERMINAL_ENABLED", "0")
    manager.sweep()
    assert second.reason == "disabled"


def test_docker_terminal_real(manager, monkeypatch):
    if (
        not shutil.which("docker")
        or subprocess.run(
            ["docker", "info"], capture_output=True, timeout=10, check=False
        ).returncode
    ):
        pytest.skip("Docker daemon unavailable")
    monkeypatch.setenv("RUNTIME_SHOWCASE_BACKEND", "docker")
    session = manager.get(
        OWNER, manager.create(OWNER, str(uuid4()), 24, 80)["terminal_id"]
    )
    session.write(
        b"test -t 0 && echo docker-tty; echo saved > terminal.txt; test ! -e /var/run/docker.sock && echo no-socket\n",
        0,
    )
    output, _ = wait_output(session, b"\r\nno-socket\r\n")
    assert (session.root / "terminal.txt").read_text().strip() == "saved", output
    session.resize(35, 100)
    session.write(b"stty size\n", 1)
    wait_output(session, b"35 100")
    session.close()
    assert (
        subprocess.run(
            ["docker", "inspect", session.container],
            capture_output=True,
            timeout=10,
            check=False,
        ).returncode
        != 0
    )


def test_dearflow_terminal_mount_policy(manager, monkeypatch, tmp_path):
    if (
        not shutil.which("docker")
        or subprocess.run(
            ["docker", "info"], capture_output=True, timeout=10, check=False
        ).returncode
    ):
        pytest.skip("Docker daemon unavailable")
    monkeypatch.setenv("RUNTIME_WORKSPACE_IMAGE", "python:3.13-slim")
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path / "dear"))
    owner = (*OWNER[:3], "dearflow_agent", OWNER[4])
    session = manager.get(
        owner, manager.create(owner, str(uuid4()), 24, 80)["terminal_id"]
    )
    session.write(
        b"echo ok > /workspace/work/writable.txt; touch /workspace/denied 2>/dev/null || echo readonly-root; touch /skills/denied 2>/dev/null || echo readonly-skills\n",
        0,
    )
    wait_output(session, b"\r\nreadonly-skills\r\n")
    assert (session.root / "work/writable.txt").read_text().strip() == "ok"
    assert not (session.root / "denied").exists()
