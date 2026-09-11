"""Durable inbox contract against a real PostgreSQL instance."""

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import make_conninfo
from runtime_service.messaging import MessageInbox

DSN = os.getenv(
    "RUNTIME_MESSAGE_TEST_DSN",
    "postgresql://lijiaxin@127.0.0.1:5432/graphharbor_web_refactor_20260910",
)


@pytest.fixture()
def inbox():
    schema = "inbox_test_" + uuid4().hex
    try:
        with psycopg.connect(DSN) as c:
            c.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    except psycopg.Error as exc:
        pytest.skip(f"PostgreSQL unavailable: {exc}")
    value = MessageInbox(make_conninfo(DSN, options=f"-c search_path={schema}"))
    value.initialize()
    try:
        yield value
    finally:
        with psycopg.connect(DSN) as c:
            c.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))


def test_parallel_enqueue_claim_ack_and_recovery(inbox):
    thread, run = str(uuid4()), str(uuid4())

    def put(i):
        return inbox.enqueue(
            thread_id=thread,
            target_run_id=run,
            sender_id=f"u{i % 2}",
            client_message_id=str(uuid4()),
            idempotency_key=f"k{i}",
            content={"n": i},
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        receipts = list(pool.map(put, range(20)))
    assert sorted(r.sequence for r in receipts) == list(range(1, 21))

    token, claimed = inbox.claim(
        thread_id=thread, target_run_id=run, owner="worker-a", limit=20
    )
    assert len(claimed) == 20
    assert (
        inbox.ack(
            token=str(uuid4()),
            message_ids=[claimed[0]["message_id"]],
            checkpoint_id="cp-0",
        )
        == 0
    )
    assert (
        inbox.ack(
            token=token,
            message_ids=[item["message_id"] for item in claimed],
            checkpoint_id="cp-1",
        )
        == 20
    )


def test_checkpoint_reconciliation_is_idempotent(inbox):
    thread, run, message = str(uuid4()), str(uuid4()), str(uuid4())
    inbox.enqueue(
        thread_id=thread,
        target_run_id=run,
        sender_id="u",
        client_message_id=message,
        idempotency_key="cp",
        content="hello",
    )
    assert (
        inbox.reconcile_checkpoint(
            thread_id=thread,
            target_run_id=run,
            checkpoint_id="cp-1",
            message_ids=[message],
        )
        == 1
    )
    assert (
        inbox.reconcile_checkpoint(
            thread_id=thread,
            target_run_id=run,
            checkpoint_id="cp-1",
            message_ids=[message],
        )
        == 0
    )


def test_cancel_race_closes_only_undelivered_messages(inbox):
    thread, run = str(uuid4()), str(uuid4())
    first, second = str(uuid4()), str(uuid4())
    inbox.enqueue(
        thread_id=thread,
        target_run_id=run,
        sender_id="u",
        client_message_id=first,
        idempotency_key="one",
        content="one",
    )
    inbox.enqueue(
        thread_id=thread,
        target_run_id=run,
        sender_id="u",
        client_message_id=second,
        idempotency_key="two",
        content="two",
    )
    _, claimed = inbox.claim(
        thread_id=thread, target_run_id=run, owner="worker", limit=1
    )
    assert (
        inbox.reconcile_checkpoint(
            thread_id=thread,
            target_run_id=run,
            checkpoint_id="cp",
            message_ids=[claimed[0]["message_id"]],
        )
        == 1
    )
    assert (
        inbox.mark_run_not_consumed(
            thread_id=thread, target_run_id=run, reason="run_cancelled"
        )
        == 1
    )
    statuses = {
        item.message_id: item.status
        for item in inbox.list(thread_id=thread, sender_id="u")
    }
    assert statuses[first] == "consumed" and statuses[second] == "not_consumed"


def test_idempotency_and_expired_lease(inbox):
    thread, run, message = str(uuid4()), str(uuid4()), str(uuid4())
    first = inbox.enqueue(
        thread_id=thread,
        target_run_id=run,
        sender_id="u",
        client_message_id=message,
        idempotency_key="same",
        content={"x": 1},
    )
    assert (
        inbox.enqueue(
            thread_id=thread,
            target_run_id=run,
            sender_id="u",
            client_message_id=message,
            idempotency_key="same",
            content={"x": 1},
        )
        == first
    )
    with pytest.raises(ValueError, match="idempotency_conflict"):
        inbox.enqueue(
            thread_id=thread,
            target_run_id=run,
            sender_id="u",
            client_message_id=str(uuid4()),
            idempotency_key="same",
            content={"x": 2},
        )
    token, claimed = inbox.claim(
        thread_id=thread, target_run_id=run, owner="worker", lease_seconds=-1
    )
    assert claimed and inbox.reclaim_expired() == 1
    token2, claimed2 = inbox.claim(
        thread_id=thread, target_run_id=run, owner="worker-2"
    )
    assert token2 != token and claimed2[0]["message_id"] == message


def test_claim_automatically_recovers_expired_lease(inbox):
    thread, run, message = str(uuid4()), str(uuid4()), str(uuid4())
    inbox.enqueue(
        thread_id=thread,
        target_run_id=run,
        sender_id="u",
        client_message_id=message,
        idempotency_key="recover",
        content="recover",
    )
    old, _ = inbox.claim(
        thread_id=thread, target_run_id=run, owner="dead", lease_seconds=-1
    )
    new, rows = inbox.claim(thread_id=thread, target_run_id=run, owner="replacement")
    assert new != old and [row["message_id"] for row in rows] == [message]
    assert inbox.ack(token=old, message_ids=[message], checkpoint_id="old") == 0


def test_committed_history_reconciliation_and_run_isolation(inbox):
    import asyncio

    from langgraph.checkpoint.base import empty_checkpoint
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from runtime_service.messaging.reconcile import reconcile_run

    async def check():
        thread, run, other = str(uuid4()), str(uuid4()), str(uuid4())
        ids = [str(uuid4()) for _ in range(5)]
        for i, message in enumerate(ids):
            inbox.enqueue(
                thread_id=thread,
                target_run_id=other if i == 2 else run,
                sender_id="u",
                client_message_id=message,
                idempotency_key=message,
                content="message",
            )
        async with AsyncPostgresSaver.from_conn_string(inbox.dsn) as saver:
            await saver.setup()
            config = {"configurable": {"thread_id": thread, "checkpoint_ns": ""}}
            for i in range(2):
                checkpoint = empty_checkpoint()
                checkpoint["channel_values"] = {
                    "runtime_message_claim": {
                        "run_id": run,
                        "message_ids": ids[: i + 1],
                    }
                }
                checkpoint["channel_versions"] = {"runtime_message_claim": str(i + 1)}
                config = await saver.aput(
                    config,
                    checkpoint,
                    {"run_id": run, "source": "loop", "step": i},
                    checkpoint["channel_versions"],
                )
            # Input/fork snapshots and child namespaces cannot confirm root delivery.
            for message, namespace, source in [
                (ids[3], "child", "loop"),
                (ids[4], "", "input"),
            ]:
                checkpoint = empty_checkpoint()
                checkpoint["channel_values"] = {
                    "runtime_message_claim": {"run_id": run, "message_ids": [message]}
                }
                checkpoint["channel_versions"] = {"runtime_message_claim": "3"}
                await saver.aput(
                    {"configurable": {"thread_id": thread, "checkpoint_ns": namespace}},
                    checkpoint,
                    {"run_id": run, "source": source, "step": 3},
                    checkpoint["channel_versions"],
                )
            # A later compacted state must not erase earlier delivery evidence.
            await saver.aput(
                config,
                empty_checkpoint(),
                {"run_id": run, "source": "loop", "step": 4},
                {},
            )
            assert (
                await reconcile_run(inbox, saver, thread_id=thread, run_id=other) == 0
            )
            assert (
                await reconcile_run(
                    inbox,
                    saver,
                    thread_id=thread,
                    run_id=run,
                    terminal_reason="run_cancelled",
                )
                == 2
            )
            assert await reconcile_run(inbox, saver, thread_id=thread, run_id=run) == 0
            states = {
                r.message_id: r.status
                for r in inbox.list(thread_id=thread, sender_id="u")
            }
            assert states == {
                ids[0]: "consumed",
                ids[1]: "consumed",
                ids[2]: "queued",
                ids[3]: "not_consumed",
                ids[4]: "not_consumed",
            }

    asyncio.run(check())


@pytest.mark.parametrize("authorized", [True, False, "unavailable", "live"])
def test_running_tool_then_root_model_receives_queue(inbox, monkeypatch, authorized):
    import asyncio

    import httpx
    import langgraph_runtime_pg.checkpoint as checkpoint_module
    from langchain.agents import create_agent
    from langchain_core.messages import AIMessage, HumanMessage
    from langchain_core.tools import tool
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from runtime_service.messaging.reconcile import reconcile_run
    from runtime_service.middlewares.message_queue import MessageQueueMiddleware
    from support import BindableFakeMessagesChatModel

    async def check():
        thread, run, message = str(uuid4()), str(uuid4()), str(uuid4())
        entered, release = asyncio.Event(), asyncio.Event()

        @tool
        async def long_task() -> str:
            """Wait until external work completes."""
            entered.set()
            await release.wait()
            return "completed"

        seen = []

        class RecordingModel(BindableFakeMessagesChatModel):
            async def _agenerate(self, messages, *args, **kwargs):
                seen.append(messages)
                return await super()._agenerate(messages, *args, **kwargs)

        model = RecordingModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "long_task",
                            "args": {},
                            "id": "tool-1",
                            "type": "tool_call",
                        }
                    ],
                ),
                AIMessage(content="finished"),
            ]
        )
        if authorized == "live":
            if os.getenv("RUNTIME_MESSAGE_LIVE_MODEL") != "1":
                pytest.skip("Set RUNTIME_MESSAGE_LIVE_MODEL=1 for the real model probe")
            from pathlib import Path

            from dotenv import dotenv_values
            from langchain_deepseek import ChatDeepSeek

            settings = dotenv_values(Path(__file__).resolve().parents[2] / ".env")

            class LiveModel(ChatDeepSeek):
                async def _agenerate(self, messages, *args, **kwargs):
                    seen.append(messages)
                    return await super()._agenerate(messages, *args, **kwargs)

            model = LiveModel(
                model="DeepSeek-V4-Flash",
                api_key=settings["DEEPSEEK_PROXY_API_KEY"],
                base_url=settings["DEEPSEEK_PROXY_URL"],
                request_timeout=30,
                max_retries=0,
                http_async_client=httpx.AsyncClient(timeout=30),
            )
        async with AsyncPostgresSaver.from_conn_string(inbox.dsn) as saver:
            await saver.setup()
            monkeypatch.setattr(checkpoint_module, "get_checkpointer", lambda: saver)
            monkeypatch.setenv("DATABASE_URI", inbox.dsn)
            monkeypatch.setenv(
                "PLATFORM_RUNTIME_MESSAGE_AUTH_URL", "http://authorization/check"
            )
            original_client = httpx.AsyncClient
            transport = httpx.MockTransport(
                lambda request: httpx.Response(
                    503 if authorized == "unavailable" else 200 if authorized else 403,
                    json={"allowed": bool(authorized)},
                )
            )
            monkeypatch.setattr(
                httpx,
                "AsyncClient",
                lambda **kwargs: original_client(transport=transport, **kwargs),
            )
            graph = create_agent(
                model,
                tools=[long_task],
                middleware=[MessageQueueMiddleware()],
                checkpointer=saver,
            )
            config = {
                "configurable": {"thread_id": thread},
                "metadata": {"run_id": run},
            }
            task = asyncio.create_task(
                graph.ainvoke(
                    {
                        "messages": [
                            HumanMessage(
                                content="Call long_task once first. After it returns, repeat the latest user instruction exactly. Do not call any other tools."
                            )
                        ]
                    },
                    config,
                    durability="sync",
                )
            )
            entered_task = asyncio.create_task(entered.wait())
            done, _ = await asyncio.wait(
                {entered_task, task}, timeout=60, return_when=asyncio.FIRST_COMPLETED
            )
            if task in done:
                entered_task.cancel()
                await task
                pytest.fail("Model completed without invoking the requested long_task")
            if entered_task not in done:
                entered_task.cancel()
                task.cancel()
                await asyncio.gather(entered_task, task, return_exceptions=True)
                pytest.fail("Model did not reach long_task within 60 seconds")
            inbox.enqueue(
                thread_id=thread,
                target_run_id=run,
                sender_id="u",
                client_message_id=message,
                idempotency_key=message,
                content="add another verification",
                authorization_ref="test-reference",
            )
            assert not task.done()
            release.set()
            if authorized == "unavailable":
                with pytest.raises(httpx.HTTPStatusError):
                    await asyncio.wait_for(task, 90)
                assert (
                    inbox.list(thread_id=thread, sender_id="u")[0].status == "claimed"
                )
                assert not any(
                    m.id == message for invocation in seen for m in invocation
                )
                return
            result = await asyncio.wait_for(task, 90)
            await reconcile_run(
                inbox, saver, thread_id=thread, run_id=run, terminal_reason="run_ended"
            )
            matching = [m for m in result["messages"] if m.id == message]
            assert len(matching) == int(bool(authorized))
            assert any(m.id == message for m in seen[-1]) == bool(authorized)
            receipt = inbox.list(thread_id=thread, sender_id="u")[0]
            assert receipt.status == ("consumed" if authorized else "rejected")

    asyncio.run(check())


