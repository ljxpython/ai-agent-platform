"""Lost responses may query an existing receipt, but may never replay a command."""

from types import SimpleNamespace

import httpx
import pytest

from runtime_service.errors import RuntimeWorkspaceError, WorkspaceExecutionNotStarted
from runtime_service.workspace import node_client
from runtime_service.workspace.documents import DocumentError
from runtime_service.workspace.scoped import thread_scope_hash
from runtime_service.workspace.target import NodeConnection, RemoteWorkspace


@pytest.fixture
def workspace(monkeypatch):
    monkeypatch.setattr(
        NodeConnection,
        "load",
        lambda: SimpleNamespace(execution_host="host", node_id="node"),
    )
    return RemoteWorkspace(
        ("tenant", "project", "thread"),
        "dearflow_agent",
        "host",
        "node",
        thread_scope_hash("tenant", "project", "thread"),
    )


@pytest.mark.parametrize("status", ["finished", "accepted", "missing", "rejected"])
def test_response_loss_queries_original_id_once(workspace, monkeypatch, status):
    requests = []

    def request(connection, method, path, *, json):
        requests.append(json)
        if len(requests) == 1:
            raise httpx.ReadTimeout("lost response")
        return {
            "result": {
                "status": status,
                "result": {"output": "once"}
                if status == "finished"
                else {"code": "sandbox_capacity_reached", "status_code": 429}
                if status == "rejected"
                else None,
            }
        }

    monkeypatch.setattr(node_client, "request", request)
    if status == "finished":
        assert node_client.call(workspace, "execute", {}, operation_id="a" * 32) == {
            "output": "once"
        }
    else:
        with pytest.raises(
            WorkspaceExecutionNotStarted
            if status == "rejected"
            else RuntimeWorkspaceError
        ):
            node_client.call(workspace, "execute", {}, operation_id="a" * 32)
    assert len(requests) == 2
    assert [item["operation"] for item in requests] == ["execute", "operation"]
    assert requests[1]["arguments"]["resource_id"] == "a" * 32


def test_recovery_query_refusal_does_not_prove_original_command_not_started(
    workspace, monkeypatch
):
    responses = iter(
        [
            httpx.ReadTimeout("lost"),
            WorkspaceExecutionNotStarted("runtime.workspace.execution_unavailable"),
        ]
    )

    def fail(*args, **kwargs):
        raise next(responses)

    monkeypatch.setattr(node_client, "request", fail)
    with pytest.raises(
        RuntimeWorkspaceError, match="execution_outcome_unknown"
    ) as caught:
        node_client.call(workspace, "execute", {})
    assert not isinstance(caught.value, WorkspaceExecutionNotStarted)


def test_safe_errors_preserve_code_without_raw_message():
    with pytest.raises(DocumentError, match="invalid_pdf_magic"):
        node_client.node_error(
            {"code": "invalid_pdf_magic", "message": "/private/secret"}, 415
        )
    with pytest.raises(RuntimeWorkspaceError, match="execution_unavailable"):
        node_client.node_error({"code": "runtime.workspace./private/secret"}, 409)


@pytest.mark.parametrize("lost_response", [False, True])
def test_terminal_capacity_preserves_http_contract(
    workspace, monkeypatch, lost_response
):
    operations = []
    error = {"code": "sandbox_capacity_reached", "status_code": 429}

    def request(connection, method, path, *, json):
        operations.append(json["operation"])
        if lost_response and len(operations) == 1:
            raise httpx.ReadTimeout("lost response")
        if json["operation"] == "operation":
            return {"result": {"status": "rejected", "result": error}}
        node_client.node_error(error, 429, operation=json["operation"])

    monkeypatch.setattr(node_client, "request", request)
    with pytest.raises(DocumentError) as caught:
        node_client.call(workspace, "terminal.create", {}, operation_id="a" * 32)
    assert caught.value.code == "terminal_session_limit"
    assert caught.value.status_code == 429
    assert operations == (
        ["terminal.create", "operation"] if lost_response else ["terminal.create"]
    )


def test_read_failure_is_unavailable_and_never_rebuilds_workspace(
    workspace, monkeypatch
):
    operations = []

    def fail(connection, method, path, *, json):
        operations.append(json["operation"])
        raise httpx.ConnectError("disconnected")

    monkeypatch.setattr(node_client, "request", fail)
    with pytest.raises(RuntimeWorkspaceError, match="execution_unavailable"):
        node_client.call(workspace, "read", {"path": "/workspace/work/a"})
    assert "prepare" not in operations and "execute" not in operations
