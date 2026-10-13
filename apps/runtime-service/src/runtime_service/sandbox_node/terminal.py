"""Reuse byte replay/input deduplication and expiry from the native PTY manager."""

import time

from runtime_service.workspace.documents import DocumentError
from runtime_service.workspace.terminal import (
    LIFETIME_SECONDS,
    TerminalManager,
    TerminalSession,
)


class NodeTerminals(TerminalManager):
    def __init__(self, node):
        super().__init__()
        self.node = node
        self.pending = None

    def create_session(self, identifier, owner, request_id, rows, cols):
        request = self.pending
        image = request.arguments.get(
            "image",
            "runtime-agent-workspace:p5"
            if request.graph == "dearflow_agent"
            else "python:3.13-slim",
        )
        row = self.node.engine.reserve(
            request,
            "terminal",
            image,
            LIFETIME_SECONDS,
            request.arguments.get("skills"),
        )
        command = self.node.engine.argv(
            "run",
            "-it",
            "--rm",
            "--env",
            "TERM=xterm-256color",
            *self.node.engine.create_args(row),
            "timeout",
            "-s",
            "KILL",
            str(LIFETIME_SECONDS),
            "sh",
            "-i",
        )
        session = None

        def cleanup():
            with self.node.locks.hold((row["host"], row["id"])):
                try:
                    if not self.node.engine.remove(row, stop=True):
                        raise OSError("Node terminal cleanup unconfirmed")
                except DocumentError:
                    self.node.ledger.update(row["host"], row["id"], "unconfirmed")
                    raise OSError("Node terminal cleanup unconfirmed") from None

        try:
            with self.node.locks.hold((row["host"], row["id"])):
                if (
                    self.node.ledger.resource(row["host"], row["id"], row["workspace"])[
                        "status"
                    ]
                    == "removed"
                ):
                    raise DocumentError("sandbox_resource_cancelled", 409)
                session = TerminalSession(
                    identifier,
                    owner,
                    request_id,
                    rows,
                    cols,
                    node={
                        "root": self.node.storage.check(request),
                        "container": row["name"],
                        "docker_command": self.node.engine.argv(),
                        "command": command,
                        "environment": self.node.engine.environment(),
                        "cleanup": cleanup,
                    },
                )
                deadline = time.monotonic() + 12
                while time.monotonic() < deadline and session.finished is None:
                    state = self.node.engine.inspect(row)
                    if state and state["Running"]:
                        self.node.ledger.update(row["host"], row["id"], "running")
                        return session
                    time.sleep(0.05)
                raise DocumentError("terminal_start_failed", 503)
        except BaseException:
            if session is not None:
                session.close("start_failed")
            cleanup()
            raise

    def handle(self, request, operation, arguments):
        owner = (
            *request.scope,
            request.graph,
            request.execution_host + ":" + arguments.pop("owner"),
        )
        if operation == "list":
            return self.list(owner)
        if operation == "create":
            arguments.pop("skills", None)
            arguments.pop("image", None)
            with self.node.locks.hold(self.node.storage.key(request)):
                self.node.storage.prepare(request, {})
            with self.lock:
                self.pending = request
                try:
                    return self.create(owner, **arguments)
                finally:
                    self.pending = None
        session = self.get(owner, arguments.pop("terminal_id"))
        if operation not in {"read", "write", "resize", "close", "describe"}:
            from runtime_service.workspace.documents import DocumentError

            raise DocumentError("sandbox_operation_invalid")
        return getattr(session, operation)(**arguments)
