"""Node trust, durable operations and file lifecycle without a Docker fixture."""

import hashlib
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from runtime_service.sandbox_node.config import NodeConfig
from runtime_service.sandbox_node.protocol import Rpc
from runtime_service.sandbox_node.service import Node
from runtime_service.workspace.documents import DocumentError
from runtime_service.workspace.node_client import decode, encode
from runtime_service.workspace.remote_backend import RemoteWorkspaceBackend
from runtime_service.workspace.scoped import thread_scope_hash
from runtime_service.workspace.target import RemoteWorkspace


@pytest.fixture
def node(tmp_path):
    path = tmp_path.resolve()
    (path / "workspaces").mkdir()
    (path / "state").mkdir()
    value = Node(
        NodeConfig(
            "test-node",
            path / "workspaces",
            path / "state",
            {},
            frozenset({"approved-image"}),
            min_free=0,
        )
    )
    value.ready = True
    yield value
    value.locks.close()


def request(
    operation,
    arguments=None,
    *,
    scope=("tenant", "project", "thread"),
    operation_id=None,
    host="test-host",
):
    return Rpc(
        version=1,
        node_id="test-node",
        execution_host=host,
        scope=list(scope),
        graph="dearflow_agent",
        workspace_id=thread_scope_hash(*scope),
        operation=operation,
        operation_id=operation_id or uuid4().hex,
        arguments=encode(arguments or {}),
    )


def invoke(node, operation, **arguments):
    return decode(encode(node.rpc(request(operation, arguments))))


def test_prepare_write_edit_missing_and_traversal(node):
    assert invoke(node, "prepare")["prepared"]
    assert invoke(
        node, "write", path="/workspace/work/file.txt", content="first\nsecond\n"
    )["path"]
    read = invoke(node, "read", path="/workspace/work/file.txt", limit=1)
    assert read["file_data"]["content"] == "first\n" and read["next_offset"] == 1
    assert (
        invoke(
            node,
            "edit",
            path="/workspace/work/file.txt",
            old_string="second",
            new_string="third",
        )["occurrences"]
        == 1
    )
    assert (
        invoke(node, "write", path="/workspace/uploads/a", content="no")["error"]
        == "workspace_write_denied"
    )
    assert (
        invoke(node, "read", path="/workspace/work/missing")["error"]
        == "file_not_found"
    )
    assert invoke(node, "glob", pattern="missing*")["matches"] == []
    assert invoke(node, "write", path="/workspace/work/../../outside", content="no")[
        "error"
    ]
    assert not list(node.config.workspaces.rglob(".node-*"))


def test_terminal_rejects_unapproved_image_before_docker(node):
    invoke(node, "prepare")
    with pytest.raises(DocumentError, match="runtime.workspace.image_invalid"):
        invoke(
            node,
            "terminal.create",
            owner="owner",
            request_id="unapproved",
            rows=24,
            cols=80,
            image="unapproved-image",
        )
    assert invoke(node, "discover") == []
    assert not node.terminals.sessions


def test_caller_ip_and_tls_are_enforced_without_forwarded_header_trust(node):
    from dataclasses import replace
    from types import SimpleNamespace

    node.config = replace(
        node.config,
        callers={
            "test-host": {
                "certificate_cn": "test-host",
                "token_sha256": hashlib.sha256(b"t" * 64).hexdigest(),
                "allowed_ips": ["127.0.0.1/32"],
            }
        },
    )
    headers = {
        "x-execution-host": "test-host",
        "x-sandbox-node": "test-node",
        "authorization": "Bearer " + "t" * 64,
        "x-forwarded-for": "127.0.0.1",
    }
    certificate = {"subject": ((("commonName", "test-host"),),)}
    for address, scheme, trusted in (
        ("127.0.0.1", "https", True),
        ("127.0.0.2", "https", False),
        ("127.0.0.1", "http", False),
    ):
        incoming = SimpleNamespace(
            headers=headers,
            client=SimpleNamespace(host=address),
            scope={"scheme": scheme, "sandbox_client_certificate": certificate},
        )
        if trusted:
            assert node.authenticate(incoming) == "test-host"
        else:
            with pytest.raises(DocumentError, match="sandbox_caller_denied"):
                node.authenticate(incoming)


