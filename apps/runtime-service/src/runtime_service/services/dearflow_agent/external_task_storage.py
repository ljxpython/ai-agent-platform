"""Dear media facts in PostgreSQL; never owns LangGraph Run/checkpoint state."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


class ExternalTaskStorage:
    def __init__(self, dsn: str):
        self.dsn = dsn.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg://", "postgresql://")

    def connect(self):
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def initialize(self):
        """Explicit deployment command only, never called by a request/lifespan."""
        with self.connect() as db:
            db.execute(Path(__file__).with_name("migrations").joinpath("001_external_tasks.sql").read_text())

    def create(self, scope: tuple[str, str, str, str], key: str, operation: str,
               request: dict, *, run_id: str, approval_ref: str) -> tuple[dict, bool]:
        encoded = json.dumps(request, sort_keys=True, separators=(",", ":"))
        if not all(scope) or not key or len(key) > 128 or not approval_ref or not run_id or len(encoded.encode()) > 65536:
            raise ValueError("invalid_external_task")
        digest = hashlib.sha256((operation + "\n" + encoded).encode()).hexdigest()
        with self.connect() as db:
            db.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (json.dumps(scope),))
            row = db.execute("SELECT * FROM dear_external_tasks WHERE tenant_id=%s AND project_id=%s AND user_id=%s AND thread_id=%s AND idem_key=%s", (*scope, key)).fetchone()
            if row:
                if row["digest"] != digest:
                    raise ValueError("external_task_idempotency_conflict")
                return row, False
            count = db.execute("SELECT count(*) AS n FROM dear_external_tasks WHERE tenant_id=%s AND project_id=%s AND user_id=%s AND thread_id=%s AND status IN ('intent','unknown')", scope).fetchone()["n"]
            if count >= 32:
                raise ValueError("external_task_capacity")
            row = db.execute("""INSERT INTO dear_external_tasks
                (id,tenant_id,project_id,user_id,thread_id,idem_key,operation,request,digest,origin_run_id,approval_ref)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
                (uuid4(), *scope, key, operation, Jsonb(request), digest, run_id, approval_ref)).fetchone()
            return row, True

    def get(self, scope: tuple[str, str, str, str], task_id: str) -> dict:
        UUID(task_id)
        with self.connect() as db:
            db.execute("""UPDATE dear_external_tasks SET status='unknown', error_code='submission_unknown',
                lease_until=NULL, updated_at=now() WHERE id=%s AND tenant_id=%s AND project_id=%s AND user_id=%s AND thread_id=%s
                AND status='intent' AND fence>0 AND lease_until<=now()""", (task_id, *scope))
            row = db.execute("SELECT * FROM dear_external_tasks WHERE id=%s AND tenant_id=%s AND project_id=%s AND user_id=%s AND thread_id=%s", (task_id, *scope)).fetchone()
            if row is None:
                raise ValueError("external_task_not_found")
            return row

    def claim(self, task_id: str, *, lease_seconds: int = 360) -> dict | None:
        with self.connect() as db:
            # Expired intents are ambiguous: no automatic second purchase.
            db.execute("""UPDATE dear_external_tasks SET status='unknown', error_code='submission_unknown',
                lease_until=NULL, updated_at=now() WHERE id=%s AND status='intent'
                AND fence>0 AND lease_until<=now()""", (task_id,))
            return db.execute("""UPDATE dear_external_tasks SET fence=fence+1,
                lease_until=now()+(%s * interval '1 second'), attempts=attempts+1
                WHERE id=%s AND status='intent' AND deadline_at>now()
                AND (lease_until IS NULL OR lease_until<=now())
                RETURNING *""", (lease_seconds, task_id)).fetchone()

    def finish(self, row: dict, *, status: str, result: dict | None = None, error: str | None = None) -> bool:
        if status not in {"succeeded", "unknown"}:
            raise ValueError("invalid_external_task_status")
        with self.connect() as db:
            return db.execute("""UPDATE dear_external_tasks SET status=%s,
                result=%s,error_code=%s,
                lease_until=NULL,updated_at=now()
                WHERE id=%s AND fence=%s AND lease_until>now()""",
                (status, Jsonb(result or {}), error, row["id"], row["fence"])).rowcount == 1

    def stats(self):
        with self.connect() as db:
            return db.execute("""SELECT status, count(*) AS count,
                max(extract(epoch from now()-created_at)) AS oldest_seconds
                FROM dear_external_tasks GROUP BY status""").fetchall()


if __name__ == "__main__":
    import os
    ExternalTaskStorage(os.environ["DATABASE_URI"]).initialize()
