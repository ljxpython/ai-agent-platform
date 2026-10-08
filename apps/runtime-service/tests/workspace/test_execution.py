"""Single-execution, cancellation ownership and real subprocess boundary checks."""

import asyncio
import errno
import importlib.util
import json
import math
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from runtime_service.runtime.errors import RuntimeWorkspaceError
from runtime_service.workspace import execution

UNKNOWN = "runtime.workspace.execution_outcome_unknown"


class Process:
    def __init__(self, code=0, *, read_error=None):
        self.returncode = None
        self.code = code
        self.stdout = AsyncMock()
        self.stdout.read.side_effect = read_error or [b"output", b""]
        self.killed = False

    async def wait(self):
        self.returncode = self.code
        return self.code

    def kill(self):
        self.killed = True
        self.returncode = -9


@pytest.mark.parametrize("code", [0, 7, 125, 137])
def test_results_are_never_replayed_and_only_125_probes(monkeypatch, tmp_path, code):
    spawn = AsyncMock(return_value=Process(code))
    control, report = AsyncMock(return_value=True), AsyncMock()
    monkeypatch.setattr(execution.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(execution, "_docker_control", control)
    monkeypatch.setattr(execution, "_report", report)
    result = asyncio.run(
        execution.execute_in_workspace(tmp_path, "exit 7", image="test")
    )
    assert result.exit_code == code and result.output == "output"
    spawn.assert_awaited_once()
    assert control.await_count == (1 if code == 125 else 0)
    if code == 125:
        assert control.await_args.args == ("info", "--format", "{{.ServerVersion}}")
        assert control.await_args.kwargs == {"seconds": 2}
    report.assert_not_awaited()


@pytest.mark.parametrize(
    "failure",
    [
        errno.EAGAIN,
        errno.EACCES,
        errno.EPERM,
        errno.ENOENT,
        errno.ENOSPC,
        errno.ENOMEM,
        errno.EBUSY,
    ],
)
def test_os_creation_failures_are_single_attempts(monkeypatch, tmp_path, failure):
    spawn = AsyncMock(side_effect=OSError(failure, "CANARY"))
    monkeypatch.setattr(execution.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(execution, "_docker_control", AsyncMock(return_value=True))
    with pytest.raises(
        RuntimeWorkspaceError, match="runtime.workspace.execution_unavailable"
    ):
        asyncio.run(execution.execute_in_workspace(tmp_path, "one", image="test"))
    spawn.assert_awaited_once()


@pytest.mark.parametrize("phase", ["start", "read", "wait", "probe", "cleanup"])
def test_failures_stop_once_without_raw_os_error_or_private_output(
    monkeypatch, tmp_path, phase
):
    error = OSError(errno.EAGAIN, "PRIVATE_COMMAND_PATH_CANARY")
    process = Process(
        125 if phase == "probe" else 0,
        read_error=error if phase in {"read", "cleanup"} else None,
    )
    if phase == "wait":
        process.wait = AsyncMock(side_effect=[error, 0])
    spawn = (
        AsyncMock(side_effect=error)
        if phase == "start"
        else AsyncMock(return_value=process)
    )
    control = AsyncMock(return_value=phase not in {"probe", "cleanup"})
    report = AsyncMock()
    monkeypatch.setattr(execution.asyncio, "create_subprocess_exec", spawn)
    monkeypatch.setattr(execution, "_docker_control", control)
    monkeypatch.setattr(execution, "_report", report)
    with pytest.raises(RuntimeWorkspaceError) as caught:
        asyncio.run(execution.execute_in_workspace(tmp_path, "secret", image="test"))
    expected = (
        "runtime.workspace.execution_unavailable" if phase == "start" else UNKNOWN
    )
    assert str(caught.value) == expected and not isinstance(caught.value, OSError)
    spawn.assert_awaited_once()
    summary = report.await_args.args[0]
    assert summary["code"] == expected and summary["attempts"] == 1
    assert summary["command_state"] == "unknown" and summary["retry_wait_ms"] == 0
    assert "CANARY" not in repr(summary) and "secret" not in repr(summary)
    assert summary["phase"] == (
        "cleanup"
        if phase in {"probe", "cleanup"}
        else "start"
        if phase == "start"
        else "execute"
    )


@pytest.mark.parametrize("confirmed", [False, True])
def test_confirmed_timeout_keeps_existing_backend_semantics(
    monkeypatch, tmp_path, confirmed
):
    process = Process(read_error=TimeoutError("CANARY"))
    monkeypatch.setattr(
        execution.asyncio, "create_subprocess_exec", AsyncMock(return_value=process)
    )
    monkeypatch.setattr(execution, "_docker_control", AsyncMock(return_value=confirmed))
    report = AsyncMock()
    monkeypatch.setattr(execution, "_report", report)
    with pytest.raises(TimeoutError if confirmed else RuntimeWorkspaceError):
        asyncio.run(execution.execute_in_workspace(tmp_path, "sleep", image="test"))
    assert process.killed
    assert report.await_args.args[0]["code"] == (None if confirmed else UNKNOWN)


@pytest.mark.parametrize("during_creation", [False, True])
@pytest.mark.parametrize("reap_failure", [False, True])
def test_cancellation_reaps_owned_process_and_keeps_workspace(
    monkeypatch, tmp_path, during_creation, reap_failure
):
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        process = Process()

        async def spawn(*args, **kwargs):
            if during_creation:
                entered.set()
                await release.wait()
            return process

        async def read(_size):
            entered.set()
            await asyncio.Event().wait()

        process.stdout.read.side_effect = read
        if reap_failure:
            process.wait = AsyncMock(side_effect=RuntimeError("REAP_CANARY"))
        control = AsyncMock(side_effect=OSError("CLEANUP_CANARY"))
        report = AsyncMock()
        monkeypatch.setattr(execution.asyncio, "create_subprocess_exec", spawn)
        monkeypatch.setattr(execution, "_docker_control", control)
        monkeypatch.setattr(execution, "_report", report)
        task = asyncio.create_task(
            execution.execute_in_workspace(tmp_path, "sleep", image="test")
        )
        await entered.wait()
        task.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert process.killed and tmp_path.is_dir()
        assert control.await_count == 1
        assert report.await_args.args[0]["outcome"] == "cancelled"

    asyncio.run(run())


def test_read_only_control_has_a_deadline_even_during_creation(monkeypatch):
    async def spawn(*args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(execution.asyncio, "create_subprocess_exec", spawn)
    assert not asyncio.run(execution._docker_control("info", seconds=0.01))


@pytest.mark.parametrize(
    "code,output,healthy",
    [(0, b"28.0.4\n", True), (0, b"\n", False), (1, b"28.0.4\n", False)],
)
def test_info_requires_server_version_even_when_cli_exits_zero(
    monkeypatch, code, output, healthy
):
    process = Process(code)
    process.returncode = code
    process.communicate = AsyncMock(return_value=(output, None))
    spawn = AsyncMock(return_value=process)
    monkeypatch.setattr(execution.asyncio, "create_subprocess_exec", spawn)
    assert (
        asyncio.run(
            execution._docker_control(
                "info", "--format", "{{.ServerVersion}}", seconds=2
            )
        )
        is healthy
    )
    assert spawn.await_args.kwargs["stdout"] == asyncio.subprocess.PIPE
    assert spawn.await_args.kwargs["stderr"] == asyncio.subprocess.DEVNULL


def test_control_cancellation_reaps_a_process_returned_after_cancellation(monkeypatch):
    async def run():
        entered, release = asyncio.Event(), asyncio.Event()
        process = Process()

        async def spawn(*args, **kwargs):
            entered.set()
            await release.wait()
            return process

        monkeypatch.setattr(execution.asyncio, "create_subprocess_exec", spawn)
        task = asyncio.create_task(execution._docker_control("info", seconds=2))
        await entered.wait()
        task.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert process.killed

    asyncio.run(run())


def test_repeated_cancel_during_creation_has_bounded_cleanup(monkeypatch, tmp_path):
    async def run():
        entered = asyncio.Event()
        closed = asyncio.Event()

        async def spawn(*args, **kwargs):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                closed.set()

        monkeypatch.setattr(execution.asyncio, "create_subprocess_exec", spawn)
        monkeypatch.setattr(execution, "_docker_control", AsyncMock(return_value=True))
        task = asyncio.create_task(
            execution.execute_in_workspace(tmp_path, "one", image="test")
        )
        await entered.wait()
        task.cancel()
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
        assert closed.is_set() and tmp_path.is_dir()

    asyncio.run(run())


@pytest.mark.parametrize("failure", [RuntimeError("CANARY"), TimeoutError("CANARY")])
def test_diagnostics_callback_failure_keeps_primary_workspace_error(
    monkeypatch, tmp_path, failure
):
    monkeypatch.setattr(
        execution.asyncio,
        "create_subprocess_exec",
        AsyncMock(side_effect=OSError(errno.EACCES, "CANARY")),
    )
    monkeypatch.setattr(execution, "_docker_control", AsyncMock(return_value=True))
    monkeypatch.setattr(
        execution, "adispatch_custom_event", AsyncMock(side_effect=failure)
    )
    with pytest.raises(
        RuntimeWorkspaceError, match="runtime.workspace.execution_unavailable"
    ):
        asyncio.run(execution.execute_in_workspace(tmp_path, "secret", image="test"))


def test_slow_diagnostics_does_not_extend_execution_failure(monkeypatch, tmp_path):
    async def slow(*args, **kwargs):
        await asyncio.sleep(10)

    monkeypatch.setattr(
        execution.asyncio,
        "create_subprocess_exec",
        AsyncMock(side_effect=OSError("CANARY")),
    )
    monkeypatch.setattr(execution, "_docker_control", AsyncMock(return_value=True))
    monkeypatch.setattr(execution, "adispatch_custom_event", slow)

    async def run():
        with pytest.raises(RuntimeWorkspaceError):
            async with asyncio.timeout(1):
                await execution.execute_in_workspace(tmp_path, "one", image="test")

    asyncio.run(run())


def test_creation_eagain_can_follow_a_real_child_side_effect(monkeypatch, tmp_path):
    marker = tmp_path / "counter"
    error = BlockingIOError(errno.EAGAIN, "synthetic boundary fault")

    async def run():
        loop = asyncio.get_running_loop()

        original_connect = loop.connect_read_pipe

        async def broken_pipe(factory, pipe):
            protocol = factory()
            parent = protocol.proc
            await original_connect(lambda: protocol, pipe)
            async with asyncio.timeout(2):
                while not marker.exists() or parent.get_returncode() is None:
                    await asyncio.sleep(0.01)
            raise error

        with monkeypatch.context() as patch:
            patch.setattr(loop, "connect_read_pipe", broken_pipe)
            with pytest.raises(BlockingIOError) as caught:
                await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-c",
                    "from pathlib import Path; Path(__import__('sys').argv[1]).write_text('once')",
                    str(marker),
                    stdout=asyncio.subprocess.PIPE,
                )
            assert caught.value is error and marker.read_text() == "once"

    asyncio.run(run())
    marker.unlink()

    def failed_fork(*args, **kwargs):
        raise error

    monkeypatch.setattr(subprocess, "_fork_exec", failed_fork)
    with pytest.raises(BlockingIOError):
        subprocess.Popen(
            [
                sys.executable,
                "-c",
                "from pathlib import Path; Path(__import__('sys').argv[1]).write_text('once')",
                str(marker),
            ],
            stdout=subprocess.PIPE,
        )
    assert not marker.exists()


@pytest.mark.integration
def test_real_unreachable_daemon_keeps_workspace_and_never_uses_host_shell(
    monkeypatch, tmp_path
):
    tmp_path.joinpath("counter").write_text("keep")
    # macOS pytest paths can exceed the Unix socket path limit before Docker runs.
    with tempfile.TemporaryDirectory(prefix="workspace-daemon-", dir="/tmp") as root:
        monkeypatch.setenv("DOCKER_HOST", "unix://" + str(Path(root) / "missing.sock"))
        monkeypatch.delenv("DOCKER_CONTEXT", raising=False)
        with pytest.raises(RuntimeWorkspaceError, match=UNKNOWN):
            asyncio.run(
                execution.execute_in_workspace(
                    tmp_path, "printf replayed >> counter", image="python:3.13-slim"
                )
            )
    assert tmp_path.joinpath("counter").read_text() == "keep"


@pytest.mark.integration
def test_real_docker_unknown_and_cancel_do_not_repeat_or_replace_workspace(
    monkeypatch, tmp_path
):
    async def run():
        control = execution._docker_control
        probes = []

        async def observed_control(*args, **kwargs):
            result = await control(*args, **kwargs)
            if args[0] == "info":
                probes.append(result)
            return result

        monkeypatch.setattr(execution, "_docker_control", observed_control)
        for command, expected in (
            ("printf a >> counter; exit 7", 7),
            ("printf b >> counter; exit 125", 125),
        ):
            try:
                result = await execution.execute_in_workspace(
                    tmp_path, command, image="python:3.13-slim"
                )
            except RuntimeWorkspaceError as exc:
                assert expected == 125 and probes == [False] and str(exc) == UNKNOWN
            else:
                assert result.exit_code == expected
                assert probes == ([] if expected == 7 else [True])
        assert (tmp_path / "counter").read_text() == "ab"

        async def unavailable_probe(*args, **kwargs):
            return False if args[0] == "info" else await control(*args, **kwargs)

        monkeypatch.setattr(execution, "_docker_control", unavailable_probe)
        with pytest.raises(RuntimeWorkspaceError, match=UNKNOWN):
            await execution.execute_in_workspace(
                tmp_path, "printf c >> counter; exit 125", image="python:3.13-slim"
            )
        assert (tmp_path / "counter").read_text() == "abc"
        task = asyncio.create_task(
            execution.execute_in_workspace(
                tmp_path,
                "printf d >> counter; sleep 3; touch leaked",
                image="python:3.13-slim",
            )
        )
        async with asyncio.timeout(5):
            while (tmp_path / "counter").read_text() != "abcd":
                await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(3.1)
        assert not (tmp_path / "leaked").exists()
        assert (tmp_path / "counter").read_text() == "abcd" and tmp_path.is_dir()

    asyncio.run(run())


@pytest.mark.integration
def test_real_docker_success_measurement_and_parallel_isolation(monkeypatch, tmp_path):
    baseline_file = tmp_path / "baseline_execution.py"
    repo = Path(__file__).resolve().parents[4]
    baseline_file.write_bytes(
        subprocess.check_output(
            [
                "git",
                "show",
                "HEAD:apps/runtime-service/src/runtime_service/workspace/execution.py",
            ],
            cwd=repo,
        )
    )
    spec = importlib.util.spec_from_file_location("workspace_baseline", baseline_file)
    baseline = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(baseline)
    original = asyncio.create_subprocess_exec
    calls = []

    async def spawn(*args, **kwargs):
        calls.append(args[:2])
        return await original(*args, **kwargs)

    monkeypatch.setattr(execution.asyncio, "create_subprocess_exec", spawn)
    report = AsyncMock()
    monkeypatch.setattr(execution, "_report", report)

    async def run():
        modules = {"baseline": baseline, "current": execution}
        latencies = {label: [] for label in modules}
        cpu_ms = dict.fromkeys(modules, 0.0)
        for label, module in modules.items():
            (tmp_path / label).mkdir()
            result = await module.execute_in_workspace(
                tmp_path / label, "true", image="python:3.13-slim"
            )
            assert result.exit_code == 0
        calls.clear()
        for _ in range(12):
            for label, module in modules.items():
                cpu = time.process_time()
                start = time.perf_counter()
                result = await module.execute_in_workspace(
                    tmp_path / label, "printf x >> counter", image="python:3.13-slim"
                )
                latencies[label].append((time.perf_counter() - start) * 1000)
                cpu_ms[label] += (time.process_time() - cpu) * 1000
                assert result.exit_code == 0
        assert calls == [("docker", "run")] * 24
        for label, durations in latencies.items():
            assert (tmp_path / label / "counter").read_text() == "x" * 12
            print(
                json.dumps(
                    {
                        "workspace_success": label,
                        "sampling": "warmup_then_alternating",
                        "samples": 12,
                        "p50_ms": round(statistics.median(durations), 3),
                        "p95_ms": round(
                            sorted(durations)[math.ceil(0.95 * len(durations)) - 1], 3
                        ),
                        "python_cpu_ms": round(cpu_ms[label], 3),
                        "command_processes": 12,
                        "extra_control_processes": 0,
                    }
                ),
                flush=True,
            )
        report.assert_not_awaited()
        roots = [tmp_path / "parallel-one", tmp_path / "parallel-two"]
        for root in roots:
            root.mkdir()
        results = await asyncio.gather(
            *(
                execution.execute_in_workspace(
                    root, "printf once >> counter", image="python:3.13-slim"
                )
                for root in roots
            )
        )
        assert all(result.exit_code == 0 for result in results)
        assert [root.joinpath("counter").read_text() for root in roots] == [
            "once",
            "once",
        ]

    asyncio.run(run())


@pytest.mark.integration
def test_real_parallel_repeated_cancel_reaps_only_owned_resources(
    monkeypatch, tmp_path
):
    original_spawn = asyncio.create_subprocess_exec
    processes, names = [], []

    async def spawn(*args, **kwargs):
        process = await original_spawn(*args, **kwargs)
        if args[:2] == ("docker", "run"):
            names.append(args[args.index("--name") + 1])
            processes.append(process)
        return process

    monkeypatch.setattr(execution.asyncio, "create_subprocess_exec", spawn)
    roots = [tmp_path / name for name in ("one", "two")]
    for root in roots:
        root.mkdir()
        (root / "keep").write_text("keep")

    async def run():
        tasks = [
            asyncio.create_task(
                execution.execute_in_workspace(
                    root,
                    "printf once >> counter; "
                    "while [ ! -e release ]; do sleep 0.1; done; touch leaked",
                    image="python:3.13-slim",
                )
            )
            for root in roots
        ]
        try:
            async with asyncio.timeout(15):
                while not all(root.joinpath("counter").is_file() for root in roots):
                    await asyncio.sleep(0.05)
            tasks[0].cancel()
            await asyncio.sleep(0)
            tasks[0].cancel()
            with pytest.raises(asyncio.CancelledError):
                await tasks[0]
            assert not tasks[1].done()
            tasks[1].cancel()
            await asyncio.sleep(0)
            tasks[1].cancel()
            with pytest.raises(asyncio.CancelledError):
                await tasks[1]
            for root in roots:
                root.joinpath("release").touch()
            await asyncio.sleep(0.3)
            assert len(set(names)) == 2
            assert all(process.returncode is not None for process in processes)
            for root in roots:
                assert root.joinpath("counter").read_text() == "once"
                assert root.joinpath("keep").read_text() == "keep"
                assert not root.joinpath("leaked").exists()
            for name in names:
                remaining = subprocess.check_output(
                    [
                        "docker",
                        "ps",
                        "-a",
                        "--filter",
                        f"name={name}",
                        "--format",
                        "{{.Names}}",
                    ],
                    timeout=15,
                    text=True,
                )
                assert not remaining.strip()
            print(
                json.dumps(
                    {
                        "parallel_cancellations": 2,
                        "repeat_cancel": True,
                        "side_effects": ["once", "once"],
                        "owned_cli_and_containers_remaining": 0,
                        "workspace_preserved": True,
                    }
                ),
                flush=True,
            )
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            for name in names:
                subprocess.run(
                    ["docker", "rm", "-f", name],
                    capture_output=True,
                    timeout=15,
                )

    asyncio.run(run())
