"""Small, fail-soft Langfuse adapter for Runtime Service graphs."""

from __future__ import annotations

import inspect
import json
import logging
import os
import threading
import time
from asyncio import CancelledError
from collections import Counter
from collections.abc import Mapping
from typing import Any, cast

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.errors import GraphBubbleUp
from langgraph.pregel import Pregel

from runtime_service.observability.diagnostics import (
    log_diagnostic,
    safe_fields,
    trace_id_for,
    workspace_execution_fields,
)
from runtime_service.observability.errors import error_type, execution_outcome
from runtime_service.observability.otel import (
    OTelDiagnosticsCallback,
    close_otel,
    initialize_otel,
)
from runtime_service.runtime.errors import RuntimeExecutionError, workspace_error_code

logger = logging.getLogger(__name__)

_REQUIRED_SETTINGS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL")
_CALLER_METADATA = frozenset(
    {
        "run_id",
        "thread_id",
        "assistant_id",
        "assistant_version",
        "deployment_version",
    }
)
_TRUSTED_METADATA = frozenset(
    {
        "tenant_id",
        "project_id",
        "user_id",
        "model_id",
        "config_hash",
        "prompt_version",
        "prompt_hash",
        "policy_version",
        "policy_hash",
        "skills_hash",
        "execution_mode",
        "effective_reasoning",
        "request_id",
        "platform_trace_id",
    }
)
_ALLOWED_TAGS = frozenset({"environment", "service", "graph_id", "source", "release"})
_SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "cookie",
        "set-cookie",
        "token",
        "access_token",
        "api_key",
        "x-api-key",
        "secret",
        "client_secret",
        "password",
    }
)
_MAX_VALUE_LENGTH = 256

_client: Any | None = None
_client_lock = threading.Lock()
_metrics: Counter[str] = Counter()


class LangfuseConfigurationError(RuntimeError):
    """Raised when Langfuse was explicitly enabled with invalid settings."""


def _error_category(error: BaseException) -> str:
    status_code = getattr(error, "status_code", None)
    if status_code == 401:
        return "unauthorized"
    if status_code == 429:
        return "rate_limited"
    if isinstance(status_code, int) and 500 <= status_code <= 599:
        return "upstream_5xx"
    if isinstance(error, TimeoutError):
        return "timeout"
    return type(error).__name__


def _record_export_error(error: BaseException) -> None:
    _metrics["export_error"] += 1
    _metrics["event_dropped"] += 1
    logger.warning(
        "runtime_langfuse_event_dropped",
        extra={"error_category": _error_category(error)},
    )


class _FailSoftCallback(BaseCallbackHandler):
    """Keep SDK callback failures outside the Agent result path."""

    def __init__(self, delegate: BaseCallbackHandler) -> None:
        self._delegate = delegate
        self.raise_error = False

    def __getattribute__(self, name: str) -> Any:
        if name.startswith("on_"):
            delegate = object.__getattribute__(self, "_delegate")
            method = getattr(delegate, name)

            def call(*args: Any, **kwargs: Any) -> Any:
                if name.endswith("_error"):
                    if args and isinstance(args[0], BaseException):
                        args = (RuntimeError(error_type(args[0])), *args[1:])
                    if isinstance(kwargs.get("error"), BaseException):
                        kwargs["error"] = RuntimeError(error_type(kwargs["error"]))
                try:
                    result = method(*args, **kwargs)
                except Exception as error:  # noqa: BLE001 - exporter must remain fail-soft.
                    _record_export_error(error)
                    return None
                if not inspect.isawaitable(result):
                    return result

                async def wait() -> Any:
                    try:
                        return await result
                    except Exception as error:  # noqa: BLE001 - exporter must remain fail-soft.
                        _record_export_error(error)
                        return None

                return wait()

            return call
        return super().__getattribute__(name)


def _enabled(env: Mapping[str, str]) -> bool:
    return env.get("LANGFUSE_ENABLED", "").strip().lower() == "true"


def _settings(env: Mapping[str, str]) -> dict[str, str] | None:
    if not _enabled(env):
        return None
    missing = [name for name in _REQUIRED_SETTINGS if not env.get(name)]
    if missing:
        raise LangfuseConfigurationError(
            "Missing Langfuse settings: " + ", ".join(missing)
        )
    return {
        "public_key": env["LANGFUSE_PUBLIC_KEY"],
        "secret_key": env["LANGFUSE_SECRET_KEY"],
        "base_url": env["LANGFUSE_BASE_URL"],
        "environment": env.get("LANGFUSE_TRACING_ENVIRONMENT", "local"),
    }