@pytest.mark.parametrize("crash_at", ["before_checkpoint", "after_checkpoint"])
def test_process_crash_resumes_one_human_message(inbox, tmp_path, crash_at):
    import subprocess
    import sys
    import time

    thread, run, message = str(uuid4()), str(uuid4()), str(uuid4())
    inbox.enqueue(
        thread_id=thread,
        target_run_id=run,
        sender_id="u",
        client_message_id=message,
        idempotency_key=message,
        content="durable supplement",
        authorization_ref="test",
    )
    marker = tmp_path / "crash-window"
    script = r"""
import asyncio, os, time
from pathlib import Path
import httpx
from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
import langgraph_runtime_pg.checkpoint as cp
from runtime_service.messaging import MessageInbox
from runtime_service.middlewares.message_queue import MessageQueueMiddleware
from runtime_service.messaging.reconcile import reconcile_run

def pause():
    Path(os.environ["PROBE_MARKER"]).touch()
    while True: time.sleep(.05)

class Model(FakeListChatModel):
    def bind_tools(self, *args, **kwargs): return self
    async def _agenerate(self, messages, *args, **kwargs):
        if os.environ["PROBE_STAGE"] == "after_checkpoint": pause()
        return await super()._agenerate(messages, *args, **kwargs)

async def main():
    original = httpx.AsyncClient
    httpx.AsyncClient = lambda **kw: original(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"allowed": True})), **kw)
    if os.environ["PROBE_STAGE"] == "before_checkpoint":
        claim = MessageInbox.claim
        def claim_then_pause(self, **kwargs):
            result = claim(self, **kwargs)
            if result[1]: pause()
            return result
        MessageInbox.claim = claim_then_pause
    async with AsyncPostgresSaver.from_conn_string(os.environ["DATABASE_URI"]) as saver:
        await saver.setup()
        cp.get_checkpointer = lambda: saver
        graph = create_agent(Model(responses=["done"]), middleware=[MessageQueueMiddleware()], checkpointer=saver)
        config = {"configurable": {"thread_id": os.environ["PROBE_THREAD"]}, "metadata": {"run_id": os.environ["PROBE_RUN"]}}
        result = await graph.ainvoke(None if os.environ["PROBE_STAGE"] == "resume" else {"messages": [HumanMessage(content="start")]}, config, durability="sync")
        assert sum(m.id == os.environ["PROBE_MESSAGE"] for m in result["messages"]) == 1
        await reconcile_run(MessageInbox(os.environ["DATABASE_URI"]), saver, thread_id=os.environ["PROBE_THREAD"], run_id=os.environ["PROBE_RUN"])
asyncio.run(main())
"""
    env = {
        **os.environ,
        "DATABASE_URI": inbox.dsn,
        "PROBE_MARKER": str(marker),
        "PROBE_THREAD": thread,
        "PROBE_RUN": run,
        "PROBE_MESSAGE": message,
        "PROBE_STAGE": crash_at,
        "PLATFORM_RUNTIME_MESSAGE_AUTH_URL": "http://test/check",
        "PYTHONPATH": str(
            __import__("pathlib").Path(__file__).resolve().parents[2] / "src"
        ),
    }
    process = subprocess.Popen(
        [sys.executable, "-c", script],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        deadline = time.monotonic() + 25
        while (
            not marker.exists()
            and time.monotonic() < deadline
            and process.poll() is None
        ):
            time.sleep(0.05)
        assert marker.exists(), "Worker failed to reach the selected crash window"
    finally:
        process.kill()
        process.communicate(timeout=5)
    assert inbox.list(thread_id=thread, sender_id="u")[0].status == "claimed"
    with psycopg.connect(inbox.dsn) as connection:
        connection.execute(
            "UPDATE runtime_message_inbox SET claim_until=now()-interval '1 second' WHERE message_id=%s",
            (message,),
        )
    resumed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        env={**env, "PROBE_STAGE": "resume"},
        capture_output=True,
        text=True,
        timeout=25,
    )
    assert resumed.returncode == 0, resumed.stderr[-3000:]
    assert inbox.list(thread_id=thread, sender_id="u")[0].status == "consumed"


