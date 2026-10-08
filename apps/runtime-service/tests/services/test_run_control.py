"""Stop boundaries, recovery leases and evidence against isolated PostgreSQL."""

import asyncio
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import psycopg
import pytest
from langchain_core.messages import AIMessage, ToolMessage
from psycopg import sql
from psycopg.conninfo import make_conninfo

from runtime_service.db import connect
from runtime_service.messaging import MessageInbox
from runtime_service.run_control import repository, resources, service
from runtime_service.run_control.authorization import cancellation_context_hash
from runtime_service.run_control.report import build_report, safe_label


@pytest.fixture
def inbox(monkeypatch):
    dsn = os.environ.get("RUNTIME_MESSAGE_TEST_DSN")
    if not dsn:
        pytest.skip("RUNTIME_MESSAGE_TEST_DSN must point to an isolated database")
    schema = "stop_test_" + uuid4().hex
    with psycopg.connect(dsn) as c:
        c.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    value = MessageInbox(make_conninfo(dsn, options=f"-c search_path={schema}"))
    value.initialize()
    monkeypatch.setenv("DATABASE_URI", value.dsn)
    try:
        yield value
    finally:
        with psycopg.connect(dsn) as c:
            c.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def facts(thread):
    return {
        "identity": "owner",
        "tenant_id": "tenant",
        "project_id": "project",
        "role": "developer",
        "runtime_scope": {
            "tenant_id": "tenant",
            "project_id": "project",
            "thread_id": thread,
            "assistant_id": "probe",
            "operation": "thread-stop",
        },
        "token": "DO-NOT-STORE",
        "runtime_policy": {"allowed_model_ids": ["private-model"]},
    }


def put(inbox, thread, run):
    return inbox.enqueue(
        thread_id=thread,
        target_run_id=run,
        sender_id="owner",
        client_message_id=str(uuid4()),
        idempotency_key=uuid4().hex,
        content="private message",
    )


def test_idempotency_barrier_lease_fence_and_new_run(inbox):
    thread, run, new = str(uuid4()), str(uuid4()), str(uuid4())
    message = put(inbox, thread, run)
    row = repository.request_stop(facts(thread), thread, "same")
    assert (
        row["inbox_run_ids"] == [run]
        and "token" not in row["auth_facts"]
        and "runtime_policy" not in row["auth_facts"]
    )
    assert (
        repository.request_stop(facts(thread), thread, "same")["stop_id"]
        == row["stop_id"]
    )
    with pytest.raises(ValueError, match="thread_stopping"):
        put(inbox, thread, run)
    assert inbox.claim(thread_id=thread, target_run_id=run, owner="worker")[1] == []
    assert put(inbox, thread, new).status == "queued"
    assert len(inbox.claim(thread_id=thread, target_run_id=new, owner="worker")[1]) == 1
    old = repository.claim_stop(row["stop_id"])
    assert repository.claim_stop(row["stop_id"]) is None
    assert repository.renew_stop(old)
    with connect() as c:
        c.execute(
            "UPDATE runtime_stop_requests SET lease_until=now()-interval '1 second' WHERE stop_id=%s",
            (row["stop_id"],),
        )
    claimed = repository.claim_stop(row["stop_id"])
    assert claimed["lease_token"] != old["lease_token"]
    assert repository.save_stop(old, phase="rejected") is None
    receipt = {
        "accepted_at": datetime.now(UTC).isoformat(),
        "targets": [{"run_id": run}],
        "reconcile_run_ids": [],
        "target_count": 1,
        "execution_stopped": True,
        "pending_cancelled_count": 0,
        "has_pending_interrupts": False,
    }
    repository.save_stop(claimed, phase="stopping", receipt=receipt)
    assert put(inbox, thread, new).status == "queued"
    assert (
        inbox.list(thread_id=thread, sender_id="owner")[-1].message_id
        == message.message_id
    )
    assert (
        repository.read_stop(
            {**facts(thread)["runtime_scope"], "project_id": "other"}, row["stop_id"]
        )
        is None
    )


