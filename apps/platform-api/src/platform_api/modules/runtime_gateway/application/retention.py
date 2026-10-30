"""Register platform policy through the engine API; never scan its database."""

import time
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy import select, text

from platform_api.core.security import create_runtime_delegation_token
from platform_api.modules.projects.models import ProjectRecord
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    ThreadAccessRecord,
)

POLICY = {"mode": "idle", "ttl_minutes": 30 * 24 * 60}


@contextmanager
def maintenance_lock(factory, key):
    with factory() as session:
        engine = session.get_bind()
    if engine.dialect.name != "postgresql":
        yield True
        return
    with engine.connect() as connection:
        acquired = connection.scalar(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
        )
        connection.commit()
        try:
            yield acquired
        finally:
            if acquired:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": key}
                )
                connection.commit()


def register_missing(factory, settings, *, apply=False, limit=100, budget_seconds=30):
    with maintenance_lock(factory, 74013001) as acquired:
        if not acquired:
            return {"skipped": "maintenance_busy"}
        return _register_missing(
            factory, settings, apply=apply, limit=limit, budget_seconds=budget_seconds
        )


def _register_missing(factory, settings, *, apply, limit, budget_seconds):
    if not 1 <= limit <= 1000 or not 1 <= budget_seconds <= 300:
        raise ValueError("invalid maintenance bounds")
    with factory() as session:
        rows = session.scalars(
            select(ThreadAccessRecord)
            .where(
                ThreadAccessRecord.retention_configured_at.is_(None),
                ThreadAccessRecord.provisioning_status == "ready",
            )
            .order_by(
                ThreadAccessRecord.retention_attempted_at.asc().nulls_first(),
                ThreadAccessRecord.thread_id,
            )
            .limit(limit)
        ).all()
        candidates = [(row.thread_id, row.project_id) for row in rows]
    report = {"candidates": len(candidates), "configured": 0, "missing": 0, "failed": 0}
    if not apply:
        return report
    deadline = time.monotonic() + budget_seconds
    with httpx.Client(
        base_url=settings.langgraph_upstream_url.rstrip("/"), timeout=5, trust_env=False
    ) as client:
        for thread, project in candidates:
            if time.monotonic() >= deadline:
                break
            with factory.begin() as session:
                access = session.get(ThreadAccessRecord, thread, with_for_update=True)
                if access is None or access.retention_configured_at:
                    continue
                access.retention_attempted_at = datetime.now(UTC)
                try:
                    scope = session.get(ProjectRecord, UUID(project))
                except ValueError:
                    scope = None
                tenant = str(scope.tenant_id) if scope else None
            if not tenant:
                report["failed"] += 1
                continue
            try:
                token = create_runtime_delegation_token(
                    subject="platform-retention-maintenance",
                    role="platform_maintenance",
                    tenant_id=tenant,
                    project_id=project,
                    permissions=[],
                    policy_version="retention-v1",
                    allowed_model_ids=["maintenance"],
                    tool_overrides={},
                    tool_policy_version="retention-v1",
                    scope={
                        "tenant_id": tenant,
                        "project_id": project,
                        "thread_id": thread,
                        "operation": "thread-retention",
                    },
                    settings=settings,
                )
                headers = {"authorization": "Bearer " + token}
                path = f"/threads/{UUID(thread)}/retention"
                response = client.get(path, headers=headers)
                if response.status_code == 404:
                    # Deletion callbacks own ACL removal; absence alone proves no deletion.
                    report["missing"] += 1
                    continue
                response.raise_for_status()
                if response.json()["policy"] is None:
                    response = client.patch(
                        path, headers=headers, json={"policy": POLICY}
                    )
                    response.raise_for_status()
                with factory.begin() as session:
                    access = session.get(
                        ThreadAccessRecord, thread, with_for_update=True
                    )
                    if access:
                        access.retention_configured_at = datetime.now(UTC)
                report["configured"] += 1
            except (httpx.HTTPError, ValueError, KeyError):
                report["failed"] += 1
    return report
