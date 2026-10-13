"""Runtime authorization stays unchanged; PTY ownership lives on the Node."""

from runtime_service.workspace.documents import DocumentError
from runtime_service.workspace.scoped import resolve_thread_workspace
from runtime_service.workspace.target import RemoteWorkspace


def terminal_workspace(owner):
    root = resolve_thread_workspace(*owner[:4])
    if not isinstance(root, RemoteWorkspace):
        raise DocumentError("terminal_backend_invalid", 409)
    return root


class RemoteTerminalSession:
    def __init__(self, owner, identifier):
        self.workspace = terminal_workspace(owner)
        self.owner = owner[-1]
        self.id = identifier

    def call(self, operation, **arguments):
        return self.workspace.call(
            "terminal." + operation, owner=self.owner, terminal_id=self.id, **arguments
        )

    def describe(self):
        return self.call("describe")

    def read(self, offset):
        return self.call("read", offset=offset)

    def write(self, data, sequence):
        return self.call("write", data=data, sequence=sequence)

    def resize(self, rows, cols):
        return self.call("resize", rows=rows, cols=cols)

    def close(self, reason="closed"):
        return self.call("close")
