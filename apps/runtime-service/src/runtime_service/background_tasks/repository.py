"""Short transactions; durable identities precede every external side effect."""

import hashlib
import json
import secrets
from uuid import NAMESPACE_URL, uuid4, uuid5

from runtime_service.db import connect
from runtime_service.runtime.errors import RuntimeWorkspaceError

TERMINAL = frozenset(("succeeded", "failed", "timed_out", "cancelled"))
UNRESOLVED = "(cleanup_state IN ('pending','unconfirmed') OR delivery_state IN ('pending','dispatching','blocked','unknown') OR (stop_id IS NOT NULL AND (delivery_inflight OR (delivery_run_id IS NOT NULL AND NOT delivery_cancel_confirmed))))"


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()


def thread_lock(connection, thread):
    connection.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (thread,)
    )


def scope_params(scope):
    return (
        scope["tenant_id"],
        scope["project_id"],
        scope["assistant_id"],
        scope["thread_id"],
    )


def submission_key(identity):
    return digest(
        {
            k: identity[k]
            for k in (
                "tenant_id",
                "project_id",
                "graph_id",
                "thread_id",
                "origin_run_id",
                "checkpoint_ns",
                "tool_call_id",
            )
        }
    )


def read_submission(identity, binding_digest, request_digest):
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM runtime_background_tasks WHERE submission_key=%s",
            (submission_key(identity),),
        ).fetchone()
        if row and (
            row["binding_digest"] != binding_digest
            or row["request_digest"] != request_digest
        ):
            raise RuntimeWorkspaceError("background_task_idempotency_conflict")
        return row


def reserve_task(identity, binding_digest, request_digest, host, timeout):
    submission = submission_key(identity)
    with connect() as connection:
        # The host is deliberately small (16 tasks); serialize reservations, not I/O.
        connection.execute("SELECT pg_advisory_xact_lock(746183210)")
        thread_lock(connection, identity["thread_id"])
        existing = connection.execute(
            "SELECT * FROM runtime_background_tasks WHERE submission_key=%s",
            (submission,),
        ).fetchone()
        if existing:
            if (
                existing["request_digest"] != request_digest
                or existing["binding_digest"] != binding_digest
            ):
                raise RuntimeWorkspaceError("background_task_idempotency_conflict")
            return existing, False
        if connection.execute(
            """SELECT 1 FROM runtime_stop_requests WHERE thread_id=%s AND phase!='rejected'
        AND (engine_receipt->'targets' @> %s::jsonb OR inbox_run_ids @> %s::jsonb) LIMIT 1""",
            (
                identity["thread_id"],
                json.dumps([{"run_id": identity["origin_run_id"]}]),
                json.dumps([identity["origin_run_id"]]),
            ),
        ).fetchone():
            raise RuntimeWorkspaceError("background_task_denied")
        counts = connection.execute(
            """SELECT
          count(*) FILTER(WHERE thread_id=%s AND tenant_id=%s AND project_id=%s) AS thread,
          count(*) FILTER(WHERE tenant_id=%s AND project_id=%s) AS project,
          count(*) FILTER(WHERE execution_host_id=%s) AS host
          FROM runtime_background_tasks WHERE cleanup_state IN ('pending','unconfirmed')""",
            (
                identity["thread_id"],
                identity["tenant_id"],
                identity["project_id"],
                identity["tenant_id"],
                identity["project_id"],
                host,
            ),
        ).fetchone()
        if counts["thread"] >= 4 or counts["project"] >= 8 or counts["host"] >= 16:
            raise RuntimeWorkspaceError("background_task_limit_reached")
        logs = connection.execute(
            "SELECT count(*) AS n FROM runtime_background_tasks WHERE execution_host_id=%s AND log_reserved",
            (host,),
        ).fetchone()["n"]
        if logs >= 1024:
            raise RuntimeWorkspaceError("background_task_log_capacity_reached")
        task_id, resource = uuid4(), uuid4()
        row = connection.execute(
            """INSERT INTO runtime_background_tasks(task_id,tenant_id,project_id,owner_id,credential_id,graph_id,thread_id,origin_run_id,checkpoint_ns,tool_call_id,submission_key,request_digest,execution_host_id,container_name,binding_digest,runner_secret,resource_id,deadline_at,event_id,request_id,platform_trace_id,lease_token,lease_until,fence)
        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now()+%s*interval '1 second',%s,%s,%s,%s,now()+interval '45 seconds',1) RETURNING *""",
            (
                task_id,
                identity["tenant_id"],
                identity["project_id"],
                identity["owner_id"],
                identity.get("credential_id"),
                identity["graph_id"],
                identity["thread_id"],
                identity["origin_run_id"],
                identity["checkpoint_ns"],
                identity["tool_call_id"],
                submission,
                request_digest,
                host,
                "runtime-bg-" + task_id.hex,
                binding_digest,
                secrets.token_hex(32),
                resource,
                timeout,
                uuid5(NAMESPACE_URL, "runtime-background:" + str(task_id)),
                identity.get("request_id"),
                identity.get("platform_trace_id"),
                uuid4(),
            ),
        ).fetchone()
        connection.execute(
            "INSERT INTO runtime_run_resources(resource_id,thread_id,run_id,kind) VALUES(%s,%s,%s,'background_task')",
            (resource, identity["thread_id"], identity["origin_run_id"]),
        )
        return row, True