def test_receipt_http_reconciles_before_terminal_close(inbox, monkeypatch):
    import asyncio

    import httpx
    import langgraph_runtime_pg.checkpoint as cp
    from langgraph.checkpoint.base import empty_checkpoint
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from runtime_service import webapp

    async def check():
        thread, run = str(uuid4()), str(uuid4())
        messages = [str(uuid4()), str(uuid4())]
        scope = {
            "operation": "message-enqueue",
            "thread_id": thread,
            "project_id": "p",
            "assistant_id": "reference_agent",
        }

        async def authenticate(_):
            return {"identity": "u", "runtime_scope": scope}

        monkeypatch.setattr(webapp, "authenticate", authenticate)
        monkeypatch.setenv("DATABASE_URI", inbox.dsn)
        monkeypatch.setenv("RUNTIME_SELF_URL", "http://engine")
        status = {"value": "running"}
        original = httpx.AsyncClient
        transport = httpx.MockTransport(
            lambda r: httpx.Response(200, json={"status": status["value"]})
        )
        async with AsyncPostgresSaver.from_conn_string(inbox.dsn) as saver:
            await saver.setup()
            monkeypatch.setattr(cp, "get_checkpointer", lambda: saver)
            async with original(
                transport=httpx.ASGITransport(app=webapp.app),
                base_url="http://runtime",
                headers={"authorization": "Bearer test"},
            ) as client:
                monkeypatch.setattr(
                    httpx,
                    "AsyncClient",
                    lambda **kwargs: original(transport=transport, **kwargs),
                )
                path = f"/internal/threads/{thread}/messages"
                for message in messages:
                    response = await client.post(
                        path,
                        json={
                            "target_run_id": run,
                            "client_message_id": message,
                            "idempotency_key": message,
                            "content": "hello",
                            "authorization_ref": "signed-reference",
                        },
                    )
                    assert response.status_code == 202, response.text
                monkeypatch.setenv("RUNTIME_MESSAGE_QUEUE_ENABLED", "false")
                payload = {
                    "target_run_id": run,
                    "client_message_id": messages[0],
                    "idempotency_key": messages[0],
                    "content": "hello",
                    "authorization_ref": "signed-reference",
                }
                assert (await client.post(path, json=payload)).status_code == 202
                assert (
                    await client.post(
                        path, json={**payload, "client_message_id": str(uuid4())}
                    )
                ).status_code == 409
                assert (await client.get(path)).status_code == 200
                monkeypatch.setenv("RUNTIME_MESSAGE_QUEUE_ENABLED", "true")
                checkpoint = empty_checkpoint()
                checkpoint["channel_values"] = {
                    "runtime_message_claim": {
                        "run_id": run,
                        "message_ids": messages[:1],
                    }
                }
                checkpoint["channel_versions"] = {"runtime_message_claim": "1"}
                await saver.aput(
                    {"configurable": {"thread_id": thread, "checkpoint_ns": ""}},
                    checkpoint,
                    {"source": "loop", "run_id": run, "step": 1},
                    checkpoint["channel_versions"],
                )
                status["value"] = "cancelled"
                scope["operation"] = "message-read"
                response = await client.get(path)
                assert response.status_code == 200, response.text
                result = {
                    item["message_id"]: item["status"]
                    for item in response.json()["messages"]
                }
                assert result == {messages[0]: "consumed", messages[1]: "not_consumed"}
                scope["thread_id"] = None
                assert (await client.get(path)).status_code == 403

    asyncio.run(check())


