"""Task DTOs and current authorization at the Platform boundary."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    model_validator,
)

from platform_api.core.errors import PlatformApiError
from platform_api.core.identifiers import parse_uuid
from platform_api.modules.runtime_gateway.application import thread_access

Count = Annotated[int, Field(strict=True, ge=0, le=9007199254740991)]
Reason = Literal[
    "background_task_control_unavailable",
    "background_task_resource_missing",
    "background_task_start_unconfirmed",
    "background_task_deadline_exceeded",
    "background_task_oom",
    "background_task_command_failed",
    "background_task_disabled",
    "background_task_delivery_expired",
    "background_task_delivery_unavailable",
    "background_task_denied",
    "background_task_thread_busy",
    "background_task_approval_pending",
]


class Fields(BaseModel):
    model_config = ConfigDict(extra="ignore")


class CancelBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TaskOutput(Fields):
    available: StrictBool
    retained_bytes: Annotated[int, Field(strict=True, ge=0, le=1048576)]
    omitted_bytes: Count
    truncated: StrictBool
    updated_at: AwareDatetime | None


class TaskDelivery(Fields):
    state: Literal[
        "not_ready",
        "pending",
        "dispatching",
        "accepted",
        "blocked",
        "suppressed",
        "expired",
        "unknown",
    ]
    event_id: UUID | None
    run_id: UUID | None
    reason_code: Reason | None

    @model_validator(mode="after")
    def accepted_receipt(self):
        if self.state == "accepted" and self.run_id is None:
            raise ValueError("missing_background_run_receipt")
        return self


class BackgroundTask(Fields):
    version: Literal[1]
    task_id: UUID
    thread_id: UUID
    graph_id: Annotated[str, Field(min_length=1, max_length=128)]
    origin_run_id: UUID
    status: Literal[
        "starting",
        "running",
        "succeeded",
        "failed",
        "timed_out",
        "cancel_requested",
        "cancelled",
        "unknown",
    ]
    reason_code: Reason | None
    exit_code: Annotated[int, Field(strict=True, ge=-255, le=255)] | None
    created_at: AwareDatetime
    started_at: AwareDatetime | None
    finished_at: AwareDatetime | None
    deadline_at: AwareDatetime
    updated_at: AwareDatetime
    cleanup_state: Literal["not_required", "pending", "confirmed", "unconfirmed"]
    output: TaskOutput
    delivery: TaskDelivery
    allowed_actions: Annotated[
        list[Literal["read", "logs", "cancel"]], Field(max_length=3)
    ]


class BackgroundTaskList(Fields):
    version: Literal[1]
    thread_id: UUID
    items: Annotated[list[BackgroundTask], Field(max_length=100)]
    next_cursor: Annotated[str, Field(max_length=256)] | None
    has_unresolved: StrictBool
    latest_delivery_run_id: UUID | None


class BackgroundOutput(TaskOutput):
    version: Literal[1]
    task_id: UUID
    thread_id: UUID
    text: str

    @model_validator(mode="after")
    def bounded_text(self):
        if len(self.text.encode()) > 65536 or not self.available and self.text:
            raise ValueError("invalid_background_output")
        return self


async def background_task_action(
    gateway,
    *,
    actor,
    project_id,
    thread_id,
    task_id=None,
    action="list",
    params=None,
    key=None,
):
    from pydantic import ValidationError

    thread_id = str(parse_uuid(thread_id, code="invalid_thread_id"))
    if task_id is not None:
        task_id = str(parse_uuid(task_id, code="invalid_background_task_id"))
    thread = await gateway._load_thread(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        write=action == "cancel",
        action="edit" if action == "cancel" else "read",
    )
    graph_id = (thread.get("metadata") or {}).get("graph_id")
    operation = (
        "background-task-cancel"
        if action == "cancel"
        else "background-task-log-read"
        if action == "output"
        else "background-task-read"
    )
    upstream = await gateway._thread_upstream(
        project_id=project_id, thread=thread, operation=operation
    )
    if action == "list":
        payload = await upstream.list_background_tasks(thread_id, params or {})
        model = BackgroundTaskList
    elif action == "output":
        payload = await upstream.get_background_output(thread_id, task_id)
        model = BackgroundOutput
    elif action == "cancel":
        payload = await upstream.cancel_background_task(thread_id, task_id, key)
        model = BackgroundTask
    else:
        payload = await upstream.get_background_task(thread_id, task_id)
        model = BackgroundTask
    try:
        result = model.model_validate(payload).model_dump(mode="json")
        if result["thread_id"] != thread_id or task_id and result["task_id"] != task_id:
            raise ValueError("background_scope_mismatch")
        for item in result.get("items", [result] if action != "output" else []):
            if item["thread_id"] != thread_id or item["graph_id"] != graph_id:
                raise ValueError("background_scope_mismatch")
            # Runtime confirms tool permissions again when an action is invoked.
            if not thread_access.allowed(
                actor, project_id, thread.get("metadata") or {}, "edit"
            ):
                item["allowed_actions"] = [
                    name for name in item["allowed_actions"] if name != "cancel"
                ]
        return result
    except (ValidationError, ValueError, TypeError, KeyError) as exc:
        raise PlatformApiError(
            code="langgraph_upstream_invalid_response",
            status_code=502,
            message="Invalid Runtime background task response",
        ) from exc
