"""Frozen numeric DTOs; upstream extras never reach the browser."""

from datetime import UTC, datetime, timedelta
from math import isclose
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from platform_api.core.errors import BadRequestError
from platform_api.modules.runtime_gateway.application.usage import (
    Count,
    Identifier,
    TokenCounts,
    UsageCost,
    UsageCoverage,
    UsageFields,
)

Ratio = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]
Name = Annotated[str, Field(max_length=255)]
GroupKey = Annotated[
    str, Field(min_length=1, max_length=257, pattern=r"^[A-Za-z0-9_:/.-]+$")
]
TOKEN_FIELDS = tuple(TokenCounts.model_fields)


class Coverage(UsageCoverage):
    priced_call_count: Count
    field_call_counts: TokenCounts

    @model_validator(mode="after")
    def known_counts(self):
        counts = self.field_call_counts.model_dump().values()
        if self.priced_call_count > self.observed_call_count or any(
            n is None or n > self.observed_call_count for n in counts
        ):
            raise ValueError("Invalid field coverage")
        return self


class UsageMetrics(UsageFields):
    tokens: TokenCounts
    known_tokens: TokenCounts
    cost: UsageCost
    coverage: Coverage
    recorded_run_count: Count
    open_collection_run_count: Count
    zero_call_manifest_count: Count | None
    cache_read_ratio: Ratio | None
    ratio_sample_call_count: Count
    average_tokens_per_recorded_run: (
        Annotated[float, Field(ge=0, le=2**53 - 1, allow_inf_nan=False)] | None
    )
    pricing_versions_truncated: bool

    @model_validator(mode="after")
    def consistent(self):
        self.tokens.check_totals()
        n = self.coverage.observed_call_count
        if (
            self.recorded_run_count > n
            or self.open_collection_run_count > self.recorded_run_count
            or self.ratio_sample_call_count > n
            or self.cost.unpriced_call_count + self.coverage.priced_call_count != n
        ):
            raise ValueError("Invalid metric counts")
        for key in TOKEN_FIELDS:
            value = getattr(self.tokens, key)
            if value is not None and (
                getattr(self.known_tokens, key) != value
                or getattr(self.coverage.field_call_counts, key) != n
            ):
                raise ValueError("Invalid token completeness")
            if value is not None and (
                self.coverage.collection_degraded
                or self.open_collection_run_count
                or self.coverage.reported_call_count != n
                or self.coverage.incomplete_call_count
            ):
                raise ValueError("Invalid complete token metric")
        if self.average_tokens_per_recorded_run is not None and (
            self.tokens.total_tokens is None or not self.recorded_run_count
        ):
            raise ValueError("Invalid average")
        if self.average_tokens_per_recorded_run is not None and not isclose(
            self.average_tokens_per_recorded_run,
            self.tokens.total_tokens / self.recorded_run_count,
            rel_tol=1e-12,
        ):
            raise ValueError("Invalid average value")
        if self.cache_read_ratio is not None and not self.ratio_sample_call_count:
            raise ValueError("Ratio requires matching samples")
        return self


class Window(UsageFields):
    start: AwareDatetime = Field(alias="from")
    end: AwareDatetime = Field(alias="to")
    timezone: Literal["UTC", "Asia/Shanghai"]
    granularity: Literal["day", "hour"]
    time_basis: Literal["model_call_started_at"]


class DashboardScope(UsageFields):
    kind: Literal["platform", "project"]
    project_ids: Annotated[list[UUID], Field(max_length=200)]
    covered_project_count: Count


class PreviousWindow(UsageFields):
    window: Window
    summary: UsageMetrics
    total_token_change_ratio: Annotated[float, Field(allow_inf_nan=False)] | None


class SeriesPoint(UsageMetrics):
    start: AwareDatetime = Field(alias="from")
    end: AwareDatetime = Field(alias="to")


class Group(UsageMetrics):
    key: GroupKey
    label: Name
    project_id: UUID | None = None
    agent_id: UUID | None = None


class Breakdown(UsageFields):
    group_by: Literal["project", "model", "agent", "purpose", "scope"]
    rank_by: Literal["known_total_tokens", "known_cost_usd", "observed_call_count"]
    items: Annotated[list[Group], Field(max_length=50)]
    other: UsageMetrics | None


