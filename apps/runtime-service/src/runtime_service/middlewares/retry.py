"""Official retry loops with typed errors, per-call budgets and stream guards."""

from __future__ import annotations

import asyncio
import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

import httpx
import openai
from langchain.agents.middleware import ModelRetryMiddleware, ToolRetryMiddleware
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.exceptions import (
    ModelAPIError,
    ModelAuthenticationError,
    ModelConnectionError,
    ModelError,
    ModelPermissionDeniedError,
    ModelRateLimitError,
    ModelTimeoutError,
)
from langchain_core.messages import ToolMessage
from langchain_core.runnables.config import patch_config, set_config_context
from langgraph.config import get_config
from langgraph.errors import GraphBubbleUp

from runtime_service.observability.diagnostics import log_diagnostic
from runtime_service.observability.errors import classify_exception
from runtime_service.observability.langfuse import record_diagnostic_event
from runtime_service.runtime.errors import RuntimeExecutionError
from runtime_service.tools.errors import task_failure_content

try:
    import anthropic
except ImportError:
    anthropic = None

_STATUSES = frozenset({408, 429, 500, 502, 503, 504, 529})
_PROVIDER_ERRORS = (
    ModelError,
    openai.APIError,
    httpx.TransportError,
    httpx.HTTPStatusError,
)
if anthropic is not None:
    _PROVIDER_ERRORS += (anthropic.APIError,)


def is_transient_model_error(exc: BaseException) -> bool:
    if not isinstance(exc, _PROVIDER_ERRORS) or isinstance(
        exc, (ModelAuthenticationError, ModelPermissionDeniedError)
    ):
        return False
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    if type(status) is int:
        return status in _STATUSES
    return isinstance(
        exc,
        (
            ModelRateLimitError,
            ModelConnectionError,
            ModelTimeoutError,
            openai.APIConnectionError,
            httpx.TransportError,
            *((anthropic.APIConnectionError,) if anthropic is not None else ()),
        ),
    ) and not isinstance(exc, ModelAPIError)


@dataclass
class _RetryCall:
    parent: _RetryCall | None = None
    attempts: int = 0
    emitted: bool = False
    last_error: BaseException | None = None


_call: ContextVar[_RetryCall | None] = ContextVar("runtime_retry_call", default=None)


class _StreamGuard(BaseCallbackHandler):
    run_inline = True

    def __init__(self, call):
        self.call = call

    def on_llm_new_token(self, token, *, chunk=None, **kwargs):
        message = getattr(chunk, "message", None)
        if token or (
            message is not None
            and (
                message.content
                or message.tool_call_chunks
                or message.additional_kwargs.get("reasoning_content")
                or message.additional_kwargs.get("reasoning")
            )
        ):
            call = self.call
            while call is not None:
                call.emitted = True
                call = call.parent


def _retry_on(exc):
    call = _call.get()
    return call is not None and not call.emitted and is_transient_model_error(exc)


def _guarded_config(call):
    try:
        config = get_config()
    except RuntimeError:
        config = {}
    callbacks = config.get("callbacks")
    guard = _StreamGuard(call)
    if callbacks is None or isinstance(callbacks, list):
        callbacks = [*(callbacks or []), guard]
    else:
        callbacks = callbacks.copy()
        callbacks.add_handler(guard, inherit=True)
    return patch_config(config, callbacks=callbacks)


def _fields(metadata, call, unit, role, outcome, started):
    try:
        config = get_config()
    except RuntimeError:
        config = {}
    namespace = (config.get("metadata") or {}).get("langgraph_checkpoint_ns", "")
    return {
        **metadata,
        "scope": metadata.get("scope", "primary"),
        "namespace": namespace.split("|") if namespace else [],
        "unit": unit,
        "role": role,
        "attempts": call.attempts,
        "outcome": outcome,
        "code": classify_exception(call.last_error) if call.last_error else None,
        "duration_ms": round((time.monotonic() - started) * 1000, 3),
    }


