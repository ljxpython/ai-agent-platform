"""Candidate-wheel migration/backup/rollback checks on disposable PG/Redis only."""

import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import httpx
import psycopg
from alembic import command
from alembic.config import Config
from langgraph_runtime_pg.database import connect, start_pool, stop_pool
from langgraph_runtime_pg.migrate import downgrade, head_revision, upgrade_head
from langgraph_runtime_pg.models import ThreadRow
from langgraph_runtime_pg.run_store import RunRepository
from langhost.cancellation import cancel_active
from runtime_service import db
from runtime_service.messaging import MessageInbox
from runtime_service.run_control import repository
from sqlalchemy import create_engine
from starlette.applications import Starlette
from starlette.routing import Route


async def seed():
    thread, stop, assistant = uuid4(), uuid4(), uuid4()
    await start_pool()
    try:
        async with connect() as connection:
            connection.session.add(ThreadRow(thread_id=thread))
            await connection.session.flush()
            run = await RunRepository().create(
                connection.session,
                assistant_id=assistant,
                thread_id=thread,
                kwargs={},
                metadata={},
                multitask_strategy="enqueue",
            )
        inbox = MessageInbox(os.environ["POSTGRES_URI"])
        inbox.initialize()
        inbox.enqueue(
            thread_id=str(thread),
            target_run_id=str(run.run_id),
            sender_id="probe",
            client_message_id=str(uuid4()),
            idempotency_key="message",
            content="synthetic",
        )
        scope = {"tenant_id": "probe", "project_id": "probe", "thread_id": str(thread)}
        row = repository.request_stop(
            {"identity": "probe", "runtime_scope": scope}, str(thread), "stop"
        )
        app = Starlette(
            routes=[
                Route(
                    "/threads/{thread_id}/runs/cancel-active",
                    cancel_active,
                    methods=["POST"],
                )
            ]
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                f"/threads/{thread}/runs/cancel-active",
                json={"cancellation_id": str(stop), "action": "interrupt"},
                headers={"Idempotency-Key": "fixed"},
            )
            assert response.status_code == 202, response.text
            assert response.json()["execution_stopped"] is True
        return (
            str(run.run_id),
            str(row["stop_id"]),
            str(stop),
            str(thread),
            str(assistant),
        )
    finally:
        await stop_pool()


def snapshot(uri, ids):
    run, stop, cancellation, _, _ = ids
    with psycopg.connect(uri) as connection:
        return [
            connection.execute(
                "SELECT status,reason,lease_owner FROM runs WHERE run_id=%s", (run,)
            ).fetchone(),
            connection.execute(
                "SELECT phase,idem_hash,inbox_run_ids,auth_facts FROM runtime_stop_requests WHERE stop_id=%s",
                (stop,),
            ).fetchone(),
            connection.execute(
                "SELECT targets,principal,idempotency_key FROM run_cancellations WHERE cancellation_id=%s",
                (cancellation,),
            ).fetchone(),
            connection.execute(
                "SELECT status,payload FROM runtime_message_inbox WHERE target_run_id=%s",
                (run,),
            ).fetchall(),
        ]


OLD_PROBE = """
import asyncio, json, os
from uuid import uuid4
import httpx
from starlette.applications import Starlette
from starlette.routing import Route
from langgraph_runtime_pg.database import connect, start_pool, stop_pool
from langgraph_runtime_pg.models import RunRow
from langgraph_runtime_pg.run_store import RunRepository
from langhost.core_api import runs_cancel

async def main():
    await start_pool()
    try:
        from uuid import UUID
        ids=json.loads(os.environ['STOP_ROLLBACK_IDS'])
        async with connect() as c:
            old=await c.session.get(RunRow, UUID(ids[0]))
            assert old.status=='interrupted' and old.lease_owner is None
            run=await RunRepository().create(c.session, assistant_id=UUID(ids[4]), thread_id=UUID(ids[3]), kwargs={}, metadata={}, multitask_strategy='enqueue')
        app=Starlette(routes=[Route('/threads/{thread_id}/runs/{run_id}/cancel', runs_cancel, methods=['POST'])])
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            r=await client.post(f'/threads/{ids[3]}/runs/{run.run_id}/cancel?action=interrupt')
            assert r.status_code in {200, 202}, r.text
        async with connect() as c:
            run=await c.session.get(RunRow,run.run_id)
            assert run.status=='interrupted' and run.lease_owner is None
        print('passed: old_package_single_run_cancel')
    finally:
        await stop_pool()
asyncio.run(main())
"""


def main():
    uri = os.environ["POSTGRES_URI"]
    parsed = urlsplit(uri)
    assert (
        parsed.hostname == "127.0.0.1"
        and parsed.path == "/graphharbor_event_retention_verify"
    )
    assert parsed.port and os.environ.get("REDIS_URI", "").startswith(
        "redis://127.0.0.1:"
    )
    upgrade_head()
    db.upgrade()
    ids = asyncio.run(seed())
    original = snapshot(uri, ids)
    config = Config()
    config.set_main_option(
        "script_location", str(Path(db.__file__).with_name("migrations"))
    )
    engine = create_engine(uri.replace("postgresql://", "postgresql+psycopg://", 1))
    try:
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.downgrade(config, "0001_application")
        assert snapshot(uri, ids) == original
        db.upgrade()
        assert snapshot(uri, ids) == original
    finally:
        engine.dispose()
    with tempfile.TemporaryDirectory(prefix="stop-backup-") as directory:
        backup = Path(directory) / "stop.dump"
        subprocess.run(
            ["pg_dump", "--format=custom", "--file", str(backup), uri],
            check=True,
            capture_output=True,
        )
        restored = urlunsplit(parsed._replace(path="/graphharbor_stop_restore_verify"))
        subprocess.run(
            ["createdb", "--maintenance-db", uri, "graphharbor_stop_restore_verify"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["pg_restore", "--no-owner", "--dbname", restored, str(backup)],
            check=True,
            capture_output=True,
        )
        assert snapshot(restored, ids) == original
        downgrade("010_run_queue_position", restored)
        with psycopg.connect(restored) as connection:
            assert connection.execute(
                "SELECT to_regclass('run_cancellations')"
            ).fetchone() == (None,)
            assert (
                connection.execute(
                    "SELECT status,reason,lease_owner FROM runs WHERE run_id=%s",
                    (ids[0],),
                ).fetchone()
                == original[0]
            )
        old_python = os.environ["STOP_ROLLBACK_PYTHON"]
        subprocess.run(
            [old_python, "-c", OLD_PROBE],
            check=True,
            env={
                **os.environ,
                "PYTHONPATH": "",
                "DATABASE_URI": restored,
                "POSTGRES_URI": restored,
                "LG_RUNTIME_PG_AUTO_MIGRATE": "false",
                "STOP_ROLLBACK_IDS": json.dumps(ids),
            },
        )
        upgrade_head(restored)
        assert head_revision() == "011_run_cancellations"
    evidence = {
        "cases": {
            "candidate_wheel_http_cancellation": "passed",
            "runtime_downgrade_retains_receipts": "passed",
            "runtime_forward_is_idempotent": "passed",
            "pg_backup_restore": "passed",
            "engine_downgrade_preserves_cancel_intent": "passed",
            "old_package_single_run_cancel": "passed",
            "engine_forward_after_rollback": "passed",
        }
    }
    if os.getenv("STOP_MIGRATION_OUTPUT"):
        Path(os.environ["STOP_MIGRATION_OUTPUT"]).write_text(
            json.dumps(evidence, indent=2)
        )
    print(json.dumps(evidence))


if __name__ == "__main__":
    main()