class ProjectOption(UsageFields):
    id: UUID
    label: Name


class ModelOption(UsageFields):
    id: UUID | Literal["unmapped"]
    label: Name


class AgentOption(UsageFields):
    project_id: UUID
    graph_id: Identifier
    agent_id: UUID | None
    label: Name


class ProjectFacet(UsageFields):
    items: Annotated[list[ProjectOption], Field(max_length=200)]
    truncated: bool


class ModelFacet(UsageFields):
    items: Annotated[list[ModelOption], Field(max_length=200)]
    truncated: bool


class AgentFacet(UsageFields):
    items: Annotated[list[AgentOption], Field(max_length=200)]
    truncated: bool


class Facets(UsageFields):
    projects: ProjectFacet
    models: ModelFacet
    agents: AgentFacet


class Collection(UsageFields):
    enabled_now: bool | None
    first_recorded_at: AwareDatetime | None
    last_recorded_at: AwareDatetime | None
    excluded_operations: Annotated[list[Identifier], Field(max_length=16)]


class UsageDashboardV1(UsageFields):
    version: Literal[1]
    scope: DashboardScope
    window: Window
    as_of: AwareDatetime
    availability: Literal["available", "partial", "disabled", "unavailable"]
    unavailable_reason: Literal["not_recorded", "backend_unavailable"] | None
    coverage_basis: Literal["recorded_native_runs"]
    summary: UsageMetrics
    previous_window: PreviousWindow
    series: Annotated[list[SeriesPoint], Field(max_length=200)]
    breakdown: Breakdown
    facets: Facets
    collection: Collection
    request_id: Identifier


class UsageRun(UsageMetrics):
    project_id: UUID
    thread_id: UUID
    run_id: UUID
    graph_id: Identifier
    agent_id: UUID | None = None
    agent_name: Name
    first_matching_call_at: AwareDatetime
    last_matching_call_at: AwareDatetime


class UsageRunPageV1(UsageFields):
    version: Literal[1]
    items: Annotated[list[UsageRun], Field(max_length=200)]
    next_cursor: Annotated[str, Field(max_length=2048)] | None
    as_of: AwareDatetime
    request_id: Identifier


class Filters(UsageFields):
    model_id: UUID | None
    model_mapping: Literal["unmapped"] | None
    graph_id: Identifier | None
    purpose: (
        Literal["agent", "summarization", "memory_extraction", "vision", "other"] | None
    )
    scope: Literal["primary", "subagent", "auxiliary"] | None


class DashboardQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    start: AwareDatetime = Field(alias="from")
    end: AwareDatetime = Field(alias="to")
    timezone: Literal["UTC", "Asia/Shanghai"] = "Asia/Shanghai"
    granularity: Literal["day", "hour"] = "day"
    model_id: UUID | None = None
    model_mapping: Literal["unmapped"] | None = None
    agent_id: UUID | None = None
    purpose: (
        Literal["agent", "summarization", "memory_extraction", "vision", "other"] | None
    ) = None
    scope: Literal["primary", "subagent", "auxiliary"] | None = None
    group_by: Literal["project", "model", "agent", "purpose", "scope"] = "model"
    rank_by: Literal["known_total_tokens", "known_cost_usd", "observed_call_count"] = (
        "known_total_tokens"
    )
    top_n: Annotated[int, Field(ge=1, le=50)] = 10

    @model_validator(mode="after")
    def bounded(self):
        if any(
            v.utcoffset() != timedelta(0) for v in (self.start, self.end)
        ) or not timedelta(0) < self.end - self.start <= timedelta(days=90):
            raise ValueError("Window must be in UTC and within 90 days")
        if (
            self.model_id
            and self.model_mapping
            or self.granularity == "hour"
            and self.end - self.start > timedelta(days=7)
        ):
            raise ValueError("Conflicting query")
        return self


class RunsQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: AwareDatetime = Field(alias="from")
    end: AwareDatetime = Field(alias="to")
    model_id: UUID | None = None
    model_mapping: Literal["unmapped"] | None = None
    agent_id: UUID | None = None
    purpose: (
        Literal["agent", "summarization", "memory_extraction", "vision", "other"] | None
    ) = None
    scope: Literal["primary", "subagent", "auxiliary"] | None = None
    limit: Annotated[int, Field(ge=1, le=200)] = 50
    cursor: Annotated[str, Field(min_length=1, max_length=2048)] | None = None

    @model_validator(mode="after")
    def bounded(self):
        DashboardQuery.model_validate(
            {
                "from": self.start,
                "to": self.end,
                "model_id": self.model_id,
                "model_mapping": self.model_mapping,
            }
        )
        return self


def parse_query(params, *, runs=False, platform=False):
    from pydantic import ValidationError

    model = RunsQuery if runs else DashboardQuery
    allowed = {field.alias or name for name, field in model.model_fields.items()}
    if platform:
        allowed.add("project_ids")
    if set(params.keys()) - allowed or any(
        len(params.getlist(key)) != 1 for key in params.keys() if key != "project_ids"
    ):
        raise BadRequestError(
            code="invalid_usage_analytics_query",
            message="Unsupported or repeated usage parameter",
        )
    try:
        for key in ("top_n", "limit"):
            if key in params and (
                len(params[key]) > 3
                or not params[key].isascii()
                or not params[key].isdecimal()
            ):
                raise ValueError("Invalid integer parameter")
        for key in ("from", "to"):
            if key in params and "T" not in params[key]:
                raise ValueError("ISO timestamp required")
        query = model.model_validate(
            {key: params[key] for key in params.keys() if key != "project_ids"}
        )
        projects = (
            [str(UUID(value)) for value in params.getlist("project_ids")]
            if platform
            else None
        )
        if projects and (len(projects) > 200 or len(projects) != len(set(projects))):
            raise ValueError("Project range exceeds limit")
        return query, projects
    except (ValidationError, ValueError) as exc:
        raise BadRequestError(
            code="invalid_usage_analytics_query",
            message="Invalid usage window, filters or project range",
        ) from exc


def empty_dashboard(query, request_id):
    tokens = dict.fromkeys(TOKEN_FIELDS)
    metric = {
        "tokens": tokens,
        "known_tokens": tokens,
        "cost": {
            "status": "unknown",
            "estimated_cost_usd": None,
            "known_cost_usd": None,
            "currency": "USD",
            "source": None,
            "unpriced_call_count": 0,
            "pricing_versions": [],
        },
        "coverage": {
            "observed_call_count": 0,
            "reported_call_count": 0,
            "missing_usage_call_count": 0,
            "incomplete_call_count": 0,
            "priced_call_count": 0,
            "field_call_counts": dict.fromkeys(TOKEN_FIELDS, 0),
            "collection_degraded": False,
            "excluded_operations": ["suggestions", "title", "non_llm_provider_fees"],
        },
        "recorded_run_count": 0,
        "open_collection_run_count": 0,
        "zero_call_manifest_count": 0,
        "cache_read_ratio": None,
        "ratio_sample_call_count": 0,
        "average_tokens_per_recorded_run": None,
        "pricing_versions_truncated": False,
    }
    window = {
        "from": query.start,
        "to": query.end,
        "timezone": query.timezone,
        "granularity": query.granularity,
        "time_basis": "model_call_started_at",
    }
    return UsageDashboardV1.model_validate(
        {
            "version": 1,
            "scope": {
                "kind": "platform",
                "project_ids": [],
                "covered_project_count": 0,
            },
            "window": window,
            "as_of": datetime.now(UTC),
            "availability": "unavailable",
            "unavailable_reason": "not_recorded",
            "coverage_basis": "recorded_native_runs",
            "summary": metric,
            "previous_window": {
                "window": {
                    **window,
                    "from": query.start - (query.end - query.start),
                    "to": query.start,
                },
                "summary": metric,
                "total_token_change_ratio": None,
            },
            "series": [],
            "breakdown": {
                "group_by": query.group_by,
                "rank_by": query.rank_by,
                "items": [],
                "other": None,
            },
            "facets": {
                key: {"items": [], "truncated": False}
                for key in ("projects", "models", "agents")
            },
            "collection": {
                "enabled_now": None,
                "first_recorded_at": None,
                "last_recorded_at": None,
                "excluded_operations": metric["coverage"]["excluded_operations"],
            },
            "request_id": request_id,
        }
    )