def _redact(value: Any, *, key: str | None = None) -> Any:
    if key is not None and key.lower() in _SENSITIVE_KEYS:
        return "[REDACTED]"
    if isinstance(value, str):
        return (
            value[:_MAX_VALUE_LENGTH]
            if len(value) <= _MAX_VALUE_LENGTH
            else "[REDACTED]"
        )
    if isinstance(value, Mapping):
        return {
            str(item_key): _redact(item, key=str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item) for item in value[:32]]
    if isinstance(value, tuple):
        return tuple(_redact(item) for item in value[:32])
    return value


def _mask(*, data: Any, **_: Any) -> Any:
    """Mask callback payloads before Langfuse export.

    Metadata is attached separately; callback input/output strings are intentionally not retained.
    """

    if isinstance(data, str):
        return "[REDACTED]"
    return _redact(data)


def _mask_spans(*, params: Any) -> Any:
    from langfuse.types import MaskOtelSpansResult, OtelSpanPatch

    patches = {}
    for identifier, span in params.spans.items():
        keys = tuple(
            key
            for key in span.attributes
            if key.startswith("exception.")
            or "status_message" in key
            or key
            in {
                "langfuse.observation.input",
                "langfuse.observation.output",
                "langfuse.trace.input",
                "langfuse.trace.output",
            }
        )
        if keys:
            patches[identifier] = OtelSpanPatch(delete_attributes=keys)
    return MaskOtelSpansResult(span_patches=patches)


def record_diagnostic_event(event: str, fields: Mapping[str, Any]) -> None:
    trace_id = trace_id_for(fields)
    if _client is None or trace_id is None:
        return
    try:
        from langfuse import propagate_attributes

        metadata = safe_fields(fields)
        with propagate_attributes(session_id=metadata.get("thread_id")):
            _client.create_event(
                name=event,
                trace_context={"trace_id": trace_id},
                metadata={"schema_version": 1, "event": event, **metadata},
                level="ERROR" if event == "runtime.model_call.failed" else "DEFAULT",
            )
    except Exception as error:
        _record_export_error(error)


