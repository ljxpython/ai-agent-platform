"""Versioned, numeric-only public usage projection."""

import base64
import binascii
import json
from datetime import datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from platform_api.core.errors import BadRequestError

Count = Annotated[int, Field(strict=True, ge=0, le=2**53 - 1)]
Identifier = Annotated[
    str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_:.-]+$")
]
Money = Annotated[str, Field(pattern=r"^[0-9]{1,16}\.[0-9]{12}$", max_length=29)]


class UsageFields(BaseModel):
    model_config = ConfigDict(extra="ignore")


class TokenCounts(UsageFields):
    input_tokens: Count | None
    output_tokens: Count | None
    total_tokens: Count | None
    cache_read_tokens: Count | None
    cache_creation_tokens: Count | None
    cache_creation_5m_tokens: Count | None
    cache_creation_1h_tokens: Count | None
    reasoning_tokens: Count | None

    def check_totals(self):
        if (
            all(
                value is not None
                for value in (self.input_tokens, self.output_tokens, self.total_tokens)
            )
            and self.input_tokens + self.output_tokens != self.total_tokens
        ):
            raise ValueError("Inconsistent token total")
        if (
            all(
                value is not None
                for value in (
                    self.input_tokens,
                    self.cache_read_tokens,
                    self.cache_creation_tokens,
                )
            )
            and self.cache_read_tokens + self.cache_creation_tokens > self.input_tokens
        ):
            raise ValueError("Inconsistent cache tokens")
        if (
            self.reasoning_tokens is not None
            and self.output_tokens is not None
            and self.reasoning_tokens > self.output_tokens
        ):
            raise ValueError("Inconsistent reasoning tokens")


class UsageCost(UsageFields):
    status: Literal["estimated", "partial", "unknown", "not_applicable"]
    estimated_cost_usd: Money | None
    known_cost_usd: Money | None
    currency: Literal["USD"]
    source: Literal["configured_catalog"] | None
    unpriced_call_count: Count
    pricing_versions: Annotated[list[UUID], Field(max_length=50)]

    @model_validator(mode="after")
    def validate_amount(self):
        if (self.status == "estimated") != (self.estimated_cost_usd is not None):
            raise ValueError("Inconsistent cost completeness")
        if self.status == "estimated" and (
            self.unpriced_call_count or self.estimated_cost_usd != self.known_cost_usd
        ):
            raise ValueError("Inconsistent estimated cost")
        return self


class UsageCoverage(UsageFields):
    observed_call_count: Count
    reported_call_count: Count
    missing_usage_call_count: Count
    incomplete_call_count: Count
    collection_degraded: Annotated[bool, Field(strict=True)]
    excluded_operations: Annotated[list[Identifier], Field(max_length=16)]

    @model_validator(mode="after")
    def validate_counts(self):
        if (
            self.reported_call_count + self.missing_usage_call_count
            != self.observed_call_count
            or self.incomplete_call_count > self.missing_usage_call_count
        ):
            raise ValueError("Inconsistent call coverage")
        return self


class UsageCall(UsageFields):
    model_call_id: UUID
    model_id: UUID | None
    provider: Identifier | None
    model_name: Identifier | None
    scope: Literal["primary", "subagent", "auxiliary"]
    purpose: Literal["agent", "summarization", "memory_extraction", "vision", "other"]
    namespace: Annotated[list[Identifier], Field(max_length=8)]
    outcome: Literal["started", "completed", "failed", "cancelled"]
    quality: Literal[
        "reported", "derived_from_reported", "partial", "missing", "invalid"
    ]
    tokens: TokenCounts
    cost: UsageCost
    started_at: AwareDatetime
    ended_at: AwareDatetime | None

    @model_validator(mode="after")
    def validate_tokens(self):
        self.tokens.check_totals()
        return self


class CallPage(UsageFields):
    items: Annotated[list[UsageCall], Field(max_length=200)]
    next_cursor: Annotated[str, Field(min_length=1, max_length=512)] | None


class UsageSummary(UsageFields):
    version: Literal[1]
    availability: Literal["available", "partial", "disabled", "unavailable"]
    unavailable_reason: Literal["not_recorded", "backend_unavailable"] | None
    tokens: TokenCounts
    known_tokens: TokenCounts
    cost: UsageCost
    coverage: UsageCoverage
    truncated: Annotated[bool, Field(strict=True)]

    @model_validator(mode="after")
    def validate_completeness(self):
        self.tokens.check_totals()
        if (self.availability == "unavailable") != (
            self.unavailable_reason is not None
        ):
            raise ValueError("Inconsistent usage availability")
        if self.availability == "available" and (
            self.coverage.collection_degraded
            or self.coverage.incomplete_call_count
            or self.coverage.missing_usage_call_count
            or self.tokens.total_tokens is None
        ):
            raise ValueError("Inconsistent usage completeness")
        return self