@pytest.mark.parametrize(
    "content",
    [
        "",
        "  ",
        [],
        [{"type": "image", "url": "http://internal"}],
        [{"type": "file", "mimeType": "application/pdf", "data": "invalid!"}],
        [{"type": "tool_call", "name": "execute"}],
    ],
)
def test_message_intake_rejects_untrusted_content(content):
    from pydantic import ValidationError
    from runtime_service.webapp import EnqueueMessage

    with pytest.raises(ValidationError):
        EnqueueMessage(
            target_run_id=uuid4(),
            client_message_id=uuid4(),
            idempotency_key="test",
            content=content,
            authorization_ref="ref",
        )


def test_limits_sender_isolation_metrics_and_additive_recovery(inbox):
    thread, run, message = str(uuid4()), str(uuid4()), str(uuid4())
    request = {
        "thread_id": thread,
        "target_run_id": run,
        "sender_id": "owner",
        "client_message_id": message,
        "idempotency_key": "original",
        "content": "private text",
    }
    original = inbox.enqueue(**request)
    with pytest.raises(ValueError, match="message_id_conflict"):
        inbox.enqueue(**{**request, "sender_id": "other"})
    assert inbox.list(thread_id=thread, sender_id="other") == []
    assert inbox.list(thread_id=thread, sender_id="owner")[0].content == "private text"
    with pytest.raises(ValueError, match="payload_too_large"):
        inbox.enqueue(**{**request, "content": "中" * 22000})
    # Exercise the actual migration from a legacy schema, preserving existing data.
    with psycopg.connect(inbox.dsn) as c:
        c.execute("ALTER TABLE runtime_message_inbox DROP COLUMN authorization_ref")
    inbox.initialize()
    inbox.initialize()
    assert inbox.enqueue(**request) == original
    token, _ = inbox.claim(thread_id=thread, target_run_id=run, owner="worker")
    assert (
        inbox.reject(token=token, message_id=message, reason="permission_revoked") == 1
    )
    for i in range(100):
        inbox.enqueue(
            **{**request, "client_message_id": str(uuid4()), "idempotency_key": str(i)}
        )
    with pytest.raises(ValueError, match="queue_full"):
        inbox.enqueue(
            **{
                **request,
                "client_message_id": str(uuid4()),
                "idempotency_key": "overflow",
            }
        )
    token, rows = inbox.claim(
        thread_id=thread, target_run_id=run, owner="worker", limit=1
    )
    inbox.ack(
        token=token, message_ids=[rows[0]["message_id"]], checkpoint_id="checkpoint"
    )
    stats = inbox.stats()
    assert stats["pending"] == 99 and stats["rejected"] == 1 and stats["consumed"] == 1
    assert stats["oldest_pending_seconds"] >= 0
    assert stats["consumption_seconds_max"] >= stats["consumption_seconds_avg"] >= 0
    assert "private text" not in str(stats) and "owner" not in str(stats)


