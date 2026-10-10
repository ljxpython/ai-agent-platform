"""Owned Docker containers; neither user paths nor log content are control facts."""

import asyncio
import base64
import hashlib
import hmac
import json
import os
import re
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from runtime_service.run_control.resources import wait_cleanup
from runtime_service.runtime.errors import RuntimeWorkspaceError
from runtime_service.workspace.execution import docker_workspace_args, runtime_backend

MAX_LOG_BYTES = 1024 * 1024


@dataclass(frozen=True)
class BackgroundBinding:
    workspace: Path
    image: str
    scope: tuple[str, str, str]
    graph_id: str
    skills: Path | None = None
    protected: bool = False


def host_id():
    value = os.getenv("RUNTIME_EXECUTION_HOST_ID", "")
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}", value):
        raise RuntimeWorkspaceError("background_task_not_supported")
    return value


def labels(row):
    return {
        "runtime.background.task": str(row["task_id"]),
        "runtime.background.host": row["execution_host_id"],
        "runtime.background.scope": row["binding_digest"],
    }


async def docker(*args, timeout=12, limit=65536):
    creation = asyncio.create_task(
        asyncio.create_subprocess_exec(
            "docker",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    )
    process = None
    try:
        async with asyncio.timeout(timeout):
            process = await asyncio.shield(creation)
            output = bytearray()
            while chunk := await process.stdout.read(8192):
                if len(output) + len(chunk) > limit:
                    raise ValueError("background_control_output_limit")
                output.extend(chunk)
            return await process.wait(), bytes(output)
    except (OSError, TimeoutError, ValueError) as exc:
        raise RuntimeWorkspaceError("background_task_control_unavailable") from exc
    finally:

        async def reap():
            child = process or await creation
            if child.returncode is None:
                try:
                    child.kill()
                except ProcessLookupError:
                    pass
            await child.wait()

        await wait_cleanup(asyncio.create_task(reap()))


async def inspect_task_container(row):
    if row["execution_host_id"] != host_id():
        raise RuntimeWorkspaceError("background_task_control_unavailable")
    code, data = await docker(
        "inspect", "--type=container", "--format={{json .}}", row["container_name"]
    )
    if code:
        ready, server = await docker("info", "--format={{.ServerVersion}}")
        if ready or not server.strip():
            raise RuntimeWorkspaceError("background_task_control_unavailable")
        return None
    try:
        value = json.loads(data)
        if (
            not isinstance(value, dict)
            or any(
                value["Config"]["Labels"].get(k) != v for k, v in labels(row).items()
            )
            or (row.get("container_id") and value["Id"] != row["container_id"])
        ):
            raise ValueError()
        return {"id": value["Id"], **value["State"]}
    except (ValueError, TypeError, KeyError) as exc:
        raise RuntimeWorkspaceError("background_task_control_unavailable") from exc


async def create_task_container(row, binding, command, timeout):
    if runtime_backend() != "docker":
        raise RuntimeWorkspaceError("background_task_not_supported")
    # The Docker daemon cannot resolve paths inside the Runtime container. Embed
    # the approved runner source in the container argv instead of bind mounting it.
    runner = (
        files("runtime_service.workspace")
        .joinpath("background_runner.py")
        .read_text(encoding="utf-8")
    )
    runner_payload = base64.b64encode(runner.encode()).decode("ascii")
    runner_loader = (
        "import base64;exec(compile(base64.b64decode("
        + repr(runner_payload)
        + "),'<runtime-background-runner>','exec'))"
    )
    args = docker_workspace_args(
        binding.workspace,
        image=binding.image,
        name=row["container_name"],
        skills=binding.skills,
        protected=binding.protected,
        background=True,
    )
    options = [
        "--restart=no",
        "--log-driver=local",
        "--log-opt=max-size=2m",
        "--log-opt=max-file=2",
        "--entrypoint=python3",
        "--env",
        "RUNTIME_BACKGROUND_RECEIPT_SECRET=" + row["runner_secret"],
    ]
    for key, value in labels(row).items():
        options += ["--label", f"{key}={value}"]
    args = [
        *args[:-1],
        *options,
        args[-1],
        "-I",
        "-u",
        "-c",
        runner_loader,
        command,
        str(timeout),
    ]
    await docker(*args[1:])
    state = await inspect_task_container(row)
    if state is None:
        raise RuntimeWorkspaceError("background_task_control_unavailable")
    return state


async def start_task_container(row):
    state = await inspect_task_container(row)
    if state is not None and state["Status"] == "created":
        await docker("start", state["id"])
        state = await inspect_task_container(row)
    return state


async def stop_task_container(row):
    state = await inspect_task_container(row)
    if state is not None and state["Running"]:
        await docker("stop", "--time=10", state["id"], timeout=15)
        state = await inspect_task_container(row)
        if state is not None and state["Running"]:
            await docker("kill", state["id"])
            state = await inspect_task_container(row)
    return state


async def remove_task_container(row):
    state = await inspect_task_container(row)
    if state is None:
        return True
    if state["Running"]:
        return False
    code, _ = await docker("rm", state["id"])
    return code == 0 and await inspect_task_container(row) is None


def decode_snapshots(data):
    current, parts, result = None, [], None
    for line in data.splitlines():
        try:
            value = json.loads(line)
            if (
                type(value["snapshot"]) is not int
                or type(value["part"]) is not int
                or type(value["parts"]) is not int
                or not 1 <= value["parts"] <= 128
                or type(value["omitted"]) is not int
                or value["omitted"] < 0
                or type(value["truncated"]) is not bool
            ):
                raise ValueError()
            if value["part"] == 0:
                current, parts = value["snapshot"], []
            if current != value["snapshot"] or value["part"] != len(parts):
                raise ValueError()
            piece = base64.b64decode(value["data"], validate=True)
            if len(piece) > 8192:
                raise ValueError()
            parts.append(piece)
            if len(parts) == value["parts"]:
                text = b"".join(parts)
                if len(text) > MAX_LOG_BYTES:
                    raise ValueError()
                result = (text.decode("utf-8"), value["omitted"], value["truncated"])
        except (ValueError, KeyError, TypeError, UnicodeError):
            current, parts = None, []
    return result


async def read_task_output(row):
    state = await inspect_task_container(row)
    if state is None:
        return None
    code, data = await docker(
        "logs", "--tail=260", state["id"], limit=3 * MAX_LOG_BYTES
    )
    return None if code else decode_snapshots(data)


async def read_task_receipt(row):
    code, data = await docker("logs", "--tail=1", row["container_id"])
    if code:
        return None
    try:
        value = json.loads(data)
        receipt = value["receipt"]
        canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":"))
        signature = hmac.new(
            row["runner_secret"].encode(), canonical.encode(), hashlib.sha256
        ).hexdigest()
        if (
            set(receipt) != {"exit_code", "outcome"}
            or type(receipt["exit_code"]) is not int
            or type(receipt["outcome"]) is not int
            or not hmac.compare_digest(value["signature"], signature)
        ):
            return None
        return receipt
    except (KeyError, TypeError, ValueError):
        return None
