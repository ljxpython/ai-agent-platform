"""Public stop request projection, isolated from raw Runtime control records."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Count = Annotated[int, Field(ge=0, strict=True)]
Text = Annotated[str, Field(max_length=256)]


class Fields(BaseModel):
    model_config = ConfigDict(extra="ignore")


class StopBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QueueCounts(Fields):
    pending_cancelled_count: Count | None
    inbox_consumed_count: Count | None
    inbox_not_consumed_count: Count | None


class Progress(Fields):
    kind: Literal["saved_plan", "tool_receipt"]
    label: Text
    observed_status: Literal["pending", "in_progress", "completed", "recorded"]
    source_run_id: UUID
    source_message_id: Text | None


class Checkpoint(Fields):
    run_id: UUID
    checkpoint_id: Text
    checkpoint_at: AwareDatetime | None


class Artifact(Fields):
    artifact_id: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    path: Annotated[
        str, Field(pattern=r"^/workspace/outputs/[0-9a-f]{64}\.[a-z0-9]{1,8}$")
    ]
    source_run_id: UUID
    source_message_id: Text | None


class StopReport(Fields):
    version: Literal[1]
    source: Literal["checkpoint_and_receipts"]
    checkpoint_id: Text | None
    checkpoint_at: AwareDatetime | None
    checkpoints: Annotated[list[Checkpoint], Field(max_length=20)]
    progress: Annotated[list[Progress], Field(max_length=30)]
    artifacts: Annotated[list[Artifact], Field(max_length=20)]
    uncertainties: Annotated[
        list[
            Literal[
                "checkpoint_unavailable",
                "progress_unavailable",
                "external_effect_unknown",
                "resource_cleanup_unconfirmed",
            ]
        ],
        Field(max_length=10),
    ]
    truncated: Annotated[bool, Field(strict=True)]
    background_tasks: "BackgroundStopSummary | None" = None


class BackgroundStopSummary(Fields):
    target_count: Count
    cleanup_confirmed_count: Count
    cleanup_unconfirmed_count: Count
    notifications_suppressed_count: Count
    truncated: Annotated[bool, Field(strict=True)]


class StopRequest(Fields):
    version: Literal[1]
    stop_id: UUID
    thread_id: UUID
    phase: Literal[
        "accepted",
        "stopping",
        "stopped",
        "no_active_run",
        "confirmation_unavailable",
        "rejected",
    ]
    requested_at: AwareDatetime
    accepted_at: AwareDatetime | None
    confirmed_at: AwareDatetime | None
    target_count: Count | None
    execution_stopped: Annotated[bool, Field(strict=True)] | None
    resource_cleanup: Literal["pending", "confirmed", "unconfirmed", "not_required"]
    has_pending_interrupts: Annotated[bool, Field(strict=True)] | None
    queue: QueueCounts
    report: StopReport | None
    reason_code: (
        Literal[
            "stop_denied",
            "stop_confirmation_unavailable",
            "resource_cleanup_unconfirmed",
        ]
        | None
    )
    request_id: Text = ""

    @model_validator(mode="after")
    def confirmed_phase(self):
        if self.phase in {"stopped", "no_active_run"} and (
            self.execution_stopped is not True
            or self.confirmed_at is None
            or self.report is None
        ):
            raise ValueError("invalid_stop_confirmation")
        return self


class StopRequestList(Fields):
    items: Annotated[list[StopRequest], Field(max_length=100)]
    next_cursor: Text | None


class StopAuditBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stop_id: UUID
    tenant_id: Annotated[str, Field(min_length=1, max_length=64)]
    project_id: UUID
    thread_id: UUID
    owner_id: Annotated[str, Field(min_length=1, max_length=255)]
    credential_id: UUID | None
    authorize: Annotated[bool, Field(strict=True)]
    phase: Literal[
        "accepted",
        "stopping",
        "stopped",
        "no_active_run",
        "confirmation_unavailable",
        "rejected",
    ]
    request_id: Annotated[str, Field(max_length=256)] | None
    platform_trace_id: Annotated[str, Field(max_length=256)] | None
    target_count: Count | None


def authorize_and_audit_stop(factory, payload):
    from platform_api.core.errors import ForbiddenError
    from platform_api.modules.iam.application import (
        AuthorizationRequest,
        IamPolicyEngine,
        PermissionCode,
    )
    from platform_api.modules.identity.actors import (
        load_service_account_actor,
        load_user_actor,
    )
    from platform_api.modules.runtime_gateway.application import thread_access
    from platform_api.modules.runtime_gateway.infra.sqlalchemy.run_control import (
        assert_project_scope,
        record_stop_phase,
    )

    data = payload.model_dump(mode="json")
    assert_project_scope(factory, payload)
    owner = data["owner_id"]
    actor = (
        load_service_account_actor(
            session_factory=factory,
            subject=owner,
            credential_id=data["credential_id"],
            project_id=data["project_id"],
        )
        if owner.startswith("service-account:")
        else load_user_actor(
            session_factory=factory, user_id=owner, project_id=data["project_id"]
        )
        if data["credential_id"] is None
        else None
    )
    allowed = False
    if actor is not None:
        try:
            IamPolicyEngine().require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PROJECT_RUNTIME_EXECUTE,
                    project_id=data["project_id"],
                ),
            )
            allowed = thread_access.allowed(
                actor,
                data["project_id"],
                thread_access.get(factory, data["thread_id"]) or {},
                "edit",
            )
        except ForbiddenError:
            pass
    if payload.authorize:
        return {"allowed": allowed}
    record_stop_phase(factory, payload)
    return {"allowed": allowed}
