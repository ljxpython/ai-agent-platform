"""Budget contract: decimal text at HTTP boundaries, never binary floats."""

from datetime import UTC, timedelta
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)


class BudgetDuration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    unit: Literal["DAYS", "WEEKS", "MONTHS"]
    value: Literal[1] = 1

    @field_validator("value", mode="before")
    @classmethod
    def integer_one(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("duration value must be integer 1")
        return value


class BudgetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: Literal["GLOBAL", "PROJECT"]
    project_id: UUID | None = None
    budget_amount: str = Field(max_length=40)
    budget_unit: Literal["USD"] = "USD"
    duration: BudgetDuration
    action: Literal["ALERT", "REJECT"]

    @field_validator("budget_amount")
    @classmethod
    def decimal_amount(cls, value):
        try:
            amount = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("USD decimal string required") from exc
        if (
            not amount.is_finite()
            or amount <= 0
            or amount >= Decimal("1e16")
            or amount.as_tuple().exponent < -12
        ):
            raise ValueError("USD amount must be positive numeric(28,12)")
        return format(amount, ".12f")

    @model_validator(mode="after")
    def project_scope(self):
        if (self.scope == "PROJECT") != (self.project_id is not None):
            raise ValueError("PROJECT requires project_id; GLOBAL forbids it")
        return self


class BudgetPolicy(BudgetInput):
    id: UUID
    version: int = Field(ge=1, strict=True)
    definition_version: int = Field(ge=1, strict=True)
    created_at: AwareDatetime
    definition_started_at: AwareDatetime
    updated_at: AwareDatetime
    deleted_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def chronological(self):
        if not self.created_at <= self.definition_started_at <= self.updated_at:
            raise ValueError("invalid policy effective time")
        return self


class PolicySnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(ge=0, strict=True)
    policies: list[BudgetPolicy] = Field(max_length=200)

    @model_validator(mode="after")
    def unique_ids(self):
        if len({p.id for p in self.policies}) != len(self.policies):
            raise ValueError("duplicate policy identity")
        return self


def period(unit, at):
    start = at.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    if unit == "DAYS":
        return start, start + timedelta(days=1)
    if unit == "WEEKS":
        start -= timedelta(days=(start.weekday() + 1) % 7)
        return start, start + timedelta(days=7)
    start = start.replace(day=1)
    return start, start.replace(
        year=start.year + 1, month=1
    ) if start.month == 12 else start.replace(month=start.month + 1)


def nonnegative_money(value):
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError("decimal text required")
    try:
        amount = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid money") from exc
    if (
        not amount.is_finite()
        or amount < 0
        or amount >= Decimal("1e16")
        or amount.as_tuple().exponent < -12
    ):
        raise ValueError("invalid money")
    return format(amount, ".12f")


class BudgetState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy_id: UUID
    definition_version: int = Field(ge=1, strict=True)
    window_start: AwareDatetime
    window_end: AwareDatetime
    accounting_status: Literal["complete", "unverifiable", "reconciling"]
    known_spend: str
    current_spend: str | None
    is_exceeded: bool | None = Field(strict=True)
    as_of: AwareDatetime

    @field_validator("known_spend", "current_spend")
    @classmethod
    def money(cls, value):
        return None if value is None else nonnegative_money(value)

    @model_validator(mode="after")
    def coherent(self):
        if not self.window_start <= self.as_of < self.window_end:
            raise ValueError("invalid state window")
        if self.accounting_status == "complete":
            if self.current_spend != self.known_spend or self.is_exceeded is None:
                raise ValueError("incomplete state")
        elif self.current_spend is not None or self.is_exceeded is False:
            raise ValueError("unknown state presented as complete")
        return self


class BudgetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1]
    tenant_id: str
    revision: int = Field(ge=0, strict=True)
    capabilities: dict[str, StrictBool]
    states: list[BudgetState] = Field(max_length=200)

    @field_validator("version", mode="before")
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("unsupported budget response version")
        return value


class BudgetEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    tenant_id: str = Field(min_length=1, max_length=128)
    policy: BudgetPolicy
    window_start: AwareDatetime
    window_end: AwareDatetime
    known_spend: str

    @field_validator("known_spend")
    @classmethod
    def money(cls, value):
        return nonnegative_money(value)

    @model_validator(mode="after")
    def coherent(self):
        if period(self.policy.duration.unit, self.window_start) != (
            self.window_start,
            self.window_end,
        ):
            raise ValueError("invalid event window")
        identity = (
            self.tenant_id,
            self.policy.id,
            self.policy.definition_version,
            self.window_start,
        )
        expected = uuid5(
            NAMESPACE_URL, "gateway-budget:" + ":".join(map(str, identity))
        )
        if self.event_id != expected or Decimal(self.known_spend) < Decimal(
            self.policy.budget_amount
        ):
            raise ValueError("invalid threshold event")
        return self