def test_transaction_failure_never_returns_receipt(inbox):
    # Fail at the database write boundary, not by mocking enqueue itself.
    with psycopg.connect(inbox.dsn) as c:
        c.execute(
            "ALTER TABLE runtime_message_inbox ADD CONSTRAINT reject_fixture CHECK (sender_id != 'denied')"
        )
    with pytest.raises(psycopg.errors.CheckViolation):
        inbox.enqueue(
            thread_id="thread",
            target_run_id="run",
            sender_id="denied",
            client_message_id=str(uuid4()),
            idempotency_key="key",
            content="do not commit",
        )
    assert inbox.list(thread_id="thread", sender_id="denied") == []
    assert inbox.stats()["pending"] == 0


def test_deleted_thread_retention_never_purges_live_or_retryable_receipts(inbox):
    with pytest.raises(psycopg.errors.UndefinedTable):
        inbox.prune_deleted_threads()
    with psycopg.connect(inbox.dsn) as c:
        c.execute("CREATE TABLE threads(thread_id uuid PRIMARY KEY)")
        c.execute("CREATE TABLE runs(thread_id uuid, status text)")
    scopes = [str(uuid4()) for _ in range(4)]
    for thread in scopes:
        inbox.enqueue(
            thread_id=thread,
            target_run_id=str(uuid4()),
            sender_id="u",
            client_message_id=str(uuid4()),
            idempotency_key="one",
            content="retained",
        )
    with psycopg.connect(inbox.dsn) as c:
        c.execute("INSERT INTO threads VALUES (%s)", (scopes[0],))
        c.execute("INSERT INTO runs VALUES (%s, 'running')", (scopes[1],))
        c.execute(
            "UPDATE runtime_message_inbox SET updated_at=now()-interval '25 hours' WHERE thread_id != %s",
            (scopes[2],),
        )
    assert inbox.prune_deleted_threads() == 1
    assert [bool(inbox.list(thread_id=thread, sender_id="u")) for thread in scopes] == [
        True,
        True,
        True,
        False,
    ]
    assert inbox.prune_deleted_threads() == 0


