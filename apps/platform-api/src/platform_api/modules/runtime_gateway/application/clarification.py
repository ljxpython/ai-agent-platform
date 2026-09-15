"""Validate P1 clarification answers before creating a resume Run."""
from __future__ import annotations

import json
import math
from datetime import date

from platform_api.core.errors import PlatformApiError


def validate_clarification_resumes(state: dict, resumes: dict) -> None:
    interrupts = state.get("interrupts")
    if isinstance(interrupts, dict):
        entries = [(key, value.get("value", value)) for key, value in interrupts.items() if isinstance(value, dict)]
    else:
        records = interrupts if isinstance(interrupts, list) else [
            item for task in state.get("tasks", []) if isinstance(task, dict)
            for item in task.get("interrupts", [])
        ]
        entries = [
            (item.get("id") or item.get("interrupt_id"), item.get("value"))
            for item in records if isinstance(item, dict)
        ]
    for identifier, request in entries:
        if identifier not in resumes or not isinstance(request, dict) or request.get("kind") != "clarification":
            continue
        try:
            _validate(request, resumes[identifier])
        except (ValueError, TypeError, KeyError) as exc:
            raise PlatformApiError(
                code="invalid_clarification_answer", status_code=422,
                message="Clarification answer does not match the active request",
            ) from exc


def _validate(request: dict, answer: object) -> None:
    if type(request.get("schema_version")) is not int or request["schema_version"] != 1:
        raise ValueError("unsupported request")
    fields = request.get("fields")
    if not isinstance(fields, list) or not 1 <= len(fields) <= 16:
        raise ValueError("invalid fields")
    if not isinstance(answer, dict) or set(answer) != {"schema_version", "status", "values"}:
        raise ValueError("invalid answer")
    if type(answer["schema_version"]) is not int or answer["schema_version"] != 1 or answer["status"] != "answered":
        raise ValueError("unsupported answer")
    values = answer["values"]
    names = [field["name"] for field in fields]
    if len(set(names)) != len(names) or not isinstance(values, dict) or set(values) - set(names):
        raise ValueError("unknown or duplicate fields")
    for field in fields:
        if field["type"] not in {"text", "textarea", "number", "select", "multi_select", "checkbox", "date"}:
            raise ValueError("unsupported field")
        name = field["name"]
        if name not in values and not field.get("required", True):
            continue
        value = values.get(name)
        kind = field["type"]
        if kind == "number":
            if type(value) not in (int, float) or abs(value) > 1e308 or not math.isfinite(value):
                raise ValueError("invalid finite number")
        elif kind == "checkbox":
            if type(value) is not bool:
                raise ValueError("invalid boolean")
        elif kind == "multi_select":
            if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
                raise ValueError("invalid selection")
            if (field.get("required", True) and not value) or len(set(value)) != len(value) or set(value) - {o["value"] for o in field["options"]}:
                raise ValueError("invalid options")
        else:
            if not isinstance(value, str) or (field.get("required", True) and not value.strip()):
                raise ValueError("invalid field value")
            if kind == "select" and value not in {option["value"] for option in field["options"]}:
                raise ValueError("invalid option")
            if kind == "date" and (len(value) != 10 or date.fromisoformat(value).isoformat() != value):
                raise ValueError("invalid date")
    if sum(len(v) for v in values.values() if isinstance(v, str)) > 8000 or len(json.dumps(answer, allow_nan=False).encode()) > 16384:
        raise ValueError("answer too large")