class TokenBudgetSummary(UsageFields):
    version: Literal[1]
    budget_scope: Literal["run"]
    unit: Literal["tokens_total"]
    max_tokens: Annotated[int, Field(strict=True, ge=1, le=2**53 - 1)]
    warn_at_tokens: Count
    known_used_tokens: Count | None
    remaining_tokens: Count | None
    coverage: Literal["complete", "partial", "unavailable"]
    stop_code: Literal["token_budget_exhausted", "token_budget_unverifiable"] | None

    @field_validator("version", mode="before")
    @classmethod
    def check_version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("Invalid token budget version")
        return value

    @model_validator(mode="after")
    def validate_budget(self):
        if self.warn_at_tokens != (self.max_tokens * 4 + 4) // 5:
            raise ValueError("Inconsistent token warning threshold")
        if self.known_used_tokens is None and self.coverage != "unavailable":
            raise ValueError("Invalid token budget subtotal")
        if self.coverage == "unavailable" and self.known_used_tokens not in (None, 0):
            raise ValueError("Inconsistent token budget availability")
        expected = max(0, self.max_tokens - (self.known_used_tokens or 0))
        if self.remaining_tokens != (expected if self.coverage == "complete" else None):
            raise ValueError("Inconsistent token budget coverage")
        if (
            self.stop_code == "token_budget_exhausted"
            and self.known_used_tokens is not None
            and self.known_used_tokens < self.max_tokens
        ):
            raise ValueError("Inconsistent token budget stop reason")
        return self


class RuntimeRunUsage(UsageSummary):
    thread_id: UUID
    run_id: UUID
    finalized: Annotated[bool, Field(strict=True)]
    calls: CallPage
    token_budget: TokenBudgetSummary | None = None


class RunUsage(RuntimeRunUsage):
    run_status: Annotated[str, Field(max_length=128)]
    request_id: Annotated[str, Field(max_length=256)]


class RuntimeThreadUsage(UsageSummary):
    thread_id: UUID
    coverage_basis: Literal["recorded_native_runs"]
    created_from: AwareDatetime | None
    created_to: AwareDatetime | None
    recorded_run_count: Count
    first_recorded_at: AwareDatetime | None
    last_recorded_at: AwareDatetime | None


class ThreadUsage(RuntimeThreadUsage):
    request_id: Annotated[str, Field(max_length=256)]


def validate_run_query(limit, cursor):
    try:
        if (
            isinstance(limit, bool)
            or not str(limit).isascii()
            or not str(limit).isdigit()
            or len(str(limit)) > 3
            or not 1 <= int(limit) <= 200
        ):
            raise ValueError("invalid_usage_limit")
        if cursor is not None:
            if not isinstance(cursor, str) or not 1 <= len(cursor) <= 512:
                raise ValueError("invalid_usage_cursor")
            pair = json.loads(base64.b64decode(cursor, altchars=b"-_", validate=True))
            if (
                not isinstance(pair, list)
                or len(pair) != 2
                or not all(isinstance(v, str) for v in pair)
            ):
                raise ValueError("invalid_usage_cursor")
            if datetime.fromisoformat(pair[0]).utcoffset() != timedelta(0):
                raise ValueError("invalid_usage_cursor")
            UUID(pair[1])
        return {
            "limit": int(limit),
            **({"cursor": cursor} if cursor is not None else {}),
        }
    except (ValueError, TypeError, binascii.Error) as exc:
        raise BadRequestError(
            code="invalid_usage_query", message="Invalid usage pagination"
        ) from exc


def validate_thread_query(created_from, created_to):
    if created_from is None and created_to is None:
        return {}
    try:
        if not created_from or not created_to:
            raise ValueError("invalid_usage_window")
        start, end = (
            datetime.fromisoformat(created_from),
            datetime.fromisoformat(created_to),
        )
        if (
            start.utcoffset() != timedelta(0)
            or end.utcoffset() != timedelta(0)
            or not timedelta(0) < end - start <= timedelta(days=90)
        ):
            raise ValueError("invalid_usage_window")
        return {"created_from": start.isoformat(), "created_to": end.isoformat()}
    except (ValueError, TypeError) as exc:
        raise BadRequestError(
            code="invalid_usage_query", message="Invalid usage window"
        ) from exc