def read_task(scope, task_id):
    with connect() as connection:
        return connection.execute(
            "SELECT * FROM runtime_background_tasks WHERE tenant_id=%s AND project_id=%s AND graph_id=%s AND thread_id=%s AND task_id=%s",
            (*scope_params(scope), task_id),
        ).fetchone()


def list_tasks(scope, limit=20, before=None):
    with connect() as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        rows = connection.execute(
            """SELECT * FROM runtime_background_tasks WHERE tenant_id=%s AND project_id=%s AND graph_id=%s AND thread_id=%s
          AND (%s::timestamptz IS NULL OR (created_at,task_id)<(%s::timestamptz,%s::uuid)) ORDER BY created_at DESC,task_id DESC LIMIT %s""",
            (
                *scope_params(scope),
                before[0] if before else None,
                before[0] if before else None,
                before[1] if before else None,
                limit + 1,
            ),
        ).fetchall()
        unresolved = (
            connection.execute(
                f"SELECT 1 FROM runtime_background_tasks WHERE tenant_id=%s AND project_id=%s AND graph_id=%s AND thread_id=%s AND {UNRESOLVED} LIMIT 1",
                scope_params(scope),
            ).fetchone()
            is not None
        )
        latest = connection.execute(
            "SELECT delivery_run_id FROM runtime_background_tasks WHERE tenant_id=%s AND project_id=%s AND graph_id=%s AND thread_id=%s AND delivery_run_id IS NOT NULL ORDER BY delivery_accepted_at DESC,task_id DESC LIMIT 1",
            scope_params(scope),
        ).fetchone()
        return rows, unresolved, latest["delivery_run_id"] if latest else None


def claim_due(host, task_id=None):
    with connect() as connection:
        return connection.execute(
            f"""UPDATE runtime_background_tasks SET lease_token=%s,lease_until=now()+interval '45 seconds',fence=fence+1,attempts=attempts+1
        WHERE task_id=(SELECT task_id FROM runtime_background_tasks WHERE execution_host_id=%s AND {UNRESOLVED}
        AND next_check_at<=now() AND (lease_until IS NULL OR lease_until<=now()) AND (%s::uuid IS NULL OR task_id=%s)
        ORDER BY next_check_at LIMIT 1 FOR UPDATE SKIP LOCKED) RETURNING *""",
            (uuid4(), host, task_id, task_id),
        ).fetchone()


def renew(row):
    with connect() as connection:
        return (
            connection.execute(
                "UPDATE runtime_background_tasks SET lease_until=now()+interval '45 seconds' WHERE task_id=%s AND lease_token=%s AND fence=%s AND lease_until>now() RETURNING task_id",
                (row["task_id"], row["lease_token"], row["fence"]),
            ).fetchone()
            is not None
        )


def save(row, *, status, cleanup, state=None, reason=None, output=None, delay=5):
    with connect() as connection:
        thread_lock(connection, row["thread_id"])
        current = connection.execute(
            "SELECT task_id FROM runtime_background_tasks WHERE task_id=%s AND lease_token=%s AND fence=%s AND lease_until>now() FOR UPDATE",
            (row["task_id"], row["lease_token"], row["fence"]),
        ).fetchone()
        if current is None:
            return None

    if output is not None:
        from runtime_service.background_tasks.output import write_output

        write_output(row, output)

    result = _commit_observation(row, status, cleanup, state, reason, output, delay)
    from runtime_service.background_tasks.output import (
        delete_output,
        delete_unpublished,
    )

    if result is None:
        if output is not None:
            delete_unpublished(row)
        return None
    delete_output(result, stale=True)
    return result


