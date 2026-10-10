"""Short PostgreSQL transactions for control actions and inbox barriers."""

import hashlib
import json
from uuid import uuid4

from runtime_service.db import connect


def actor_scope(facts):
    return facts["identity"] + ":" + (facts.get("runtime_credential_id") or "")


def request_stop(facts, thread_id, key):
    scope = facts["runtime_scope"]
    params = (
        scope["tenant_id"],
        scope["project_id"],
        thread_id,
        actor_scope(facts),
        hashlib.sha256(key.encode()).hexdigest(),
    )
    with connect() as connection:
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (thread_id,)
        )
        row = connection.execute(
            "SELECT * FROM runtime_stop_requests WHERE tenant_id=%s AND project_id=%s AND thread_id=%s AND actor_scope=%s AND idem_hash=%s",
            params,
        ).fetchone()
        if row:
            return row
        background = connection.execute(
            """SELECT task_id,event_id FROM runtime_background_tasks WHERE tenant_id=%s AND project_id=%s AND thread_id=%s
            AND (cleanup_state IN ('pending','unconfirmed') OR delivery_state IN ('pending','dispatching','blocked','unknown','accepted')) FOR UPDATE""",
            params[:3],
        ).fetchall()
        inbox_runs = connection.execute(
            "SELECT DISTINCT target_run_id FROM runtime_message_inbox WHERE thread_id=%s AND status IN ('queued','claimed') LIMIT 100",
            (thread_id,),
        ).fetchall()
        safe_facts = {
            name: facts.get(name)
            for name in (
                "identity",
                "tenant_id",
                "project_id",
                "role",
                "runtime_credential_id",
                "runtime_scope",
                "request_id",
                "platform_trace_id",
            )
        }
        saved = connection.execute(
            "INSERT INTO runtime_stop_requests(stop_id,tenant_id,project_id,thread_id,actor_scope,idem_hash,auth_facts,inbox_run_ids,background_task_ids,background_event_ids) VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb) RETURNING *",
            (
                uuid4(),
                *params,
                json.dumps(safe_facts),
                json.dumps(sorted(r["target_run_id"] for r in inbox_runs)),
                json.dumps([str(r["task_id"]) for r in background]),
                json.dumps([str(r["event_id"]) for r in background]),
            ),
        ).fetchone()
        connection.execute(
            """UPDATE runtime_background_tasks SET stop_id=%s,delivery_state='suppressed',next_check_at=now(),
            cancel_requested_at=CASE WHEN cleanup_state IN ('pending','unconfirmed') THEN coalesce(cancel_requested_at,now()) ELSE cancel_requested_at END,
            status=CASE WHEN status IN ('starting','running','unknown','cancel_requested') THEN 'cancel_requested' ELSE status END
            WHERE task_id=ANY(%s::uuid[])""",
            (saved["stop_id"], [str(r["task_id"]) for r in background]),
        )
        return saved


def read_stop(scope, stop_id):
    with connect() as connection:
        return connection.execute(
            "SELECT * FROM runtime_stop_requests WHERE stop_id=%s AND tenant_id=%s AND project_id=%s AND thread_id=%s",
            (stop_id, scope["tenant_id"], scope["project_id"], scope["thread_id"]),
        ).fetchone()


def list_stops(scope, limit, before=None):
    with connect() as connection:
        return connection.execute(
            """SELECT * FROM runtime_stop_requests WHERE tenant_id=%s AND project_id=%s AND thread_id=%s
            AND (%s::timestamptz IS NULL OR (requested_at,stop_id) < (%s::timestamptz,%s::uuid))
            ORDER BY requested_at DESC,stop_id DESC LIMIT %s""",
            (
                scope["tenant_id"],
                scope["project_id"],
                scope["thread_id"],
                before[0] if before else None,
                before[0] if before else None,
                before[1] if before else None,
                limit + 1,
            ),
        ).fetchall()


