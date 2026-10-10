"""Bounded Docker execution shared by service-specific filesystem backends."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from uuid import uuid4

from deepagents.backends.protocol import ExecuteResponse
from langchain_core.callbacks.manager import adispatch_custom_event

from runtime_service.runtime.errors import RuntimeWorkspaceError

MAX_OUTPUT = 128 * 1024
logger = logging.getLogger(__name__)


async def _reap(process) -> bool:
    try:
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        await asyncio.wait_for(process.wait(), 2)
        return True
    except Exception:
        return False


async def _docker_control(*args: str, seconds: float) -> bool:
    probe = args == ("info", "--format", "{{.ServerVersion}}")
    creation = asyncio.create_task(
        asyncio.create_subprocess_exec(
            "docker",
            *args,
            stdout=asyncio.subprocess.PIPE if probe else asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
    )
    process = None
    try:
        async with asyncio.timeout(seconds):
            process = await asyncio.shield(creation)
            if probe:
                # Docker info can exit zero on daemon failure with an empty template.
                output, _ = await process.communicate()
                return process.returncode == 0 and bool(output.strip())
            return await process.wait() == 0
    except (OSError, TimeoutError):
        return False
    finally:
        await _shielded(_control_cleanup(process, creation))


def _reap_late_creation(creation) -> None:
    if not creation.cancelled() and creation.exception() is None:
        asyncio.create_task(_reap(creation.result()))


async def _settle_creation(creation):
    done, _ = await asyncio.wait({creation}, timeout=2)
    if not done:
        creation.cancel()
        done, _ = await asyncio.wait({creation}, timeout=2)
    if done and not creation.cancelled() and creation.exception() is None:
        return creation.result(), True
    return None, bool(done)


async def _control_cleanup(process, creation) -> bool:
    settled = True
    if process is None:
        process, settled = await _settle_creation(creation)
        if not settled:
            creation.cancel()
            creation.add_done_callback(_reap_late_creation)
    return (await _reap(process) if process is not None else True) and settled


async def _cleanup(name: str, process, creation=None) -> bool:
    settled = True
    if process is None and creation is not None:
        process, settled = await _settle_creation(creation)
        if not settled:
            creation.cancel()

            def late_cleanup(completed):
                if not completed.cancelled() and completed.exception() is None:
                    asyncio.create_task(_cleanup(name, completed.result()))

            creation.add_done_callback(late_cleanup)
    # Stop the CLI before removing its container so it cannot submit a later run.
    reaped = await _reap(process) if process is not None else True
    try:
        removed = await _docker_control("rm", "-f", name, seconds=10)
    except Exception:
        removed = False
    if not removed or not reaped or not settled:
        try:
            logger.warning("workspace execution cleanup unconfirmed")
        except Exception:
            pass
    return removed and reaped and settled


async def _shielded(operation) -> bool:
    task = asyncio.create_task(operation)
    cancelled = False
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            cancelled = True
    if cancelled:
        raise asyncio.CancelledError
    return task.result()


async def _shield_cleanup(name: str, process, creation=None, *, resource=None) -> bool:
    from runtime_service.run_control.resources import finish_resource

    async def cleanup_and_record():
        confirmed = await _cleanup(name, process, creation)
        await finish_resource(resource, confirmed)
        return confirmed

    return await _shielded(cleanup_and_record())


async def _report(fields: dict) -> None:
    try:
        async with asyncio.timeout(0.1):
            await adispatch_custom_event(
                "runtime.workspace.execution_completed", fields
            )
    except Exception:
        pass


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


async def execute_in_workspace(
    workspace: Path,
    command: str,
    *,
    image: str,
    timeout: int | None = None,
    skills: Path | None = None,
    protected: bool = False,
) -> ExecuteResponse:
    if not isinstance(command, str) or not command.strip() or len(command) > 32768:
        raise ValueError("command must be non-empty and at most 32768 characters")
    seconds = 30 if timeout is None else timeout
    if type(seconds) is not int or not 1 <= seconds <= 60:
        raise ValueError("timeout must be between 1 and 60 seconds")
    name = f"runtime-{uuid4().hex}"
    started = time.monotonic()
    deadline = started + seconds + 15
    fields = {
        "backend": "docker",
        "phase": "start",
        "outcome": "failed",
        "command_state": "unknown",
        "attempts": 1,
        "retry_wait_ms": 0.0,
    }

    async def report(code=None, *, outcome="failed"):
        await _report(
            {
                **fields,
                "outcome": outcome,
                "code": code,
                "duration_ms": (time.monotonic() - started) * 1000,
            }
        )

    try:
        args = docker_workspace_args(
            workspace, image=image, name=name, skills=skills, protected=protected
        )
    except RuntimeWorkspaceError as exc:
        await report(exc.code)
        raise
    args += [
        "sh",
        "-c",
        'timeout -s KILL "$1" sh -c "$2" > /tmp/output 2>&1; result=$?; '
        + f'head -c {MAX_OUTPUT} /tmp/output; exit "$result"',
        "runtime",
        str(seconds),
        command,
    ]
    from runtime_service.run_control.resources import (
        finish_resource,
        register_resource,
    )

    resource = await register_resource("docker_execute")

    # Creation can fail after exec while connecting pipes: never replay this call.
    creation = asyncio.create_task(
        asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
    )
    process = None
    output = bytearray()
    total = 0

    async def consume():
        nonlocal total
        while chunk := await process.stdout.read(8192):
            total += len(chunk)
            output.extend(chunk[: max(0, MAX_OUTPUT - len(output))])
        return await process.wait()

    try:
        process = await asyncio.wait_for(
            asyncio.shield(creation), max(0, deadline - time.monotonic())
        )
        fields["phase"] = "execute"
        code = await asyncio.wait_for(consume(), max(0, deadline - time.monotonic()))
        if code == 125 and not await _docker_control(
            "info", "--format", "{{.ServerVersion}}", seconds=2
        ):
            raise RuntimeWorkspaceError("runtime.workspace.execution_outcome_unknown")
    except asyncio.CancelledError:
        confirmed = await _shield_cleanup(name, process, creation, resource=resource)
        if not confirmed:
            fields["phase"] = "cleanup"
        await report(outcome="cancelled")
        raise
    except (OSError, RuntimeWorkspaceError) as exc:
        confirmed = await _shield_cleanup(name, process, creation, resource=resource)
        stable = (
            "runtime.workspace.execution_unavailable"
            if fields["phase"] == "start"
            else "runtime.workspace.execution_outcome_unknown"
        )
        if not confirmed:
            fields["phase"] = "cleanup"
            stable = "runtime.workspace.execution_outcome_unknown"
        timed_out = isinstance(exc, TimeoutError) and process is not None and confirmed
        await report(None if timed_out else stable)
        if timed_out:
            raise
        raise RuntimeWorkspaceError(stable) from exc
    except Exception:
        await _shield_cleanup(name, process, creation, resource=resource)
        raise
    await finish_resource(resource, True)
    return ExecuteResponse(
        output=output.decode("utf-8", errors="replace"),
        exit_code=code,
        truncated=total >= MAX_OUTPUT,
    )