def _commit_observation(row, status, cleanup, state, reason, output, delay):
    with connect() as connection:
        thread_lock(connection, row["thread_id"])
        current = connection.execute(
            "SELECT * FROM runtime_background_tasks WHERE task_id=%s AND lease_token=%s AND fence=%s AND lease_until>now() FOR UPDATE",
            (row["task_id"], row["lease_token"], row["fence"]),
        ).fetchone()
        if current is None:
            return None
        if current["cancel_requested_at"] and status not in TERMINAL:
            status = "cancel_requested"
        delivery = current["delivery_state"]
        if status in {"succeeded", "failed", "timed_out"} and delivery == "not_ready":
            delivery = "pending"
        if current["cancel_requested_at"] or current["stop_id"]:
            delivery = "suppressed"
        result = connection.execute(
            """UPDATE runtime_background_tasks SET status=%s,cleanup_state=%s,reason_code=%s,
          container_id=coalesce(%s,container_id),exit_code=coalesce(exit_code,%s),started_at=coalesce(started_at,%s::timestamptz),
          finished_at=CASE WHEN %s THEN coalesce(finished_at,now()) ELSE finished_at END,
          delivery_state=%s,log_bytes=coalesce(%s,log_bytes),omitted_bytes=coalesce(%s,omitted_bytes),
          output_available=coalesce(%s,output_available),output_truncated=coalesce(%s,output_truncated),
          log_updated_at=CASE WHEN %s THEN now() ELSE log_updated_at END,log_fence=coalesce(%s,log_fence),
          next_check_at=now()+%s*interval '1 second',updated_at=now(),lease_token=NULL,lease_until=NULL
          WHERE task_id=%s AND lease_token=%s AND fence=%s AND lease_until>now() RETURNING *""",
            (
                status,
                cleanup,
                reason,
                state.get("id") if state else None,
                state.get("ExitCode") if state and not state.get("Running") else None,
                state.get("StartedAt")
                if state and state.get("StartedAt", "").startswith("2")
                else None,
                status in TERMINAL,
                delivery,
                len(output[0].encode()) if output else None,
                output[1] if output else None,
                True if output else None,
                output[2] if output else None,
                output is not None,
                row["fence"] if output is not None else None,
                delay,
                row["task_id"],
                row["lease_token"],
                row["fence"],
            ),
        ).fetchone()
        if result is None:
            return None
        connection.execute(
            "UPDATE runtime_run_resources SET status=%s,updated_at=now() WHERE resource_id=%s",
            (
                "cleanup_confirmed"
                if cleanup in {"confirmed", "not_required"}
                else "cleanup_unconfirmed"
                if cleanup == "unconfirmed"
                else "active",
                row["resource_id"],
            ),
        )
    return result


def request_cancel(scope, task_id):
    with connect() as connection:
        thread_lock(connection, scope["thread_id"])
        return connection.execute(
            """UPDATE runtime_background_tasks SET cancel_requested_at=CASE WHEN status IN ('starting','running','unknown','cancel_requested') THEN coalesce(cancel_requested_at,now()) ELSE cancel_requested_at END,
          status=CASE WHEN status IN ('starting','running','unknown','cancel_requested') THEN 'cancel_requested' ELSE status END,
          delivery_state=CASE WHEN delivery_state='accepted' THEN delivery_state ELSE 'suppressed' END,
          next_check_at=now(),updated_at=now()
          WHERE tenant_id=%s AND project_id=%s AND graph_id=%s AND thread_id=%s AND task_id=%s RETURNING *""",
            (*scope_params(scope), task_id),
        ).fetchone()


def request_source_cancel(row):
    return request_cancel(
        {
            "tenant_id": row["tenant_id"],
            "project_id": row["project_id"],
            "assistant_id": row["graph_id"],
            "thread_id": row["thread_id"],
        },
        row["task_id"],
    )


def finish_delivery(row, state, *, run_id=None, reason=None, retry=30, attempted=False):
    with connect() as connection:
        thread_lock(connection, row["thread_id"])
        return connection.execute(
            """UPDATE runtime_background_tasks SET delivery_state=CASE WHEN stop_id IS NOT NULL OR delivery_state='suppressed' THEN 'suppressed' ELSE %s END,
        delivery_run_id=coalesce(delivery_run_id,%s),delivery_accepted_at=CASE WHEN %s::text IS NOT NULL THEN coalesce(delivery_accepted_at,now()) ELSE delivery_accepted_at END,
        delivery_inflight=CASE WHEN %s::text IS NOT NULL OR %s IN ('pending','blocked','expired') THEN false ELSE delivery_inflight END,
        delivery_reason=%s,delivery_attempts=delivery_attempts+%s,next_check_at=now()+%s*interval '1 second',updated_at=now(),lease_token=NULL,lease_until=NULL
        WHERE task_id=%s AND lease_token=%s AND fence=%s AND lease_until>now() RETURNING *""",
            (
                state,
                run_id,
                run_id,
                run_id,
                state,
                reason,
                int(attempted),
                retry,
                row["task_id"],
                row["lease_token"],
                row["fence"],
            ),
        ).fetchone()