def test_report_fixed_run_bounded_safe_and_artifact(inbox):
    thread, run = str(uuid4()), str(uuid4())
    digest = "a" * 64
    inherited = ToolMessage(
        content="secret inherited", tool_call_id="old", name="old", id="old"
    )
    messages = [
        inherited,
        ToolMessage(
            content=json.dumps(
                {
                    "version": 1,
                    "sha256": digest,
                    "path": "/workspace/outputs/" + digest + ".txt",
                }
            ),
            tool_call_id="publish",
            name="present_artifacts",
            id="published",
        ),
    ]
    messages += [
        ToolMessage(
            content="Bearer private",
            tool_call_id=str(i),
            name="execute",
            id="tool-" + str(i),
        )
        for i in range(15)
    ]

    class Saver:
        async def alist(self, config, filter=None, limit=None):
            assert (
                config["configurable"]["thread_id"] == thread
                and filter["run_id"] == run
                and limit == 1
            )
            values = (
                {"messages": [inherited]}
                if filter["source"] == "input"
                else {
                    "messages": messages,
                    "todos": [{"content": "api_key=SECRET", "status": "completed"}]
                    * 25,
                }
            )
            yield SimpleNamespace(
                checkpoint={
                    "channel_values": values,
                    "ts": datetime.now(UTC).isoformat(),
                },
                config={"configurable": {"checkpoint_id": "saved-checkpoint"}},
            )

    row = {
        "thread_id": thread,
        "engine_receipt": {"targets": [{"run_id": run}], "pending_cancelled_count": 0},
    }
    report = asyncio.run(build_report(row, Saver()))
    assert report["truncated"] and len(report["progress"]) == 30
    assert all(
        p["label"] == "[redacted]"
        for p in report["progress"]
        if p["kind"] == "saved_plan"
    )
    assert report["artifacts"][0]["path"].endswith(digest + ".txt")
    assert "old" not in [p["label"] for p in report["progress"]]
    assert "Bearer" not in str(report) and "SECRET" not in str(report)


@pytest.mark.parametrize(
    "label",
    [
        "read `/private/cache/session.txt`",
        "write /tmp/session.txt",
        "source=/mnt/session.txt",
        "open /etc/credentials",
        r"open C:\Users\private.txt",
        "open C:/Temp/session.txt",
        "visit https://private.example/result",
        "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJwcml2YXRlIn0.synthetic-signature",
    ],
)
def test_report_labels_redact_host_paths(label):
    assert safe_label(label) == "[redacted]"
    assert (
        safe_label("write /workspace/outputs/report.txt")
        == "write /workspace/outputs/report.txt"
    )
    assert safe_label("a" * 300) == "a" * 256


def test_report_in_flight_tool_marks_external_effect_unknown(inbox):
    thread, run = str(uuid4()), str(uuid4())

    class Saver:
        async def alist(self, config, filter=None, limit=None):
            yield SimpleNamespace(
                checkpoint={
                    "channel_values": {
                        "messages": []
                        if filter["source"] == "input"
                        else [
                            AIMessage(
                                content="",
                                id="submitted",
                                tool_calls=[
                                    {
                                        "id": "call",
                                        "name": "deploy_preview",
                                        "args": {"secret": "PRIVATE"},
                                    }
                                ],
                            ),
                        ]
                    },
                    "ts": datetime.now(UTC).isoformat(),
                },
                config={"configurable": {"checkpoint_id": "submitted-checkpoint"}},
            )

    report = asyncio.run(
        build_report(
            {
                "thread_id": thread,
                "engine_receipt": {
                    "targets": [{"run_id": run}],
                    "pending_cancelled_count": 0,
                },
            },
            Saver(),
        )
    )
    assert "external_effect_unknown" in report["uncertainties"]
    assert report["progress"] == [] and "PRIVATE" not in json.dumps(report)


