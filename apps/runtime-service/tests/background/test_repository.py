"""PostgreSQL concurrency and replay gates; use an explicitly isolated DSN."""

import asyncio
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo

from runtime_service.background_tasks import output, repository, service
from runtime_service.db import connect, upgrade
from runtime_service.run_control.repository import request_stop
from runtime_service.runtime.errors import (
    BackgroundTaskNotStarted,
    RuntimeWorkspaceError,
)
from runtime_service.workspace.background import (
    BackgroundBinding,
    remove_task_container,
    stop_task_container,
)


@pytest.fixture
def database(monkeypatch, tmp_path):
    dsn = os.getenv("BACKGROUND_TEST_DSN")
    if not dsn:
        pytest.skip("BACKGROUND_TEST_DSN must point to an isolated database")
    schema = "background_test_" + uuid4().hex
    with psycopg.connect(dsn) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    scoped = make_conninfo(dsn, options=f"-c search_path={schema}")
    monkeypatch.setenv("DATABASE_URI", scoped)
    monkeypatch.setenv("RUNTIME_EXECUTION_HOST_ID", "background-test")
    monkeypatch.setenv("RUNTIME_BACKGROUND_LOG_ROOT", str(tmp_path))
    upgrade()
    upgrade()
    try:
        yield scoped
    finally:
        with psycopg.connect(dsn) as connection:
            connection.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema))
            )


def identity(**overrides):
    return {
        "tenant_id": "tenant",
        "project_id": "project",
        "owner_id": "owner",
        "graph_id": "showcase_demo",
        "thread_id": str(uuid4()),
        "origin_run_id": str(uuid4()),
        "checkpoint_ns": "",
        "tool_call_id": "call",
        **overrides,
    }


def scope(value):
    return {**value, "assistant_id": value["graph_id"]}


def reserve(value):
    return repository.reserve_task(value, "binding", "request", "background-test", 300)


@pytest.mark.parametrize("status", ["running", "unknown", "succeeded"])
@pytest.mark.parametrize("backend", ["local", "docker"])
def test_start_replay_after_disabling_preserves_original_receipt(
    database, tmp_path, monkeypatch, status, backend
):
    values = identity()
    binding = BackgroundBinding(
        tmp_path,
        "python:3.13-slim",
        ("tenant", "project", values["thread_id"]),
        "showcase_demo",
    )
    bound = repository.digest(
        [
            str(binding.workspace),
            binding.image,
            str(binding.skills),
            binding.protected,
            binding.scope,
            binding.graph_id,
            "background-test",
        ]
    )
    request = repository.digest(["printf done", 30, bound])
    row, _ = repository.reserve_task(values, bound, request, "background-test", 30)
    repository.save(
        row,
        status=status,
        cleanup="unconfirmed" if status == "unknown" else "confirmed",
    )
    monkeypatch.setenv("RUNTIME_BACKGROUND_TASKS_ENABLED", "0")
    monkeypatch.setenv("RUNTIME_BACKEND", backend)
    monkeypatch.delenv("RUNTIME_EXECUTION_HOST_ID")
    reserve_call, create = Mock(), AsyncMock()
    monkeypatch.setattr(repository, "reserve_task", reserve_call)
    monkeypatch.setattr(service, "create_task_container", create)
    replay = asyncio.run(service.start_task(values, binding, "printf done", 30))
    assert replay["task_id"] == row["task_id"] and replay["status"] == status
    for changed, command, timeout in (
        (binding, "printf changed", 30),
        (binding, "printf done", 31),
        (replace(binding, workspace=tmp_path / "other"), "printf done", 30),
        (replace(binding, skills=tmp_path / "other-skills"), "printf done", 30),
        (replace(binding, protected=True), "printf done", 30),
    ):
        with pytest.raises(RuntimeWorkspaceError, match="idempotency_conflict"):
            asyncio.run(service.start_task(values, changed, command, timeout))
    with pytest.raises(BackgroundTaskNotStarted):
        asyncio.run(service.start_task(identity(), binding, "printf done", 30))
    reserve_call.assert_not_called()
    create.assert_not_awaited()


