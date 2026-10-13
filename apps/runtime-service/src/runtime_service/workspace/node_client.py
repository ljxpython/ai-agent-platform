"""mTLS caller with bounded messages and no transport replay of side effects."""

import asyncio
import atexit
import base64
import re
import threading
from dataclasses import asdict, is_dataclass
from uuid import uuid4
from weakref import WeakSet

import httpx
from pydantic import BaseModel

from runtime_service.errors import (
    WORKSPACE_ERROR_CODES,
    RuntimeWorkspaceError,
    WorkspaceExecutionNotStarted,
)
from runtime_service.workspace.documents import DocumentError
from runtime_service.workspace.target import NodeConnection, RemoteWorkspace

MAX_MESSAGE = 32 * 1024 * 1024
_thread_client = threading.local()
_clients = WeakSet()
_clients_lock = threading.Lock()


def close_clients():
    with _clients_lock:
        for client in tuple(_clients):
            client.close()
        _clients.clear()


atexit.register(close_clients)


def _transport_client(connection):
    key = (connection.url, connection.tls)
    with _clients_lock:
        client = getattr(_thread_client, "client", None)
        if client is not None and not client.is_closed and _thread_client.key == key:
            return client
        if client is not None:
            client.close()
        client = httpx.Client(
            verify=connection.tls,
            trust_env=False,
            follow_redirects=False,
            limits=httpx.Limits(max_connections=1, max_keepalive_connections=1),
        )
        _thread_client.key, _thread_client.client = key, client
        _clients.add(client)
        return client


NOT_STARTED_CODES = frozenset(
    {
        "sandbox_capacity_reached",
        "sandbox_disk_capacity_reached",
        "sandbox_resource_cancelled",
        "sandbox_not_ready",
        "sandbox_execute_invalid",
        "runtime.workspace.image_invalid",
    }
)


def node_error(error, status_code, *, operation=None):
    code = error.get("code") if isinstance(error, dict) else None
    if operation == "terminal.create" and code == "sandbox_capacity_reached":
        raise DocumentError("terminal_session_limit", 429)
    if code in NOT_STARTED_CODES:
        raise WorkspaceExecutionNotStarted(
            "runtime.workspace.image_invalid"
            if code == "runtime.workspace.image_invalid"
            else "runtime.workspace.execution_unavailable"
        )
    if code in WORKSPACE_ERROR_CODES:
        raise RuntimeWorkspaceError(code)
    if not isinstance(code, str) or not re.fullmatch(
        r"(?:sandbox|workspace|document|image|artifact|terminal|skill|invalid|file|encrypted|damaged|unsupported|archive|zip|pdf|mime)_[a-z0-9_]{1,80}",
        code,
    ):
        raise RuntimeWorkspaceError("runtime.workspace.execution_unavailable")
    raise DocumentError(code, status_code)


def encode(value):
    if isinstance(value, bytes):
        return {"$bytes": base64.b64encode(value).decode("ascii")}
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [encode(item) for item in value]
    return value


def decode(value):
    if isinstance(value, dict):
        if set(value) == {"$bytes"}:
            return base64.b64decode(value["$bytes"], validate=True)
        return {key: decode(item) for key, item in value.items()}
    if isinstance(value, list):
        return [decode(item) for item in value]
    return value


def request(connection, method, path, **kwargs):
    operation = kwargs.get("json", {}).get("operation")
    seconds = 5 if operation in {"operation", "discover"} or path == "/v1/ready" else 80
    client = _transport_client(connection)
    with client.stream(
        method,
        connection.url + path,
        timeout=httpx.Timeout(seconds, connect=5),
        headers={
            "Authorization": "Bearer " + connection.token,
            "X-Execution-Host": connection.execution_host,
            "X-Sandbox-Node": connection.node_id,
        },
        **kwargs,
    ) as response:
        data = bytearray()
        for chunk in response.iter_bytes():
            if len(data) + len(chunk) > MAX_MESSAGE:
                raise ValueError("node response too large")
            data.extend(chunk)
        if response.is_redirect:
            raise httpx.TransportError("node unavailable")
        import json

        result = decode(json.loads(data))
        if not isinstance(result, dict):
            raise ValueError("invalid Node response")
        if response.status_code >= 400:
            node_error(result.get("error"), response.status_code, operation=operation)
        return result


def call(workspace: RemoteWorkspace, operation, arguments, *, operation_id=None):
    connection = NodeConnection.load()
    if (connection.execution_host, connection.node_id) != (
        workspace.execution_host,
        workspace.node_id,
    ):
        raise RuntimeWorkspaceError("runtime.workspace.unavailable")
    payload = {
        "version": 1,
        "node_id": workspace.node_id,
        "execution_host": workspace.execution_host,
        "scope": workspace.scope,
        "graph": workspace.graph,
        "workspace_id": workspace.workspace_id,
        "operation": operation,
        "operation_id": operation_id or uuid4().hex,
        "arguments": encode(arguments),
    }
    try:
        return request(connection, "POST", "/v1/rpc", json=payload)["result"]
    except (DocumentError, RuntimeWorkspaceError):
        raise
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        if operation != "operation":
            lookup = {
                **payload,
                "operation": "operation",
                "operation_id": uuid4().hex,
                "arguments": {"resource_id": payload["operation_id"]},
            }
            found = None
            try:
                found = request(connection, "POST", "/v1/rpc", json=lookup)["result"]
            except Exception:
                pass
            if isinstance(found, dict) and found.get("status") == "finished":
                return found["result"]
            if isinstance(found, dict) and found.get("status") == "rejected":
                node_error(
                    found["result"], found["result"]["status_code"], operation=operation
                )
        # Recovery queries only; never resubmit a side effect after transport loss.
        from runtime_service.sandbox_node.protocol import READ_OPERATIONS

        raise RuntimeWorkspaceError(
            "runtime.workspace.execution_unavailable"
            if operation in READ_OPERATIONS
            else "runtime.workspace.execution_outcome_unknown"
        ) from exc


async def execute(workspace, command, *, image, timeout, skills=None, protected=False):
    from deepagents.backends.protocol import ExecuteResponse

    from runtime_service.run_control.resources import (
        finish_resource,
        register_resource,
        wait_cleanup,
    )

    operation_id = uuid4().hex
    resource = await register_resource(
        "docker_execute",
        node_id=workspace.node_id,
        operation_id=operation_id,
        workspace=workspace,
    )
    arguments = {
        "command": command,
        "image": image,
        "timeout": timeout,
        "skills": getattr(skills, "digest", None),
        "protected": protected,
    }
    task = asyncio.create_task(
        asyncio.to_thread(
            call, workspace, "execute", arguments, operation_id=operation_id
        )
    )
    try:
        result = await asyncio.shield(task)
        await finish_resource(resource, result.get("cleanup_confirmed", False))
        return ExecuteResponse(
            **{key: result[key] for key in ("output", "exit_code", "truncated")}
        )
    except asyncio.CancelledError:

        async def cancel():
            try:
                result = await asyncio.to_thread(
                    call, workspace, "cancel", {"resource_id": operation_id}
                )
                confirmed = result["confirmed"]
            except Exception:
                confirmed = False
            await finish_resource(resource, confirmed)

        await wait_cleanup(asyncio.create_task(cancel()))
        task.add_done_callback(
            lambda done: done.exception() if not done.cancelled() else None
        )
        raise
    except WorkspaceExecutionNotStarted:
        await finish_resource(resource, True)
        raise
    except BaseException:
        await finish_resource(resource, False)
        raise
