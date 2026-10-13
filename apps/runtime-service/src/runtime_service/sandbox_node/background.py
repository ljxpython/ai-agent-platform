"""Detached runner facts survive Node restart; logs require explicit persistence ack."""

import base64
import time
from importlib.resources import files

from runtime_service.workspace.background import MAX_LOG_BYTES, decode_snapshots
from runtime_service.workspace.documents import DocumentError


def handle_background(node, request):
    action = request.operation.split(".")[1]
    arguments = request.arguments
    resource_id = arguments["resource_id"]
    with node.locks.hold((request.execution_host, resource_id)):
        if action == "create":
            return create(node, request, arguments)
        row = node.ledger.resource(
            request.execution_host, resource_id, node.storage.key(request)
        )
        state = node.engine.inspect(row)
        if action == "inspect":
            return state
        if action == "start":
            if state and state["Status"] == "created":
                if row["status"] != "reserved" or time.time() >= row["deadline"]:
                    raise DocumentError("sandbox_resource_cancelled", 409)
                code, _ = node.engine.control("start", row["name"])
                if code:
                    raise DocumentError("sandbox_control_unavailable", 503)
                node.ledger.update(row["host"], row["id"], "running")
            return node.engine.inspect(row)
        if action == "stop":
            if state and state["Running"]:
                node.engine.control("stop", "--time=10", row["name"], seconds=15)
            return node.engine.inspect(row)
        if action == "remove":
            if arguments.get("acknowledged") is not True:
                raise DocumentError("sandbox_receipt_ack_required", 409)
            node.ledger.update(row["host"], row["id"], row["status"], acknowledged=True)
            return node.engine.remove(row)
        if action in {"output", "receipt"}:
            if state is None:
                return None
            code, data = node.engine.control(
                "logs",
                "--tail=" + ("260" if action == "output" else "1"),
                row["name"],
                limit=3 * MAX_LOG_BYTES,
            )
            if code:
                return None
            return decode_snapshots(data) if action == "output" else data
        raise DocumentError("sandbox_operation_invalid")


def create(node, request, arguments):
    command, timeout = arguments["command"], arguments["timeout"]
    if (
        not isinstance(command, str)
        or not command.strip()
        or len(command) > 32768
        or type(timeout) is not int
        or not 1 <= timeout <= 3600
    ):
        raise DocumentError("sandbox_execute_invalid")
    row = node.engine.reserve(
        request, "background", arguments["image"], timeout, arguments.get("skills")
    )
    runner = (
        files("runtime_service.workspace").joinpath("background_runner.py").read_text()
    )
    payload = base64.b64encode(runner.encode()).decode("ascii")
    loader = (
        "import base64;exec(compile(base64.b64decode("
        + repr(payload)
        + "),'<runtime-background-runner>','exec'))"
    )
    args = node.engine.create_args(row)
    code, _ = node.engine.control(
        "create",
        *args[:-1],
        "--entrypoint=python3",
        "--env",
        "RUNTIME_BACKGROUND_RECEIPT_SECRET=" + arguments["runner_secret"],
        args[-1],
        "-I",
        "-u",
        "-c",
        loader,
        command,
        str(timeout),
    )
    if code:
        raise DocumentError("runtime.workspace.execution_outcome_unknown", 409)
    return node.engine.inspect(row)
