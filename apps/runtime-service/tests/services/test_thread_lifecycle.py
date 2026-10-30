"""Deletion handoff and application maintenance in a disposable PG schema."""

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb

from runtime_service import maintenance
from runtime_service import thread_lifecycle as lifecycle
from runtime_service.db import connect
from runtime_service.messaging import MessageInbox
from runtime_service.run_control import resources
from runtime_service.workspace.scoped import get_thread_local_workspace_root


@pytest.fixture
def handoff(monkeypatch, tmp_path):
    dsn = os.getenv("RUNTIME_MESSAGE_TEST_DSN")
    if not dsn:
        pytest.skip("RUNTIME_MESSAGE_TEST_DSN must point to an isolated database")
    schema = "retention_" + uuid4().hex
    with psycopg.connect(dsn) as db:
        db.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    inbox = MessageInbox(make_conninfo(dsn, options=f"-c search_path={schema}"))
    inbox.initialize()
    monkeypatch.setenv("DATABASE_URI", inbox.dsn)
    monkeypatch.setenv("RUNTIME_EXECUTION_HOST_ID", "host-test")
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("RUNTIME_SANDBOX_TARGET", "local")
    event = {
        "thread_id": str(uuid4()),
        "task_id": str(uuid4()),
        "metadata": {"project_id": "project-test"},
    }
    with connect() as db:
        db.execute(
            "CREATE TABLE threads(thread_id uuid PRIMARY KEY,graph_id text,metadata jsonb,deletion_requested_at timestamptz)"
        )
        db.execute("CREATE TABLE runs(thread_id uuid,status text)")
        db.execute(
            "CREATE TABLE thread_deletions(task_id uuid,thread_id uuid PRIMARY KEY,state text,metadata jsonb,completed_at timestamptz)"
        )
        db.execute(
            "INSERT INTO threads VALUES(%s,NULL,'{}',now())", (event["thread_id"],)
        )
        db.execute(
            "INSERT INTO thread_deletions VALUES(%s,%s,'before_delete',%s,NULL)",
            (event["task_id"], event["thread_id"], Jsonb(event["metadata"])),
        )
    try:
        yield event, inbox
    finally:
        with psycopg.connect(dsn) as db:
            db.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_handoff_rejects_forged_tasks_before_resource_actions(handoff, monkeypatch):
    event, _ = handoff
    sweep = AsyncMock()
    monkeypatch.setattr(resources, "reconcile_terminal_resources", sweep)
    with pytest.raises(ValueError, match="handoff_invalid"):
        lifecycle._before({**event, "task_id": str(uuid4())})
    sweep.assert_not_called()
    with pytest.raises(ValueError, match="handoff_invalid"):
        lifecycle._clean_application(event)


def test_pending_inbox_and_unconfirmed_resources_block_cleanup(handoff):
    event, inbox = handoff
    thread = str(uuid4())
    inbox.enqueue(
        thread_id=thread,
        target_run_id=str(uuid4()),
        sender_id="owner",
        client_message_id=str(uuid4()),
        idempotency_key="key",
        content="secret",
    )
    with connect() as db:
        assert lifecycle._pending(db, thread)
        db.execute(
            "UPDATE runtime_message_inbox SET status='cancelled' WHERE thread_id=%s",
            (thread,),
        )
        assert not lifecycle._pending(db, thread)
        db.execute(
            "INSERT INTO runtime_run_resources(resource_id,thread_id,run_id,kind) VALUES(%s,%s,%s,'local_execute')",
            (uuid4(), thread, str(uuid4())),
        )
        assert lifecycle._pending(db, thread)
        db.execute(
            "UPDATE runtime_run_resources SET status='cleanup_confirmed' WHERE thread_id=%s",
            (thread,),
        )
        assert not lifecycle._pending(db, thread)
        assert lifecycle.deletion_pending(db, event["thread_id"])
    with pytest.raises(Exception, match="runtime.workspace.unavailable"):
        resources._register("local_execute", event["thread_id"], str(uuid4()))


