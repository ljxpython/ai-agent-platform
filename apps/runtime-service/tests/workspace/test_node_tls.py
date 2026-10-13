"""Actual TLS handshake, caller binding and owned Docker execution on a local Node."""

import importlib.util
import os
import socket
import ssl
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from e2e.test_background_tasks import (
    BACKGROUND_STACK,
    background_thread,
    first_task,
    task_when,
)
from e2e.test_run_reliability import run_body, terminal
from services.dearflow_agent.test_tool_error_platform import (
    facts,
    wait_for,
)
from services.dearflow_agent.test_tool_error_platform import (
    request as platform_request,
)
from services.dearflow_agent.test_tool_error_platform import stack as disposable_stack

from runtime_service.workspace.node_client import call, request
from runtime_service.workspace.scoped import thread_scope_hash
from runtime_service.workspace.target import NodeConnection, RemoteWorkspace

stack = disposable_stack


@pytest.fixture(scope="module")
def tls_node(tmp_path_factory):
    monkeypatch = pytest.MonkeyPatch()
    tmp_path = tmp_path_factory.mktemp("tls-node")
    probe = subprocess.run(
        ["docker", "info", "--format={{.ServerVersion}}"],
        capture_output=True,
        timeout=15,
    )
    if probe.returncode or not probe.stdout.strip():
        pytest.skip("local Docker daemon required")
    root = tmp_path.resolve()
    from uuid import uuid4

    node_id = "tls-test-" + uuid4().hex
    script = (
        Path(__file__).resolve().parents[2] / "scripts/sandbox_node_certificates.py"
    )
    spec = importlib.util.spec_from_file_location("test_certificates", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    secrets = root / "secrets"
    module.generate(secrets, "127.0.0.1", "tls-test-host", "127.0.0.1/32")
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.close()
    node_env = {
        "PATH": os.environ["PATH"],
        "SANDBOX_NODE_ID": node_id,
        "SANDBOX_LISTEN_HOST": "127.0.0.1",
        "SANDBOX_LISTEN_PORT": str(port),
        "SANDBOX_WORKSPACE_ROOT": str(root / "workspaces"),
        "SANDBOX_STATE_ROOT": str(root / "state"),
        "SANDBOX_AUTH_FILE": str(secrets / "callers.json"),
        "SANDBOX_TLS_CERT_FILE": str(secrets / "server.pem"),
        "SANDBOX_TLS_KEY_FILE": str(secrets / "server-key.pem"),
        "SANDBOX_TLS_CLIENT_CA_FILE": str(secrets / "ca.pem"),
        "SANDBOX_ALLOWED_IMAGES": "python:3.13-slim,runtime-agent-workspace:p5,"
        + os.getenv("OFFICE_TEST_IMAGE", "runtime-agent-workspace:p5"),
        "SANDBOX_MIN_FREE_DISK_BYTES": "0",
    }
    log = (root / "node.log").open("w")
    process = subprocess.Popen(
        [sys.executable, "-m", "runtime_service.sandbox_node"],
        env=node_env,
        stdout=log,
        stderr=log,
    )
    values = {
        "RUNTIME_SANDBOX_NODE_URL": f"https://127.0.0.1:{port}",
        "RUNTIME_SANDBOX_NODE_ID": node_id,
        "RUNTIME_EXECUTION_HOST_ID": "tls-test-host",
        "RUNTIME_SANDBOX_NODE_AUTH_FILE": str(secrets / "caller-token"),
        "RUNTIME_SANDBOX_NODE_CA_FILE": str(secrets / "ca.pem"),
        "RUNTIME_SANDBOX_NODE_CLIENT_CERT_FILE": str(secrets / "client.pem"),
        "RUNTIME_SANDBOX_NODE_CLIENT_KEY_FILE": str(secrets / "client-key.pem"),
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    connection = NodeConnection.load()
    control = {"process": process, "env": node_env, "log": log}
    try:
        deadline = time.monotonic() + 180
        last_error = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                pytest.fail((root / "node.log").read_text()[-3000:])
            try:
                if request(connection, "GET", "/v1/ready")["ready"]:
                    break
            except (httpx.HTTPError, ValueError) as exc:
                last_error = repr(exc)
                time.sleep(0.2)
        else:
            pytest.fail(
                str(last_error) + "\n" + (root / "node.log").read_text()[-3000:]
            )
        yield connection, root, control
    finally:
        process = control["process"]
        process.terminate()
        try:
            process.wait(timeout=100)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        log.close()
        owned = subprocess.run(
            ["docker", "ps", "-aq", "--filter=label=runtime.sandbox.node=" + node_id],
            capture_output=True,
            timeout=15,
        )
        if owned.stdout.strip():
            subprocess.run(
                ["docker", "rm", "-f", *owned.stdout.decode().split()],
                check=True,
                capture_output=True,
                timeout=30,
            )
        monkeypatch.undo()


def test_actual_mtls_and_node_execute(tls_node):
    connection, _, _ = tls_node
    with httpx.Client(
        verify=ssl.create_default_context(
            cafile=os.environ["RUNTIME_SANDBOX_NODE_CA_FILE"]
        ),
        trust_env=False,
        timeout=5,
    ) as client:
        with pytest.raises(httpx.HTTPError):
            client.get(connection.url + "/v1/ready")
    workspace = RemoteWorkspace(
        ("tenant", "project", "thread"),
        "dearflow_agent",
        connection.execution_host,
        connection.node_id,
        thread_scope_hash("tenant", "project", "thread"),
    )
    call(workspace, "prepare", {})
    operation_id = "a" * 32
    arguments = {
        "command": "printf once >> counter; cat counter",
        "image": "python:3.13-slim",
        "timeout": 5,
    }
    result = call(workspace, "execute", arguments, operation_id=operation_id)
    assert (
        result["output"] == "once"
        and result["exit_code"] == 0
        and result["cleanup_confirmed"]
    )
    assert call(workspace, "execute", arguments, operation_id=operation_id) == result
    assert (
        call(workspace, "read", {"path": "/workspace/work/counter"})["file_data"][
            "content"
        ]
        == "once"
    )
    assert call(workspace, "discover", {})[0]["status"] == "removed"


def test_wrong_token_node_and_execution_host_rejected(tls_node):
    connection, _, _ = tls_node
    from dataclasses import replace

    from runtime_service.workspace.documents import DocumentError

    for changed in (
        replace(connection, token="x" * 64),
        replace(connection, node_id="other-node"),
        replace(connection, execution_host="other-host"),
    ):
        with pytest.raises(DocumentError, match="sandbox_caller_denied"):
            request(changed, "GET", "/v1/ready")


def test_actual_tls_client_reuses_connection_and_closes(tls_node, monkeypatch):
    from contextlib import contextmanager

    from runtime_service.workspace import node_client

    streams = []
    original = httpx.Client.stream

    @contextmanager
    def observed(client, *args, **kwargs):
        with original(client, *args, **kwargs) as response:
            streams.append(response.extensions["network_stream"])
            yield response

    monkeypatch.setattr(httpx.Client, "stream", observed)
    node_client.close_clients()
    try:
        for _ in range(2):
            assert request(NodeConnection.load(), "GET", "/v1/ready")["ready"]
        assert streams[0] is streams[1]
        node_client.close_clients()
        assert request(NodeConnection.load(), "GET", "/v1/ready")["ready"]
        assert streams[-1] is not streams[0]
    finally:
        node_client.close_clients()


@pytest.mark.parametrize(
    "case", ["untrusted-client", "expired-client", "wrong-san", "untrusted-server"]
)
def test_actual_tls_rejects_invalid_trust(tls_node, tmp_path, case):
    from dataclasses import replace
    from datetime import UTC, datetime, timedelta

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

    connection, root, _ = tls_node
    ca_file = root / "secrets/ca.pem"
    if case in {"untrusted-client", "expired-client"}:
        ca = x509.load_pem_x509_certificate(ca_file.read_bytes())
        issuer = serialization.load_pem_private_key(
            (root / "secrets/ca-key.pem").read_bytes(), password=None
        )
        if case == "untrusted-client":
            issuer = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        now = datetime.now(UTC)
        certificate = (
            x509.CertificateBuilder()
            .subject_name(
                x509.Name(
                    [x509.NameAttribute(NameOID.COMMON_NAME, connection.execution_host)]
                )
            )
            .issuer_name(ca.subject)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=2))
            .not_valid_after(
                now - timedelta(days=1)
                if case == "expired-client"
                else now + timedelta(days=1)
            )
            .add_extension(
                x509.BasicConstraints(ca=False, path_length=None), critical=True
            )
            .add_extension(
                x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]), critical=False
            )
            .sign(issuer, hashes.SHA256())
        )
        certificate_file, key_file = (
            tmp_path / "client.pem",
            tmp_path / "client-key.pem",
        )
        certificate_file.write_bytes(
            certificate.public_bytes(serialization.Encoding.PEM)
        )
        key_file.write_bytes(
            key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        key_file.chmod(0o600)
        tls = ssl.create_default_context(cafile=str(ca_file))
        tls.load_cert_chain(str(certificate_file), str(key_file))
        changed = replace(connection, tls=tls)
    elif case == "wrong-san":
        changed = replace(
            connection, url=connection.url.replace("127.0.0.1", "localhost")
        )
    else:
        tls = ssl.create_default_context()
        tls.load_cert_chain(
            str(root / "secrets/client.pem"), str(root / "secrets/client-key.pem")
        )
        changed = replace(connection, tls=tls)
    with pytest.raises(httpx.TransportError):
        request(changed, "GET", "/v1/ready")
    assert request(connection, "GET", "/v1/ready")["ready"]


def bound(connection, thread):
    scope = ("tenant", "project", thread)
    root = RemoteWorkspace(
        scope,
        "dearflow_agent",
        connection.execution_host,
        connection.node_id,
        thread_scope_hash(*scope),
    )
    call(root, "prepare", {})
    return root


def test_real_node_terminal_input_replay_resize_and_close(tls_node):
    import base64

    root = bound(tls_node[0], "terminal")
    image = os.getenv("OFFICE_TEST_IMAGE", "runtime-agent-workspace:p5")
    created = root.call(
        "terminal.create",
        owner="owner",
        request_id="terminal-once",
        rows=24,
        cols=80,
        image=image,
    )
    identifier = created["terminal_id"]
    assert (
        root.call(
            "terminal.create",
            owner="owner",
            request_id="terminal-once",
            rows=24,
            cols=80,
            image=image,
        )["terminal_id"]
        == identifier
    )
    args = {
        "owner": "owner",
        "terminal_id": identifier,
        "data": b"printf terminal >> proof; cat proof\n",
        "sequence": 0,
    }
    try:
        running_image = subprocess.run(
            [
                "docker",
                "ps",
                "--filter=label=runtime.sandbox.node=" + root.node_id,
                "--format={{.Image}}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert image in running_image.stdout.splitlines()
        accepted = call(root, "terminal.write", args)
        assert call(root, "terminal.write", args) == accepted
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            output = root.call(
                "terminal.read", owner="owner", terminal_id=identifier, offset=0
            )
            if b"terminal" in base64.b64decode(output["data_base64"]):
                break
            time.sleep(0.1)
        assert (
            root.call(
                "terminal.resize",
                owner="owner",
                terminal_id=identifier,
                rows=30,
                cols=100,
            )["cols"]
            == 100
        )
        from runtime_service.workspace.documents import DocumentError

        with pytest.raises(DocumentError, match="terminal_not_found"):
            root.call("terminal.describe", owner="other", terminal_id=identifier)
    finally:
        root.call("terminal.close", owner="owner", terminal_id=identifier)
    assert (
        root.call("read", path="/workspace/work/proof")["file_data"]["content"]
        == "terminal"
    )
    assert root.call("discover")[0]["status"] == "removed"


def test_real_background_receipt_and_log_ack(tls_node):
    from uuid import uuid4

    from runtime_service.workspace.background import verify_receipt
    from runtime_service.workspace.documents import DocumentError

    root = bound(tls_node[0], "background")
    identifier, secret = uuid4().hex, "a" * 64
    args = {
        "resource_id": identifier,
        "command": "printf background",
        "image": "python:3.13-slim",
        "timeout": 5,
        "runner_secret": secret,
    }
    call(root, "background.create", args, operation_id=identifier)
    root.call("background.start", resource_id=identifier)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        state = root.call("background.inspect", resource_id=identifier)
        if state and not state["Running"]:
            break
        time.sleep(0.1)
    assert state["ExitCode"] == 0
    receipt = root.call("background.receipt", resource_id=identifier)
    assert verify_receipt(receipt, {"runner_secret": secret})["exit_code"] == 0
    assert root.call("background.output", resource_id=identifier)[0] == "background"
    with pytest.raises(DocumentError, match="sandbox_receipt_ack_required"):
        root.call("background.remove", resource_id=identifier, acknowledged=False)
    assert root.call("background.inspect", resource_id=identifier) is not None
    assert root.call("background.remove", resource_id=identifier, acknowledged=True)


@pytest.mark.parametrize(
    "command,timeout,expected",
    [
        ("printf pg-once >> proof", 30, "succeeded"),
        ("exit 7", 30, "failed"),
        ("sleep 10", 1, "timed_out"),
        ("sleep 30", 30, "cancelled"),
    ],
)
def test_real_node_pg_background_reconciler(
    tls_node, monkeypatch, tmp_path, command, timeout, expected
):
    import asyncio
    from uuid import uuid4

    import psycopg
    from psycopg import sql
    from psycopg.conninfo import make_conninfo

    from runtime_service.background_tasks import repository, service
    from runtime_service.db import connect, upgrade
    from runtime_service.workspace.background import (
        BackgroundBinding,
        remove_task_container,
        stop_task_container,
    )

    dsn = os.getenv("BACKGROUND_TEST_DSN")
    if not dsn:
        pytest.skip("BACKGROUND_TEST_DSN must point to this Worktree database")
    schema = "sandbox_background_" + uuid4().hex
    with psycopg.connect(dsn) as db:
        db.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    monkeypatch.setenv(
        "DATABASE_URI", make_conninfo(dsn, options=f"-c search_path={schema}")
    )
    monkeypatch.setenv("RUNTIME_EXECUTION_HOST_ID", tls_node[0].execution_host)
    monkeypatch.setenv("RUNTIME_BACKGROUND_LOG_ROOT", str(tmp_path / "logs"))
    monkeypatch.setenv("RUNTIME_BACKEND", "docker")
    monkeypatch.setenv("RUNTIME_SANDBOX_TARGET", "remote")
    monkeypatch.setenv("RUNTIME_BACKGROUND_TASKS_ENABLED", "1")
    monkeypatch.setattr(
        service, "source_failed", lambda row: asyncio.sleep(0, result=False)
    )
    root = bound(tls_node[0], "pg-background-" + uuid4().hex)
    identity = {
        "tenant_id": "tenant",
        "project_id": "project",
        "owner_id": "owner",
        "graph_id": "dearflow_agent",
        "assistant_id": "dearflow_agent",
        "thread_id": root.scope[2],
        "origin_run_id": str(uuid4()),
        "checkpoint_ns": "",
        "tool_call_id": "once",
    }
    binding = BackgroundBinding(
        root, "python:3.13-slim", root.scope, root.graph, protected=True
    )

    async def verify():
        row = await service.start_task(identity, binding, command, timeout)
        try:
            assert (await service.start_task(identity, binding, command, timeout))[
                "task_id"
            ] == row["task_id"]
            if expected == "cancelled":
                repository.request_cancel(identity, row["task_id"])
            deadline = time.monotonic() + 40
            while time.monotonic() < deadline:
                with connect() as db:
                    db.execute(
                        "UPDATE runtime_background_tasks SET lease_until=NULL,next_check_at=now() WHERE task_id=%s",
                        (row["task_id"],),
                    )
                await service.reconcile_due(row["task_id"])
                actual = repository.read_task(identity, row["task_id"])
                if actual["cleanup_state"] == "confirmed":
                    break
                await asyncio.sleep(0.1)
            assert (
                actual["status"] == expected and actual["cleanup_state"] == "confirmed"
            )
            assert actual["sandbox_node_id"] == root.node_id
            if expected == "succeeded":
                assert (
                    root.call("read", path="/workspace/work/proof")["file_data"][
                        "content"
                    ]
                    == "pg-once"
                )
        finally:
            await stop_task_container(row)
            await remove_task_container(row)

    try:
        upgrade()
        asyncio.run(verify())
    finally:
        with psycopg.connect(dsn) as db:
            db.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


@pytest.mark.parametrize(
    "stack",
    [
        {
            **BACKGROUND_STACK,
            "startup_timeout": 360,
            "env": {
                **BACKGROUND_STACK["env"],
                "RUNTIME_SANDBOX_TARGET": "remote",
                "RUNTIME_EXECUTION_HOST_ID": "tls-test-host",
            },
        }
    ],
    indirect=True,
)
def test_real_node_background_api_worker_completion_and_stop(tls_node, stack):
    import json

    client, spec, env, processes, start, stop, tmp_path = stack
    thread = background_thread(client)
    source = platform_request(
        client,
        "POST",
        f"/threads/{thread}/runs",
        json=run_body(spec, "background-short"),
    )
    assert (
        terminal(client, thread, source["run_id"], timeout=360)["status"] == "success"
    )
    row = first_task(client, thread)
    completed = task_when(
        client,
        thread,
        row["task_id"],
        lambda item: item["delivery"]["state"] == "accepted",
    )
    assert (
        completed["status"] == "succeeded" and completed["cleanup_state"] == "confirmed"
    )
    assert (
        terminal(client, thread, completed["delivery"]["run_id"], timeout=360)["status"]
        == "success"
    )
    output = platform_request(
        client, "GET", f"/threads/{thread}/background-tasks/{row['task_id']}/output"
    )
    assert output["available"] and output["text"] == "BACKGROUND_DONE"
    assert sum(item["event"] == "completion-model" for item in facts(env)) == 1

    thread = background_thread(client)
    source = platform_request(
        client,
        "POST",
        f"/threads/{thread}/runs",
        json=run_body(spec, "background-long"),
    )
    assert (
        terminal(client, thread, source["run_id"], timeout=360)["status"] == "success"
    )
    row = first_task(client, thread)
    assert row["status"] == "running"
    receipt = platform_request(
        client,
        "POST",
        f"/threads/{thread}/cancel",
        json={},
        headers={"Idempotency-Key": "remote-background-stop"},
    )

    def confirmed():
        current = platform_request(
            client, "GET", f"/threads/{thread}/stop-requests/{receipt['stop_id']}"
        )
        return (
            current
            if current["phase"] in {"stopped", "no_active_run"}
            and current["resource_cleanup"] == "confirmed"
            else None
        )

    stopped = wait_for(confirmed, timeout=360)
    assert stopped["report"]["background_tasks"]["cleanup_confirmed_count"] == 1
    cancelled = task_when(
        client,
        thread,
        row["task_id"],
        lambda item: item["cleanup_state"] == "confirmed",
    )
    assert (
        cancelled["status"] == "cancelled"
        and cancelled["delivery"]["state"] == "suppressed"
    )
    assert sum(item["event"] == "completion-model" for item in facts(env)) == 1
    (tmp_path / "remote-background-chain.json").write_text(
        json.dumps(
            {
                "mode": "remote-loopback",
                "completed": completed,
                "cancelled": cancelled,
                "stop": stopped,
            },
            indent=2,
        )
    )


def test_real_node_timeout_bounded_output_and_no_secrets(tls_node):
    root = bound(tls_node[0], "limits")
    output = root.call(
        "execute",
        command="yes large | head -c 200000",
        image="python:3.13-slim",
        timeout=5,
    )
    assert output["truncated"] and len(output["output"].encode()) <= 128 * 1024
    result = root.call(
        "execute", command="sleep 10", image="python:3.13-slim", timeout=1
    )
    assert result["exit_code"] in {124, 137} and result["cleanup_confirmed"]
    env = root.call(
        "execute",
        command="env; id -u; test ! -e /var/run/docker.sock",
        image="python:3.13-slim",
        timeout=5,
    )
    assert (
        env["exit_code"] == 0
        and "SANDBOX_NODE" not in env["output"]
        and "RUNTIME_SANDBOX" not in env["output"]
    )


def test_node_capacity_is_hard_and_rejection_has_zero_side_effects(tls_node):
    from runtime_service.errors import WorkspaceExecutionNotStarted

    root = bound(tls_node[0], "capacity")
    terminals = []
    try:
        for index in range(2):
            terminals.append(
                root.call(
                    "terminal.create",
                    owner="capacity",
                    request_id=str(index),
                    rows=24,
                    cols=80,
                )["terminal_id"]
            )
        with pytest.raises(WorkspaceExecutionNotStarted):
            root.call(
                "execute",
                command="touch forbidden",
                image="python:3.13-slim",
                timeout=5,
            )
        assert (
            root.call("read", path="/workspace/work/forbidden")["error"]
            == "file_not_found"
        )
        assert request(tls_node[0], "GET", "/v1/ready")["ready"]
    finally:
        for identifier in terminals:
            root.call("terminal.close", owner="capacity", terminal_id=identifier)
    assert (
        root.call(
            "execute", command="printf recovered", image="python:3.13-slim", timeout=5
        )["output"]
        == "recovered"
    )


@pytest.mark.parametrize("kind", ["docx", "pptx"])
def test_remote_office_uses_real_node_reader_and_continuation(tls_node, kind):
    import asyncio
    import hashlib

    from workspace.test_office_documents import docx_bytes, pptx_bytes

    from runtime_service.tools.documents import build_document_tools
    from runtime_service.workspace.document_reader import DOCX_MIME, PPTX_MIME
    from runtime_service.workspace.documents import DocumentWorkspace

    root = bound(tls_node[0], "office-" + kind)
    text = "真实远端沙箱 " + "OfficeReader125中文" * 1500
    raw = docx_bytes(text) if kind == "docx" else pptx_bytes(text, "")
    ref = DocumentWorkspace(root).put(
        raw, hashlib.sha256(raw).hexdigest(), DOCX_MIME if kind == "docx" else PPTX_MIME
    )
    image = os.getenv("OFFICE_TEST_IMAGE")
    if not image:
        pytest.skip("OFFICE_TEST_IMAGE must identify a current reader image")
    tool = build_document_tools(root, execution_image=image)[0]
    tool.handle_tool_error = False
    first = asyncio.run(tool.ainvoke({"file_path": ref["path"]}))
    assert isinstance(first, dict), first
    assert "OfficeReader125" in first["text"] and first["next_read"]
    following = asyncio.run(tool.ainvoke(first["next_read"]))
    assert isinstance(following, dict) and following["chunks"][0]["char_offset"] > 0
    assert DocumentWorkspace(root).read(ref["path"])[0] == raw


def test_real_remote_binary_image_html_archive_and_fork(tls_node):
    import hashlib
    import io
    import zipfile

    from PIL import Image

    from runtime_service.workspace.artifact_refs import ArtifactWorkspace
    from runtime_service.workspace.browser import WorkspaceBrowser
    from runtime_service.workspace.image_io import ImageWorkspace

    root = bound(tls_node[0], "file-contracts")
    data = b"\0\x01\xffbinary"
    assert (
        root.call("upload_files", files=[("/workspace/work/binary", data)])[0]["error"]
        is None
    )
    assert (
        root.call("download_files", paths=["/workspace/work/binary"])[0]["content"]
        == data
    )
    output = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(output, format="PNG")
    raw = output.getvalue()
    image = ImageWorkspace(root).put_upload(raw, hashlib.sha256(raw).hexdigest())
    assert ImageWorkspace(root).read_asset(image["path"])[0] == raw
    root.call(
        "write",
        path="/workspace/work/site.html",
        content="<html><body>sandbox proof</body></html>",
    )
    artifact = ArtifactWorkspace(root).publish("/workspace/work/site.html")
    preview = WorkspaceBrowser(root).preview(artifact["path"])
    assert preview and "sandbox proof" in str(preview)
    archive, _ = WorkspaceBrowser(root).create_archive()
    with zipfile.ZipFile(io.BytesIO(archive)) as files:
        assert files.read("work/binary") == data
    fork = bound(tls_node[0], "file-fork")
    assert fork.call("fork", source_scope=list(root.scope))["files_copied"] > 0
    fork.call("write", path="/workspace/work/site.html", content="changed")
    assert root.call("read", path="/workspace/work/site.html")["file_data"][
        "content"
    ].startswith("<html>")


@pytest.mark.parametrize("graph_id", ["dearflow_agent", "showcase_demo"])
def test_real_node_graph_root_child_and_skills(
    tls_node, monkeypatch, tmp_path, graph_id
):
    import asyncio
    from uuid import uuid4

    import psycopg
    from langchain_core.messages import AIMessage, ToolMessage
    from langgraph.checkpoint.memory import InMemorySaver
    from psycopg import sql
    from psycopg.conninfo import make_conninfo
    from services.dearflow_agent.test_agent import config as dear_config
    from services.showcase_demo.test_agent import config as showcase_config
    from support import BindableFakeMessagesChatModel, with_run_budget

    from runtime_service.db import upgrade
    from runtime_service.middlewares.message_queue import MessageQueueMiddleware
    from runtime_service.runtime import runtime_context_hash
    from runtime_service.services.dearflow_agent import agent as dear_agent
    from runtime_service.services.demo.showcase_demo import agent as showcase_agent
    from runtime_service.workspace.scoped import resolve_thread_workspace

    dsn = os.getenv("BACKGROUND_TEST_DSN")
    if not dsn:
        pytest.skip("BACKGROUND_TEST_DSN must point to this Worktree database")
    schema = "sandbox_graph_" + uuid4().hex
    with psycopg.connect(dsn) as db:
        db.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    monkeypatch.setenv(
        "DATABASE_URI", make_conninfo(dsn, options=f"-c search_path={schema}")
    )
    monkeypatch.setenv("RUNTIME_BACKEND", "docker")
    monkeypatch.setenv("RUNTIME_SANDBOX_TARGET", "remote")
    monkeypatch.setenv("RUNTIME_WORKSPACE_IMAGE", "python:3.13-slim")
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path / "local-dear"))
    monkeypatch.setenv(
        "RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path / "local-showcase")
    )
    monkeypatch.setenv("RUNTIME_DEAR_GOVERNANCE_ENABLED", "0")

    async def no_queue(self, state, runtime):
        return None

    # This fixture owns workspace storage, not the engine's durable inbox/checkpointer.
    monkeypatch.setattr(MessageQueueMiddleware, "abefore_model", no_queue)
    cfg = with_run_budget(
        dear_config() if graph_id == "dearflow_agent" else showcase_config(),
        timeout=900,
    )
    cfg["context"] = {"execution_mode": "ultra", "access_policy": "full_access"}
    cfg["configurable"]["langgraph_auth_user"]["runtime_context_hash"] = (
        runtime_context_hash(cfg["context"])
    )
    agent = dear_agent if graph_id == "dearflow_agent" else showcase_agent
    skill = "runtime-smoke" if graph_id == "dearflow_agent" else "showcase-notes"
    child = "general-purpose" if graph_id == "dearflow_agent" else "research"

    def tool(name, args, identifier):
        return AIMessage(
            content="", tool_calls=[{"name": name, "args": args, "id": identifier}]
        )

    model = BindableFakeMessagesChatModel(
        responses=[
            tool("read_file", {"file_path": f"/skills/{skill}/SKILL.md"}, "skills"),
            tool(
                "execute",
                {"command": "printf graph-node > /workspace/work/shared.txt"},
                "execute",
            ),
            tool(
                "task",
                {
                    "description": "Read the shared.txt proof only",
                    "subagent_type": child,
                },
                "delegate",
            ),
            tool(
                "read_file", {"file_path": "/workspace/work/shared.txt"}, "child-read"
            ),
            AIMessage(content="child verified"),
            tool(
                "present_artifacts",
                {"file_path": "/workspace/work/shared.txt"},
                "publish",
            ),
            AIMessage(content="parent verified"),
        ]
    )
    monkeypatch.setattr(agent, "build_model", lambda *args, **kwargs: model)

    async def verify():
        graph = await agent.get_agent(cfg)
        graph.checkpointer = InMemorySaver()
        result = await graph.ainvoke(
            {"messages": [("user", "Verify the remote workspace")]},
            cfg,
            context=cfg["context"],
        )
        assert result["messages"][-1].text == "parent verified"
        outputs = {m.name: m for m in result["messages"] if isinstance(m, ToolMessage)}
        assert {"read_file", "execute", "task", "present_artifacts"} <= outputs.keys()
        assert all(m.status != "error" for m in outputs.values()), str(outputs)
        assert outputs["execute"].artifact["exit_code"] == 0
        assert "child verified" in str(outputs["task"].content)
        root = resolve_thread_workspace(
            "tenant", "project", cfg["configurable"]["thread_id"], graph_id
        )
        assert (
            root.call("read", path="/workspace/work/shared.txt")["file_data"]["content"]
            == "graph-node"
        )
        assert (
            not (tmp_path / "local-dear").exists()
            and not (tmp_path / "local-showcase").exists()
        )

    try:
        upgrade()
        asyncio.run(verify())
    finally:
        with psycopg.connect(dsn) as db:
            db.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_real_node_bulk_io_and_mixed_readiness(tls_node):
    import hashlib
    import json
    from concurrent.futures import ThreadPoolExecutor

    from runtime_service.workspace.remote_backend import RemoteWorkspaceBackend

    connection, directory, control = tls_node
    root = bound(connection, "bulk-mixed")
    backend = RemoteWorkspaceBackend(root)
    data = b"bulk-proof\n" * (10 * 1024**2 // 11)

    def rss(pid):
        result = subprocess.run(
            ["ps", "-o", "rss=", "-p", str(pid)],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return int(result.stdout.strip()) * 1024

    before = {"runtime": rss(os.getpid()), "node": rss(control["process"].pid)}
    started = time.monotonic()
    assert backend.upload_files([("/workspace/work/bulk", data)])[0].error is None
    uploaded = time.monotonic() - started
    started = time.monotonic()
    restored = backend.download_files(["/workspace/work/bulk"])[0].content
    downloaded = time.monotonic() - started
    assert hashlib.sha256(restored).digest() == hashlib.sha256(data).digest()
    for start in range(0, 201, 64):
        responses = backend.upload_files(
            [
                (f"/workspace/work/tree/{index:03}.txt", b"bounded-match\n")
                for index in range(start, min(start + 64, 201))
            ]
        )
        assert all(item.error is None for item in responses)
    listing = root.call("ls", path="/workspace/work/tree")
    assert len(listing["entries"]) == 200 and listing["error"] == "directory_truncated"
    searched = root.call(
        "grep", path="/workspace/work/tree", pattern="bounded-match", max_count=10
    )
    assert len(searched["matches"]) == 10 and searched["truncated"]
    terminal = root.call(
        "terminal.create", owner="mixed", request_id="one", rows=24, cols=80
    )
    latencies = []
    try:
        with ThreadPoolExecutor(2) as pool:
            work = pool.submit(
                root.call,
                "execute",
                command="sleep 2; printf mixed",
                image="python:3.13-slim",
                timeout=10,
            )
            while not work.done():
                started = time.monotonic()
                assert request(connection, "GET", "/v1/ready")["ready"]
                assert (
                    root.call("read", path="/workspace/work/tree/000.txt")["error"]
                    is None
                )
                latencies.append(time.monotonic() - started)
            assert work.result()["output"] == "mixed"
    finally:
        root.call("terminal.close", owner="mixed", terminal_id=terminal["terminal_id"])
    assert latencies and max(latencies) < 5
    assert all(row["status"] == "removed" for row in root.call("discover"))
    after = {"runtime": rss(os.getpid()), "node": rss(control["process"].pid)}
    assert all(after[key] - before[key] < 256 * 1024**2 for key in after)
    (directory / "bulk-performance.json").write_text(
        json.dumps(
            {
                "bytes": len(data),
                "upload_seconds": uploaded,
                "download_seconds": downloaded,
                "rss_before": before,
                "rss_after": after,
                "readiness_and_read_max_seconds": max(latencies),
                "mode": "remote-loopback",
            },
            indent=2,
        )
    )


def test_real_node_restart_and_certificate_rotation_preserve_data(
    tls_node, monkeypatch
):
    from concurrent.futures import ThreadPoolExecutor
    from uuid import uuid4

    from runtime_service.workspace.documents import DocumentError

    connection, directory, control = tls_node
    root = bound(connection, "restart-persistent")
    root.call("write", path="/workspace/work/proof", content="restart-data")
    terminal = root.call(
        "terminal.create",
        owner="restart",
        request_id="before-restart",
        rows=24,
        cols=80,
    )
    background_id = uuid4().hex
    call(
        root,
        "background.create",
        {
            "resource_id": background_id,
            "command": "printf retained",
            "image": "python:3.13-slim",
            "timeout": 30,
            "runner_secret": "c" * 64,
        },
        operation_id=background_id,
    )
    root.call("background.start", resource_id=background_id)
    control["process"].kill()
    control["process"].wait(timeout=10)
    script = (
        Path(__file__).resolve().parents[2] / "scripts/sandbox_node_certificates.py"
    )
    spec = importlib.util.spec_from_file_location("rotate_tls", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rotated = directory / "rotated"
    module.generate(
        rotated, "127.0.0.1", "tls-test-host", "127.0.0.1/32", directory / "secrets"
    )
    for name in ("AUTH_FILE", "TLS_CERT_FILE", "TLS_KEY_FILE", "TLS_CLIENT_CA_FILE"):
        env_key = "SANDBOX_" + name
        control["env"][env_key] = str(rotated / Path(control["env"][env_key]).name)
    for suffix, filename in (
        ("AUTH_FILE", "caller-token"),
        ("CA_FILE", "ca.pem"),
        ("CLIENT_CERT_FILE", "client.pem"),
        ("CLIENT_KEY_FILE", "client-key.pem"),
    ):
        monkeypatch.setenv("RUNTIME_SANDBOX_NODE_" + suffix, str(rotated / filename))
    control["process"] = subprocess.Popen(
        [sys.executable, "-m", "runtime_service.sandbox_node"],
        env=control["env"],
        stdout=control["log"],
        stderr=control["log"],
    )
    current = NodeConnection.load()
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if control["process"].poll() is not None:
            pytest.fail((directory / "node.log").read_text()[-3000:])
        try:
            if request(current, "GET", "/v1/ready")["ready"]:
                break
        except httpx.HTTPError:
            time.sleep(0.2)
    else:
        pytest.fail("Rotated Node did not become ready")
    with pytest.raises(DocumentError, match="sandbox_caller_denied"):
        request(connection, "GET", "/v1/ready")
    assert (
        root.call("read", path="/workspace/work/proof")["file_data"]["content"]
        == "restart-data"
    )
    with pytest.raises(DocumentError, match="terminal_instance_changed"):
        root.call(
            "terminal.describe", owner="restart", terminal_id=terminal["terminal_id"]
        )
    from runtime_service.workspace.background import verify_receipt

    receipt = root.call("background.receipt", resource_id=background_id)
    assert verify_receipt(receipt, {"runner_secret": "c" * 64})["exit_code"] == 0
    assert root.call("background.output", resource_id=background_id)[0] == "retained"
    with pytest.raises(DocumentError, match="sandbox_receipt_ack_required"):
        root.call("background.remove", resource_id=background_id, acknowledged=False)
    assert root.call("background.remove", resource_id=background_id, acknowledged=True)
    assert all(row["status"] == "removed" for row in root.call("discover"))
    with ThreadPoolExecutor(2) as pool:
        outputs = list(
            pool.map(
                lambda i: root.call(
                    "execute",
                    command="printf sibling" + str(i),
                    image="python:3.13-slim",
                    timeout=5,
                ),
                range(2),
            )
        )
    assert {item["output"] for item in outputs} == {"sibling0", "sibling1"}
