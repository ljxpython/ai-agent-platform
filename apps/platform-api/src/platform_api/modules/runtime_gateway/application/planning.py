"""Plan review validation at the authenticated platform boundary."""

import hashlib
import json
import re
from datetime import datetime

from platform_api.core.errors import BadRequestError, ConflictError, ForbiddenError

PLAN_GRAPHS = frozenset(
    ("reference_agent", "workflow_demo", "showcase_demo", "dearflow_agent")
)


def _snapshot_fields(raw: object) -> dict | None:
    if (
        not isinstance(raw, dict)
        or type(raw.get("version")) is not int
        or raw["version"] != 1
    ):
        return None
    if type(raw.get("revision")) is not int or raw["revision"] < 0:
        return None
    if not all(
        isinstance(raw.get(key), str) for key in ("plan_id", "title", "markdown")
    ):
        return None
    if not 0 < len(raw["plan_id"]) <= 128 or len(raw["title"]) > 128:
        return None
    try:
        if len(raw["markdown"].encode("utf-8")) > 65536:
            return None
        fields = {
            key: raw[key]
            for key in ("version", "plan_id", "revision", "title", "markdown")
        }
        canonical = json.dumps(
            fields,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except UnicodeError:
        return None
    if raw["revision"] == 0:
        if raw["title"] or raw["markdown"] or raw.get("content_hash") is not None:
            return None
    elif (
        not raw["title"].strip()
        or not raw["markdown"].strip()
        or raw.get("content_hash") != "sha256:" + hashlib.sha256(canonical).hexdigest()
    ):
        return None
    return {**fields, "content_hash": raw.get("content_hash")}


def interrupt_entries(state: dict) -> dict[str, dict]:
    raw = state.get("interrupts")
    if isinstance(raw, dict):
        return {
            key: value.get("value", value)
            for key, value in raw.items()
            if isinstance(value, dict)
        }
    records = (
        raw
        if isinstance(raw, list)
        else [
            i
            for task in state.get("tasks", [])
            if isinstance(task, dict)
            for i in task.get("interrupts", [])
        ]
    )
    return {
        item.get("id") or item.get("interrupt_id"): item.get("value")
        for item in records
        if isinstance(item, dict)
    }


def validate_plan_resumes(state: dict, resumes: dict, actor) -> None:
    entries = interrupt_entries(state)
    for identifier, reply in resumes.items():
        request = entries.get(identifier)
        if not isinstance(request, dict) or request.get("type") != "agent_plan_review":
            if isinstance(reply, dict) and reply.get("type") == "agent_plan_response":
                raise ConflictError(
                    code="plan_revision_conflict",
                    message="Plan review is no longer active",
                )
            continue
        if actor.principal_type != "user" or not actor.user_id or actor.credential_id:
            raise ForbiddenError(
                code="plan_actor_denied", message="Plan review requires a human user"
            )
        if (
            _snapshot_fields(request) is None
            or request["revision"] == 0
            or request.get("allowed_decisions")
            != ["approve", "request_changes", "abandon"]
        ):
            raise BadRequestError(
                code="plan_response_invalid", message="Invalid plan snapshot"
            )
        required = {
            "version",
            "type",
            "plan_id",
            "revision",
            "content_hash",
            "decision",
        }
        if (
            not isinstance(reply, dict)
            or not required <= set(reply)
            or set(reply) - required - {"feedback"}
        ):
            raise BadRequestError(
                code="plan_response_invalid", message="Invalid plan response"
            )
        feedback = reply.get("feedback")
        if (
            type(reply["version"]) is not int
            or reply["version"] != 1
            or reply["type"] != "agent_plan_response"
            or type(reply["revision"]) is not int
            or reply["revision"] < 1
        ):
            raise BadRequestError(
                code="plan_response_invalid", message="Invalid plan response"
            )
        if (
            not isinstance(reply["decision"], str)
            or reply["decision"] not in {"approve", "request_changes", "abandon"}
            or feedback is not None
            and (not isinstance(feedback, str) or len(feedback) > 2000)
        ):
            raise BadRequestError(
                code="plan_response_invalid", message="Invalid plan response"
            )
        if reply["decision"] == "request_changes" and not (
            feedback and feedback.strip()
        ):
            raise BadRequestError(
                code="plan_response_invalid", message="Feedback is required"
            )
        try:
            if feedback is not None:
                feedback.encode("utf-8")
        except UnicodeError as exc:
            raise BadRequestError(
                code="plan_response_invalid", message="Invalid feedback"
            ) from exc
        if not all(
            reply[key] == request.get(key)
            for key in ("plan_id", "revision", "content_hash")
        ):
            raise ConflictError(
                code="plan_revision_conflict", message="Plan snapshot changed"
            )
        if (
            type(request.get("version")) is not int
            or request["version"] != 1
            or not isinstance(reply["content_hash"], str)
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", reply["content_hash"])
        ):
            raise BadRequestError(
                code="plan_response_invalid", message="Invalid plan snapshot"
            )


def execution_id(project_id: str, thread_id: str, key: str) -> str:
    encoded = json.dumps(
        ["plan-execution/v1", project_id, thread_id, key], separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode()).hexdigest()


def project_agent_plan(raw: object) -> dict | None:
    fields = _snapshot_fields(raw)
    if fields is None or type(raw.get("active")) is not bool:
        return None
    reply = raw.get("decision")
    decision = reply.get("decision") if isinstance(reply, dict) else None
    if decision is not None and (
        not isinstance(decision, str)
        or decision not in {"approve", "request_changes", "abandon"}
    ):
        return None
    if reply is not None and (
        decision is None
        or not all(
            reply.get(key) == fields[key]
            for key in ("plan_id", "revision", "content_hash")
        )
    ):
        return None
    if (
        not raw["active"]
        and decision != "approve"
        or raw["active"]
        and decision == "approve"
    ):
        return None
    result = {**fields, "active": raw["active"]}
    result.update(
        decision=decision,
        status="abandoned"
        if decision == "abandon"
        else "planning"
        if raw["active"]
        else "approved",
    )
    if not raw["active"] and decision == "approve":
        approved_by = raw.get("approved_by")
        if (
            not isinstance(approved_by, dict)
            or set(approved_by) != {"user_id"}
            or not isinstance(approved_by["user_id"], str)
            or not 0 < len(approved_by["user_id"]) <= 128
        ):
            return None
        try:
            if (
                not isinstance(raw.get("approved_at"), str)
                or len(raw["approved_at"]) > 64
                or datetime.fromisoformat(raw["approved_at"]).tzinfo is None
            ):
                return None
        except ValueError:
            return None
        result.update(approved_by=approved_by, approved_at=raw["approved_at"])
    return result


def mark_plan_review(state: object) -> object:
    if not isinstance(state, dict):
        return state
    values = state.get("values")
    if not isinstance(values, dict):
        return state
    for item in interrupt_entries(state).values():
        if isinstance(item, dict) and item.get("type") == "agent_plan_review":
            fields = _snapshot_fields(item)
            if fields and fields["revision"] > 0:
                # Nested Workflow state commits after resume; the native interrupt is current.
                plan = {
                    **fields,
                    "active": True,
                    "decision": None,
                    "status": "awaiting_review",
                }
                return {**state, "values": {**values, "agent_plan": plan}}
    return state
