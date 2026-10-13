"""Real database binding races, migration branches and guarded data removal."""

import os
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from runtime_service import db
from runtime_service.errors import RuntimeWorkspaceError
from runtime_service.workspace import locations
from runtime_service.workspace.cleanup import cleanup
from runtime_service.workspace.documents import DocumentError
from runtime_service.workspace.target import NodeConnection, RemoteWorkspace


@pytest.fixture
def database(monkeypatch):
    dsn = os.getenv("WORKSPACE_TEST_DSN")
    if not dsn:
        pytest.skip("WORKSPACE_TEST_DSN must point to this Worktree database")
    schema = "sandbox_test_" + uuid4().hex
    with psycopg.connect(dsn) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    scoped = make_conninfo(dsn, options=f"-c search_path={schema}")
    monkeypatch.setenv("DATABASE_URI", scoped)
    monkeypatch.setenv("RUNTIME_EXECUTION_HOST_ID", "test-host")
    monkeypatch.setenv("RUNTIME_BACKEND", "local")
    monkeypatch.setenv("RUNTIME_SANDBOX_TARGET", "local")
    try:
        db.upgrade()
        with db.connect() as connection:
            connection.execute("""CREATE TABLE threads(thread_id text PRIMARY KEY);
                CREATE TABLE runs(thread_id text, status text);
                CREATE TABLE crons(thread_id text, enabled boolean);""")
        yield
    finally:
        with psycopg.connect(dsn) as connection:
            connection.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )


def test_atomic_binding_local_docker_and_root_change(database, tmp_path, monkeypatch):
    scope = ("tenant", "project", "thread")
    root = tmp_path / "workspace"
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert (
            list(
                pool.map(
                    lambda _: locations.bind(scope, "dearflow_agent", root), range(16)
                )
            )
            == [root] * 16
        )
    monkeypatch.setenv("RUNTIME_BACKEND", "docker")
    assert locations.bind(scope, "dearflow_agent", root) == root
    with pytest.raises(RuntimeWorkspaceError, match="unavailable"):
        locations.bind(scope, "dearflow_agent", tmp_path / "other-root")
    with db.connect() as connection:
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM runtime_workspace_locations"
            ).fetchone()["n"]
            == 1
        )
        assert (
            connection.execute(
                "SELECT version_num FROM runtime_app_alembic_version"
            ).fetchone()["version_num"]
            == "0008_sandbox_resource_binding"
        )


def remote(monkeypatch):
    monkeypatch.setenv("RUNTIME_BACKEND", "docker")
    monkeypatch.setenv("RUNTIME_SANDBOX_TARGET", "remote")
    monkeypatch.setattr(
        NodeConnection,
        "load",
        lambda: SimpleNamespace(execution_host="test-host", node_id="test-node"),
    )


def test_remote_does_not_move_old_local_or_change_nodes(
    database, tmp_path, monkeypatch
):
    remote(monkeypatch)
    scope = ("tenant", "project", "thread")
    old = tmp_path / "old"
    old.mkdir()
    with pytest.raises(RuntimeWorkspaceError):
        locations.bind(scope, "dearflow_agent", old)
    root = locations.bind(scope, "dearflow_agent", tmp_path / "missing")
    assert isinstance(root, RemoteWorkspace)
    monkeypatch.setattr(
        NodeConnection,
        "load",
        lambda: SimpleNamespace(execution_host="test-host", node_id="changed-node"),
    )
    with pytest.raises(RuntimeWorkspaceError):
        locations.bind(scope, "dearflow_agent", tmp_path / "missing")
    monkeypatch.setenv("RUNTIME_BACKEND", "local")
    with pytest.raises(RuntimeWorkspaceError):
        locations.bind(scope, "dearflow_agent", tmp_path / "missing")


def test_retained_threads_and_pending_runs_protect_cleanup(
    database, tmp_path, monkeypatch
):
    remote(monkeypatch)
    scope = ("tenant", "project", "thread")
    locations.bind(scope, "dearflow_agent", tmp_path / "missing")
    monkeypatch.setattr(
        RemoteWorkspace,
        "call",
        lambda self, operation, **args: pytest.fail(
            "protected data must not reach Node mutation"
        ),
    )
    with db.connect() as connection:
        connection.execute("INSERT INTO threads VALUES ('thread')")
    with pytest.raises(DocumentError, match="workspace_cleanup_protected"):
        cleanup(scope, "dearflow_agent", action="mark", verified_by="operator")
    with db.connect() as connection:
        connection.execute("DELETE FROM threads")
        connection.execute("INSERT INTO runs VALUES ('thread','interrupted')")
    with pytest.raises(DocumentError, match="workspace_cleanup_protected"):
        cleanup(scope, "dearflow_agent", action="mark", verified_by="operator")


def test_cleanup_tombstone_commit_loss_can_be_reconciled(
    database, tmp_path, monkeypatch
):
    remote(monkeypatch)
    scope = ("tenant", "project", "orphan")
    locations.bind(scope, "dearflow_agent", tmp_path / "missing")
    statuses = {"mark": "deleting", "report": "deleting", "apply": "purged"}
    monkeypatch.setattr(
        RemoteWorkspace,
        "call",
        lambda self, operation, **args: {
            "status": statuses[operation.split(".")[1]],
            "eligible": True,
        },
    )
    assert (
        cleanup(scope, "dearflow_agent", action="mark", verified_by="operator")[
            "status"
        ]
        == "deleting"
    )
    with pytest.raises(RuntimeWorkspaceError):
        locations.bind(scope, "dearflow_agent", tmp_path / "missing")
    assert (
        cleanup(scope, "dearflow_agent", action="apply", candidate_token="token")[
            "status"
        ]
        == "purged"
    )
    with db.connect() as connection:
        assert (
            connection.execute(
                "SELECT status FROM runtime_workspace_locations"
            ).fetchone()["status"]
            == "purged"
        )
    with pytest.raises(RuntimeWorkspaceError):
        locations.bind(scope, "dearflow_agent", tmp_path / "missing")


def test_worker_restart_recovers_original_remote_id_and_scope(
    database, tmp_path, monkeypatch
):
    from runtime_service.run_control import resources

    remote(monkeypatch)
    scope = ("tenant", "project", "thread")
    root = locations.bind(scope, "dearflow_agent", tmp_path / "missing")
    resource = resources._register(
        "docker_execute", "thread", "run", root.node_id, "a" * 32, root
    )
    calls = []

    def query(workspace, operation, arguments):
        assert workspace == root
        calls.append((operation, arguments))
        if operation == "operation":
            return {"status": "accepted", "result": None}
        if operation == "cancel":
            return {"confirmed": True}
        return [{"id": "a" * 32, "status": "running"}]

    monkeypatch.setattr("runtime_service.workspace.node_client.call", query)
    resources.reconcile_remote_resources()
    assert resources.resource_state("thread", ["run"]) == "pending"
    resources.reconcile_remote_resources("thread", ["run"], cancel=True)
    assert resources.resource_state("thread", ["run"]) == "confirmed"
    assert calls[-1] == ("cancel", {"resource_id": "a" * 32})
    assert not any(operation == "execute" for operation, _ in calls)
    with db.connect() as connection:
        assert (
            connection.execute(
                "SELECT resource_id FROM runtime_run_resources"
            ).fetchone()["resource_id"]
            == resource
        )
