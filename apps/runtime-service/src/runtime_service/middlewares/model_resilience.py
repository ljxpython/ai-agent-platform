"""Bound official model retry/fallback without replaying tools or partial answers."""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import anthropic
import httpx
import openai
from deepagents.middleware.summarization import (
    SummarizationMiddleware,
    create_summarization_middleware,
)
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelFallbackMiddleware,
    ModelRequest,
    ModelRetryMiddleware,
)
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.callbacks.base import BaseCallbackManager
from langchain_core.exceptions import ContextOverflowError, ModelError
from langchain_core.messages import AIMessage
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI
from langgraph.errors import GraphBubbleUp

from runtime_service.runtime.contracts import ModelResiliencePolicy
from runtime_service.runtime.errors import RuntimeErrorBase, RuntimeResolutionError

logger = logging.getLogger(__name__)
_STATUS_CODES = {408, 429, 500, 502, 503, 504, 529}
_SDK_ERRORS = (openai.APIError, anthropic.APIError)
_QUOTA_CODES = {"insufficient_quota", "billing_hard_limit_reached", "billing_error"}
_INCOMPATIBLE_CODES = {
    "unsupported_parameter",
    "unsupported_value",
    "unsupported_content_type",
    "unsupported_image",
    "unsupported_tool",
    "model_not_supported",
}
_TRANSPORT_ERRORS = (
    TimeoutError,
    ConnectionError,
    httpx.TimeoutException,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
    openai.APIConnectionError,
    anthropic.APIConnectionError,
)


def _provider_error(exc: Exception) -> Exception:
    if isinstance(exc, ModelError) and isinstance(exc.__cause__, _SDK_ERRORS):
        return exc.__cause__
    return exc


def _provider_codes(exc: Exception) -> set[str]:
    body = getattr(_provider_error(exc), "body", None)
    detail = body.get("error", body) if isinstance(body, Mapping) else None
    if not isinstance(detail, Mapping):
        return set()
    return {
        value for key in ("code", "type") if isinstance(value := detail.get(key), str)
    }


def is_transient_model_error(exc: Exception) -> bool:
    if isinstance(exc, (RuntimeErrorBase, ContextOverflowError, GraphBubbleUp)):
        return False
    provider = _provider_error(exc)
    if isinstance(provider, _SDK_ERRORS):
        if _provider_codes(exc) & _QUOTA_CODES:
            return False
        status = getattr(provider, "status_code", None)
        if status is not None:
            return status in _STATUS_CODES
    if isinstance(exc, ModelError):
        return exc.is_retryable
    return isinstance(provider, _TRANSPORT_ERRORS)


def retry_after_seconds(exc: Exception) -> float:
    response = getattr(_provider_error(exc), "response", None)
    raw = (
        response.headers.get("retry-after")
        if isinstance(response, httpx.Response)
        else None
    )
    if not raw:
        return 0.0
    try:
        seconds = float(raw)
    except ValueError:
        try:
            value = parsedate_to_datetime(raw)
            seconds = (
                value.replace(tzinfo=value.tzinfo or UTC) - datetime.now(UTC)
            ).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return 0.0
    return max(0.0, seconds) if math.isfinite(seconds) else 0.0


def model_failure_code(
    exc: BaseException,
    *,
    partial: bool = False,
    budget_expired: bool = False,
    fallback: bool = False,
) -> str | None:
    if isinstance(exc, (RuntimeErrorBase, GraphBubbleUp)):
        return None
    if isinstance(exc, ContextOverflowError):
        return (
            "runtime.model.stream_interrupted"
            if partial
            else "runtime.model.provider_rejected"
        )
    if not isinstance(exc, (*_SDK_ERRORS, *_TRANSPORT_ERRORS, ModelError)):
        return None
    if partial:
        return "runtime.model.stream_interrupted"
    if budget_expired:
        return "runtime.model.retry_budget_exceeded"
    if fallback and _provider_codes(exc) & _INCOMPATIBLE_CODES:
        return "runtime.model.fallback_incompatible"
    return (
        "runtime.model.retry_exhausted"
        if is_transient_model_error(exc)
        else "runtime.model.provider_rejected"
    )


def _has_content(content: object) -> bool:
    if isinstance(content, str):
        return bool(content)
    if isinstance(content, list):
        return any(
            _has_content(block)
            if isinstance(block, str)
            else bool(
                isinstance(block, Mapping)
                and any(
                    block.get(key)
                    for key in (
                        "text",
                        "reasoning",
                        "thinking",
                        "args",
                        "input",
                        "image_url",
                        "data",
                        "signature",
                    )
                )
            )
            for block in content
        )
    return False


