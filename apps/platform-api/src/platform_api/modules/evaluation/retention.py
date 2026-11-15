"""Bounded cleanup of explicitly managed exports, never source conversations."""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from platform_api.core.db import session_scope
from platform_api.modules.audit.models import AuditLogRecord
from platform_api.modules.evaluation.models import EvaluationExport

# Stable policy ID covers both synthetic and consented business batches.
POLICY = "local-synthetic-20261114"
logger = logging.getLogger(__name__)


def scrub_payload(payload, now):
    return {
        **{
            key: payload[key]
            for key in (
                "purpose",
                "thread_id",
                "run_id",
                "agent_id",
                "source_event",
                "content_hash",
                "retention_policy",
                "source_kind",
                "work_item_id",
            )
            if key in payload
        },
        "purged_at": now.isoformat(),
    }


def sweep(factory, project_id, *, now=None):
    now = now or datetime.now(UTC)
    cleaned = removed = audit_removed = 0
    with session_scope(factory) as session:
        rows = session.scalars(
            select(EvaluationExport)
            .where(
                EvaluationExport.project_id == project_id,
                (
                    (EvaluationExport.expires_at <= now)
                    | (EvaluationExport.status == "revoked")
                ),
                EvaluationExport.payload["retention_policy"].as_string() == POLICY,
                (
                    EvaluationExport.payload["purged_at"].as_string().is_(None)
                    | (EvaluationExport.created_at <= now - timedelta(days=90))
                ),
            )
            .order_by(EvaluationExport.expires_at)
            .limit(100)
            .with_for_update(skip_locked=True)
        )
        for row in rows:
            if row.payload.get("retention_policy") != POLICY:
                continue
            controlled = set(row.receipt.get("assistant_threads", [])) | set(
                row.receipt.get("execution_threads", {})
            )
            if row.payload.get("source_kind") == "work_item" and controlled - set(
                row.receipt.get("cleaned_threads", [])
            ):
                continue
            created = (
                row.created_at.replace(tzinfo=UTC)
                if row.created_at.tzinfo is None
                else row.created_at
            )
            if created + timedelta(days=90) <= now:
                session.delete(row)
                removed += 1
            elif not row.payload.get("purged_at"):
                row.payload = scrub_payload(row.payload, now)
                row.receipt = {
                    key: row.receipt[key]
                    for key in (
                        "assistant_threads",
                        "execution_threads",
                        "cleaned_threads",
                    )
                    if key in row.receipt
                }
                row.status = "expired" if row.status != "revoked" else "revoked"
                cleaned += 1
            if cleaned + removed >= 100:
                break
        audits = session.scalars(
            select(AuditLogRecord)
            .where(
                AuditLogRecord.project_id == project_id,
                AuditLogRecord.target_type == "evaluation",
                AuditLogRecord.metadata_json["retention_policy"].as_string() == POLICY,
                AuditLogRecord.created_at <= now - timedelta(days=90),
            )
            .limit(100)
            .with_for_update(skip_locked=True)
        )
        for row in audits:
            session.delete(row)
            audit_removed += 1
    return {"cleaned": cleaned, "removed": removed, "audit_removed": audit_removed}


async def maintain(factory, project_id, settings=None):
    while True:
        try:
            if settings is not None:
                from platform_api.modules.evaluation.assistant_control import (
                    sweep as sweep_assistants,
                )

                await asyncio.to_thread(sweep_assistants, factory, settings, project_id)
            result = await asyncio.to_thread(sweep, factory, project_id)
        except Exception:
            logger.warning("evaluation_retention_failed")
            result = {}
        await asyncio.sleep(1 if sum(result.values()) >= 100 else 60)
