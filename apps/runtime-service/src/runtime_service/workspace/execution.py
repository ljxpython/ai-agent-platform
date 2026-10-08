"""Bounded Docker execution shared by service-specific filesystem backends."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from uuid import uuid4

from deepagents.backends.protocol import ExecuteResponse

from runtime_service.runtime.errors import RuntimeWorkspaceError

MAX_OUTPUT = 128 * 1024
logger = logging.getLogger(__name__)


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
) -> list[str]:
    """Share the same mount and resource policy between commands and terminals."""
    if not workspace.is_dir() or workspace.is_symlink():
        raise RuntimeWorkspaceError("runtime.workspace.unavailable")
    if not image or image.startswith("-"):
        raise RuntimeWorkspaceError("runtime.workspace.image_invalid")
    args = [
        "docker",
        "run",
        "--rm",
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
    args = docker_workspace_args(
        workspace, image=image, name=name, skills=skills, protected=protected
    )
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
        wait_cleanup,
    )

    resource = await register_resource("docker_execute")
    cancelled = None
    spawn = asyncio.create_task(
        asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
    )
    try:
        process = await asyncio.shield(spawn)
    except asyncio.CancelledError as exc:
        cancelled = exc
        try:
            process = await wait_cleanup(spawn)
        except OSError:
            await finish_resource(resource, True)
            raise cancelled from None
    except OSError as exc:
        await finish_resource(resource, True)
        raise RuntimeWorkspaceError("runtime.workspace.execution_unavailable") from exc
    output = bytearray()
    total = 0

    async def consume():
        nonlocal total
        while chunk := await process.stdout.read(8192):
            total += len(chunk)
            output.extend(chunk[: max(0, MAX_OUTPUT - len(output))])
        return await process.wait()

    async def cleanup():
        confirmed = False
        try:
            remover = await asyncio.create_subprocess_exec(
                "docker",
                "rm",
                "-f",
                name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                await asyncio.wait_for(remover.wait(), 10)
                if remover.returncode:
                    logger.warning(
                        "execution cleanup requires inspection container=%s", name
                    )
                else:
                    confirmed = True
            except TimeoutError:
                remover.kill()
                await remover.wait()
                logger.error("execution cleanup timed out container=%s", name)
        except OSError:
            logger.warning("Execution cleanup unavailable container=%s", name)
        finally:
            if process.returncode is None:
                process.kill()
            await process.wait()
            await finish_resource(resource, confirmed)

    try:
        if cancelled is not None:
            raise cancelled
        code = await asyncio.wait_for(consume(), seconds + 15)
    except BaseException:
        task = asyncio.create_task(cleanup())
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            await wait_cleanup(task)
        raise
    await finish_resource(resource, True)
    return ExecuteResponse(
        output=output.decode("utf-8", errors="replace"),
        exit_code=code,
        truncated=total >= MAX_OUTPUT,
    )