def test_replay_cancel_and_log_expiry_keep_receipts(database):
    values = identity()
    row, fresh = reserve(values)
    assert fresh
    assert reserve(values)[0]["task_id"] == row["task_id"]
    with pytest.raises(RuntimeWorkspaceError, match="idempotency_conflict"):
        repository.reserve_task(values, "binding", "different", "background-test", 300)
    saved = repository.save(
        row, status="succeeded", cleanup="confirmed", output=("done", 0, False), delay=0
    )
    assert saved["delivery_state"] == "pending" and output.read_output(saved) == "done"
    output.delete_output(saved)
    repository.expire_output(saved)
    replay = reserve(values)[0]
    assert replay["task_id"] == row["task_id"] and not replay["output_available"]
    cancelled = repository.request_cancel(scope(values), row["task_id"])
    repeated = repository.request_cancel(scope(values), row["task_id"])
    assert cancelled["status"] == repeated["status"] == "succeeded"
    assert repeated["delivery_state"] == "suppressed"
    assert (
        repository.read_task({**scope(values), "project_id": "other"}, row["task_id"])
        is None
    )


def test_disabled_start_after_source_stop_is_not_recoverable(database, monkeypatch):
    values = identity()
    facts = {
        "identity": "owner",
        "tenant_id": "tenant",
        "project_id": "project",
        "role": "developer",
        "runtime_scope": {**scope(values), "operation": "thread-stop"},
    }
    stop = request_stop(facts, values["thread_id"], "source-stop")
    with connect() as connection:
        connection.execute(
            "UPDATE runtime_stop_requests SET engine_receipt=%s::jsonb WHERE stop_id=%s",
            (
                json.dumps({"targets": [{"run_id": values["origin_run_id"]}]}),
                stop["stop_id"],
            ),
        )
    monkeypatch.setenv("RUNTIME_BACKEND", "local")
    monkeypatch.setenv("RUNTIME_BACKGROUND_TASKS_ENABLED", "0")
    with pytest.raises(RuntimeWorkspaceError, match="background_task_denied") as caught:
        asyncio.run(service.start_task(values, None, "printf done"))
    assert not isinstance(caught.value, BackgroundTaskNotStarted)


def test_container_cleanup_preserves_real_command_exit_code(database):
    values = identity()
    row, _ = reserve(values)
    repository.save(
        row, status="failed", cleanup="pending", state={"ExitCode": 124}, delay=0
    )
    claimed = repository.claim_due("background-test")
    saved = repository.save(
        claimed, status="failed", cleanup="confirmed", state={"ExitCode": 1}
    )
    assert saved["exit_code"] == 124


def test_terminal_intent_and_resource_receipt_rollback_together(database):
    values = identity()
    row, _ = reserve(values)
    with connect() as connection:
        connection.execute("""CREATE FUNCTION fail_resource_update() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'synthetic terminal commit fault'; END; $$;
        CREATE TRIGGER fail_resource_update BEFORE UPDATE ON runtime_run_resources FOR EACH ROW EXECUTE FUNCTION fail_resource_update()""")
    with pytest.raises(
        psycopg.errors.RaiseException, match="synthetic terminal commit fault"
    ):
        repository.save(row, status="succeeded", cleanup="confirmed", delay=0)
    retained = repository.read_task(scope(values), row["task_id"])
    assert (
        retained["status"] == "starting" and retained["delivery_state"] == "not_ready"
    )
    with connect() as connection:
        assert (
            connection.execute(
                "SELECT status FROM runtime_run_resources WHERE resource_id=%s",
                (row["resource_id"],),
            ).fetchone()["status"]
            == "active"
        )
        connection.execute("DROP TRIGGER fail_resource_update ON runtime_run_resources")
    saved = repository.save(row, status="succeeded", cleanup="confirmed", delay=0)
    assert saved["status"] == "succeeded" and saved["delivery_state"] == "pending"


def test_fork_and_checkpoint_namespace_do_not_adopt_old_task(database):
    values = identity()
    original, _ = reserve(values)
    for changes in (
        {"thread_id": str(uuid4())},
        {"origin_run_id": str(uuid4())},
        {"checkpoint_ns": "child:fork"},
    ):
        forked, fresh = reserve({**values, **changes})
        assert fresh and forked["task_id"] != original["task_id"]
        assert reserve({**values, **changes})[0]["task_id"] == forked["task_id"]
    assert reserve(values)[0]["task_id"] == original["task_id"]