def claim_stop(stop_id=None):
    token = uuid4()
    with connect() as connection:
        return connection.execute(
            """UPDATE runtime_stop_requests SET lease_token=%s, lease_until=now()+interval '45 seconds', attempts=attempts+1
            WHERE stop_id=(SELECT stop_id FROM runtime_stop_requests
              WHERE (phase IN ('accepted','stopping','confirmation_unavailable') OR audit_pending!='[]'::jsonb) AND retry_at<=now()
              AND (lease_until IS NULL OR lease_until<=now()) AND (%s::uuid IS NULL OR stop_id=%s)
              ORDER BY requested_at LIMIT 1 FOR UPDATE SKIP LOCKED) RETURNING *""",
            (token, stop_id, stop_id),
        ).fetchone()


def save_stop(row, *, phase, receipt=None, report=None, reason=None, release=True):
    with connect() as connection:
        return connection.execute(
            """UPDATE runtime_stop_requests SET phase=%s,engine_receipt=coalesce(%s::jsonb,engine_receipt),
            accepted_at=coalesce(accepted_at,%s::timestamptz),report=coalesce(%s::jsonb,report),reason_code=%s,
            confirmed_at=CASE WHEN %s IN ('stopped','no_active_run') THEN coalesce(confirmed_at,now()) ELSE confirmed_at END,
            reconciled_count=%s, audit_pending=%s::jsonb,
            lease_token=CASE WHEN %s THEN NULL ELSE lease_token END,
            lease_until=CASE WHEN %s THEN NULL ELSE lease_until END,
            retry_at=now()+interval '2 seconds'
            WHERE stop_id=%s AND lease_token=%s RETURNING *""",
            (
                phase,
                json.dumps(receipt) if receipt is not None else None,
                receipt["accepted_at"] if receipt else None,
                json.dumps(report) if report is not None else None,
                reason,
                phase,
                row.get("reconciled_count", 0),
                json.dumps(
                    list(
                        dict.fromkeys(
                            row["audit_pending"]
                            + ([phase] if phase != row["phase"] else [])
                        )
                    )
                ),
                release,
                release,
                row["stop_id"],
                row["lease_token"],
            ),
        ).fetchone()


def renew_stop(row):
    with connect() as connection:
        return (
            connection.execute(
                "UPDATE runtime_stop_requests SET lease_until=now()+interval '45 seconds' WHERE stop_id=%s AND lease_token=%s AND lease_until>now() RETURNING stop_id",
                (row["stop_id"], row["lease_token"]),
            ).fetchone()
            is not None
        )


def stop_run_ids(receipt):
    return list(
        dict.fromkeys(
            [target["run_id"] for target in receipt["targets"]]
            + receipt.get("reconcile_run_ids", [])
        )
    )


def run_stop_pending(thread_id, run_id):
    with connect() as connection:
        return inbox_blocked(connection, thread_id, run_id)


def inbox_blocked(connection, thread_id, run_id):
    return (
        connection.execute(
            """SELECT 1 FROM runtime_stop_requests WHERE thread_id=%s AND phase!='rejected'
        AND (engine_receipt->'targets' @> %s::jsonb
             OR inbox_run_ids @> %s::jsonb) LIMIT 1""",
            (thread_id, json.dumps([{"run_id": run_id}]), json.dumps([run_id])),
        ).fetchone()
        is not None
    )


def inbox_counts(thread_id, targets):
    with connect() as connection:
        rows = connection.execute(
            "SELECT status,count(*) AS n FROM runtime_message_inbox WHERE thread_id=%s AND target_run_id=ANY(%s) GROUP BY status",
            (thread_id, targets),
        ).fetchall()
        counts = {r["status"]: r["n"] for r in rows}
        return {
            "inbox_consumed_count": counts.get("consumed", 0),
            "inbox_not_consumed_count": counts.get("not_consumed", 0),
        }
