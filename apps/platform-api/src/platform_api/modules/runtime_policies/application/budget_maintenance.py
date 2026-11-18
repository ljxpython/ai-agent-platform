"""Recoverable policy synchronization and external notification delivery."""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from platform_api.modules.runtime_policies.application.budget_notifications import (
    deliver,
)
from platform_api.modules.runtime_policies.application.budgets import BudgetService
from platform_api.modules.runtime_policies.infra.sqlalchemy.budgets import (
    BudgetNonceRecord,
    BudgetTenantRecord,
)

logger = logging.getLogger(__name__)


def synchronize_pending(service):
    with service.factory.begin() as session:
        session.execute(
            delete(BudgetNonceRecord).where(
                BudgetNonceRecord.created_at < datetime.now(UTC) - timedelta(minutes=5)
            )
        )
    with service.factory() as session:
        tenants = session.scalars(
            select(BudgetTenantRecord.tenant_id)
            .where(BudgetTenantRecord.synced_revision < BudgetTenantRecord.revision)
            .limit(20)
        ).all()
    for tenant in tenants:
        service.sync(tenant)


@asynccontextmanager
async def budget_maintenance(factory, settings):
    async def maintain():
        service = BudgetService(factory, settings)
        while True:
            try:
                await asyncio.to_thread(synchronize_pending, service)
                await deliver(factory)
            except Exception:
                logger.warning("gateway_budget_maintenance_unavailable")
            await asyncio.sleep(5)

    task = asyncio.create_task(maintain())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