def test_symlink_and_cross_scope_rejected(node):
    invoke(node, "prepare")
    root = node.storage.check(request("prepare"))
    (root / "work" / "alias").symlink_to(root.parent)
    assert invoke(node, "write", path="/workspace/work/alias/outside", content="no")[
        "error"
    ]
    with pytest.raises(DocumentError, match="workspace_not_found"):
        node.rpc(
            request(
                "image.read",
                {"path": "/workspace/work/file.txt"},
                scope=("tenant", "other", "thread"),
            )
        )


def test_operation_replay_conflict_and_unfinished_id(node):
    first = request("prepare")
    result = node.rpc(first)
    assert node.rpc(first) == result
    with pytest.raises(DocumentError, match="sandbox_operation_conflict"):
        node.rpc(
            first.model_copy(update={"arguments": {"examples": {"file": "changed"}}})
        )
    pending = request("execute", {"command": "side-effect", "image": "approved-image"})
    node.ledger.begin(
        pending.execution_host,
        pending.operation_id,
        node.storage.key(pending),
        pending.model_dump(),
    )
    with pytest.raises(DocumentError, match="execution_outcome_unknown"):
        node.rpc(pending)


def test_files_restore_after_node_restart_without_recreating_missing_data(node):
    invoke(node, "prepare")
    invoke(node, "write", path="/workspace/work/proof.txt", content="persistent")
    reopened = Node(node.config)
    reopened.ready = True
    try:
        assert (
            invoke(reopened, "read", path="/workspace/work/proof.txt")["file_data"][
                "content"
            ]
            == "persistent"
        )
        root = reopened.storage.check(request("prepare"))
        root.rename(root.with_name("fixture-missing-workspace"))
        with pytest.raises(DocumentError, match="workspace_not_found"):
            invoke(reopened, "prepare")
        assert not root.exists()
    finally:
        reopened.locks.close()


def test_same_run_skills_snapshot_is_pinned_and_immutable(node):
    invoke(node, "prepare")
    original = invoke(
        node,
        "publish_skills",
        files={"read/SKILL.md": b"first"},
        documents=[],
        run_id="run-1",
    )
    retry = invoke(
        node,
        "publish_skills",
        files={"read/SKILL.md": b"changed"},
        documents=[],
        run_id="run-1",
    )
    assert original == retry
    assert (
        invoke(node, "read", path="/read/SKILL.md", skills=original["digest"])[
            "file_data"
        ]["content"]
        == "first"
    )
    assert (
        invoke(
            node, "download_files", paths=["/read/SKILL.md"], skills=original["digest"]
        )[0]["content"]
        == b"first"
    )
    root = node.storage.check(request("prepare"))
    snapshot = node.storage.snapshot_path(root, original["digest"])
    (snapshot / "read/SKILL.md").write_text("corrupted")
    with pytest.raises(DocumentError, match="skill_snapshot_mismatch"):
        invoke(node, "restore_skills", ref=original)


def test_concurrent_edits_validate_inside_workspace_lock(node):
    invoke(node, "prepare")
    invoke(node, "write", path="/workspace/work/edit.txt", content="initial")

    def edit(new):
        return invoke(
            node,
            "edit",
            path="/workspace/work/edit.txt",
            old_string="initial",
            new_string=new,
        )

    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(edit, ["first", "second"]))
    assert sum(result.get("occurrences") == 1 for result in results) == 1


