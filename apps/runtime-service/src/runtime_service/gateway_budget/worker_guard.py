"""Fence legacy workers at the engine's durable pending-to-running transition."""

import os

from sqlalchemy import event
from sqlalchemy.engine import Engine


def mark_connection(connection, record):
    if os.getenv("RUNTIME_GATEWAY_BUDGET_ENABLED", "false").strip().lower() in {
        "true",
        "1",
    } and os.getenv("RUNTIME_USAGE_ENABLED", "false").strip().lower() in {
        "true",
        "1",
        "yes",
        "on",
    }:
        cursor = connection.cursor()
        try:
            cursor.execute(
                "SELECT set_config('runtime.gateway_budget_guard','v1',false)"
            )
            # Dialect initialization rolls back its probe transaction on new connections.
            connection.commit()
        finally:
            cursor.close()


event.listen(Engine, "connect", mark_connection)


def activate(conn):
    state = conn.execute(
        "SELECT active FROM runtime_budget_worker_fence WHERE id=1"
    ).fetchone()
    if state["active"]:
        return
    conn.execute("SELECT pg_advisory_xact_lock(81019, 1)")
    state = conn.execute(
        "SELECT active FROM runtime_budget_worker_fence WHERE id=1"
    ).fetchone()
    if state["active"]:
        return
    installed = conn.execute(
        "SELECT EXISTS(SELECT 1 FROM pg_trigger WHERE tgname='runtime_budget_worker_fence') AS ok"
    ).fetchone()
    if not installed["ok"]:
        raise ValueError("budget_worker_fence_unavailable")
    if conn.execute(
        "SELECT EXISTS(SELECT 1 FROM runs WHERE status='running') AS busy"
    ).fetchone()["busy"]:
        raise ValueError("budget_activation_requires_drained_workers")
    conn.execute("UPDATE runtime_budget_worker_fence SET active=true WHERE id=1")