def test_deployment_cancel_retains_unknown_receipt_without_resubmit(inbox, monkeypatch):
    import hashlib

    import httpx

    from runtime_service.services.dearflow_agent.external_task_storage import (
        ExternalTaskStorage,
    )
    from runtime_service.services.dearflow_agent.tools import deployment

    raw = b"synthetic-approved-package"
    digest = hashlib.sha256(raw).hexdigest()
    monkeypatch.setenv("RUNTIME_DEAR_PREVIEW_DEPLOY_ENABLED", "1")
    monkeypatch.setattr(
        deployment,
        "ArtifactWorkspace",
        lambda root: SimpleNamespace(
            read=lambda path: (raw, {"mime_type": "application/zip"})
        ),
    )
    monkeypatch.setattr(deployment, "deployment_package", lambda raw, files: raw)
    monkeypatch.setattr(
        deployment, "memory_scope", lambda runtime: ("tenant", "project", "owner")
    )
    runtime = SimpleNamespace(
        execution_info=SimpleNamespace(thread_id="thread", run_id="run"),
        tool_call_id="approved-deployment",
    )
    tool = deployment.build_deployment_tool(SimpleNamespace(root="synthetic"))
    calls = []
    client_type = httpx.AsyncClient

    async def check():
        started = asyncio.Event()

        async def supplier(request):
            calls.append(request.url.host)
            started.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(
            httpx,
            "AsyncClient",
            lambda **kwargs: client_type(
                transport=httpx.MockTransport(supplier), **kwargs
            ),
        )
        params = dict(
            file_path="/workspace/outputs/approved.zip",
            sha256=digest,
            approved_files=["index.html"],
            idempotency_key="approved-once",
            runtime=runtime,
        )
        task = asyncio.create_task(tool.coroutine(**params))
        await asyncio.wait_for(started.wait(), 5)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        receipt = await tool.coroutine(**params)
        assert receipt["status"] == "unknown" and len(calls) == 1
        stored = ExternalTaskStorage(inbox.dsn).get(
            ("tenant", "project", "owner", "thread"), receipt["task_id"]
        )
        assert stored["status"] == "unknown" and stored["attempts"] == 1

    asyncio.run(check())


def test_local_cancellation_waits_twice_and_preserves_cancel(inbox, monkeypatch):
    thread, run = str(uuid4()), str(uuid4())
    monkeypatch.setattr(
        resources,
        "get_config",
        lambda: {"configurable": {"thread_id": thread}, "metadata": {"run_id": run}},
    )
    entered, release = threading.Event(), threading.Event()

    def execute(command, timeout=None):
        entered.set()
        release.wait(5)
        raise RuntimeError("command failed after cancellation")

    async def check():
        task = asyncio.create_task(resources.execute_local(execute, "private-command"))
        await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.sleep(0.01)
        assert not task.done() and resources.resource_state(thread, [run]) == "pending"
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert resources.resource_state(thread, [run]) == "unconfirmed"

    asyncio.run(check())


def test_unconfigured_callback_releases_lease_and_old_inbox_reasons(inbox, monkeypatch):
    thread, old, run = str(uuid4()), str(uuid4()), str(uuid4())
    put(inbox, thread, old)
    put(inbox, thread, run)
    row = repository.request_stop(facts(thread), thread, "config-failure")
    monkeypatch.delenv("PLATFORM_RUNTIME_DELEGATION_ISSUER", raising=False)
    result = asyncio.run(service.advance_stop(row["stop_id"]))
    assert (
        result["phase"] == "confirmation_unavailable" and result["lease_token"] is None
    )
    row["engine_receipt"] = {
        "targets": [{"run_id": run}],
        "reconcile_run_ids": [old],
        "reconcile_targets": [{"run_id": old, "status": "success", "reason": None}],
    }

    class Saver:
        async def alist(self, *args, **kwargs):
            for item in []:
                yield item

    assert asyncio.run(service._settle_inbox(row, Saver()))
    rows = inbox.list(thread_id=thread, sender_id="owner")
    assert {r.target_run_id: r.reason for r in rows} == {
        old: "run_ended",
        run: "user_stopped",
    }