def test_global_capacity_and_cancel_before_creation(node):
    def resource(identifier):
        return {
            "host": "host",
            "id": identifier,
            "workspace": "workspace",
            "kind": "execute",
            "name": "owned",
            "image": "approved-image",
            "policy": "{}",
            "deadline": 100,
        }

    node.ledger.reserve(resource("1"), 2)
    node.ledger.reserve(resource("2"), 2)
    with pytest.raises(DocumentError, match="sandbox_capacity_reached"):
        node.ledger.reserve(resource("3"), 2)
    node.ledger.update("host", "1", "removed")
    node.ledger.cancellation("host", "3", "workspace")
    with pytest.raises(DocumentError, match="sandbox_resource_cancelled"):
        node.ledger.reserve(resource("3"), 2)


def test_real_backend_and_document_browser_share_node_files(node, monkeypatch):
    root = RemoteWorkspace(
        ("tenant", "project", "thread"),
        "dearflow_agent",
        "test-host",
        "test-node",
        thread_scope_hash("tenant", "project", "thread"),
    )
    monkeypatch.setattr(
        "runtime_service.workspace.node_client.call",
        lambda workspace, op, args, **kw: decode(encode(node.rpc(request(op, args)))),
    )
    backend = RemoteWorkspaceBackend(root)
    backend.prepare()
    assert backend.write("/workspace/work/proof.md", "remote only").error is None
    assert (
        backend.read("/workspace/work/proof.md").file_data["content"] == "remote only"
    )
    from runtime_service.workspace.artifact_refs import ArtifactWorkspace
    from runtime_service.workspace.browser import WorkspaceBrowser
    from runtime_service.workspace.documents import DocumentWorkspace

    data = b"uploaded remote"
    ref = DocumentWorkspace(root).put(
        data, hashlib.sha256(data).hexdigest(), "text/plain", "proof.txt"
    )
    assert DocumentWorkspace(root).read(ref["path"])[0] == data
    assert (
        WorkspaceBrowser(root).list_directory("/workspace/work").items[0].name
        == "proof.md"
    )
    artifact = ArtifactWorkspace(root).publish("/workspace/work/proof.md")
    assert WorkspaceBrowser(root).read_file(artifact["path"])[0] == b"remote only"


def test_fork_isolates_files_and_rejects_other_projects(node):
    source = ("tenant", "project", "source")
    node.rpc(request("prepare", scope=source))
    node.rpc(
        request(
            "write",
            {"path": "/workspace/work/file", "content": "original"},
            scope=source,
        )
    )
    result = invoke(node, "fork", source_scope=source)
    assert result["files_copied"] == 1
    invoke(node, "write", path="/workspace/work/file", content="changed")
    assert (
        node.rpc(
            request("read", {"path": "/workspace/work/file"}, scope=source)
        ).file_data["content"]
        == "original"
    )
    assert (
        invoke(node, "fork", source_scope=("tenant", "project", "thread"))[
            "files_copied"
        ]
        == 0
    )
    with pytest.raises(DocumentError, match="workspace_fork_scope_mismatch"):
        invoke(node, "fork", source_scope=("tenant", "other-project", "source"))


def test_control_boundary_rejects_extra_docker_parameters_before_receipt(node):
    invalid = request(
        "execute",
        {"command": "touch forbidden", "image": "approved-image", "mount": "/etc"},
    )
    with pytest.raises(DocumentError, match="sandbox_request_invalid"):
        node.rpc(invalid)
    assert (
        node.ledger.operation(
            invalid.execution_host, invalid.operation_id, node.storage.key(invalid)
        )["status"]
        == "missing"
    )


def test_not_ready_preserves_query_and_cancellation(node):
    invoke(node, "prepare")
    node.ready = False
    assert invoke(node, "is_prepared")["prepared"]
    assert invoke(node, "operation", resource_id="b" * 32)["status"] == "missing"
    assert invoke(node, "cancel", resource_id="b" * 32)["confirmed"]
    with pytest.raises(DocumentError, match="sandbox_not_ready"):
        invoke(node, "write", path="/workspace/work/file", content="no")
    accepted = request("execute", {"command": "side-effect", "image": "approved-image"})
    node.ledger.begin(
        accepted.execution_host,
        accepted.operation_id,
        node.storage.key(accepted),
        accepted.model_dump(),
    )
    with pytest.raises(DocumentError, match="execution_outcome_unknown"):
        node.rpc(accepted)