def test_two_real_output_floods_keep_private_and_response_bytes_bounded(
    database, tmp_path, monkeypatch
):
    if os.getenv("BACKGROUND_DOCKER_TEST") != "1":
        pytest.skip("BACKGROUND_DOCKER_TEST=1 requires the managed test daemon")
    monkeypatch.setenv("RUNTIME_BACKGROUND_TASKS_ENABLED", "1")
    monkeypatch.setenv("RUNTIME_BACKEND", "docker")
    monkeypatch.setattr(
        service, "source_failed", lambda row: asyncio.sleep(0, result=False)
    )
    command = 'python3 -c \'import sys,time; sys.stdout.write("测试"*2000000+"TAIL"); sys.stdout.flush(); time.sleep(2)\''
    values = [identity(), identity()]
    bindings = [
        BackgroundBinding(
            tmp_path / str(index),
            "python:3.13-slim",
            (value["tenant_id"], value["project_id"], value["thread_id"]),
            "showcase_demo",
        )
        for index, value in enumerate(values)
    ]
    for binding in bindings:
        binding.workspace.mkdir()
    with output.directory():
        pass

    async def verify():
        rows = []
        try:
            rows = list(
                await asyncio.gather(
                    *(
                        service.start_task(value, binding, command, 60)
                        for value, binding in zip(values, bindings, strict=True)
                    )
                )
            )
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                for row in rows:
                    with connect() as connection:
                        connection.execute(
                            "UPDATE runtime_background_tasks SET next_check_at=now() WHERE task_id=%s",
                            (row["task_id"],),
                        )
                    await service.reconcile_due(row["task_id"])
                actual = [
                    repository.read_task(scope(value), row["task_id"])
                    for value, row in zip(values, rows, strict=True)
                ]
                if all(row["cleanup_state"] == "confirmed" for row in actual):
                    break
                await asyncio.sleep(0.5)
            for row in actual:
                assert (
                    row["status"] == "succeeded" and row["cleanup_state"] == "confirmed"
                )
                assert row["log_bytes"] <= 1048576 and row["omitted_bytes"] > 9000000
                for limit in (16384, 65536):
                    text = output.read_output(row, limit)
                    assert text.endswith("TAIL") and len(text.encode()) <= limit
            logs = list(tmp_path.rglob("*.log"))
            assert len(logs) == 2 and all(
                path.stat().st_size <= 1048576 for path in logs
            )
        finally:
            for row in rows:
                await stop_task_container(row)
                await remove_task_container(row)

    asyncio.run(verify())


def test_two_processes_cannot_exceed_thread_capacity(database):
    values = identity()
    payloads = [
        json.dumps(
            [
                {**values, "tool_call_id": str(index)}
                for index in range(offset, offset + 10)
            ]
        )
        for offset in (0, 10)
    ]
    script = "import json,sys; from runtime_service.background_tasks.repository import reserve_task; from runtime_service.runtime.errors import RuntimeWorkspaceError\nfor value in json.load(sys.stdin):\n try:\n  row,fresh=reserve_task(value,'binding','request','background-test',300); print(row['task_id'])\n except RuntimeWorkspaceError as exc:\n  print(exc.code)"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda payload: subprocess.run(
                    [sys.executable, "-c", script],
                    input=payload,
                    text=True,
                    capture_output=True,
                    timeout=180,
                ),
                payloads,
            )
        )
    assert all(value.returncode == 0 for value in results), [
        value.stderr for value in results
    ]
    assert (
        sum(
            "background_task_limit_reached" not in line
            for value in results
            for line in value.stdout.splitlines()
        )
        == 4
    )
    with connect() as connection:
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM runtime_background_tasks"
            ).fetchone()["n"]
            == 4
        )


@pytest.mark.parametrize("level,maximum", [("project", 8), ("host", 16)])
def test_project_and_host_capacity_keep_uncertain_resources_reserved(
    database, level, maximum
):
    values = identity()
    rows = []
    for index in range(maximum):
        row, _ = reserve(
            {
                **values,
                "thread_id": str(uuid4()),
                "project_id": "project" if level == "project" else str(uuid4()),
                "tool_call_id": str(index),
            }
        )
        rows.append(row)
    repository.save(rows[0], status="unknown", cleanup="unconfirmed")
    repository.request_cancel(scope(rows[1]), rows[1]["task_id"])
    candidate = {**values, "thread_id": str(uuid4()), "tool_call_id": "overflow"}
    with pytest.raises(RuntimeWorkspaceError, match="background_task_limit_reached"):
        reserve(candidate)
    repository.save(rows[2], status="cancelled", cleanup="confirmed")
    assert reserve(candidate)[1]


