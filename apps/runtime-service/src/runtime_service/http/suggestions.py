"""Scoped one-shot suggestions endpoint; it never enters the Agent graph."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from runtime_service.auth.platform import authenticate
from runtime_service.runtime import (
    RuntimeAuthError,
    RuntimeResolutionError,
    verified_delegation_from_user,
)
from runtime_service.services.suggestions import generate_suggestions

router = APIRouter(prefix="/internal/threads/{thread_id}", tags=["suggestions"])


class SuggestionMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("role")
    @classmethod
    def valid_role(cls, value: str) -> str:
        if value not in {"user", "assistant"}:
            raise ValueError("role must be user or assistant")
        return value


class SuggestionsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assistant_id: str = Field(min_length=1, max_length=128)
    messages: list[SuggestionMessage] = Field(min_length=1, max_length=6)
    n: int = Field(default=3, ge=1, le=5, strict=True)
    timeout_seconds: float = Field(default=8.0, gt=0, le=30, strict=True)
    context: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_runtime_fields(self) -> SuggestionsRequest:
        if set(self.context) - {
            "model_id",
            "temperature",
            "max_tokens",
            "top_p",
            "execution_mode",
            "access_policy",
        }:
            raise ValueError("invalid suggestion context")
        if set(self.config) - {"configurable"}:
            raise ValueError("invalid suggestion config")
        configurable = self.config.get("configurable", {})
        if not isinstance(configurable, dict) or set(configurable) - {
            "runtime_model_ref",
            "platform_runtime",
        }:
            raise ValueError("invalid suggestion configurable")
        platform_runtime = configurable.get("platform_runtime")
        if platform_runtime is not None and (
            not isinstance(platform_runtime, dict)
            or set(platform_runtime)
            - {"model_id", "temperature", "max_tokens", "top_p", "execution_mode"}
        ):
            raise ValueError("invalid suggestion runtime options")
        return self


class SuggestionsResponse(BaseModel):
    suggestions: list[str]


def _authorize_scope(thread_id: str, payload: SuggestionsRequest, facts: dict) -> None:
    scope = facts.get("runtime_scope", {})
    principal = facts.get("runtime_principal", {})
    if (
        scope.get("operation") != "suggestions-generate"
        or scope.get("thread_id") != thread_id
        or scope.get("assistant_id") != payload.assistant_id
        or scope.get("project_id") != principal.get("project_id")
        or scope.get("tenant_id") != principal.get("tenant_id")
    ):
        raise HTTPException(403, {"code": "suggestions_scope_denied"})


@router.post("/suggestions", response_model=SuggestionsResponse)
async def suggestions_endpoint(
    thread_id: str,
    payload: SuggestionsRequest,
    authorization: str | None = Header(default=None),
) -> SuggestionsResponse:
    facts_dict = await authenticate(authorization)
    _authorize_scope(thread_id, payload, facts_dict)
    try:
        facts = verified_delegation_from_user(facts_dict)
        suggestions = await generate_suggestions(
            facts=facts,
            thread_id=thread_id,
            payload=payload.model_dump(),
        )
    except RuntimeAuthError as exc:
        raise HTTPException(403, {"code": exc.code}) from exc
    except RuntimeResolutionError as exc:
        raise HTTPException(403, {"code": exc.code}) from exc
    except ValueError as exc:
        raise HTTPException(422, {"code": str(exc)}) from exc
    return SuggestionsResponse(suggestions=suggestions)


__all__ = ["router"]