def test_cleanup_grace_and_tombstone_protect_data(node):
    import time

    invoke(node, "prepare")
    invoke(node, "write", path="/workspace/work/file", content="kept")
    evidence = {
        "kind": "verified_orphan",
        "verified_by": "fixture",
        "confirmed_at": time.time(),
        "thread_absent": True,
        "pending_work_absent": True,
    }
    report = invoke(node, "cleanup.report")
    assert report["status"] == "retained" and not report["eligible"]
    with pytest.raises(DocumentError, match="workspace_cleanup_protected"):
        invoke(node, "cleanup.apply", candidate_token=report["candidate_token"])
    marked = invoke(node, "cleanup.mark", evidence=evidence)
    assert marked["status"] == "deleting" and not marked["eligible"]
    with node.ledger.connect() as db:
        db.execute("UPDATE workspaces SET deletion_at=deletion_at-700000")
    candidate = invoke(node, "cleanup.report")
    assert candidate["eligible"]
    invoke(node, "cleanup.apply", candidate_token=candidate["candidate_token"])
    assert invoke(node, "cleanup.report")["status"] == "purged"
    assert not node.storage.root(request("prepare")).exists()
    with pytest.raises(DocumentError, match="workspace_not_found"):
        invoke(node, "prepare")


def test_read_distinguishes_missing_permission_invalid_and_large_files(node):
    invoke(node, "prepare")
    root = node.storage.check(request("prepare"))
    file = root / "work/private"
    file.write_bytes(b"private")
    file.chmod(0)
    try:
        assert (
            invoke(node, "read", path="/workspace/work/private")["error"]
            == "file_permission_denied"
        )
        assert (
            invoke(node, "download_files", paths=["/workspace/work/private"])[0][
                "error"
            ]
            == "permission_denied"
        )
    finally:
        file.chmod(0o600)
    assert (
        invoke(node, "read", path="/workspace/work/none")["error"] == "file_not_found"
    )
    (root / "work/link").symlink_to(file)
    assert (
        invoke(node, "read", path="/workspace/work/link")["error"]
        == "invalid_workspace_path"
    )
    from runtime_service.workspace.file_refs import MAX_FILE_BYTES

    with file.open("wb") as stream:
        stream.truncate(MAX_FILE_BYTES + 1)
    assert (
        invoke(node, "read", path="/workspace/work/private")["error"]
        == "file_too_large"
    )
    assert invoke(node, "is_prepared")["prepared"]


def test_search_empty_exact_limit_extra_and_partial_error(node):
    invoke(node, "prepare")
    invoke(node, "write", path="/workspace/work/a", content="match\nmatch")
    assert invoke(node, "grep", pattern="absent")["matches"] == []
    exact = invoke(node, "grep", pattern="match", max_count=2)
    assert len(exact["matches"]) == 2 and not exact["truncated"]
    extra = invoke(node, "grep", pattern="match", max_count=1)
    assert len(extra["matches"]) == 1 and extra["truncated"]
    root = node.storage.check(request("prepare"))
    denied = root / "work/z"
    denied.mkdir()
    denied.chmod(0)
    try:
        partial = invoke(node, "grep", pattern="match", path="/workspace/work")
        assert (
            len(partial["matches"]) == 2
            and partial["error"] == "search_incomplete"
            and partial["truncated"]
        )
    finally:
        denied.chmod(0o700)