def test_legacy_workspace_uses_unique_persisted_scope_and_rejects_conflicts(handoff):
    event, _ = handoff
    root = get_thread_local_workspace_root(
        "tenant-test", "project-test", event["thread_id"], "dearflow_agent"
    )
    root.mkdir(parents=True)
    (root / "private.txt").write_text("private")
    thread = {"graph_id": "dearflow_agent", "metadata": {}}
    with connect() as db:
        with pytest.raises(ValueError, match="scope_unconfirmed"):
            lifecycle._bind_legacy_local(db, event, thread)
        db.execute(
            "INSERT INTO runtime_usage_runs(tenant_id,project_id,run_id,thread_id,graph_id) VALUES(%s,%s,%s,%s,%s)",
            (
                "tenant-test",
                "project-test",
                uuid4(),
                event["thread_id"],
                "dearflow_agent",
            ),
        )
        lifecycle._bind_legacy_local(db, event, thread)
        location = db.execute("SELECT * FROM runtime_workspace_locations").fetchone()
        assert location["storage_path"] == str(root)
        db.execute("DELETE FROM runtime_workspace_locations")
        db.execute(
            "INSERT INTO runtime_usage_runs(tenant_id,project_id,run_id,thread_id,graph_id) VALUES(%s,%s,%s,%s,%s)",
            (
                "other-tenant",
                "project-test",
                uuid4(),
                event["thread_id"],
                "dearflow_agent",
            ),
        )
        with pytest.raises(ValueError, match="scope_conflict"):
            lifecycle._bind_legacy_local(db, event, thread)


@pytest.mark.parametrize("backend", ["local", "docker"])
def test_legacy_workspace_respects_effective_target(handoff, monkeypatch, backend):
    event, _ = handoff
    monkeypatch.setenv("RUNTIME_BACKEND", backend)
    monkeypatch.setenv("RUNTIME_SANDBOX_TARGET", "remote")
    root = get_thread_local_workspace_root(
        "tenant-test", "project-test", event["thread_id"], "dearflow_agent"
    )
    root.mkdir(parents=True)
    thread = {"graph_id": "dearflow_agent", "metadata": {"tenant_id": "tenant-test"}}
    with connect() as db:
        if backend == "docker":
            with pytest.raises(ValueError, match="location_unconfirmed"):
                lifecycle._bind_legacy_local(db, event, thread)
        else:
            lifecycle._bind_legacy_local(db, event, thread)
            assert (
                db.execute(
                    "SELECT count(*) AS n FROM runtime_workspace_locations"
                ).fetchone()["n"]
                == 1
            )


def test_after_delete_removes_bound_workspace_and_retries_notification(
    handoff, monkeypatch
):
    event, _ = handoff
    root = get_thread_local_workspace_root(
        "tenant-test", "project-test", event["thread_id"], "dearflow_agent"
    )
    root.mkdir(parents=True)
    (root / "private.txt").write_text("private")
    with connect() as db:
        lifecycle._bind_legacy_local(
            db,
            event,
            {"graph_id": "dearflow_agent", "metadata": {"tenant_id": "tenant-test"}},
        )
        db.execute("UPDATE thread_deletions SET state='after_delete'")
    with pytest.raises(ValueError, match="not_committed"):
        lifecycle._clean_application(event)
    with connect() as db:
        db.execute("DELETE FROM threads")
    notify = AsyncMock(side_effect=[OSError("temporary"), None])
    monkeypatch.setattr(lifecycle, "_notify_platform", notify)
    with pytest.raises(OSError, match="temporary"):
        asyncio.run(lifecycle.after_delete(event))
    assert not root.parent.exists()
    assert asyncio.run(lifecycle.after_delete(event))
    assert notify.await_count == 2
    with connect() as db:
        assert (
            db.execute("SELECT status FROM runtime_workspace_locations").fetchone()[
                "status"
            ]
            == "purged"
        )


