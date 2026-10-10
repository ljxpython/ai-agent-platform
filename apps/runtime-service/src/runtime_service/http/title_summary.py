"""Internal HTTP endpoint for thread title summarization."""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from runtime_service.auth.platform import authenticate, authorize_thread_targets
from runtime_service.runtime import (
    RuntimeAuthError,
    RuntimeResolutionError,
    verified_delegation_from_user,
)
from runtime_service.services.thread_titles import generate_thread_title

router = APIRouter(prefix="/internal/threads/{thread_id}/title", tags=["title-summary"])


class MessagePayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    role: str
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str) -> str:
        if value not in {"user", "assistant"}:
            raise ValueError("role must be user or assistant")
        return value


class SummarizeTitleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    assistant_id: str = Field(min_length=1, max_length=128)
    messages: list[MessagePayload] = Field(default_factory=list, max_length=8)
    files: list[dict[str, Any]] = Field(default_factory=list, max_length=8)
    timeout_seconds: float = Field(default=8.0, gt=0, le=30, strict=True)
    context: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_runtime_fields(self) -> SummarizeTitleRequest:
        if sum(len(item.content) for item in self.messages) > 12000:
            raise ValueError("title_payload_too_large")
        if set(self.context) - {
            "model_id",
            "temperature",
            "max_tokens",
            "top_p",
            "execution_mode",
            "access_policy",
            "offload_conversation",
        }:
            raise ValueError("invalid title context")
        if set(self.config) - {"configurable"}:
            raise ValueError("invalid title config")
        configurable = self.config.get("configurable", {})
        if not isinstance(configurable, dict) or set(configurable) - {
            "runtime_model_ref",
            "platform_runtime",
        }:
            raise ValueError("invalid title configurable")
        platform_runtime = configurable.get("platform_runtime")
        if platform_runtime is not None and (
            not isinstance(platform_runtime, dict)
            or set(platform_runtime)
            - {
                "model_id",
                "temperature",
                "max_tokens",
                "top_p",
                "execution_mode",
                "access_policy",
                "offload_conversation",
            }
        ):
            raise ValueError("invalid title runtime options")
        return self


class SummarizeTitleResponse(BaseModel):
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
    ) = None


def _authorize_scope(
    thread_id: str, payload: SummarizeTitleRequest, facts: dict
) -> None:
    scope = facts.get("runtime_scope", {})
    principal = facts.get("runtime_principal", {})
    if (
        scope.get("operation") != "title-generate"
        or scope.get("thread_id") != thread_id
        or scope.get("assistant_id") != payload.assistant_id
        or scope.get("project_id") != principal.get("project_id")
        or scope.get("tenant_id") != principal.get("tenant_id")
    ):
        raise HTTPException(403, {"code": "title_scope_denied"})


@router.post("/summarize", response_model=SummarizeTitleResponse)
async def summarize_thread_title_endpoint(
    thread_id: str,
    payload: SummarizeTitleRequest,
    authorization: str | None = Header(default=None),
) -> SummarizeTitleResponse:
    """通过精确委托调用一次受管模型，不进入 Agent graph。"""
    if not thread_id or not thread_id.strip():
        raise HTTPException(status_code=400, detail="Invalid thread_id")
    facts_dict = await authenticate(authorization)
    _authorize_scope(thread_id, payload, facts_dict)
    await authorize_thread_targets(facts_dict, [thread_id], action="comment")
    await authorize_thread_targets(facts_dict, [thread_id], action="edit")
    try:
        result = await generate_thread_title(
            facts=verified_delegation_from_user(facts_dict),
            thread_id=thread_id,
            payload={
                "assistant_id": payload.assistant_id,
                "messages": [msg.model_dump() for msg in payload.messages],
                "files": payload.files,
                "timeout_seconds": payload.timeout_seconds,
                "context": payload.context,
                "config": payload.config,
            },
        )
        return SummarizeTitleResponse(thread_id=thread_id, **result)
    except (RuntimeAuthError, RuntimeResolutionError) as exc:
        raise HTTPException(status_code=403, detail={"code": exc.code}) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail={"code": "invalid_title_payload"}
        ) from exc
