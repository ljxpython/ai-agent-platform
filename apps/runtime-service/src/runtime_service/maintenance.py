"""Bounded application retention maintenance; GraphHarbor owns thread expiry."""

import argparse
import json
import os
import time

from runtime_service.background_tasks import output, repository
from runtime_service.db import connect
from runtime_service.messaging import MessageInbox
from runtime_service.run_control.resources import (
    reconcile_remote_resources,
    reconcile_terminal_resources,
)


def maintain(*, apply=False, limit=100, budget_seconds=30):
    if not 1 <= limit <= 1000 or not 1 <= budget_seconds <= 300:
        raise ValueError("invalid maintenance bounds")
    host = os.environ.get("RUNTIME_EXECUTION_HOST_ID")
    if not host:
        raise ValueError("RUNTIME_EXECUTION_HOST_ID is required")
    deadline = time.monotonic() + budget_seconds
    report = {
        "apply": apply,
        "expired_logs": 0,
        "terminal_resources": 0,
        "remote_resources": 0,
        "deleted_inbox": 0,
    }
    with connect() as lock:
        acquired = lock.execute("SELECT pg_try_advisory_lock(74013003)").fetchone()[
            "pg_try_advisory_lock"
        ]
        lock.commit()
        if not acquired:
            return {**report, "skipped": "maintenance_busy"}
        try:
            # Each resource pass handles one persisted binding; remote I/O holds no SQL lock.
            for kind, reconciler in (
                ("terminal", reconcile_terminal_resources),
                ("docker_execute", reconcile_remote_resources),
            ):
                if time.monotonic() >= deadline:
                    return {**report, "budget_exhausted": True}
                key = "terminal_resources" if kind == "terminal" else "remote_resources"
                with connect() as db:
                    db.execute("SET LOCAL statement_timeout='5s'")
                    rows = db.execute(
                        """SELECT resource_id FROM runtime_run_resources
                        WHERE kind=%s AND status<>'cleanup_confirmed'
                        AND coalesce(local_binding->>'execution_host',sandbox_binding->>'execution_host')=%s
                        ORDER BY updated_at LIMIT %s""",
                        (kind, host, limit),
                    ).fetchall()
                report[key] = len(rows)
                if apply:
                    for _ in rows:
                        if time.monotonic() >= deadline:
                            break
                        reconciler(limit=1)
            if time.monotonic() >= deadline:
                return {**report, "budget_exhausted": True}
            logs = repository.logs_to_expire(host, limit=limit)
            report["expired_logs"] = len(logs)
            if apply:
                for row in logs:
                    if time.monotonic() >= deadline:
                        break
                    output.delete_output(row)
                    repository.expire_output(row)
            if time.monotonic() < deadline:
                report["deleted_inbox"] = MessageInbox(
                    os.environ["DATABASE_URI"]
                ).prune_deleted_threads(apply=apply, limit=limit)
            report["budget_exhausted"] = time.monotonic() >= deadline
        finally:
            lock.execute("SELECT pg_advisory_unlock(74013003)")
            lock.commit()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--budget-seconds", type=int, default=30)
    args = parser.parse_args()
    print(
        json.dumps(
            maintain(
                apply=args.apply, limit=args.limit, budget_seconds=args.budget_seconds
            )
        )
    )


if __name__ == "__main__":
    main()
