"""Read-only caller preflight. Never creates workspaces or containers."""

import json

from runtime_service.workspace.node_client import request
from runtime_service.workspace.target import NodeConnection


def main():
    connection = NodeConnection.load()
    result = request(connection, "GET", "/v1/ready")
    if (
        not result.get("ready")
        or result.get("version") != 1
        or result.get("node_id") != connection.node_id
    ):
        raise SystemExit("Sandbox Node identity/readiness mismatch")
    print(json.dumps({"ready": True, "node_id": connection.node_id, "version": 1}))


if __name__ == "__main__":
    main()