def test_low_disk_and_failed_ledger_never_submit_docker(node, monkeypatch):
    from types import SimpleNamespace

    invoke(node, "prepare")
    calls = []
    monkeypatch.setattr(node.engine, "control", lambda *args, **kw: calls.append(args))
    monkeypatch.setattr(
        "runtime_service.sandbox_node.engine.shutil.disk_usage",
        lambda path: SimpleNamespace(free=-1),
    )
    with pytest.raises(DocumentError, match="sandbox_disk_capacity_reached"):
        invoke(node, "execute", command="touch forbidden", image="approved-image")
    assert not calls
    monkeypatch.setattr(
        "runtime_service.sandbox_node.engine.shutil.disk_usage",
        lambda path: SimpleNamespace(free=1),
    )
    import sqlite3

    def unavailable(*args):
        raise sqlite3.OperationalError("fixture disk failure")

    monkeypatch.setattr(node.ledger, "reserve", unavailable)
    with pytest.raises(sqlite3.OperationalError):
        invoke(node, "execute", command="touch forbidden", image="approved-image")
    assert not calls


def test_read_discovery_has_no_resource_mutations(node, monkeypatch):
    invoke(node, "prepare")
    monkeypatch.setattr(
        node.engine,
        "control",
        lambda *args, **kw: pytest.fail("read must not call Docker"),
    )
    before = node.ledger.resources()
    assert invoke(node, "discover") == before
    assert invoke(node, "operation", resource_id="a" * 32)["status"] == "missing"
    assert node.ledger.resources() == before


def test_cross_scope_cancel_cannot_poison_original_resource(node):
    identifier = "a" * 32
    original = request("prepare")
    node.ledger.reserve(
        {
            "host": "test-host",
            "id": identifier,
            "workspace": node.storage.key(original),
            "kind": "execute",
            "name": "owned",
            "image": "approved-image",
            "policy": "{}",
            "deadline": 100,
        },
        2,
    )
    with pytest.raises(DocumentError, match="sandbox_resource_not_found"):
        node.ledger.cancellation("test-host", identifier, "other/workspace")
    with node.ledger.connect() as db:
        assert db.execute("SELECT count(*) FROM cancellations").fetchone()[0] == 0
    node.ledger.cancellation("test-host", identifier, node.storage.key(original))


def test_background_create_requires_resource_id_to_match_operation(node):
    invalid = request(
        "background.create",
        {
            "resource_id": "a" * 32,
            "command": "touch forbidden",
            "image": "approved-image",
            "timeout": 30,
            "runner_secret": "b" * 64,
        },
    )
    with pytest.raises(DocumentError, match="sandbox_request_invalid"):
        node.rpc(invalid)
    assert not node.ledger.resources()


@pytest.mark.parametrize("status,expired", [("reserved", True), ("exited", False)])
def test_expired_or_released_background_cannot_start_late(
    node, monkeypatch, status, expired
):
    import time

    identifier = "a" * 32
    original = request("background.start", {"resource_id": identifier})
    node.ledger.reserve(
        {
            "host": "test-host",
            "id": identifier,
            "workspace": node.storage.key(original),
            "kind": "background",
            "name": "owned",
            "image": "approved-image",
            "policy": "{}",
            "deadline": time.time() + (-1 if expired else 60),
        },
        2,
    )
    node.ledger.update("test-host", identifier, status)
    monkeypatch.setattr(
        node.engine, "inspect", lambda row: {"Status": "created", "Running": False}
    )
    controls = []
    monkeypatch.setattr(
        node.engine, "control", lambda *args, **kw: controls.append(args)
    )
    with pytest.raises(DocumentError, match="sandbox_resource_cancelled"):
        node.rpc(original)
    assert controls == []


