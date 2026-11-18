"""Control-plane rules, reliable synchronization and notification receipts."""

from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from platform_api.core.db.base import Base


class BudgetTenantRecord(Base):
    __tablename__ = "runtime_budget_tenants"
    tenant_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    revision: Mapped[int] = mapped_column(Integer, default=0)
    synced_revision: Mapped[int] = mapped_column(Integer, default=-1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(128), nullable=True)


class BudgetPolicyRecord(Base):
    __tablename__ = "runtime_budget_policies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    payload: Mapped[dict] = mapped_column(JSON)


class BudgetNonceRecord(Base):
    __tablename__ = "runtime_budget_nonces"
    nonce: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BudgetReceiptRecord(Base):
    __tablename__ = "runtime_budget_event_receipts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128))
    payload: Mapped[dict] = mapped_column(JSON)


class BudgetDeliveryRecord(Base):
    __tablename__ = "runtime_budget_deliveries"
    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    channel_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(String(128), nullable=True)
