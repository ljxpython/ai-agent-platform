"""Durable runtime inbox. It owns queue state, never graph business data."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

import psycopg


@dataclass(frozen=True)
class MessageReceipt:
    message_id: str
    thread_id: str
    target_run_id: str
    sequence: int
    status: str
    reason: str | None = None
    content: Any = None


class MessageInbox:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn.replace("postgresql+asyncpg://", "postgresql://").replace(
            "postgresql+psycopg://", "postgresql://"
        )

    def initialize(self) -> None:
        with psycopg.connect(self.dsn) as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS runtime_message_inbox (
                message_id uuid PRIMARY KEY, thread_id text NOT NULL,
                target_run_id text NOT NULL, sender_id text NOT NULL,
                authorization_ref text, idem_key text NOT NULL, payload jsonb NOT NULL, digest text NOT NULL,
                sequence bigint NOT NULL, status text NOT NULL DEFAULT 'queued',
                reason text, claim_token uuid, claim_until timestamptz,
                consumed_checkpoint_id text, created_at timestamptz NOT NULL DEFAULT now(),
                updated_at timestamptz NOT NULL DEFAULT now(),
                UNIQUE(thread_id, sender_id, idem_key), UNIQUE(thread_id, sequence))"""
            )

            connection.execute(
                "ALTER TABLE runtime_message_inbox ADD COLUMN IF NOT EXISTS authorization_ref text"
            )

    def enqueue(
        self,
        *,
        thread_id: str,
        target_run_id: str,
        sender_id: str,
        client_message_id: str,
        idempotency_key: str,
        content: Any,
        authorization_ref: str | None = None,
    ) -> MessageReceipt:
        payload = content
        if (
            len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode())
            > 65536
        ):
            raise ValueError("payload_too_large")
        if not thread_id or not target_run_id or not sender_id:
            raise ValueError("message_scope_required")
        digest = hashlib.sha256(
            json.dumps(
                payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()
        message_id = uuid.UUID(client_message_id)
        with psycopg.connect(self.dsn) as connection:
            # Lock before reading idempotency as well as allocating sequence.
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (thread_id,)
            )
            row = connection.execute(
                "SELECT message_id, target_run_id, sequence, status, reason, digest FROM runtime_message_inbox WHERE thread_id=%s AND sender_id=%s AND idem_key=%s",
                (thread_id, sender_id, idempotency_key),
            ).fetchone()
            if row:
                if (
                    row[-1] != digest
                    or row[1] != target_run_id
                    or str(row[0]) != str(message_id)
                ):
                    raise ValueError("idempotency_conflict")
                return MessageReceipt(
                    str(row[0]), thread_id, row[1], row[2], row[3], row[4], payload
                )
            pending = connection.execute(
                "SELECT count(*) FROM runtime_message_inbox WHERE thread_id=%s AND status IN ('queued','claimed')",
                (thread_id,),
            ).fetchone()[0]
            if pending >= 100:
                raise ValueError("queue_full")
            sequence = connection.execute(
                "SELECT COALESCE(max(sequence), 0) + 1 FROM runtime_message_inbox WHERE thread_id=%s",
                (thread_id,),
            ).fetchone()[0]
            try:
                with connection.transaction():
                    connection.execute(
                        "INSERT INTO runtime_message_inbox(message_id,thread_id,target_run_id,sender_id,idem_key,payload,digest,sequence,authorization_ref) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (
                            message_id,
                            thread_id,
                            target_run_id,
                            sender_id,
                            idempotency_key,
                            json.dumps(payload),
                            digest,
                            sequence,
                            authorization_ref,
                        ),
                    )
            except psycopg.errors.UniqueViolation as exc:
                raise ValueError("message_id_conflict") from exc
            return MessageReceipt(
                str(message_id),
                thread_id,
                target_run_id,
                sequence,
                "queued",
                content=payload,
            )

    def claim(
        self,
        *,
        thread_id: str,
        target_run_id: str,
        owner: str,
        limit: int = 20,
        lease_seconds: int = 30,
    ) -> tuple[str, list[dict[str, Any]]]:
        token = str(uuid.uuid4())
        with psycopg.connect(self.dsn) as connection:
            connection.execute(
                "UPDATE runtime_message_inbox SET status='queued', claim_token=NULL, claim_until=NULL WHERE thread_id=%s AND target_run_id=%s AND status='claimed' AND claim_until <= now()",
                (thread_id, target_run_id),
            )
            rows = connection.execute(
                """UPDATE runtime_message_inbox SET status='claimed', claim_token=%s,
                claim_until=now() + (%s || ' seconds')::interval, updated_at=now()
                WHERE message_id IN (SELECT message_id FROM runtime_message_inbox
                WHERE thread_id=%s AND target_run_id=%s AND status='queued'
                ORDER BY sequence LIMIT %s FOR UPDATE SKIP LOCKED)
                RETURNING message_id, payload, sequence, authorization_ref""",
                (token, lease_seconds, thread_id, target_run_id, limit),
            ).fetchall()
            return token, [
                {
                    "message_id": str(row[0]),
                    "payload": row[1],
                    "sequence": row[2],
                    "authorization_ref": row[3],
                }
                for row in sorted(rows, key=lambda row: row[2])
            ]

    def ack(self, *, token: str, message_ids: list[str], checkpoint_id: str) -> int:
        if not message_ids:
            return 0
        with psycopg.connect(self.dsn) as connection:
            result = connection.execute(
                """UPDATE runtime_message_inbox SET status='consumed', consumed_checkpoint_id=%s,
                claim_token=NULL, claim_until=NULL, updated_at=now()
                WHERE claim_token=%s AND status='claimed' AND claim_until > now()
                AND message_id = ANY(%s::uuid[])""",
                (checkpoint_id, token, message_ids),
            )
            return result.rowcount

    def reclaim_expired(self) -> int:
        with psycopg.connect(self.dsn) as connection:
            result = connection.execute(
                "UPDATE runtime_message_inbox SET status='queued', claim_token=NULL, claim_until=NULL, updated_at=now() WHERE status='claimed' AND claim_until <= now()"
            )
            return result.rowcount

    def list(
        self, *, thread_id: str, sender_id: str, limit: int = 100
    ) -> list[MessageReceipt]:
        with psycopg.connect(self.dsn) as connection:
            rows = connection.execute(
                "SELECT message_id,target_run_id,sequence,status,reason,payload FROM runtime_message_inbox WHERE thread_id=%s AND sender_id=%s ORDER BY (status IN ('queued','claimed')) DESC, sequence DESC LIMIT %s",
                (thread_id, sender_id, min(max(limit, 1), 100)),
            ).fetchall()
        return [
            MessageReceipt(
                str(row[0]), thread_id, row[1], row[2], row[3], row[4], row[5]
            )
            for row in rows
        ]

    def reconcile_checkpoint(
        self,
        *,
        thread_id: str,
        target_run_id: str,
        checkpoint_id: str,
        message_ids: list[str],
    ) -> int:
        """Acknowledge only IDs observed in a committed checkpoint snapshot."""
        if not checkpoint_id or not message_ids:
            return 0
        with psycopg.connect(self.dsn) as connection:
            result = connection.execute(
                """UPDATE runtime_message_inbox SET status='consumed', consumed_checkpoint_id=%s,
                claim_token=NULL, claim_until=NULL, updated_at=now()
                WHERE thread_id=%s AND target_run_id=%s AND status IN ('queued','claimed')
                  AND message_id = ANY(%s::uuid[])""",
                (checkpoint_id, thread_id, target_run_id, message_ids),
            )
            return result.rowcount

    def mark_run_not_consumed(
        self, *, thread_id: str, target_run_id: str, reason: str
    ) -> int:
        """Close undelivered records when a target run reaches a terminal state."""
        with psycopg.connect(self.dsn) as connection:
            result = connection.execute(
                """UPDATE runtime_message_inbox SET status='not_consumed', reason=%s,
                claim_token=NULL, claim_until=NULL, updated_at=now()
                WHERE thread_id=%s AND target_run_id=%s AND status IN ('queued','claimed')""",
                (reason, thread_id, target_run_id),
            )
            return result.rowcount

    def reject(self, *, token: str, message_id: str, reason: str) -> int:
        with psycopg.connect(self.dsn) as connection:
            return connection.execute(
                "UPDATE runtime_message_inbox SET status='rejected', reason=%s, claim_token=NULL, claim_until=NULL, updated_at=now() WHERE message_id=%s AND claim_token=%s AND status='claimed' AND claim_until > now()",
                (reason, message_id, token),
            ).rowcount

    def stats(self) -> dict[str, int | float]:
        """Operational aggregates only; never expose message text or sender IDs."""
        with psycopg.connect(self.dsn) as connection:
            row = connection.execute(
                """SELECT count(*) FILTER (WHERE status IN ('queued','claimed')),
                COALESCE(max(extract(epoch FROM now()-created_at)) FILTER
                    (WHERE status IN ('queued','claimed')), 0),
                count(*) FILTER (WHERE status='rejected'),
                count(*) FILTER (WHERE status='not_consumed'),
                count(*) FILTER (WHERE status='consumed'),
                COALESCE(avg(extract(epoch FROM updated_at-created_at)) FILTER
                    (WHERE status='consumed'), 0),
                COALESCE(max(extract(epoch FROM updated_at-created_at)) FILTER
                    (WHERE status='consumed'), 0)
                FROM runtime_message_inbox"""
            ).fetchone()
        keys = (
            "pending",
            "oldest_pending_seconds",
            "rejected",
            "not_consumed",
            "consumed",
            "consumption_seconds_avg",
            "consumption_seconds_max",
        )
        return {
            key: float(value) if i in {1, 5, 6} else int(value)
            for i, (key, value) in enumerate(zip(keys, row, strict=True))
        }

    def prune_deleted_threads(self) -> int:
        """Keep live-thread idempotency forever; purge deleted scopes after 24h.

        This is an explicit Runtime maintenance operation against its configured
        GraphHarbor PG database. A missing engine schema fails closed.
        """
        with psycopg.connect(self.dsn) as connection:
            return connection.execute(
                """DELETE FROM runtime_message_inbox AS inbox
                WHERE inbox.updated_at < now() - interval '24 hours'
                AND NOT EXISTS (SELECT 1 FROM threads
                    WHERE threads.thread_id::text = inbox.thread_id)
                AND NOT EXISTS (SELECT 1 FROM runs
                    WHERE runs.thread_id::text = inbox.thread_id
                    AND runs.status IN ('pending', 'running'))"""
            ).rowcount

    def pending_runs(self, *, thread_id: str, sender_id: str) -> list[str]:
        with psycopg.connect(self.dsn) as connection:
            return [
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT target_run_id FROM runtime_message_inbox WHERE thread_id=%s AND sender_id=%s AND status IN ('queued','claimed')",
                    (thread_id, sender_id),
                ).fetchall()
            ]

    def has_message(self, *, thread_id: str, sender_id: str, message_id: str) -> bool:
        with psycopg.connect(self.dsn) as connection:
            return (
                connection.execute(
                    "SELECT 1 FROM runtime_message_inbox WHERE thread_id=%s AND sender_id=%s AND message_id=%s",
                    (thread_id, sender_id, message_id),
                ).fetchone()
                is not None
            )