@pytest.mark.parametrize("boundary", ["create", "start"])
def test_real_docker_lost_control_ack_never_replays_command(
    database, tmp_path, monkeypatch, boundary
):
    if os.getenv("BACKGROUND_DOCKER_TEST") != "1":
        pytest.skip("BACKGROUND_DOCKER_TEST=1 requires the managed test daemon")
    monkeypatch.setenv("RUNTIME_BACKGROUND_TASKS_ENABLED", "1")
    monkeypatch.setenv("RUNTIME_BACKEND", "docker")
    operation = (
        "create_task_container" if boundary == "create" else "start_task_container"
    )
    original = getattr(service, operation)

    async def lose_ack(*args):
        await original(*args)
        raise RuntimeWorkspaceError("background_task_control_unavailable")

    monkeypatch.setattr(service, operation, lose_ack)
    monkeypatch.setattr(
        service, "source_failed", lambda row: asyncio.sleep(0, result=False)
    )
    values = identity()
    binding = BackgroundBinding(
        tmp_path,
        "python:3.13-slim",
        ("tenant", "project", values["thread_id"]),
        "showcase_demo",
    )
    command = "printf once >> counter.txt; printf DONE"

    async def verify():
        row = await service.start_task(values, binding, command, 30)
        try:
            assert row["status"] == "unknown"
            assert (await service.start_task(values, binding, command, 30))[
                "task_id"
            ] == row["task_id"]
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                with connect() as connection:
                    connection.execute(
                        "UPDATE runtime_background_tasks SET lease_until=NULL,next_check_at=now() WHERE task_id=%s",
                        (row["task_id"],),
                    )
                await service.reconcile_due(row["task_id"])
                if (
                    repository.read_task(scope(values), row["task_id"])["cleanup_state"]
                    == "confirmed"
                ):
                    break
                await asyncio.sleep(0.5)
            actual = repository.read_task(scope(values), row["task_id"])
            assert actual["cleanup_state"] == "confirmed"
            counter = tmp_path / "counter.txt"
            if boundary == "create":
                assert actual["status"] == "failed" and not counter.exists()
            else:
                assert actual["status"] == "succeeded" and counter.read_text() == "once"
        finally:
            await stop_task_container(row)
            await remove_task_container(row)

    asyncio.run(verify())


def test_daemon_connection_recovers_without_releasing_or_replaying_task(
    database, tmp_path, monkeypatch
):
    if os.getenv("BACKGROUND_DOCKER_TEST") != "1":
        pytest.skip("BACKGROUND_DOCKER_TEST=1 requires the managed test daemon")
    monkeypatch.setenv("RUNTIME_BACKGROUND_TASKS_ENABLED", "1")
    monkeypatch.setenv("RUNTIME_BACKEND", "docker")
    monkeypatch.setattr(
        service, "source_failed", lambda row: asyncio.sleep(0, result=False)
    )
    values = identity()
    binding = BackgroundBinding(
        tmp_path,
        "python:3.13-slim",
        ("tenant", "project", values["thread_id"]),
        "showcase_demo",
    )
    command = "printf once >> counter.txt; sleep 600"

    async def reconcile(row):
        with connect() as connection:
            connection.execute(
                "UPDATE runtime_background_tasks SET lease_until=NULL,next_check_at=now() WHERE task_id=%s",
                (row["task_id"],),
            )
        await service.reconcile_due(row["task_id"])

    async def verify():
        row = await service.start_task(values, binding, command, 900)
        try:
            assert row["status"] == "running"
            deadline = time.monotonic() + 15
            while not (tmp_path / "counter.txt").exists():
                assert time.monotonic() < deadline
                await asyncio.sleep(0.1)
            with monkeypatch.context() as unavailable:
                unavailable.setenv("DOCKER_HOST", "unix://" + str(tmp_path / "absent"))
                await reconcile(row)
                retained = repository.read_task(scope(values), row["task_id"])
                assert retained["cleanup_state"] == "pending"
                assert repository.list_tasks(scope(values))[1]
                assert (await service.start_task(values, binding, command, 900))[
                    "task_id"
                ] == row["task_id"]
            await reconcile(row)
            assert (
                repository.read_task(scope(values), row["task_id"])["status"]
                == "running"
            )
            assert (tmp_path / "counter.txt").read_text() == "once"
            repository.request_cancel(scope(values), row["task_id"])
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                await reconcile(row)
                actual = repository.read_task(scope(values), row["task_id"])
                if actual["cleanup_state"] == "confirmed":
                    break
                await asyncio.sleep(0.5)
            assert (
                actual["status"] == "cancelled"
                and actual["cleanup_state"] == "confirmed"
            )
            assert (tmp_path / "counter.txt").read_text() == "once"
        finally:
            await stop_task_container(row)
            await remove_task_container(row)

    asyncio.run(verify())


