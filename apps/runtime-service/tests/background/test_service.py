"""Reconciliation decisions preserve uncertainty and avoid model polling."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import httpx
import pytest

from runtime_service.background_tasks import delivery, service
from runtime_service.runtime.errors import (
    BackgroundTaskNotStarted,
    RuntimeWorkspaceError,
)
from runtime_service.tools.errors import tool_error_content


def task(**changes):
    return {
        "task_id": uuid4(),
        "event_id": uuid4(),
        "thread_id": str(uuid4()),
        "origin_run_id": str(uuid4()),
        "status": "running",
        "cancel_requested_at": None,
        "stop_id": None,
        "container_id": "container",
        "runner_secret": "secret",
        "cleanup_state": "pending",
        "delivery_state": "not_ready",
        "delivery_run_id": None,
        "delivery_cancel_confirmed": False,
        "deadline_at": datetime.now(UTC) + timedelta(minutes=1),
        "notification_deadline_at": datetime.now(UTC) + timedelta(days=1),
        "delivery_attempts": 0,
        "tenant_id": "tenant",
        "project_id": "project",
        "owner_id": "owner",
        "credential_id": None,
        "graph_id": "showcase_demo",
        "exit_code": None,
        **changes,
    }


@pytest.mark.parametrize(
    "command,timeout",
    [
        ("", 1),
        (" " * 5, 1),
        ("x" * 32769, 1),
        ("printf done", True),
        ("printf done", 0),
        ("printf done", 3601),
    ],
)
def test_invalid_submission_has_no_storage_or_container_side_effects(
    command, timeout, monkeypatch
):
    reserve = Mock()
    create = AsyncMock()
    monkeypatch.setattr(service.repository, "reserve_task", reserve)
    monkeypatch.setattr(service, "create_task_container", create)
    with pytest.raises(ValueError):
        asyncio.run(service.start_task({}, None, command, timeout))
    reserve.assert_not_called()
    create.assert_not_awaited()


@pytest.mark.parametrize(
    "running,receipt,oom,status,reason",
    [
        (True, None, False, "running", None),
        (False, {"outcome": 0, "exit_code": 0}, False, "succeeded", None),
        (
            False,
            {"outcome": 1, "exit_code": 124},
            False,
            "failed",
            "background_task_command_failed",
        ),
        (
            False,
            {"outcome": 1, "exit_code": 137},
            False,
            "failed",
            "background_task_command_failed",
        ),
        (
            False,
            {"outcome": 20, "exit_code": -9},
            False,
            "timed_out",
            "background_task_deadline_exceeded",
        ),
        (False, None, True, "failed", "background_task_oom"),
    ],
)
def test_observation_uses_signed_runner_receipt_and_container_facts(
    monkeypatch, running, receipt, oom, status, reason
):
    save = Mock(side_effect=lambda row, **kwargs: kwargs)
    monkeypatch.setattr(service.repository, "save", save)
    monkeypatch.setattr(
        service, "read_task_output", AsyncMock(return_value=("done", 0, False))
    )
    monkeypatch.setattr(service, "read_task_receipt", AsyncMock(return_value=receipt))
    state = {
        "id": "container",
        "Running": running,
        "Status": "running" if running else "exited",
        "ExitCode": receipt["outcome"] if receipt else 137,
        "OOMKilled": oom,
    }
    result = asyncio.run(service._observe(task(), state))
    assert result["status"] == status
    assert result.get("reason") == reason
    assert result["cleanup"] == "pending"


def test_missing_container_is_unknown_and_never_restarted(monkeypatch):
    monkeypatch.setattr(
        service.repository, "save", Mock(side_effect=lambda row, **kwargs: kwargs)
    )
    start = AsyncMock()
    monkeypatch.setattr(service, "start_task_container", start)
    result = asyncio.run(service._observe(task(), None))
    assert result["status"] == "unknown"
    assert result["cleanup"] == "unconfirmed"
    assert result["reason"] == "background_task_resource_missing"
    start.assert_not_awaited()


def test_stop_cancels_late_run_and_still_cleans_container(monkeypatch):
    late = AsyncMock()
    stop = AsyncMock(
        return_value={
            "id": "container",
            "Running": False,
            "Status": "exited",
            "ExitCode": 1,
        }
    )
    observe = AsyncMock()
    row = task(
        stop_id=uuid4(),
        delivery_run_id=str(uuid4()),
        cancel_requested_at=datetime.now(UTC),
    )
    monkeypatch.setattr(service, "cancel_completion_run", late)
    monkeypatch.setattr(
        service, "inspect_task_container", AsyncMock(return_value={"Running": True})
    )
    monkeypatch.setattr(service, "stop_task_container", stop)
    monkeypatch.setattr(service, "_observe", observe)
    asyncio.run(service._reconcile(row))
    late.assert_awaited_once_with(row)
    stop.assert_awaited_once_with(row)
    observe.assert_awaited_once()


def test_source_failure_suppresses_completed_notification(monkeypatch):
    row = task(status="succeeded", cleanup_state="confirmed", delivery_state="pending")
    monkeypatch.setattr(service, "source_failed", AsyncMock(return_value=True))
    cancel = Mock()
    finish = Mock()
    notify = AsyncMock()
    monkeypatch.setattr(service.repository, "request_source_cancel", cancel)
    monkeypatch.setattr(service.repository, "finish_delivery", finish)
    monkeypatch.setattr(delivery, "deliver_completion", notify)
    asyncio.run(service._reconcile(row))
    cancel.assert_called_once_with(row)
    assert finish.call_args.args[1] == "suppressed"
    notify.assert_not_awaited()


@pytest.mark.parametrize("state", ["unknown", "dispatching"])
def test_uncertain_acceptance_reconciles_before_current_acl(monkeypatch, state):
    row = task(status="succeeded", cleanup_state="confirmed", delivery_state=state)
    source = AsyncMock(side_effect=AssertionError("receipt recovery used current ACL"))
    notify = AsyncMock()
    monkeypatch.setattr(service, "source_failed", source)
    monkeypatch.setattr(delivery, "deliver_completion", notify)
    asyncio.run(service._reconcile(row))
    source.assert_not_awaited()
    notify.assert_awaited_once_with(row)


@pytest.mark.parametrize(
    "reason,failed",
    [("hitl_interrupt", False), ("cancel_requested", True), ("rollback", True)],
)
def test_source_interrupted_reason_uses_real_sdk_and_does_not_cancel_hitl(
    reason, failed, monkeypatch
):
    original = httpx.AsyncClient

    def respond(request):
        if request.url.path.endswith("/stream"):
            assert request.headers["Last-Event-ID"] == "0"
            return httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                text="event: lifecycle\ndata: "
                + json.dumps({"status": "interrupted", "reason": reason})
                + "\n\n",
            )
        return httpx.Response(200, json={"status": "interrupted"})

    monkeypatch.setattr(
        service.httpx,
        "AsyncClient",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(respond)),
    )
    monkeypatch.setattr(service, "engine_url", lambda: "http://isolated-test.invalid")
    monkeypatch.setattr(
        service, "native_headers", lambda *args: {"Authorization": "synthetic"}
    )
    assert asyncio.run(service.source_failed(task())) is failed


def test_control_response_loss_preserves_unknown_submission(monkeypatch):
    row = task()
    create = AsyncMock(
        side_effect=RuntimeWorkspaceError("background_task_control_unavailable")
    )
    monkeypatch.setenv("RUNTIME_BACKGROUND_TASKS_ENABLED", "1")
    monkeypatch.setenv("RUNTIME_EXECUTION_HOST_ID", "test-host")
    monkeypatch.setenv("RUNTIME_BACKEND", "docker")
    monkeypatch.setenv("DATABASE_URI", "isolated-test-only")
    monkeypatch.setattr(service, "check_space", Mock())
    monkeypatch.setattr(service.repository, "read_submission", Mock(return_value=None))
    monkeypatch.setattr(
        service.repository, "reserve_task", Mock(return_value=(row, True))
    )
    monkeypatch.setattr(service, "create_task_container", create)
    monkeypatch.setattr(
        service.repository, "save", Mock(return_value={**row, "status": "unknown"})
    )
    binding = Mock(
        workspace="workspace",
        image="image",
        skills=None,
        protected=False,
        scope=("tenant", "project", "thread"),
        graph_id="showcase_demo",
    )
    result = asyncio.run(service.start_task({}, binding, "printf done"))
    assert result["status"] == "unknown"


def test_cancelled_start_records_late_resource_cleanup_and_propagates(monkeypatch):
    row = task()
    monkeypatch.setenv("RUNTIME_BACKGROUND_TASKS_ENABLED", "1")
    monkeypatch.setenv("RUNTIME_EXECUTION_HOST_ID", "test-host")
    monkeypatch.setenv("RUNTIME_BACKEND", "docker")
    monkeypatch.setenv("DATABASE_URI", "isolated-test-only")
    monkeypatch.setattr(service, "check_space", Mock())
    monkeypatch.setattr(service.repository, "read_submission", Mock(return_value=None))
    monkeypatch.setattr(
        service.repository, "reserve_task", Mock(return_value=(row, True))
    )
    cleanup = Mock()
    monkeypatch.setattr(service.repository, "request_source_cancel", cleanup)
    binding = Mock(
        workspace="workspace",
        image="image",
        skills=None,
        protected=False,
        scope=("tenant", "project", "thread"),
        graph_id="showcase_demo",
    )

    async def verify():
        entered, release = asyncio.Event(), asyncio.Event()

        async def create(*args):
            entered.set()
            await release.wait()
            return {"id": "late-container"}

        start = AsyncMock(return_value={"Running": True})
        observe = AsyncMock(return_value=row)
        monkeypatch.setattr(service, "create_task_container", create)
        monkeypatch.setattr(service, "start_task_container", start)
        monkeypatch.setattr(service, "_observe", observe)
        pending = asyncio.create_task(service.start_task({}, binding, "sleep 60", 90))
        await entered.wait()
        pending.cancel()
        await asyncio.sleep(0)
        assert not pending.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await pending
        start.assert_awaited_once()
        observe.assert_awaited_once()
        cleanup.assert_called_once_with(row)
        assert row["container_id"] == "late-container"

    asyncio.run(verify())


@pytest.mark.parametrize(
    "backend,enabled,host,code",
    [
        ("local", "1", "test-host", "background_task_not_supported"),
        ("docker", "0", "test-host", "background_task_disabled"),
        ("docker", "1", "", "background_task_not_supported"),
    ],
)
def test_only_confirmed_absent_submission_can_recover(
    backend, enabled, host, code, monkeypatch
):
    monkeypatch.setenv("DATABASE_URI", "isolated-test-only")
    monkeypatch.setenv("RUNTIME_BACKEND", backend)
    monkeypatch.setenv("RUNTIME_BACKGROUND_TASKS_ENABLED", enabled)
    monkeypatch.setenv("RUNTIME_EXECUTION_HOST_ID", host)
    read = Mock(return_value=None)
    reserve, create = Mock(), AsyncMock()
    monkeypatch.setattr(service.repository, "read_submission", read)
    monkeypatch.setattr(service.repository, "reserve_task", reserve)
    monkeypatch.setattr(service, "create_task_container", create)
    with pytest.raises(BackgroundTaskNotStarted) as error:
        asyncio.run(service.start_task({}, None, "sleep 300", 300))
    assert error.value.code == code
    payload = json.loads(tool_error_content(error.value, "background_execute"))
    assert payload["code"] == code and payload["outcome"] == "not_started"
    assert "最大60秒" in payload["error"] and "长任务请拆分" in payload["error"]
    read.assert_called_once_with({})
    reserve.assert_not_called()
    create.assert_not_awaited()


@pytest.mark.parametrize(
    "error",
    [
        RuntimeWorkspaceError("background_task_not_supported"),
        RuntimeWorkspaceError("background_task_disabled"),
        RuntimeWorkspaceError("background_task_idempotency_conflict"),
        RuntimeError("storage unavailable"),
        asyncio.CancelledError(),
    ],
)
def test_receipt_read_failure_is_never_not_started(error, monkeypatch):
    monkeypatch.setenv("DATABASE_URI", "isolated-test-only")
    monkeypatch.setenv("RUNTIME_BACKEND", "local")
    reserve = Mock()
    monkeypatch.setattr(service.repository, "read_submission", Mock(side_effect=error))
    monkeypatch.setattr(service.repository, "reserve_task", reserve)
    with pytest.raises(type(error)) as caught:
        asyncio.run(service.start_task({}, None, "printf done"))
    assert caught.value is error
    assert tool_error_content(error, "background_execute") is None
    reserve.assert_not_called()


def test_missing_storage_does_not_claim_no_previous_submission(monkeypatch):
    monkeypatch.delenv("DATABASE_URI", raising=False)
    read = Mock()
    monkeypatch.setattr(service.repository, "read_submission", read)
    with pytest.raises(RuntimeWorkspaceError) as caught:
        asyncio.run(service.start_task({}, None, "printf done"))
    assert tool_error_content(caught.value, "background_execute") is None
    read.assert_not_called()


def test_local_startup_without_background_storage_never_probes_resources(monkeypatch):
    monkeypatch.setenv("RUNTIME_BACKEND", "local")
    monkeypatch.setenv("RUNTIME_BACKGROUND_TASKS_ENABLED", "1")
    monkeypatch.delenv("DATABASE_URI", raising=False)
    monkeypatch.delenv("RUNTIME_EXECUTION_HOST_ID", raising=False)
    loop, space = AsyncMock(), Mock()
    monkeypatch.setattr(service, "_loop", loop)
    monkeypatch.setattr(service, "check_space", space)

    async def start():
        async with service.background_tasks_lifespan():
            pass

    asyncio.run(start())
    loop.assert_not_awaited()
    space.assert_not_called()


def test_uncertain_delivery_after_deadline_only_queries_original_receipt(monkeypatch):
    row = task(
        status="succeeded",
        delivery_state="unknown",
        notification_deadline_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    monkeypatch.setattr(delivery.repository, "delivery_intent", Mock(return_value=row))
    finish = Mock()
    monkeypatch.setattr(delivery.repository, "finish_delivery", finish)
    callback = AsyncMock(
        return_value={
            "state": "unknown",
            "run_id": None,
            "reason_code": "background_task_delivery_unavailable",
        }
    )
    monkeypatch.setattr(delivery, "callback", callback)
    asyncio.run(delivery.deliver_completion(row))
    assert callback.await_args.args[1]["reconcile_only"] is True
    assert callback.await_args.args[1]["event_id"] == str(row["event_id"])
    assert finish.call_args.args[1] == "unknown"


def test_startup_can_reconcile_at_full_log_capacity(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URI", "isolated-test-only")
    monkeypatch.setenv("RUNTIME_EXECUTION_HOST_ID", "full-log-test")
    monkeypatch.setenv("RUNTIME_BACKGROUND_LOG_ROOT", str(tmp_path))
    check = Mock(
        side_effect=RuntimeWorkspaceError("background_task_log_capacity_reached")
    )
    monkeypatch.setattr(service, "check_space", check)

    async def loop():
        await asyncio.Event().wait()

    monkeypatch.setattr(service, "_loop", loop)

    async def start():
        async with service.background_tasks_lifespan():
            pass

    asyncio.run(start())
    check.assert_not_called()
