"""Validated checkpoint snapshots for the optional planning restriction."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from runtime_service.runtime.errors import RuntimeResolutionError
from runtime_service.runtime.resolver import parse_runtime_context

PLAN_TOOL_NAMES = ("enter_plan_mode", "save_plan", "submit_plan")
PLAN_GRAPHS = frozenset(
    ("reference_agent", "workflow_demo", "showcase_demo", "dearflow_agent")
)


class PlanReply(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: Literal[1]
    type: Literal["agent_plan_response"]
    plan_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(gt=0)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    decision: Literal["approve", "request_changes", "abandon"]
    feedback: str | None = Field(default=None, max_length=2000)

    @field_validator("version", mode="before")
    @classmethod
    def strict_version(cls, value):
        if type(value) is not int:
            raise ValueError("Invalid version")
        return value

    @model_validator(mode="after")
    def validate_feedback(self):
        if self.feedback is not None:
            self.feedback.encode("utf-8")
        if self.decision == "request_changes" and not (
            self.feedback and self.feedback.strip()
        ):
            raise ValueError("Feedback is required")
        if isinstance(self.version, bool):
            raise ValueError("Invalid version")
        return self


class PlanSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    version: Literal[1] = 1
    active: bool = True
    plan_id: str = Field(min_length=1, max_length=128)
    revision: int = Field(default=0, ge=0)
    title: str = Field(default="", max_length=128)
    markdown: str = ""
    content_hash: str | None = None
    bound_execution_id: str = Field(min_length=1, max_length=128)
    decision: PlanReply | None = None
    approved_by: dict[str, str] | None = None
    approved_at: str | None = None

    @field_validator("version", mode="before")
    @classmethod
    def strict_version(cls, value):
        if type(value) is not int:
            raise ValueError("Invalid version")
        return value

    @model_validator(mode="after")
    def validate_snapshot(self):
        if isinstance(self.version, bool):
            raise ValueError("Invalid version")
        if self.revision == 0:
            if (
                self.title
                or self.markdown
                or self.content_hash is not None
                or self.decision is not None
            ):
                raise ValueError("Invalid empty draft")
        else:
            validate_plan_text(self.title, self.markdown)
            if self.content_hash != plan_content_hash(self):
                raise ValueError("Invalid snapshot hash")
        if self.decision and not reply_matches(self, self.decision):
            raise ValueError("Decision snapshot mismatch")
        if not self.active and not (
            self.decision
            and self.decision.decision == "approve"
            and self.approved_by
            and set(self.approved_by) == {"user_id"}
            and self.approved_by["user_id"]
            and self.approved_at
        ):
            raise ValueError("Approval is required")
        if self.active and (
            self.approved_by is not None or self.approved_at is not None
        ):
            raise ValueError("Active plans cannot have an approval")
        if self.active and self.decision and self.decision.decision == "approve":
            raise ValueError("Approved plans cannot remain active")
        if (
            self.approved_at is not None
            and datetime.fromisoformat(self.approved_at).tzinfo is None
        ):
            raise ValueError("Approval time requires a timezone")
        return self


def validate_plan_text(title: str, markdown: str) -> None:
    try:
        valid = 0 < len(title.strip()) <= 128 and bool(markdown.strip())
        valid = valid and len(markdown.encode("utf-8")) <= 65536
        title.encode("utf-8")
    except (AttributeError, UnicodeError):
        valid = False
    if not valid:
        raise RuntimeResolutionError("runtime.plan.content_invalid")


def plan_content_hash(plan: PlanSnapshot) -> str:
    data = {
        key: getattr(plan, key)
        for key in ("version", "plan_id", "revision", "title", "markdown")
    }
    encoded = json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def read_plan(state: Mapping) -> PlanSnapshot | None:
    value = state.get("runtime_plan")
    if value is None:
        return None
    try:
        return PlanSnapshot.model_validate(value)
    except (ValidationError, UnicodeError, ValueError) as exc:
        raise RuntimeResolutionError("runtime.plan.state_invalid") from exc


def new_plan(execution_id: str | None) -> PlanSnapshot:
    if not execution_id:
        raise RuntimeResolutionError("runtime.plan.execution_missing")
    return PlanSnapshot(plan_id=str(uuid4()), bound_execution_id=execution_id)


def bound_plan(state: Mapping, context: object) -> PlanSnapshot:
    plan = read_plan(state)
    parsed = parse_runtime_context(context)
    if not plan or plan.bound_execution_id != parsed.plan_execution_id:
        raise RuntimeResolutionError("runtime.plan.state_invalid")
    return plan


def plan_is_active(state: Mapping) -> bool:
    plan = read_plan(state)
    return bool(plan and plan.active)


def reply_matches(plan: PlanSnapshot, reply: PlanReply) -> bool:
    return all(
        getattr(plan, key) == getattr(reply, key)
        for key in ("plan_id", "revision", "content_hash")
    )


def plan_interrupt(plan: PlanSnapshot) -> dict:
    return {
        "version": 1,
        "type": "agent_plan_review",
        **{
            key: getattr(plan, key)
            for key in ("plan_id", "revision", "content_hash", "title", "markdown")
        },
        "allowed_decisions": ["approve", "request_changes", "abandon"],
    }


def apply_plan_reply(plan: PlanSnapshot, raw: object, user_id: str) -> PlanSnapshot:
    try:
        reply = PlanReply.model_validate(raw)
    except (ValidationError, UnicodeError) as exc:
        raise RuntimeResolutionError("runtime.plan.response_invalid") from exc
    if not reply_matches(plan, reply) or not user_id:
        raise RuntimeResolutionError("runtime.plan.response_invalid")
    approved = reply.decision == "approve"
    return PlanSnapshot.model_validate(
        {
            **plan.model_dump(),
            "active": not approved,
            "decision": reply.model_dump(),
            "approved_by": {"user_id": user_id} if approved else None,
            "approved_at": datetime.now(UTC).isoformat() if approved else None,
        }
    )