def test_host_sixteen_real_tasks_and_no_model_cleanup(database, tmp_path, monkeypatch):
    if os.getenv("BACKGROUND_DOCKER_TEST") != "1":
        pytest.skip("BACKGROUND_DOCKER_TEST=1 requires the managed test daemon")
    monkeypatch.setenv("RUNTIME_BACKGROUND_TASKS_ENABLED", "1")
    monkeypatch.setenv("RUNTIME_BACKEND", "docker")
    monkeypatch.setattr(
        service, "source_failed", lambda row: asyncio.sleep(0, result=False)
    )
    values = [identity(project_id=str(uuid4())) for _ in range(20)]
    binding = BackgroundBinding(
        tmp_path, "python:3.13-slim", ("test", "test", "test"), "showcase_demo"
    )

    async def verify():
        results = await asyncio.gather(
            *(service.start_task(value, binding, "sleep 600", 900) for value in values),
            return_exceptions=True,
        )
        rows = [value for value in results if isinstance(value, dict)]
        try:
            assert len(rows) == 16
            rejected = [value for value in results if isinstance(value, Exception)]
            assert len(rejected) == 4 and all(
                isinstance(value, RuntimeWorkspaceError)
                and value.code == "background_task_limit_reached"
                for value in rejected
            )
            owned = subprocess.run(
                [
                    "docker",
                    "ps",
                    "-q",
                    "--filter",
                    "label=runtime.background.host=background-test",
                ],
                capture_output=True,
                text=True,
                timeout=15,
            )
            assert owned.returncode == 0 and len(owned.stdout.split()) == 16
            for row in rows:
                repository.request_source_cancel(row)
            for _ in range(2):
                with connect() as connection:
                    connection.execute(
                        "UPDATE runtime_background_tasks SET lease_until=NULL,next_check_at=now()"
                    )
                await asyncio.gather(
                    *(service.reconcile_due(row["task_id"]) for row in rows)
                )
            assert all(
                repository.read_task(scope(row), row["task_id"])["cleanup_state"]
                == "confirmed"
                for row in rows
            )
            print(
                json.dumps(
                    {
                        "concurrent_tasks": 16,
                        "rejected": 4,
                        "cleanup_confirmed": 16,
                        "model_calls": 0,
                    }
                )
            )
        finally:
            await asyncio.gather(*(stop_task_container(row) for row in rows))
            await asyncio.gather(*(remove_task_container(row) for row in rows))

    asyncio.run(verify())


def test_fence_rejects_late_facts_and_late_log_publication(database, monkeypatch):
    values = identity()
    row, _ = reserve(values)
    write = output.write_output
    current = []

    def delayed_write(old, snapshot):
        with connect() as connection:
            connection.execute(
                "UPDATE runtime_background_tasks SET lease_until=now()-interval '1 second'"
            )
        new = repository.claim_due("background-test")
        current.append(
            repository.save(
                new, status="running", cleanup="pending", output=("new fence", 0, False)
            )
        )
        write(old, snapshot)

    monkeypatch.setattr(output, "write_output", delayed_write)

    # Restore around the newer save so only the deliberately stale observer is delayed.
    def once(old, snapshot):
        monkeypatch.setattr(output, "write_output", write)
        delayed_write(old, snapshot)

    monkeypatch.setattr(output, "write_output", once)
    assert (
        repository.save(
            row, status="succeeded", cleanup="confirmed", output=("old fence", 0, False)
        )
        is None
    )
    actual = repository.read_task(scope(values), row["task_id"])
    assert actual["status"] == "running" and actual["log_fence"] > row["fence"]
    assert output.read_output(actual) == "new fence"
    assert not repository.renew(row)
    assert repository.finish_delivery(row, "accepted", run_id=str(uuid4())) is None