def test_reconcile_keeps_created_background_reserved(node, monkeypatch):
    import time

    original = request("prepare")
    node.ledger.reserve(
        {
            "host": "test-host",
            "id": "a" * 32,
            "workspace": node.storage.key(original),
            "kind": "background",
            "name": "owned",
            "image": "approved-image",
            "policy": "{}",
            "deadline": time.time() + 60,
        },
        2,
    )
    monkeypatch.setattr(node.engine, "control", lambda *args, **kw: (0, b"owned\n"))
    monkeypatch.setattr(
        node.engine, "inspect", lambda row: {"Status": "created", "Running": False}
    )
    node.engine.reconcile()
    assert node.ledger.resources()[0]["status"] == "reserved"
    assert invoke(node, "background.start", resource_id="a" * 32)["Status"] == "created"
    assert node.ledger.resources()[0]["status"] == "running"


def test_reconcile_never_removes_unregistered_containers(node, monkeypatch):
    controls = []

    def control(*args, **kwargs):
        controls.append(args)
        return 0, b"unregistered-owned-label\n"

    monkeypatch.setattr(node.engine, "control", control)
    with pytest.raises(DocumentError, match="sandbox_unregistered_resource"):
        node.engine.reconcile(startup=True)
    assert len(controls) == 1 and controls[0][0] == "ps"


def test_cleanup_cannot_race_an_accepted_file_operation(node, monkeypatch):
    import time

    invoke(node, "prepare")
    blocked = request("write", {"path": "/workspace/work/proof", "content": "pending"})
    node.ledger.begin(
        blocked.execution_host,
        blocked.operation_id,
        node.storage.key(blocked),
        blocked.model_dump(),
    )
    evidence = {
        "kind": "verified_orphan",
        "verified_by": "test-operator",
        "confirmed_at": time.time() - 10,
        "thread_absent": True,
        "pending_work_absent": True,
    }
    with pytest.raises(DocumentError, match="workspace_cleanup_protected"):
        invoke(node, "cleanup.mark", evidence=evidence)
    node.rpc(request("write", {"path": "/workspace/work/proof", "content": "retained"}))
    assert (
        invoke(node, "read", path="/workspace/work/proof")["file_data"]["content"]
        == "retained"
    )
    node.ledger.finish(blocked.execution_host, blocked.operation_id, {})
    assert invoke(node, "cleanup.mark", evidence=evidence)["status"] == "deleting"
    monkeypatch.setenv("RUNTIME_WORKSPACE_TTL_SECONDS", "1")
    candidate = invoke(node, "cleanup.report")
    assert (
        invoke(node, "cleanup.apply", candidate_token=candidate["candidate_token"])[
            "status"
        ]
        == "purged"
    )
    with pytest.raises(DocumentError, match="workspace_not_found"):
        invoke(node, "prepare")


@pytest.mark.parametrize("reason", ["idle_expired", "lifetime_expired"])
def test_real_terminal_idle_sweep_removes_owned_container_and_keeps_files(
    node, monkeypatch, reason
):
    import os
    import subprocess
    from dataclasses import replace

    if os.getenv("BACKGROUND_DOCKER_TEST") != "1":
        pytest.skip("BACKGROUND_DOCKER_TEST=1 requires the managed test daemon")
    node.config = replace(node.config, images=frozenset({"runtime-agent-workspace:p5"}))
    node.engine.config = node.config
    node.engine.readiness()
    invoke(node, "prepare")
    invoke(node, "write", path="/workspace/work/proof", content="idle-kept")
    result = invoke(
        node, "terminal.create", owner="idle", request_id="idle-test", rows=24, cols=80
    )
    session = node.terminals.sessions[result["terminal_id"]]
    try:
        last_input = session.last_input
        session.read(0)
        assert session.last_input == last_input
        if reason == "idle_expired":
            session.last_input -= 901
        else:
            session.created -= 3601
        node.terminals.sweep()
        assert session.describe()["reason"] == reason
        assert (
            subprocess.run(
                ["docker", "inspect", session.container],
                capture_output=True,
                timeout=15,
            ).returncode
            != 0
        )
        assert (
            invoke(node, "read", path="/workspace/work/proof")["file_data"]["content"]
            == "idle-kept"
        )
    finally:
        node.terminals.shutdown()