def test_cleanup_refuses_symlink_and_open_file(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "scope" / "workspace"
    root.parent.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        lifecycle._remove_local(root)
    root.parent.unlink()
    root.mkdir(parents=True)
    with (root / "held.txt").open("w"):
        with pytest.raises(ValueError, match="in_use_or_unconfirmed"):
            lifecycle._remove_local(root)
    lifecycle._remove_local(root)
    assert outside.exists() and not root.parent.exists()


@pytest.mark.parametrize("target", ["local", "remote"])
def test_unavailable_execution_host_preserves_cleanup_binding(
    handoff, monkeypatch, target
):
    event, _ = handoff
    root = get_thread_local_workspace_root(
        "tenant-test", "project-test", event["thread_id"], "dearflow_agent"
    )
    root.mkdir(parents=True)
    with connect() as db:
        lifecycle._bind_legacy_local(
            db,
            event,
            {"graph_id": "dearflow_agent", "metadata": {"tenant_id": "tenant-test"}},
        )
        db.execute("UPDATE thread_deletions SET state='after_delete'")
        db.execute("DELETE FROM threads")
        db.execute(
            "UPDATE runtime_workspace_locations SET execution_host='unavailable-host',target=%s,node_id=%s,storage_path=%s",
            (
                target,
                "unavailable-node" if target == "remote" else None,
                None if target == "remote" else str(root),
            ),
        )
    if target == "remote":
        monkeypatch.setattr(
            lifecycle.NodeConnection,
            "load",
            lambda: SimpleNamespace(
                execution_host="current-host", node_id="current-node"
            ),
        )
    with pytest.raises(ValueError, match="host_unavailable"):
        lifecycle._clean_application(event)
    with connect() as db:
        assert (
            db.execute("SELECT status FROM runtime_workspace_locations").fetchone()[
                "status"
            ]
            != "purged"
        )
    assert root.exists()
    with connect() as db:
        db.execute(
            "UPDATE runtime_workspace_locations SET execution_host='host-test',target='local',node_id=NULL,storage_path=%s",
            (str(root),),
        )
    assert lifecycle._clean_application(event)
    assert not root.parent.exists()


def test_terminal_recovery_requires_owner_exit_and_maintenance_is_read_only(
    handoff, monkeypatch, tmp_path
):
    event, _ = handoff
    root = tmp_path / "terminal" / "workspace"
    root.mkdir(parents=True)
    # Use another thread: resource registration is fenced on the deleting thread.
    resource = resources._register(
        "terminal",
        str(uuid4()),
        str(uuid4()),
        local_binding={
            "execution_host": "host-test",
            "owner_pid": os.getpid(),
            "owner_started": resources.process_started(os.getpid()),
            "root": str(root),
            "container": None,
        },
    )
    report = maintenance.maintain()
    assert report["terminal_resources"] == 1
    resources.reconcile_terminal_resources()
    with connect() as db:
        assert (
            db.execute(
                "SELECT status FROM runtime_run_resources WHERE resource_id=%s",
                (resource,),
            ).fetchone()["status"]
            == "active"
        )
        db.execute(
            "UPDATE runtime_run_resources SET local_binding=jsonb_set(local_binding,'{owner_started}','\"old-process\"') WHERE resource_id=%s",
            (resource,),
        )
    resources.reconcile_terminal_resources()
    with connect() as db:
        assert (
            db.execute(
                "SELECT status FROM runtime_run_resources WHERE resource_id=%s",
                (resource,),
            ).fetchone()["status"]
            == "cleanup_confirmed"
        )
    assert maintenance.maintain(apply=True)["terminal_resources"] == 0


def test_maintenance_is_exclusive_and_exits_when_budget_expires(handoff, monkeypatch):
    with connect() as db:
        db.execute("SELECT pg_advisory_lock(74013003)")
        try:
            assert maintenance.maintain(apply=True)["skipped"] == "maintenance_busy"
        finally:
            db.execute("SELECT pg_advisory_unlock(74013003)")
    ticks = iter((0, 31))
    monkeypatch.setattr(
        maintenance, "time", SimpleNamespace(monotonic=lambda: next(ticks))
    )
    logs = AsyncMock(side_effect=AssertionError("queried after budget"))
    monkeypatch.setattr(maintenance.repository, "logs_to_expire", logs)
    assert maintenance.maintain(apply=True)["budget_exhausted"]
    logs.assert_not_called()


@pytest.mark.parametrize("limit,budget", [(0, 30), (1001, 30), (100, 0), (100, 301)])
def test_maintenance_rejects_unbounded_work(limit, budget):
    with pytest.raises(ValueError, match="bounds"):
        maintenance.maintain(limit=limit, budget_seconds=budget)