def test_stop_snapshot_suppresses_only_existing_tasks(database):
    values = identity()
    row, _ = reserve(values)
    facts = {
        "identity": "owner",
        "tenant_id": "tenant",
        "project_id": "project",
        "role": "developer",
        "runtime_scope": {**scope(values), "operation": "thread-stop"},
    }
    stop = request_stop(facts, values["thread_id"], "fixed-stop")
    assert stop["background_task_ids"] == [str(row["task_id"])]
    assert stop["background_event_ids"] == [str(row["event_id"])]
    assert (
        repository.completion_allowed(row["task_id"], row["event_id"], str(uuid4()))
        is None
    )
    repeated = request_stop(facts, values["thread_id"], "fixed-stop")
    later, _ = reserve(
        {**values, "origin_run_id": str(uuid4()), "tool_call_id": "later"}
    )
    assert repeated["stop_id"] == stop["stop_id"]
    assert repository.read_task(scope(values), later["task_id"])["stop_id"] is None
    cancelled = repository.request_cancel(scope(values), later["task_id"])
    again = repository.request_cancel(scope(values), later["task_id"])
    assert again["cancel_requested_at"] == cancelled["cancel_requested_at"]
    assert again["status"] == "cancel_requested"


def test_stop_waits_for_inflight_receipt_and_late_run_cleanup(database):
    values = identity()
    row, _ = reserve(values)
    repository.save(row, status="succeeded", cleanup="confirmed", delay=0)
    claimed = repository.claim_due("background-test")
    dispatching = repository.delivery_intent(claimed)
    assert dispatching["delivery_inflight"]
    facts = {
        "identity": "owner",
        "tenant_id": "tenant",
        "project_id": "project",
        "role": "developer",
        "runtime_scope": {**scope(values), "operation": "thread-stop"},
    }
    stop = request_stop(facts, values["thread_id"], "stop-inflight")
    assert (
        repository.background_summary(stop["background_task_ids"])[
            "cleanup_unconfirmed_count"
        ]
        == 1
    )
    run_id = str(uuid4())
    bound = repository.bind_completion_run(row["task_id"], row["event_id"], run_id)
    assert bound["delivery_run_id"] == run_id and not bound["delivery_inflight"]
    assert (
        repository.completion_allowed(row["task_id"], row["event_id"], run_id) is None
    )
    assert (
        repository.background_summary(stop["background_task_ids"])[
            "cleanup_unconfirmed_count"
        ]
        == 1
    )
    repository.confirm_delivery_cancel(bound)
    assert (
        repository.background_summary(stop["background_task_ids"])[
            "cleanup_confirmed_count"
        ]
        == 1
    )
    assert (
        repository.bind_completion_run(row["task_id"], row["event_id"], str(uuid4()))
        is None
    )


def test_delivery_reconcile_after_stop_keeps_suppressed_and_rejects_changed_run(
    database,
):
    values = identity()
    row, _ = reserve(values)
    repository.save(row, status="succeeded", cleanup="confirmed", delay=0)
    claimed = repository.claim_due("background-test")
    repository.delivery_intent(claimed)
    facts = {
        "identity": "owner",
        "tenant_id": "tenant",
        "project_id": "project",
        "role": "developer",
        "runtime_scope": {**scope(values), "operation": "thread-stop"},
    }
    stop = request_stop(facts, values["thread_id"], "lost-ack-stop")
    run_id = str(uuid4())
    restored = repository.finish_delivery(claimed, "accepted", run_id=run_id, retry=0)
    assert restored["delivery_state"] == "suppressed"
    assert restored["delivery_run_id"] == run_id and not restored["delivery_inflight"]
    assert not restored["delivery_cancel_confirmed"]
    assert (
        repository.background_summary(stop["background_task_ids"])[
            "cleanup_unconfirmed_count"
        ]
        == 1
    )
    claimed = repository.claim_due("background-test")
    assert repository.finish_delivery(claimed, "accepted", run_id=str(uuid4())) is None
    assert (
        repository.read_task(scope(values), row["task_id"])["delivery_run_id"] == run_id
    )
    repository.confirm_delivery_cancel(restored)
    assert (
        repository.background_summary(stop["background_task_ids"])[
            "cleanup_confirmed_count"
        ]
        == 1
    )


