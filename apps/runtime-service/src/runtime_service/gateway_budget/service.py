"""Model dispatch guard and recoverable budget event delivery."""

import asyncio
import logging
import os
import threading
from contextlib import asynccontextmanager, suppress
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from langchain_core.callbacks import BaseCallbackHandler

from runtime_service.errors import RuntimeExecutionError
from runtime_service.gateway_budget import ledger
from runtime_service.gateway_budget.contracts import PolicySnapshot
from runtime_service.gateway_budget.transport import encode

logger = logging.getLogger(__name__)


class GatewayBudgetExceededError(RuntimeExecutionError):
    def __init__(self):
        super().__init__("runtime.gateway_budget.exhausted")


class GatewayBudgetUnverifiableError(RuntimeExecutionError):
    def __init__(self):
        super().__init__("runtime.gateway_budget.unverifiable")


def enabled():
    value = os.getenv("RUNTIME_GATEWAY_BUDGET_ENABLED", "false").strip().lower()
    if value not in {"true", "false", "1", "0"}:
        raise GatewayBudgetUnverifiableError()
    active = value in {"true", "1"}
    if active and os.getenv("RUNTIME_USAGE_ENABLED", "false").lower() not in {
        "true",
        "1",
        "yes",
        "on",
    }:
        raise GatewayBudgetUnverifiableError()
    return active


def platform_url(path):
    parsed = urlsplit(os.getenv("PLATFORM_RUNTIME_MODEL_CONFIG_URL", ""))
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise GatewayBudgetUnverifiableError()
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def post(path, payload):
    secret = os.getenv("PLATFORM_RUNTIME_DELEGATION_SECRET", "")
    body, headers = encode(secret, path, payload)
    with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client:
        response = client.post(platform_url(path), content=body, headers=headers)
        response.raise_for_status()
        return response.json()


class GatewayBudgetDispatchGuard(BaseCallbackHandler):
    """Sync guard also protects invoke(): coroutine callback errors can be swallowed."""

    raise_error = True
    run_inline = False

    def __init__(self, usage):
        self.usage = usage
        self.admitted = set()

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        if run_id in self.admitted:
            return
        try:
            if run_id not in self.usage._calls:
                asyncio.run(
                    self.usage.on_chat_model_start(
                        serialized, messages, run_id=run_id, **kwargs
                    )
                )
            call = self.usage._calls[run_id]
            for attempt in range(2):
                snapshot = PolicySnapshot.model_validate(
                    post(
                        "/api/runtime/internal/budgets/resolve",
                        {
                            "tenant_id": self.usage.identity["tenant_id"],
                            "project_id": self.usage.identity["project_id"],
                        },
                    )
                ).model_dump(mode="json")
                if snapshot["tenant_id"] != self.usage.identity["tenant_id"]:
                    raise ValueError("budget_tenant_mismatch")
                if self.usage._degraded and any(
                    p["action"] == "REJECT"
                    and not p.get("deleted_at")
                    and p.get("project_id") in (None, self.usage.identity["project_id"])
                    for p in snapshot["policies"]
                ):
                    raise GatewayBudgetUnverifiableError()
                try:
                    decision = ledger.admit(self.usage.identity, call, snapshot)
                    break
                except ValueError as exc:
                    if str(exc) != "budget_stale_revision" or attempt:
                        raise
            if decision:
                if decision["code"] == "runtime.gateway_budget.exhausted":
                    raise GatewayBudgetExceededError()
                raise GatewayBudgetUnverifiableError()
            self.admitted.add(run_id)
            self.usage._gateway_admitted.add(run_id)
            stop = threading.Event()
            self.usage._gateway_leases[run_id] = stop
            threading.Thread(
                target=keep_alive, args=(self.usage.identity, run_id, stop), daemon=True
            ).start()
        except (GatewayBudgetExceededError, GatewayBudgetUnverifiableError):
            raise
        except Exception as exc:
            raise GatewayBudgetUnverifiableError() from exc


def keep_alive(identity, call_id, stop):
    while not stop.wait(5):
        try:
            ledger.renew(identity, call_id)
        except Exception:
            logger.warning("gateway_budget_call_lease_failed")


def release(identity, call_id):
    from runtime_service.db.repositories.usage import _connection

    with _connection() as conn:
        conn.execute(
            "DELETE FROM runtime_budget_call_leases WHERE tenant_id=%s AND project_id=%s "
            "AND run_id=%s AND model_call_id=%s",
            (
                identity["tenant_id"],
                identity["project_id"],
                identity["run_id"],
                str(call_id),
            ),
        )


def deliver_batch():
    from runtime_service.db.repositories.usage import _connection

    with _connection() as conn:
        conn.execute(
            "DELETE FROM runtime_budget_nonces WHERE created_at < now()-interval '5 minutes'"
        )
        rows = conn.execute(
            "UPDATE runtime_budget_outbox SET attempts=attempts+1,next_attempt_at=now()+interval '30 seconds' "
            "WHERE event_id IN (SELECT event_id FROM runtime_budget_outbox WHERE delivered_at IS NULL "
            "AND next_attempt_at <= now() ORDER BY next_attempt_at FOR UPDATE SKIP LOCKED LIMIT 20) RETURNING *"
        ).fetchall()
    for row in rows:
        try:
            ack = post("/api/runtime/internal/budgets/events", row["payload"])
            if str(UUID(ack["event_id"])) != str(row["event_id"]):
                raise ValueError("budget_ack_invalid")
            with _connection() as conn:
                conn.execute(
                    "UPDATE runtime_budget_outbox SET delivered_at=now(),last_error=NULL WHERE event_id=%s",
                    (row["event_id"],),
                )
        except Exception:
            with _connection() as conn:
                conn.execute(
                    "UPDATE runtime_budget_outbox SET last_error='budget_delivery_failed' WHERE event_id=%s",
                    (row["event_id"],),
                )


@asynccontextmanager
async def budget_lifespan():
    async def maintain():
        while True:
            try:
                await asyncio.to_thread(deliver_batch)
            except Exception:
                logger.warning("gateway_budget_outbox_unavailable")
            await asyncio.sleep(5)

    task = asyncio.create_task(maintain()) if enabled() else None
    try:
        yield
    finally:
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