def test_second_manager_cannot_start_with_the_same_ledger(node, monkeypatch):
    import asyncio

    from runtime_service.sandbox_node.engine import Engine
    from runtime_service.sandbox_node.service import create_app

    monkeypatch.setattr(Engine, "readiness", lambda engine: None)
    monkeypatch.setattr(Engine, "reconcile", lambda engine, **kwargs: None)
    first, second = create_app(node.config), create_app(node.config)

    async def verify():
        async with first.router.lifespan_context(first):
            assert first.state.node.ready
            with pytest.raises(BlockingIOError):
                async with second.router.lifespan_context(second):
                    pytest.fail("Second Node manager acquired the same ledger")
            assert first.state.node.ready

    try:
        asyncio.run(verify())
    finally:
        second.state.node.locks.close()


@pytest.mark.parametrize(
    "field",
    ["image", "mount", "network", "owner", "capabilities", "seccomp", "tmpfs", "fsize"],
)
def test_existing_resource_policy_mismatch_is_never_adopted(node, monkeypatch, field):
    import json

    invoke(node, "prepare")
    row = node.engine.reserve(request("execute"), "execute", "approved-image", 30)
    policy = json.loads(row["policy"])
    facts = {
        "Id": "fixture",
        "Image": "sha256:approved",
        "Config": {
            "Image": row["image"],
            "User": f"{policy['uid']}:{policy['gid']}",
            "Labels": {
                "runtime.sandbox.node": node.config.node_id,
                "runtime.sandbox.host": row["host"],
                "runtime.sandbox.resource": row["id"],
                "runtime.sandbox.workspace": row["workspace"],
            },
        },
        "HostConfig": {
            "NetworkMode": "none",
            "ReadonlyRootfs": True,
            "Privileged": False,
            "CapDrop": ["ALL"],
            "CapAdd": [],
            "SecurityOpt": ["no-new-privileges"],
            "Tmpfs": {"/tmp": "rw,nosuid,nodev,size=16777216"},
            "Ulimits": [{"Name": "fsize", "Soft": 8388608, "Hard": 8388608}],
            "Memory": 256 * 1024**2,
            "PidsLimit": 64,
            "NanoCpus": 1_000_000_000,
            "PortBindings": {},
            "RestartPolicy": {"Name": "no"},
            "LogConfig": {
                "Type": "local",
                "Config": {"max-size": "2m", "max-file": "2"},
            },
        },
        "Mounts": [
            {"Destination": "/workspace", "Source": policy["root"], "RW": False},
            {
                "Destination": "/workspace/work",
                "Source": policy["root"] + "/work",
                "RW": True,
            },
        ],
        "State": {"Running": True, "Status": "running"},
    }
    assert node.engine.inspect_facts(row, facts)["Running"]
    if field == "image":
        facts["Config"]["Image"] = "unapproved"
    elif field == "mount":
        facts["Mounts"][0]["Source"] = "/other-workspace"
    elif field == "network":
        facts["HostConfig"]["NetworkMode"] = "bridge"
    elif field == "owner":
        facts["Config"]["Labels"]["runtime.sandbox.host"] = "other-host"
    elif field == "capabilities":
        facts["HostConfig"]["CapAdd"] = ["SYS_ADMIN"]
    elif field == "seccomp":
        facts["HostConfig"]["SecurityOpt"].append("seccomp=unconfined")
    elif field == "tmpfs":
        facts["HostConfig"]["Tmpfs"]["/tmp"] = "rw,size=1g"
    else:
        facts["HostConfig"]["Ulimits"][0]["Hard"] = -1
    with pytest.raises(DocumentError, match="sandbox_resource_policy_mismatch"):
        node.engine.inspect_facts(row, facts)
    assert (
        node.ledger.resource(row["host"], row["id"], row["workspace"])["status"]
        == "reserved"
    )