def test_scope_pagination_and_global_flags_do_not_depend_on_page(database):
    values = identity()
    first, _ = reserve(values)
    repository.save(first, status="succeeded", cleanup="confirmed", delay=0)
    claim = repository.claim_due("background-test")
    run_id = str(uuid4())
    repository.finish_delivery(claim, "accepted", run_id=run_id)
    second, _ = reserve(
        {**values, "origin_run_id": str(uuid4()), "tool_call_id": "second"}
    )
    rows, unresolved, latest = repository.list_tasks(scope(values), 1)
    assert rows[0]["task_id"] == second["task_id"] and unresolved and latest == run_id
    before = [rows[0]["created_at"].isoformat(), str(rows[0]["task_id"])]
    older, unresolved, latest = repository.list_tasks(scope(values), 1, before)
    assert older[0]["task_id"] == first["task_id"] and unresolved and latest == run_id
    assert repository.list_tasks({**scope(values), "assistant_id": "other"}, 1) == (
        [],
        False,
        None,
    )


def test_receipt_preserving_migration_round_trip(database):
    from pathlib import Path

    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    from runtime_service import db

    values = identity()
    row, _ = reserve(values)
    config = Config()
    config.set_main_option(
        "script_location", str(Path(db.__file__).with_name("migrations"))
    )
    engine = create_engine(
        "postgresql+psycopg://",
        creator=lambda: psycopg.connect(database),
        poolclass=NullPool,
    )
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "0002_run_control")
        assert (
            repository.read_task(scope(values), row["task_id"])["submission_key"]
            == row["submission_key"]
        )
        upgrade()
        assert reserve(values)[0]["task_id"] == row["task_id"]
        with connect() as connection:
            assert (
                connection.execute(
                    "SELECT version_num FROM runtime_app_alembic_version"
                ).fetchone()["version_num"]
                == "0003_background_tasks"
            )
    finally:
        engine.dispose()


def test_ten_thousand_receipts_keep_due_and_scope_queries_indexed(database):
    values = identity()
    with connect() as connection:
        connection.execute(
            """INSERT INTO runtime_background_tasks(task_id,tenant_id,project_id,owner_id,graph_id,thread_id,origin_run_id,checkpoint_ns,tool_call_id,submission_key,request_digest,execution_host_id,container_name,binding_digest,runner_secret,resource_id,deadline_at,event_id,status,cleanup_state,log_reserved,delivery_state,delivery_run_id,delivery_accepted_at,created_at)
        SELECT gen_random_uuid(),'tenant','project','owner','showcase_demo',%s,gen_random_uuid()::text,'','history-'||g,md5(g::text),'request','background-test','history-'||g,'binding','secret',gen_random_uuid(),now(),gen_random_uuid(),'succeeded','confirmed',false,'accepted',gen_random_uuid()::text,now()-g*interval '1 second',now()-g*interval '1 second'
        FROM generate_series(1,10000) AS g""",
            (values["thread_id"],),
        )
        connection.execute("ANALYZE runtime_background_tasks")
    active, _ = reserve(values)
    timings = []
    for _ in range(10):
        started = time.monotonic()
        rows, unresolved, latest = repository.list_tasks(scope(values), 20)
        timings.append((time.monotonic() - started) * 1000)
        assert len(rows) == 21 and unresolved and latest
    with connect() as connection:
        due = connection.execute(
            f"EXPLAIN (FORMAT JSON) SELECT task_id FROM runtime_background_tasks WHERE execution_host_id='background-test' AND {repository.UNRESOLVED} AND next_check_at<=now() ORDER BY next_check_at LIMIT 1"
        ).fetchone()["QUERY PLAN"]
        assert "runtime_background_due" in json.dumps(due)
    assert repository.claim_due("background-test") is None
    assert (
        repository.read_task(scope(values), active["task_id"])["status"] == "starting"
    )
    print(
        json.dumps(
            {
                "history_rows": 10000,
                "list_p50_ms": sorted(timings)[5],
                "list_max_ms": max(timings),
            }
        )
    )