def delivery_intent(row):
    with connect() as connection:
        thread_lock(connection, row["thread_id"])
        return connection.execute(
            """UPDATE runtime_background_tasks SET delivery_inflight=true,delivery_state=CASE WHEN delivery_state='unknown' THEN 'unknown' ELSE 'dispatching' END
        WHERE task_id=%s AND lease_token=%s AND fence=%s AND lease_until>now() AND stop_id IS NULL
        AND delivery_state IN ('pending','blocked','unknown','dispatching') RETURNING *""",
            (row["task_id"], row["lease_token"], row["fence"]),
        ).fetchone()


def completion_allowed(task_id, event_id, run_id):
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM runtime_background_tasks WHERE task_id=%s AND event_id=%s",
            (task_id, event_id),
        ).fetchone()
        if (
            row is None
            or row["stop_id"]
            or row["delivery_state"] in {"suppressed", "expired", "not_ready"}
            or (row["delivery_run_id"] and row["delivery_run_id"] != run_id)
        ):
            return None
        return row


def bind_completion_run(task_id, event_id, run_id):
    with connect() as connection:
        row = connection.execute(
            "SELECT thread_id FROM runtime_background_tasks WHERE task_id=%s AND event_id=%s",
            (task_id, event_id),
        ).fetchone()
        if row is None:
            return None
        thread_lock(connection, row["thread_id"])
        return connection.execute(
            "UPDATE runtime_background_tasks SET delivery_run_id=%s,delivery_inflight=false,delivery_accepted_at=coalesce(delivery_accepted_at,now()),next_check_at=now() WHERE task_id=%s AND event_id=%s AND (delivery_run_id IS NULL OR delivery_run_id=%s) RETURNING *",
            (run_id, task_id, event_id, run_id),
        ).fetchone()


def confirm_delivery_cancel(row):
    with connect() as connection:
        connection.execute(
            "UPDATE runtime_background_tasks SET delivery_cancel_confirmed=true WHERE task_id=%s AND delivery_run_id=%s AND stop_id IS NOT NULL",
            (row["task_id"], row["delivery_run_id"]),
        )


def logs_to_expire(host, *, capacity=False):
    with connect() as connection:
        return connection.execute(
            """SELECT * FROM runtime_background_tasks WHERE execution_host_id=%s AND log_reserved
          AND cleanup_state IN ('confirmed','not_required') AND (created_at<now()-interval '7 days' OR %s)
          AND status IN ('succeeded','failed','timed_out','cancelled')
          ORDER BY created_at LIMIT 100""",
            (host, capacity),
        ).fetchall()


def expire_output(row):
    with connect() as connection:
        connection.execute(
            "UPDATE runtime_background_tasks SET log_reserved=false,output_available=false,log_bytes=0,updated_at=now() WHERE task_id=%s AND cleanup_state IN ('confirmed','not_required')",
            (row["task_id"],),
        )


def background_summary(task_ids):
    with connect() as connection:
        rows = connection.execute(
            "SELECT cleanup_state,delivery_state,delivery_inflight,delivery_run_id,delivery_cancel_confirmed,stop_id FROM runtime_background_tasks WHERE task_id=ANY(%s::uuid[])",
            (task_ids,),
        ).fetchall()
        return {
            "target_count": len(task_ids),
            "cleanup_confirmed_count": sum(
                r["cleanup_state"] in {"confirmed", "not_required"}
                and not r["delivery_inflight"]
                and (
                    not r["stop_id"]
                    or not r["delivery_run_id"]
                    or r["delivery_cancel_confirmed"]
                )
                for r in rows
            ),
            "cleanup_unconfirmed_count": sum(
                bool(
                    r["cleanup_state"] in {"pending", "unconfirmed"}
                    or r["delivery_inflight"]
                    or r["stop_id"]
                    and r["delivery_run_id"]
                    and not r["delivery_cancel_confirmed"]
                )
                for r in rows
            )
            + len(task_ids)
            - len(rows),
            "notifications_suppressed_count": sum(
                r["delivery_state"] == "suppressed" for r in rows
            ),
            "truncated": False,
        }