class _OutputObserver(BaseCallbackHandler):
    run_inline = True

    def __init__(self) -> None:
        self.has_output = False
        self.correlation = {}

    def on_chat_model_start(
        self,
        serialized,
        messages,
        *,
        run_id,
        parent_run_id=None,
        metadata=None,
        **kwargs,
    ):
        self.correlation = {
            "callback_run_id": str(run_id),
            "parent_run_id": str(parent_run_id),
        }
        for key in (
            "thread_id",
            "run_id",
            "request_id",
            "platform_trace_id",
            "langgraph_checkpoint_ns",
        ):
            value = (metadata or {}).get(key)
            if isinstance(value, str):
                self.correlation[key] = value[:256]

    def on_llm_new_token(self, token: str, *, chunk=None, **kwargs) -> None:
        message = getattr(chunk, "message", None)
        self.has_output = self.has_output or bool(
            token
            or _has_content(getattr(message, "content", None))
            or getattr(message, "tool_call_chunks", None)
            or getattr(message, "additional_kwargs", {}).get("reasoning_content")
            or getattr(message, "additional_kwargs", {}).get("reasoning")
            or getattr(message, "additional_kwargs", {}).get("reasoning_details")
        )


def _observed_request(request: ModelRequest, observer: _OutputObserver) -> ModelRequest:
    callbacks = request.model.callbacks
    if isinstance(callbacks, BaseCallbackManager):
        callbacks = callbacks.copy()
        callbacks.add_handler(observer)
    else:
        callbacks = [*(callbacks or []), observer]
    # A shallow per-attempt copy keeps callbacks local and preserves the SDK clients.
    model = request.model.model_copy(update={"callbacks": callbacks})
    return request.override(model=model)


def _add_summary(result, summary: dict) -> None:
    messages = [result] if isinstance(result, AIMessage) else result.result
    for message in messages:
        if isinstance(message, AIMessage):
            message.response_metadata = {
                **message.response_metadata,
                "platform_model_resilience": summary,
            }


def _check_fallback_capabilities(request: ModelRequest) -> None:
    profile = request.model.profile or {}
    if request.tools and profile.get("tool_calling") is False:
        raise RuntimeResolutionError("runtime.model.fallback_incompatible")
    for message in request.messages:
        # These adapters omit Anthropic thinking blocks instead of translating them.
        if (
            isinstance(request.model, (ChatOpenAI, ChatDeepSeek))
            and isinstance(message.content, list)
            and any(
                isinstance(block, Mapping)
                and block.get("type") in {"thinking", "redacted_thinking"}
                for block in message.content
            )
        ):
            raise RuntimeResolutionError("runtime.model.fallback_incompatible")
        for block in message.content_blocks:
            capability = {
                "image": "image_inputs",
                "audio": "audio_inputs",
                "video": "video_inputs",
            }.get(block.get("type"))
            if capability and profile.get(capability) is False:
                raise RuntimeResolutionError("runtime.model.fallback_incompatible")


@dataclass
class _Invocation:
    policy: ModelResiliencePolicy
    primary_model_id: str
    fallback_model: object
    observer: _OutputObserver = field(default_factory=_OutputObserver)
    attempts: int = 0
    last_error: Exception | None = None
    cooldowns: dict[str, float] = field(default_factory=dict)
    effective_model_id: str = ""
    started: float = field(default_factory=time.monotonic)

    def can_retry(self, exc: Exception) -> bool:
        return (
            self.attempts < self.policy.max_attempts
            and not self.observer.has_output
            and is_transient_model_error(exc)
        )

    async def call(self, candidate: ModelRequest, handler):
        if self.last_error is not None and not self.can_retry(self.last_error):
            raise self.last_error
        fallback = candidate.model is self.fallback_model
        self.effective_model_id = (
            self.policy.fallback_model_id if fallback else self.primary_model_id
        )
        if fallback:
            _check_fallback_capabilities(candidate)
        delay = self.cooldowns.get(self.effective_model_id, 0) - time.monotonic()
        if delay > 0:
            logger.info(
                "model_attempt_wait",
                extra={
                    **self.observer.correlation,
                    "model_id": self.effective_model_id,
                    "delay_seconds": delay,
                },
            )
            await asyncio.sleep(delay)
        self.attempts += 1
        attempt_started = time.monotonic()
        try:
            return await handler(_observed_request(candidate, self.observer))
        except Exception as exc:
            self.last_error = exc
            self.cooldowns[self.effective_model_id] = (
                time.monotonic() + retry_after_seconds(exc)
            )
            logger.info(
                "model_attempt_failed",
                extra={
                    **self.observer.correlation,
                    "requested_model_id": self.primary_model_id,
                    "model_id": self.effective_model_id,
                    "attempt": self.attempts,
                    "error_category": "transient"
                    if is_transient_model_error(exc)
                    else "permanent",
                    "partial": self.observer.has_output,
                    "duration_ms": round(
                        (time.monotonic() - attempt_started) * 1000, 2
                    ),
                },
            )
            raise

    def summary(self) -> dict:
        return {
            "version": 1,
            "requested_model_id": self.primary_model_id,
            "effective_model_id": self.effective_model_id,
            "attempts": self.attempts,
            "fallback_used": self.effective_model_id != self.primary_model_id,
        }