class _RuntimeDiagnosticsCallback(BaseCallbackHandler):
    """Bounded Run/Tool diagnostics independent of Langfuse export."""

    def __init__(self, graph_id: str, metadata: Mapping[str, Any]) -> None:
        self._graph_id = graph_id
        self._metadata = safe_fields(metadata)
        self._starts: dict[Any, float] = {}

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Any = None,
        **_: Any,
    ) -> None:
        if parent_run_id is None:
            self._starts[run_id] = time.monotonic()
            log_diagnostic(
                "runtime.graph.started",
                {
                    **self._metadata,
                    "graph_id": self._graph_id,
                    "callback_run_id": str(run_id),
                },
            )

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Any = None,
        **_: Any,
    ) -> None:
        if parent_run_id is None:
            self._finish(
                run_id,
                "interrupted"
                if isinstance(outputs, Mapping) and outputs.get("__interrupt__")
                else "success",
            )

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: Any,
        parent_run_id: Any = None,
        **_: Any,
    ) -> None:
        if parent_run_id is None:
            status = execution_outcome(error)
            code = (
                error.code
                if isinstance(error, RuntimeExecutionError)
                and error.code == "runtime.loop.detected"
                else workspace_error_code(error)
            )
            self._finish(run_id, status, code)

    def on_tool_error(
        self, error: BaseException, *, run_id: Any, **kwargs: Any
    ) -> None:
        if isinstance(error, (GraphBubbleUp, CancelledError)):
            return
        _metrics["tool_error"] += 1
        fields = {
            **self._metadata,
            "graph_id": self._graph_id,
            "callback_run_id": str(run_id),
            "error_type": error_type(error),
            "error_code": workspace_error_code(error),
        }
        log_diagnostic("runtime.tool.failed", fields)
        record_diagnostic_event("runtime.tool.failed", fields)
        logger.warning(
            "runtime_tool_error",
            extra={
                "graph_id": self._graph_id,
                **self._metadata,
                "tool_name": str(kwargs.get("name", "unknown"))[:_MAX_VALUE_LENGTH],
                "error_category": type(error).__name__,
            },
        )

    def on_custom_event(self, name: str, data: Any, *, run_id: Any, **_: Any) -> None:
        if name != "runtime.workspace.execution_completed" or not isinstance(
            data, Mapping
        ):
            return
        summary = workspace_execution_fields(data)
        if summary is None:
            return
        fields = {
            **self._metadata,
            **summary,
            "graph_id": self._graph_id,
            "callback_run_id": str(run_id),
        }
        try:
            log_diagnostic(name, fields)
            record_diagnostic_event(name, fields)
        except Exception:
            pass

    def on_tool_end(self, output: Any, *, run_id: Any, **_: Any) -> None:
        if not isinstance(output, ToolMessage) or output.status != "error":
            return
        code = "tool.result_failed"
        if isinstance(output.content, str) and len(output.content.encode()) <= 2048:
            try:
                payload = json.loads(output.content)
            except (ValueError, TypeError):
                payload = None
            if (
                isinstance(payload, dict)
                and isinstance(payload.get("code"), str)
                and payload["code"]
                in {
                    "tool.invalid_input",
                    "tool.upstream_unavailable",
                    "tool.operation_failed",
                    "tool.outcome_unknown",
                }
            ):
                code = payload["code"]
        _metrics["tool_result_error"] += 1
        logger.warning(
            "runtime_tool_result_error",
            extra={
                "graph_id": self._graph_id,
                **self._metadata,
                "tool_name": str(output.name or "unknown")[:_MAX_VALUE_LENGTH],
                "error_code": code,
            },
        )

    def on_llm_end(self, response: Any, *, run_id: Any, **_: Any) -> None:
        from runtime_service.observability.usage import normalize_usage

        total = normalize_usage(response)["tokens"]["total_tokens"]
        if total is not None:
            _metrics["token_total"] += total

    def _finish(self, run_id: Any, status: str, error_code: str | None = None) -> None:
        started = self._starts.pop(run_id, None)
        duration_ms = (
            round((time.monotonic() - started) * 1000, 2)
            if started is not None
            else None
        )
        _metrics[f"run_{status}"] += 1
        fields = {
            **self._metadata,
            "graph_id": self._graph_id,
            "callback_run_id": str(run_id),
            "outcome": status,
            "duration_ms": duration_ms,
            "error_code": error_code,
        }
        log_diagnostic("runtime.graph.completed", fields)
        record_diagnostic_event("runtime.graph.completed", fields)
        logger.info(
            "runtime_run_completed",
            extra={
                "graph_id": self._graph_id,
                **self._metadata,
                "callback_run_id": str(run_id),
                "status": status,
                "duration_ms": duration_ms,
            },
        )


def initialize_langfuse(*, env: Mapping[str, str] | None = None) -> Any | None:
    """Initialize one process-scoped client, or return ``None`` when disabled."""

    global _client
    settings_env = os.environ if env is None else env
    settings = _settings(settings_env)
    initialize_otel(env=settings_env, on_error=_record_export_error)
    if settings is None:
        return None
    if _client is not None:
        return _client
    with _client_lock:
        if _client is None:
            from langfuse import Langfuse

            _client = Langfuse(mask=_mask, mask_otel_spans=_mask_spans, **settings)
    return _client


def _new_callback(*, trace_context: dict | None = None) -> Any:
    settings = _settings(os.environ)
    if settings is None:
        return None
    initialize_langfuse()
    from langfuse.langchain import CallbackHandler

    return _FailSoftCallback(
        CallbackHandler(public_key=settings["public_key"], trace_context=trace_context)
    )


def _values(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _configurable(config: RunnableConfig) -> Mapping[str, Any]:
    value = config.get("configurable")
    return value if isinstance(value, Mapping) else {}


def _approved_metadata(config: RunnableConfig, graph_id: str) -> dict[str, Any]:
    metadata = config.get("metadata")
    result = {
        str(key): _redact(value, key=str(key))
        for key, value in (metadata.items() if isinstance(metadata, Mapping) else ())
        if str(key) in _CALLER_METADATA
    }
    configurable = _configurable(config)
    for key in ("thread_id", "run_id", "assistant_id"):
        value = configurable.get(key)
        if isinstance(value, (str, int)) and str(value):
            result.setdefault(key, str(value))
    result["graph_id"] = graph_id
    return result


def _trusted_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, Mapping):
        return {}
    return {
        str(key): _redact(value, key=str(key))
        for key, value in metadata.items()
        if str(key) in _TRUSTED_METADATA
    }


