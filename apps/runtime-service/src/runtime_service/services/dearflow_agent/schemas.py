"""P1 text/select clarification contract inside official Interrupt.value."""
import json
import math
from datetime import date
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Option(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: str = Field(min_length=1, max_length=200)
    label: str = Field(min_length=1, max_length=200)


class ClarificationField(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str = Field(min_length=1, max_length=200)
    label: str = Field(min_length=1, max_length=200)
    type: Literal["text", "textarea", "number", "select", "multi_select", "checkbox", "date"]
    required: bool = True
    options: list[Option] = Field(default_factory=list, max_length=24)

    @model_validator(mode="after")
    def valid(self):
        if self.name in {"__proto__", "constructor", "prototype"}:
            raise ValueError("reserved field name")
        values = [o.value for o in self.options]
        if len(set(values)) != len(values):
            raise ValueError("duplicate options")
        if (self.type in {"select", "multi_select"} and not values) or (self.type not in {"select", "multi_select"} and values):
            raise ValueError("options do not match field type")
        return self


class ClarificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["clarification"] = "clarification"
    schema_version: Literal[1] = 1
    question: str = Field(min_length=1, max_length=2000)
    context: str = Field(default="", max_length=2000)
    fields: list[ClarificationField] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def valid(self):
        if len({f.name for f in self.fields}) != len(self.fields):
            raise ValueError("duplicate fields")
        if len(self.model_dump_json().encode()) > 16384:
            raise ValueError("request too large")
        return self


def validate_answer(request: ClarificationRequest, answer: object) -> dict:
    if not isinstance(answer, dict) or set(answer) != {"schema_version", "status", "values"}:
        raise ValueError("invalid clarification answer")
    if type(answer["schema_version"]) is not int or answer["schema_version"] != 1 or answer["status"] != "answered":
        raise ValueError("unsupported answer")
    values = answer["values"]
    if not isinstance(values, dict) or set(values) - {f.name for f in request.fields}:
        raise ValueError("unknown answer field")
    for field in request.fields:
        value = values.get(field.name)
        if value is None and not field.required and field.name not in values:
            continue
        if field.type == "number":
            if type(value) not in (int, float) or abs(value) > 1e308 or not math.isfinite(value):
                raise ValueError("invalid finite number")
        elif field.type == "checkbox":
            if type(value) is not bool:
                raise ValueError("invalid boolean")
        elif field.type == "multi_select":
            if not isinstance(value, list) or any(not isinstance(v, str) for v in value):
                raise ValueError("invalid selection")
            if (field.required and not value) or len(set(value)) != len(value) or set(value) - {o.value for o in field.options}:
                raise ValueError("invalid options")
        else:
            if not isinstance(value, str) or (field.required and not value.strip()):
                raise ValueError("missing or invalid field: " + field.name)
            if field.type == "select" and value not in {o.value for o in field.options}:
                raise ValueError("invalid option")
            if field.type == "date" and (len(value) != 10 or date.fromisoformat(value).isoformat() != value):
                raise ValueError("invalid date")
    text_size = sum(len(v) for v in values.values() if isinstance(v, str))
    if text_size > 8000 or len(json.dumps(answer, allow_nan=False).encode()) > 16384:
        raise ValueError("answer too large")
    return answer