def test_two_child_agents_do_not_claim_root_inbox(inbox, monkeypatch):
    import asyncio

    import httpx
    import langgraph_runtime_pg.checkpoint as cp
    from langchain.agents import create_agent
    from langchain_core.messages import AIMessage, HumanMessage
    from langchain_core.tools import tool
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from runtime_service.messaging.reconcile import reconcile_run
    from runtime_service.middlewares.message_queue import MessageQueueMiddleware
    from support import BindableFakeMessagesChatModel

    async def check():
        thread, run, message = str(uuid4()), str(uuid4()), str(uuid4())
        entered, release = asyncio.Event(), asyncio.Event()
        child_inputs, root_inputs = [], []
        children_started = 0

        class ChildModel(BindableFakeMessagesChatModel):
            async def _agenerate(self, messages, *args, **kwargs):
                child_inputs.append(messages)
                return await super()._agenerate(messages, *args, **kwargs)

        class RootModel(BindableFakeMessagesChatModel):
            async def _agenerate(self, messages, *args, **kwargs):
                root_inputs.append(messages)
                return await super()._agenerate(messages, *args, **kwargs)

        child = create_agent(
            ChildModel(responses=[AIMessage(content="child done")]),
            middleware=[MessageQueueMiddleware()],
        )

        @tool
        async def delegate(label: str) -> str:
            """Run one isolated child agent."""
            nonlocal children_started
            children_started += 1
            if children_started == 2:
                entered.set()
            await release.wait()
            await child.ainvoke({"messages": [HumanMessage(content=label)]})
            return "child done"

        original = httpx.AsyncClient
        monkeypatch.setattr(
            httpx,
            "AsyncClient",
            lambda **kw: original(
                transport=httpx.MockTransport(
                    lambda r: httpx.Response(200, json={"allowed": True})
                ),
                **kw,
            ),
        )
        monkeypatch.setenv("DATABASE_URI", inbox.dsn)
        monkeypatch.setenv("PLATFORM_RUNTIME_MESSAGE_AUTH_URL", "http://test/check")
        async with AsyncPostgresSaver.from_conn_string(inbox.dsn) as saver:
            await saver.setup()
            monkeypatch.setattr(cp, "get_checkpointer", lambda: saver)
            root = create_agent(
                RootModel(
                    responses=[
                        AIMessage(
                            content="",
                            tool_calls=[
                                {
                                    "id": label,
                                    "name": "delegate",
                                    "args": {"label": label},
                                    "type": "tool_call",
                                }
                                for label in ("left", "right")
                            ],
                        ),
                        AIMessage(content="root done"),
                    ]
                ),
                tools=[delegate],
                middleware=[MessageQueueMiddleware()],
                checkpointer=saver,
            )
            task = asyncio.create_task(
                root.ainvoke(
                    {"messages": [HumanMessage(content="start")]},
                    {
                        "configurable": {"thread_id": thread},
                        "metadata": {"run_id": run},
                    },
                    durability="sync",
                )
            )
            await asyncio.wait_for(entered.wait(), 10)
            inbox.enqueue(
                thread_id=thread,
                target_run_id=run,
                sender_id="u",
                client_message_id=message,
                idempotency_key=message,
                content="root only",
                authorization_ref="ref",
            )
            release.set()
            result = await asyncio.wait_for(task, 30)
            assert len(child_inputs) == 2
            assert not any(
                m.id == message for invocation in child_inputs for m in invocation
            )
            assert any(m.id == message for m in root_inputs[-1])
            assert sum(m.id == message for m in result["messages"]) == 1
            await reconcile_run(inbox, saver, thread_id=thread, run_id=run)
            assert inbox.list(thread_id=thread, sender_id="u")[0].status == "consumed"

    asyncio.run(check())