class ModelResilienceSummarizationMiddleware(AgentMiddleware):
    """Normalize final failures after the official context recovery has run."""

    name = "SummarizationMiddleware"
    state_schema = SummarizationMiddleware.state_schema

    def __init__(self, model, backend) -> None:
        super().__init__()
        self.summary = create_summarization_middleware(model, backend)

    async def awrap_model_call(self, request: ModelRequest, handler):
        try:
            return await self.summary.awrap_model_call(request, handler)
        except Exception as exc:
            code = model_failure_code(exc)
            if code is None:
                raise
        raise RuntimeResolutionError(code)


class ModelResilienceMiddleware(AgentMiddleware):
    def __init__(
        self,
        policy: ModelResiliencePolicy,
        fallback_model=None,
        *,
        primary_model_id: str,
        context_recovery: bool = False,
    ) -> None:
        super().__init__()
        self.policy = policy
        self.fallback_model = fallback_model
        self.primary_model_id = primary_model_id
        self.context_recovery = context_recovery
        if fallback_model is not None and (
            not policy.fallback_model_id or policy.fallback_model_id == primary_model_id
        ):
            raise RuntimeResolutionError("runtime.model.invalid_resilience")

    async def awrap_model_call(self, request: ModelRequest, handler):
        if not self.policy.enabled:
            return await handler(request)
        invocation = _Invocation(
            self.policy, self.primary_model_id, self.fallback_model
        )

        async def guarded(candidate):
            return await invocation.call(candidate, handler)

        async def candidates(candidate):
            if self.fallback_model is None:
                return await guarded(candidate)
            return await ModelFallbackMiddleware(self.fallback_model).awrap_model_call(
                candidate, guarded
            )

        retry = ModelRetryMiddleware(
            max_retries=self.policy.max_attempts - 1,
            retry_on=invocation.can_retry,
            on_failure="error",
            max_delay=30.0,
        )
        budget = asyncio.timeout(self.policy.total_timeout_seconds)
        try:
            async with budget:
                result = await retry.awrap_model_call(request, candidates)
        except (RuntimeErrorBase, GraphBubbleUp):
            raise
        except Exception as exc:
            if (
                isinstance(exc, ContextOverflowError)
                and self.context_recovery
                and not invocation.observer.has_output
            ):
                raise
            code = model_failure_code(
                exc,
                partial=invocation.observer.has_output,
                budget_expired=budget.expired(),
                fallback=invocation.effective_model_id != self.primary_model_id,
            )
            if code is None:
                raise
        else:
            code = None
        if code is not None:
            logger.info(
                "model_invocation_failed",
                extra={
                    **invocation.observer.correlation,
                    **invocation.summary(),
                    "error_code": code,
                },
            )
            # Raise outside the except block so raw provider context is not retained.
            raise RuntimeResolutionError(code)
        summary = invocation.summary()
        _add_summary(result, summary)
        logger.info(
            "model_attempt_succeeded",
            extra={
                **invocation.observer.correlation,
                **summary,
                "duration_ms": round((time.monotonic() - invocation.started) * 1000, 2),
            },
        )
        return result


__all__ = [
    "ModelResilienceMiddleware",
    "ModelResilienceSummarizationMiddleware",
    "is_transient_model_error",
    "retry_after_seconds",
    "model_failure_code",
]
