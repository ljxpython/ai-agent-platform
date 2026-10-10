"""Bounded title requests and materials from the committed root conversation."""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TITLE_SEED_KEY = "_runtime_title_seed"
_PRIVATE_BLOCK = re.compile(
    r"<(think|system_reminder|todo_reminder)\b[^>]*>.*?(?:</\1\s*>|$)",
    re.IGNORECASE | re.DOTALL,
)
_REFERENCE = re.compile(
    r"(?:https?://|data:|/workspace/|/Users/|/home/|[A-Za-z]:[\\/])\S+", re.IGNORECASE
)


def text_content(value: object) -> str:
    if isinstance(value, list):
        value = " ".join(
            block["text"]
            for block in value
            if isinstance(block, dict)
            and block.get("type") in {"text", "input_text", "output_text"}
            and not block.get("extras")
            and isinstance(block.get("text"), str)
        )
    if not isinstance(value, str):
        return ""
    value = _REFERENCE.sub("", _PRIVATE_BLOCK.sub("", value))
    return " ".join(
        "".join(
            ch if unicodedata.category(ch) not in {"Cc", "Cf"} else " " for ch in value
        ).split()
    )


class TitleMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    role: Literal["user", "assistant", "human", "ai"]
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("blank title material")
        return value


class TitleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    mode: Literal["manual", "auto"] = "manual"
    run_id: str | None = None
    messages: list[TitleMessage] | None = Field(
        default=None, min_length=1, max_length=8
    )

    @model_validator(mode="after")
    def validate_mode(self) -> TitleRequest:
        if (
            self.mode == "auto"
            and (not self.run_id or "messages" in self.model_fields_set)
        ) or (self.mode == "manual" and "run_id" in self.model_fields_set):
            raise ValueError("invalid title mode fields")
        if self.messages and sum(len(item.content) for item in self.messages) > 12000:
            raise ValueError("title messages too large")
        return self


class TitleGenerationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    thread_id: str
    title: str | None
    outcome: Literal["applied", "skipped", "degraded"]
    reason: (
        Literal[
            "materials_missing",
            "model_unavailable",
            "timeout",
            "provider_failure",
            "empty_output",
        ]
        | None
    )

    @model_validator(mode="after")
    def validate_result(self) -> TitleGenerationResult:
        if (self.outcome == "applied" and self.reason is not None) or (
            self.outcome != "applied" and self.reason is None
        ):
            raise ValueError("invalid title outcome")
        return self


def conversation_materials(
    messages: object, *, first_round: bool
) -> tuple[list[dict[str, str]], list[dict[str, Any]], str | None]:
    if not isinstance(messages, list):
        return [], [], "materials_missing"
    normalized: list[dict[str, str]] = []
    files: list[dict[str, Any]] = []
    users = 0
    final_answer = False
    for msg in messages:
        if not isinstance(msg, dict):
            if not hasattr(msg, "content"):
                continue
            msg = {
                key: getattr(msg, key, None)
                for key in (
                    "type",
                    "content",
                    "name",
                    "additional_kwargs",
                    "tool_calls",
                )
            }
        role = {"human": "user", "ai": "assistant"}.get(
            msg.get("role") or msg.get("type"), msg.get("role") or msg.get("type")
        )
        if role not in {"user", "assistant"} or msg.get("name") in {
            "system_reminder",
            "todo_reminder",
        }:
            continue
        content = text_content(msg.get("content"))
        refs = (
            [
                block["extras"]["runtime_file"]
                for block in msg.get("content", [])
                if isinstance(block, dict)
                and isinstance(block.get("extras"), dict)
                and isinstance(block["extras"].get("runtime_file"), dict)
            ]
            if isinstance(msg.get("content"), list)
            else []
        )
        if role == "user":
            raw = msg.get("content")
            if isinstance(raw, str) and not content and _PRIVATE_BLOCK.search(raw):
                continue
            users += 1
            files.extend(refs)
            final_answer = False
        else:
            kwargs = msg.get("additional_kwargs")
            if (
                msg.get("tool_calls")
                or isinstance(kwargs, dict)
                and kwargs.get("tool_calls")
            ):
                final_answer = False
                continue
            final_answer = bool(content)
        if content:
            normalized.append({"role": role, "content": content[:4000]})
    if first_round:
        if users != 1:
            return [], [], "not_first_round"
        if not final_answer:
            return [], [], "materials_missing"
        normalized = [item for item in normalized if item["role"] == "user"][:1] + [
            item for item in normalized if item["role"] == "assistant"
        ][-1:]
    elif len(normalized) > 8:
        normalized = normalized[:2] + normalized[-6:]
    remaining = 12000
    for item in normalized:
        item["content"] = item["content"][:remaining]
        remaining -= len(item["content"])
    normalized = [item for item in normalized if item["content"]]
    return normalized, files[:8], None if normalized or files else "materials_missing"


def public_title_metadata(metadata: dict) -> dict:
    result = {key: value for key, value in metadata.items() if key != TITLE_SEED_KEY}
    result["auto_title_pending"] = isinstance(
        metadata.get(TITLE_SEED_KEY), str
    ) and metadata[TITLE_SEED_KEY] == metadata.get("title")
    return result