@contextmanager
def _execution(metadata, *, unit, role=None):
    call = _RetryCall(parent=_call.get())
    token = _call.set(call)
    started = time.monotonic()
    outcome = "success"
    try:
        yield call
    except asyncio.CancelledError:
        outcome = "cancelled"
        raise
    except GraphBubbleUp:
        outcome = "interrupted"
        raise
    except Exception as exc:
        call.last_error = call.last_error or exc
        outcome = (
            "exhausted"
            if call.attempts == 2 and not call.emitted and is_transient_model_error(exc)
            else "failed"
        )
        raise
    finally:
        try:
            fields = _fields(metadata, call, unit, role, outcome, started)
            log_diagnostic("runtime.retry.completed", fields)
            record_diagnostic_event("runtime.retry.completed", fields)
        except Exception:
            pass
        finally:
            _call.reset(token)


def _invoke(call, handler, request):
    call.attempts += 1
    try:
        with set_config_context(_guarded_config(call)) as context:
            return context.run(handler, request)
    except Exception as exc:
        call.last_error = exc
        raise


async def _ainvoke(call, handler, request):
    call.attempts += 1
    try:
        with set_config_context(_guarded_config(call)) as context:
            task = context.run(asyncio.create_task, handler(request))
            return await task
    except Exception as exc:
        call.last_error = exc
        raise


class RuntimeModelRetryMiddleware(ModelRetryMiddleware):
    def __init__(self, metadata=None, *, delegated=False, initial_delay=1):
        super().__init__(
            max_retries=0 if delegated else 1,
            retry_on=_retry_on,
            on_failure="error",
            initial_delay=initial_delay,
            max_delay=10,
        )
        self.metadata = dict(metadata or {})
        self.delegated = delegated

    def _raise(self, exc):
        if not self.delegated and isinstance(exc, _PROVIDER_ERRORS):
            raise RuntimeExecutionError(
                classify_exception(exc) or "model_call_failed"
            ) from exc
        raise exc

    def wrap_model_call(self, request, handler):
        try:
            with _execution(self.metadata, unit="model") as call:
                return super().wrap_model_call(
                    request, lambda req: _invoke(call, handler, req)
                )
        except Exception as exc:
            self._raise(exc)

    async def awrap_model_call(self, request, handler):
        try:
            with _execution(self.metadata, unit="model") as call:
                return await super().awrap_model_call(
                    request, lambda req: _ainvoke(call, handler, req)
                )
        except Exception as exc:
            self._raise(exc)


class DelegatedTaskRetryMiddleware(ToolRetryMiddleware):
    def __init__(self, readonly_roles, metadata=None, *, initial_delay=1):
        super().__init__(
            tools=["task"],
            max_retries=1,
            retry_on=_retry_on,
            on_failure="error",
            initial_delay=initial_delay,
            max_delay=10,
        )
        self.readonly_roles = frozenset(readonly_roles)
        self.metadata = dict(metadata or {})

    def _role(self, request):
        args = request.tool_call.get("args") or {}
        role = args.get("subagent_type") if isinstance(args, dict) else None
        return (
            role
            if request.tool_call["name"] == "task"
            and isinstance(role, str)
            and role in self.readonly_roles
            else None
        )

    @staticmethod
    def _failure(request, exc):
        if not is_transient_model_error(exc):
            raise exc
        return ToolMessage(
            content=task_failure_content(exc),
            name="task",
            status="error",
            tool_call_id=request.tool_call["id"],
        )

    def wrap_tool_call(self, request, handler):
        role = self._role(request)
        if role is None:
            return handler(request)
        try:
            with _execution(self.metadata, unit="task", role=role) as call:
                return super().wrap_tool_call(
                    request, lambda req: _invoke(call, handler, req)
                )
        except Exception as exc:
            return self._failure(request, exc)

    async def awrap_tool_call(self, request, handler):
        role = self._role(request)
        if role is None:
            return await handler(request)
        try:
            with _execution(self.metadata, unit="task", role=role) as call:
                return await super().awrap_tool_call(
                    request, lambda req: _ainvoke(call, handler, req)
                )
        except Exception as exc:
            return self._failure(request, exc)


__all__ = [
    "DelegatedTaskRetryMiddleware",
    "RuntimeModelRetryMiddleware",
    "is_transient_model_error",
]