@pytest.mark.parametrize("credential", [None, str(uuid4())])
def test_cancellation_hash_binds_only_fixed_id(monkeypatch, credential):
    from langgraph_sdk.auth import exceptions

    from runtime_service.auth.platform import (
        authenticate,
        deny_image_scope_on_server_resources,
    )
    from runtime_service.run_control.authorization import native_headers

    thread, stop, other = str(uuid4()), str(uuid4()), str(uuid4())
    user = {**facts(thread), "runtime_context_hash": cancellation_context_hash(stop)}
    if credential:
        user.update(
            identity="service-account:" + str(uuid4()), runtime_credential_id=credential
        )
    user["runtime_scope"]["operation"] = "run-cancellation-read"
    for name, value in {
        "PLATFORM_RUNTIME_DELEGATION_SECRET": "synthetic-secret-for-stop-at-least-32-bytes",
        "PLATFORM_RUNTIME_DELEGATION_ISSUER": "platform-api",
        "PLATFORM_RUNTIME_DELEGATION_AUDIENCE": "runtime-service",
    }.items():
        monkeypatch.setenv(name, value)
    headers = native_headers(
        {"auth_facts": user, "stop_id": stop}, "run-cancellation-read"
    )
    user = asyncio.run(authenticate(headers["Authorization"]))
    assert user["allowed_model_ids"] == ["platform:no-enabled-model"]
    assert user.get("runtime_credential_id") == credential
    context = SimpleNamespace(user=user, resource="threads", action="read")
    acl = AsyncMock(
        side_effect=AssertionError("accepted receipt must not reauthorize a new action")
    )
    monkeypatch.setattr("runtime_service.auth.platform.post_acl", acl)
    value = {"thread_id": thread, "cancellation_id": stop, "cancellation_receipt": True}
    assert asyncio.run(deny_image_scope_on_server_resources(context, value)) == {
        "project_id": "project"
    }
    for denied in (
        {**value, "cancellation_id": other},
        {**value, "thread_id": other},
        {"thread_id": thread},
    ):
        with pytest.raises(exceptions.HTTPException) as error:
            asyncio.run(deny_image_scope_on_server_resources(context, denied))
        assert error.value.status_code == 403
    assert not acl.called


@pytest.mark.parametrize("operation", ["enqueue", "claim", "checkpoint"])
def test_stop_inbox_boundaries_under_races(inbox, operation):
    class Saver:
        async def alist(self, *args, **kwargs):
            for item in []:
                yield item

    for _ in range(20):
        thread, run = str(uuid4()), str(uuid4())
        message = put(inbox, thread, run)
        barrier = threading.Barrier(2)

        def stop(barrier=barrier, thread=thread):
            barrier.wait()
            return repository.request_stop(facts(thread), thread, uuid4().hex)

        def compete(barrier=barrier, thread=thread, run=run, message=message):
            barrier.wait()
            if operation == "claim":
                return inbox.claim(thread_id=thread, target_run_id=run, owner="worker")
            if operation == "checkpoint":
                return inbox.reconcile_checkpoint(
                    thread_id=thread,
                    target_run_id=run,
                    checkpoint_id="committed",
                    message_ids=[message.message_id],
                )
            try:
                return put(inbox, thread, run)
            except ValueError as error:
                assert str(error) == "thread_stopping"

        with ThreadPoolExecutor(max_workers=2) as pool:
            stopping, competing = pool.submit(stop), pool.submit(compete)
            row = stopping.result(timeout=10)
            competing.result(timeout=10)
        assert (
            row["inbox_run_ids"] in ([], [run])
            if operation == "checkpoint"
            else row["inbox_run_ids"] == [run]
        )
        assert inbox.claim(thread_id=thread, target_run_id=run, owner="later")[1] == []
        row["engine_receipt"] = {"targets": [{"run_id": run}], "reconcile_run_ids": []}
        assert asyncio.run(service._settle_inbox(row, Saver()))
        receipts = inbox.list(thread_id=thread, sender_id="owner")
        assert all(
            item.status == "not_consumed" and item.reason == "user_stopped"
            for item in receipts
            if item.message_id != message.message_id or operation != "checkpoint"
        )
        if operation == "checkpoint":
            assert (
                next(
                    item for item in receipts if item.message_id == message.message_id
                ).status
                == "consumed"
            )
        assert put(inbox, thread, str(uuid4())).status == "queued"