def _merge_config(
    config: RunnableConfig, callback: Any, graph_id: str
) -> RunnableConfig:
    bound = dict(config)
    metadata = _approved_metadata(config, graph_id)
    tags = [
        tag
        for tag in _values(config.get("tags"))
        if isinstance(tag, str) and tag in _ALLOWED_TAGS
    ]
    tags.extend(tag for tag in ("runtime-service", graph_id) if tag not in tags)
    callbacks = _values(config.get("callbacks"))
    if callback is not None:
        callbacks.append(callback)
    bound["metadata"] = metadata
    bound["tags"] = tags
    bound["callbacks"] = callbacks
    return cast(RunnableConfig, bound)


def with_langfuse_tracing(
    graph: Pregel,
    config: RunnableConfig,
    *,
    graph_id: str,
    trusted_metadata: Mapping[str, Any] | None = None,
    startup: Any = None,
) -> Pregel:
    """Bind one Langfuse callback without changing graph construction or failures."""

    bound = _merge_config(config, None, graph_id)
    bound_metadata = dict(bound.get("metadata") or {})
    bound_metadata.update(_trusted_metadata(trusted_metadata))
    if startup is not None:
        bound_metadata.update(
            {key: value for key, value in startup.metadata.items() if value is not None}
        )
    callbacks = list(bound["callbacks"])
    trace_id = trace_id_for(bound_metadata)
    try:
        callback = (
            _new_callback(trace_context={"trace_id": trace_id})
            if trace_id
            else _new_callback()
        )
        if callback is not None:
            callbacks.append(callback)
    except LangfuseConfigurationError:
        raise
    except Exception as error:
        _record_export_error(error)
    try:
        otel_provider = initialize_otel(on_error=_record_export_error)
        if otel_provider is not None:
            callbacks.append(
                OTelDiagnosticsCallback(
                    otel_provider, graph_id, bound_metadata, startup=startup
                )
            )
    except Exception as error:
        _record_export_error(error)
    callbacks.append(_RuntimeDiagnosticsCallback(graph_id, bound_metadata))
    bound["callbacks"] = callbacks
    bound_metadata["langfuse_trace_name"] = graph_id
    if isinstance(bound_metadata.get("thread_id"), (str, int)):
        bound_metadata["langfuse_session_id"] = str(bound_metadata["thread_id"])
    if isinstance(bound_metadata.get("user_id"), (str, int)):
        bound_metadata["langfuse_user_id"] = str(bound_metadata["user_id"])
    bound_metadata["langfuse_tags"] = ["runtime-service", graph_id]
    bound["metadata"] = bound_metadata
    _metrics["trace_bound"] += 1
    from runtime_service.observability.usage import with_runtime_usage

    return cast(
        Pregel,
        with_runtime_usage(
            graph, bound, graph_id=graph_id, trusted_metadata=trusted_metadata
        ),
    )


def close_langfuse(*, timeout_seconds: float = 5.0) -> None:
    """Flush the process client with a bounded best-effort shutdown."""

    global _client
    client = _client
    if client is not None:
        done = threading.Event()

        def flush() -> None:
            try:
                client.flush()
            except Exception as error:
                _metrics["flush_error"] += 1
                _metrics["export_error"] += 1
                _metrics["event_dropped"] += 1
                logger.warning(
                    "runtime_langfuse_flush_error",
                    extra={"error_category": _error_category(error)},
                )
            finally:
                done.set()

        threading.Thread(target=flush, daemon=True).start()
        if not done.wait(timeout_seconds):
            _metrics["flush_timeout"] += 1
            _metrics["event_dropped"] += 1
            logger.warning("runtime_langfuse_flush_timeout")
        _client = None

    if not close_otel(timeout_seconds=timeout_seconds):
        _metrics["flush_timeout"] += 1
        _metrics["event_dropped"] += 1
        logger.warning("runtime_otel_flush_timeout")


def get_observability_metrics() -> dict[str, int]:
    """Return a snapshot for tests and service diagnostics."""

    from runtime_service.observability.usage import _metrics as usage_metrics

    return dict(_metrics) | dict(usage_metrics)


__all__ = [
    "LangfuseConfigurationError",
    "close_langfuse",
    "get_observability_metrics",
    "initialize_langfuse",
    "record_diagnostic_event",
    "with_langfuse_tracing",
]
