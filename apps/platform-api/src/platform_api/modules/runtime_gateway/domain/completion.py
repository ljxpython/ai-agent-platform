"""Strict managed terminal contract and safe public completion DTOs."""

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

from platform_api.modules.runtime_gateway.domain.error_codes import (
    ModelErrorCode,
    WorkspaceErrorCode,
)

Identifier = Annotated[
    str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_:.-]+$")
]
ReasonCode = (
    WorkspaceErrorCode
    | Literal[
        "runtime_execution_failed",
        "runtime_run_timeout",
        "runtime_graph_step_limit_reached",
        "runtime_model_call_limit_reached",
        "runtime_tool_call_limit_reached",
        "runtime.model.retry_exhausted",
        "runtime.model.retry_budget_exceeded",
        "runtime.model.stream_interrupted",
        "runtime.model.provider_rejected",
        "runtime.model.fallback_incompatible",
    ]
)


class CompletionFields(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TerminalOutcome(CompletionFields):
    model_config = ConfigDict(extra="forbid", strict=True)
    reason_code: ReasonCode | None = None
    model_error_code: ModelErrorCode | None = None


class TerminalCompletion(CompletionFields):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Annotated[int, Field(strict=True, ge=1, le=1)]
    event_id: UUID
    event_type: Literal["run.terminal"]
    origin_ref: UUID
    run_id: UUID
    thread_id: UUID | None
    graph_id: Identifier
    status: Literal["success", "error", "timeout", "interrupted"]
    reason: Literal[
        "completed",
        "business_error",
        "infrastructure_error",
        "timeout",
        "hitl_interrupt",
        "cancel_requested",
        "rollback",
        "lease_expired",
    ]
    outcome: TerminalOutcome = Field(default_factory=TerminalOutcome)
    execution_stopped: Literal[True]
    sequence: Annotated[int, Field(ge=1, le=2**63 - 1, strict=True)]
    occurred_at: AwareDatetime

    @field_validator("execution_stopped", mode="before")
    @classmethod
    def stopped_is_boolean(cls, value):
        if value is not True:
            raise ValueError("execution_stopped must be true")
        return value

    @model_validator(mode="after")
    def terminal_semantics(self):
        if self.status in {"success", "interrupted"} and any(
            (self.outcome.reason_code, self.outcome.model_error_code)
        ):
            raise ValueError("non-failure terminal cannot contain failure codes")
        if self.status == "success" and self.reason != "completed":
            raise ValueError("success requires completed reason")
        if self.status == "timeout" and self.reason != "timeout":
            raise ValueError("timeout requires timeout reason")
        if self.status == "interrupted" and self.reason not in {
            "hitl_interrupt",
            "cancel_requested",
            "rollback",
        }:
            raise ValueError("interrupted reason is invalid")
        if self.status == "error" and self.reason not in {
            "business_error",
            "infrastructure_error",
            "lease_expired",
        }:
            raise ValueError("error reason is invalid")
        return self


class CompletionSummary(CompletionFields):
    event_id: UUID
    graph_id: Identifier
    status: Literal["success", "error", "timeout", "interrupted"]
    reason: Identifier
    reason_code: ReasonCode | None
    model_error_code: ModelErrorCode | None
    notification_code: Identifier | None
    occurred_at: AwareDatetime
    can_mark_read: bool
    read_at: AwareDatetime | None


class RunCompletion(CompletionFields):
    version: Literal[1] = 1
    thread_id: UUID
    run_id: UUID
    availability: Literal["available", "pending", "unsupported", "expired"]
    completion: CompletionSummary | None
    request_id: str


class RunNotification(CompletionSummary):
    thread_id: UUID
    run_id: UUID
    received_at: AwareDatetime


class RunNotifications(CompletionFields):
    version: Literal[1] = 1
    availability: Literal["available", "disabled"]
    items: list[RunNotification]
    next_cursor: str | None
    scan_limit_reached: bool
    request_id: str


class ReadCompletion(CompletionFields):
    version: Literal[1] = 1
    event_id: UUID
    read_at: AwareDatetime
    request_id: str


class CompletionAck(CompletionFields):
    accepted: Literal[True] = True
    event_id: UUID
    duplicate: bool


class ReadBody(CompletionFields):
    pass