def test_fenced_receipt_is_unconfirmed_and_retries(inbox, monkeypatch):
    thread, run = str(uuid4()), str(uuid4())
    row = repository.request_stop(facts(thread), thread, "fenced")
    receipt = {
        "accepted_at": datetime.now(UTC).isoformat(),
        "targets": [{"run_id": run}],
        "target_count": 1,
        "execution_stopped": False,
        "confirmation_unavailable": True,
    }
    monkeypatch.setattr(service, "engine_receipt", AsyncMock(return_value=receipt))
    monkeypatch.setattr(service, "stop_callback", AsyncMock(return_value=True))
    saved = asyncio.run(service.advance_stop(row["stop_id"]))
    assert saved["phase"] == "confirmation_unavailable"
    assert saved["reason_code"] == "stop_confirmation_unavailable"
    assert saved["lease_token"] is None and saved["engine_receipt"]["target_count"] == 1
    with connect() as connection:
        connection.execute(
            "UPDATE runtime_stop_requests SET retry_at=now() WHERE stop_id=%s",
            (row["stop_id"],),
        )
    assert repository.claim_stop(row["stop_id"]) is not None


def test_stop_storage_failure_is_safe_503(monkeypatch):
    from fastapi import HTTPException

    from runtime_service.http.run_control import _storage_call

    def unavailable():
        raise psycopg.OperationalError("postgres://private-credential@host/db")

    monkeypatch.setenv("DATABASE_URI", "synthetic")
    with pytest.raises(HTTPException) as error:
        asyncio.run(_storage_call(unavailable))
    assert error.value.status_code == 503
    assert error.value.detail == {"code": "stop_storage_unavailable"}


@pytest.mark.parametrize("failure", [None, "remove", "timeout", "spawn"])
def test_docker_cancel_records_cleanup_and_propagates(
    inbox, monkeypatch, tmp_path, failure
):
    from runtime_service.workspace.execution import execute_in_workspace

    thread, run = str(uuid4()), str(uuid4())
    monkeypatch.setattr(
        resources,
        "get_config",
        lambda: {"configurable": {"thread_id": thread}, "metadata": {"run_id": run}},
    )

    async def check():
        entered, release = asyncio.Event(), asyncio.Event()

        class Process:
            def __init__(self, remover=False):
                self.remover = remover
                self.returncode = None
                self.stdout = self

            async def read(self, limit):
                entered.set()
                await release.wait()
                return b""

            async def wait(self):
                if self.remover and failure == "timeout" and self.returncode is None:
                    raise TimeoutError()
                self.returncode = self.returncode or (
                    1 if self.remover and failure == "remove" else 0
                )
                return self.returncode

            def kill(self):
                self.returncode = -9

        async def spawn(*args, **kwargs):
            if args[1] == "run" and failure == "spawn":
                entered.set()
                await release.wait()
                raise OSError("docker unavailable")
            return Process(remover=args[1] == "rm")

        monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
        task = asyncio.create_task(
            execute_in_workspace(tmp_path, "sleep 10", image="fixture")
        )
        await entered.wait()
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert resources.resource_state(thread, [run]) == (
            "unconfirmed" if failure in {"remove", "timeout"} else "confirmed"
        )

    asyncio.run(check())
