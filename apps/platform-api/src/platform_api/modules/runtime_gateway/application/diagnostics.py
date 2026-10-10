"""Validate and project the Runtime diagnostic contract at the public boundary."""

from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from platform_api.modules.runtime_gateway.domain.error_codes import (
    ModelErrorCode,
    WorkspaceErrorCode,
)

Identifier = Annotated[
    str, Field(max_length=128, min_length=1, pattern=r"^[A-Za-z0-9_:.-]+$")
]
Duration = Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)]
ExecutionErrorCode = ModelErrorCode | WorkspaceErrorCode


class DiagnosticFields(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Correlation(DiagnosticFields):
    execution_request_id: Identifier | None = None
    platform_trace_id: Identifier | None = None


class TraceReference(DiagnosticFields):
    provider: Literal["langfuse"]
    trace_id: Identifier
    url: None = None


class GraphExecution(DiagnosticFields):
    observation_id: Identifier
    outcome: Literal["success", "failed", "timeout", "cancelled", "interrupted"]
    error_code: ExecutionErrorCode | None = None
    duration_ms: Duration | None = None


class ModelFailure(DiagnosticFields):
    observation_id: Identifier
    scope: Literal["primary", "subagent"]
    namespace: Annotated[list[Identifier], Field(max_length=8)]
    code: ModelErrorCode
    error_type: Identifier | None = None
    provider_status: Annotated[int, Field(ge=100, le=599, strict=True)] | None = None
    duration_ms: Duration | None = None


class StartupPhase(DiagnosticFields):
    name: Literal[
        "factory.context_resolution",
        "factory.memory_policy",
        "factory.mcp_tools",
        "factory.model_connection",
        "factory.model_build",
        "factory.workspace",
        "factory.agent_compile",
    ]
    ordinal: Annotated[int, Field(ge=0, le=15, strict=True)]
    outcome: Literal["completed", "failed", "cancelled", "incomplete"]
    started_at: AwareDatetime | None = None
    ended_at: AwareDatetime | None = None
    duration_ms: Duration | None = None
    error_code: ExecutionErrorCode | None = None


class WorkspaceExecution(DiagnosticFields):
    observation_id: Identifier
    backend: Literal["docker"]
    phase: Literal["start", "execute", "cleanup"]
    outcome: Literal["recovered", "failed", "cancelled"]
    code: WorkspaceErrorCode | None = None
    command_state: Literal["not_started", "started", "unknown"]
    attempts: Annotated[int, Field(ge=1, le=4, strict=True)]
    retry_wait_ms: Duration
    duration_ms: Duration | None = None


class StartupSummary(DiagnosticFields):
    duration_ms: Duration | None = None
    phases: Annotated[list[StartupPhase], Field(max_length=16)]


class PreparationSummary(DiagnosticFields):
    observation_id: Identifier
    scope: Literal["primary", "subagent"]
    namespace: Annotated[list[Identifier], Field(max_length=8)]
    component: Literal["workspace"]
    outcome: Literal["prepared", "reused", "repaired", "failed"]
    duration_ms: Duration | None = None
    error_code: Literal["prepare_failed", "resource_unavailable"] | None = None


class RetrySummary(DiagnosticFields):
    observation_id: Identifier
    scope: Literal["primary", "subagent"]
    namespace: Annotated[list[Identifier], Field(max_length=8)]
    unit: Literal["model", "task"]
    role: (
        Annotated[
            str, Field(max_length=64, min_length=1, pattern=r"^[A-Za-z0-9_:.-]+$")
        ]
        | None
    ) = None
    attempts: Annotated[int, Field(ge=1, le=2, strict=True)]
    outcome: Literal["success", "exhausted", "failed", "cancelled", "interrupted"]
    code: ModelErrorCode | None = None
    duration_ms: Duration | None = None


class RuntimeDiagnostics(DiagnosticFields):
    version: Literal[1]
    availability: Literal["available", "partial", "disabled", "unavailable"]
    unavailable_reason: (
        Literal["not_configured", "not_recorded", "backend_unavailable"] | None
    ) = None
    correlation: Correlation
    trace: TraceReference | None
    graph_executions: Annotated[list[GraphExecution], Field(max_length=10)]
    model_errors: Annotated[list[ModelFailure], Field(max_length=20)]
    workspace_executions: Annotated[list[WorkspaceExecution], Field(max_length=20)] = (
        Field(default_factory=list)
    )
    startup: StartupSummary | None
    preparations: Annotated[list[PreparationSummary], Field(max_length=20)] = Field(
        default_factory=list
    )
    retries: Annotated[list[RetrySummary], Field(max_length=20)] = Field(
        default_factory=list
    )
    truncated: Annotated[bool, Field(strict=True)]


class RunDiagnostics(RuntimeDiagnostics):
    thread_id: Identifier
    run_id: Identifier
    run_status: Annotated[str, Field(max_length=128)]
    request_id: Annotated[str, Field(max_length=256)]
