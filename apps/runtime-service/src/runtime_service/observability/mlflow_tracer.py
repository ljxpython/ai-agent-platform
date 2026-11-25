"""Fail-soft MLflow GenAI Tracing & Sessions adapter for Runtime Service graphs."""

from __future__ import annotations

import json
import logging
import os
import threading
from collections import OrderedDict
from collections.abc import Mapping
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from runtime_service.build_info import STARTUP_PACKAGE_DIGEST

logger = logging.getLogger(__name__)


def _chain_state_reference(value: Any, parent_run_id: Any) -> dict[str, Any]:
    # Repeated graph state is available through the root, model/tool spans and execution snapshots.
    return {
        "_runtime_chain_state": {
            "schema": "chain-state-ref/v1",
            "payload_recorded": False,
            "parent_run_id": str(parent_run_id),
            "value_type": type(value).__name__,
            "source": "root_and_model_tool_spans",
        }
    }


_DEFAULT_EXPERIMENT_NAME = "ai-agent-platform-traces"
_MAX_BUFFERED_RUNS = 512
_MAX_PENDING_EVENTS_PER_RUN = 64
_DIAG_EVENTS_TAG_KEY = "runtime.diag.events"
_DIAG_EVENTS_TRUNCATED_TAG_KEY = "runtime.diag.events_truncated"
# MLflow backends enforce a 4096-char trace tag limit; strip fields already stored on trace tags/metadata.
_MAX_DIAG_TAG_BYTES = 3800
_REDUNDANT_TAG_FIELDS = frozenset(
    {
        "tenant_id",
        "project_id",
        "graph_id",
        "thread_id",
        "run_id",
        "request_id",
        "platform_trace_id",
        "model_id",
    }
)
_ASYNC_FLUSH_JOIN_TIMEOUT_SECONDS = 1.5
_mlflow_initialized = False
_mlflow_lock = threading.Lock()
_diagnostic_lock = threading.Lock()
_active_root_spans: OrderedDict[str, Any] = OrderedDict()
_pending_span_events: OrderedDict[str, list[tuple[str, dict[str, Any]]]] = OrderedDict()
_recorded_run_events: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()


def get_tracing_provider(env: Mapping[str, str] | None = None) -> str:
    """Return the active tracing provider: 'langfuse', 'mlflow', 'both', or 'none'."""
    settings_env = os.environ if env is None else env
    provider = settings_env.get("TRACING_PROVIDER", "langfuse").strip().lower()
    if provider in {"langfuse", "mlflow", "both", "none"}:
        return provider
    return "langfuse"


def is_mlflow_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Check if MLflow tracing should be active."""
    provider = get_tracing_provider(env)
    return provider in {"mlflow", "both"}


def is_langfuse_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Check if Langfuse tracing should be active."""
    provider = get_tracing_provider(env)
    return provider in {"langfuse", "both"}


def initialize_mlflow(*, env: Mapping[str, str] | None = None) -> bool:
    """Initialize MLflow tracking URI and experiment if enabled."""
    global _mlflow_initialized
    if not is_mlflow_enabled(env):
        return False
    if _mlflow_initialized:
        return True

    with _mlflow_lock:
        if _mlflow_initialized:
            return True
        settings_env = os.environ if env is None else env
        tracking_uri = settings_env.get(
            "MLFLOW_TRACKING_URI", "http://127.0.0.1:5000"
        ).strip()
        experiment_name = settings_env.get(
            "MLFLOW_EXPERIMENT_NAME", _DEFAULT_EXPERIMENT_NAME
        ).strip()

        try:
            import mlflow

            mlflow.set_tracking_uri(tracking_uri)
            try:
                mlflow.set_experiment(experiment_name)
            except Exception as exp_err:
                logger.warning(
                    "runtime_mlflow_set_experiment_failed",
                    extra={"experiment_name": experiment_name, "error": str(exp_err)},
                )
            _mlflow_initialized = True
            logger.info(
                "runtime_mlflow_tracing_initialized",
                extra={"tracking_uri": tracking_uri, "experiment": experiment_name},
            )
            return True
        except Exception as err:
            logger.warning(
                "runtime_mlflow_init_failed",
                extra={"error": str(err)},
            )
            return False


def _is_span_recording(span: Any) -> bool:
    """Return True if a live span can still accept events without hitting an ended span."""
    if span is None or not hasattr(span, "add_event"):
        return False
    inner = getattr(span, "_span", None)
    is_recording = getattr(inner, "is_recording", None)
    if callable(is_recording):
        try:
            return bool(is_recording())
        except Exception:
            return False
    return True


def _add_span_event(span: Any, event: str, payload: Mapping[str, Any]) -> bool:
    """Attach one sanitized schema-v1 SpanEvent onto a live MLflow span."""
    if not _is_span_recording(span):
        return False
    try:
        from mlflow.entities import SpanEvent

        span.add_event(
            SpanEvent(
                name=event,
                attributes={"schema_version": 1, "event": event, **payload},
            )
        )
        return True
    except Exception as err:
        logger.debug(
            "runtime_mlflow_add_span_event_failed",
            extra={"event": event, "error": str(err)},
        )
        return False


def _queue_pending_event(run_id: str, event: str, payload: dict[str, Any]) -> None:
    if not run_id:
        return
    with _diagnostic_lock:
        if run_id not in _pending_span_events:
            if len(_pending_span_events) >= _MAX_BUFFERED_RUNS:
                _pending_span_events.popitem(last=False)
            _pending_span_events[run_id] = []
        else:
            _pending_span_events.move_to_end(run_id)
        bucket = _pending_span_events[run_id]
        if len(bucket) < _MAX_PENDING_EVENTS_PER_RUN:
            bucket.append((event, payload))


def _record_run_event_summary(
    run_id: str, event: str, payload: Mapping[str, Any]
) -> None:
    if not run_id:
        return
    compact_meta = {
        "schema_version": 1,
        "event": event,
        **{
            k: v
            for k, v in payload.items()
            if k not in _REDUNDANT_TAG_FIELDS and v is not None
        },
    }
    entry = {"name": event, "metadata": compact_meta}
    with _diagnostic_lock:
        if run_id not in _recorded_run_events:
            if len(_recorded_run_events) >= _MAX_BUFFERED_RUNS:
                _recorded_run_events.popitem(last=False)
            _recorded_run_events[run_id] = []
        else:
            _recorded_run_events.move_to_end(run_id)
        bucket = _recorded_run_events[run_id]
        if len(bucket) < _MAX_PENDING_EVENTS_PER_RUN:
            bucket.append(entry)


def _flush_run_events_to_trace_tags(root_span: Any, run_id: str) -> None:
    if root_span is None or not run_id:
        return
    with _diagnostic_lock:
        events = _recorded_run_events.pop(run_id, [])
    if not events:
        return
    request_id = getattr(root_span, "request_id", None)
    if not isinstance(request_id, str) or not request_id:
        return
    truncated = False
    trimmed = list(events)
    encoded = json.dumps(trimmed, ensure_ascii=True, separators=(",", ":"))
    while len(encoded.encode("utf-8")) > _MAX_DIAG_TAG_BYTES and len(trimmed) > 1:
        trimmed.pop(0)
        truncated = True
        encoded = json.dumps(trimmed, ensure_ascii=True, separators=(",", ":"))
    if len(encoded.encode("utf-8")) > _MAX_DIAG_TAG_BYTES:
        return
    try:
        from mlflow.tracing.trace_manager import InMemoryTraceManager

        with InMemoryTraceManager.get_instance().get_trace(request_id) as trace:
            if trace is not None:
                trace.info.tags[_DIAG_EVENTS_TAG_KEY] = encoded
                if truncated:
                    trace.info.tags[_DIAG_EVENTS_TRUNCATED_TAG_KEY] = "1"
    except Exception as err:
        logger.debug(
            "runtime_mlflow_flush_tag_events_failed",
            extra={"run_id": run_id, "error": str(err)},
        )


def record_mlflow_diagnostic_event(event: str, safe_payload: Mapping[str, Any]) -> bool:
    """Export one sanitized diagnostic event to the active or run-scoped MLflow span."""
    if not is_mlflow_enabled():
        return False
    payload = dict(safe_payload)
    exec_run_id = str(payload.get("run_id") or "").strip()
    _record_run_event_summary(exec_run_id, event, payload)
    try:
        import mlflow

        active_span = mlflow.get_current_active_span()
    except Exception:
        active_span = None
    if active_span is not None and _add_span_event(active_span, event, payload):
        return True
    if exec_run_id:
        with _diagnostic_lock:
            root_span = _active_root_spans.get(exec_run_id)
        if root_span is not None and _add_span_event(root_span, event, payload):
            return True
        _queue_pending_event(exec_run_id, event, payload)
    return False


def _flush_async_traces() -> None:
    """Drain MLflow's background exporter queue briefly so immediate queries see the trace."""
    try:
        import mlflow

        def _flush() -> None:
            try:
                mlflow.flush_trace_async_logging(terminate=False)
            except Exception as err:
                logger.debug(
                    "runtime_mlflow_async_flush_failed", extra={"error": str(err)}
                )

        worker = threading.Thread(target=_flush, daemon=True)
        worker.start()
        worker.join(timeout=_ASYNC_FLUSH_JOIN_TIMEOUT_SECONDS)
    except Exception:
        pass


class MLflowFailSoftCallback(BaseCallbackHandler):
    """Fail-soft wrapper around MLflow's LangChain tracer with session and metadata enrichment."""

    def __init__(
        self,
        *,
        graph_id: str,
        bound_metadata: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self._graph_id = graph_id
        self._metadata = dict(bound_metadata or {})
        self._exec_run_id = str(self._metadata.get("run_id") or "").strip()
        self._tracer = None
        self._internal_chain_runs: dict[Any, Any] = {}
        self._root_cb_runs: dict[Any, Any] = {}
        self.raise_error = False
        # Run inline so root span lifecycle stays ordered and active span lookup works in async runs.
        self.run_inline = True

        try:
            import mlflow

            project_id = str(self._metadata.get("project_id") or "").strip()
            if project_id:
                exp_name = f"project-{project_id}"
                try:
                    mlflow.set_experiment(exp_name)
                except Exception as exp_err:
                    logger.warning(
                        "runtime_mlflow_set_project_experiment_failed",
                        extra={"experiment": exp_name, "error": str(exp_err)},
                    )

            from mlflow.langchain.langchain_tracer import MlflowLangchainTracer

            self._tracer = MlflowLangchainTracer(run_inline=self.run_inline)
        except Exception as err:
            logger.warning(
                "runtime_mlflow_tracer_creation_failed", extra={"error": str(err)}
            )

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: Any,
        parent_run_id: Any = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        if self._tracer is None:
            return None
        try:
            if parent_run_id is not None:
                self._internal_chain_runs[run_id] = parent_run_id
                inputs = _chain_state_reference(inputs, parent_run_id)
            result = self._tracer.on_chain_start(
                serialized,
                inputs,
                run_id=run_id,
                parent_run_id=parent_run_id,
                tags=tags,
                metadata=metadata,
                **kwargs,
            )
            # 仅在 Root Chain 启动时注入 session_id 与 platform_trace_id，并补挂启动事件
            if parent_run_id is None:
                self._enrich_trace()
                self._register_root_span(run_id)
            return result
        except Exception as err:
            self._internal_chain_runs.pop(run_id, None)
            logger.warning(
                "runtime_mlflow_on_chain_start_failed", extra={"error": str(err)}
            )
            return None

    def _resolve_root_span(self, cb_run_id: Any) -> Any:
        if self._tracer is not None and hasattr(self._tracer, "_get_span_by_run_id"):
            try:
                span = self._tracer._get_span_by_run_id(cb_run_id)
                if span is not None:
                    return span
            except Exception:
                pass
        try:
            import mlflow

            return mlflow.get_current_active_span()
        except Exception:
            return None

    def _register_root_span(self, cb_run_id: Any) -> None:
        root_span = self._resolve_root_span(cb_run_id)
        if root_span is None:
            return
        self._root_cb_runs[cb_run_id] = root_span
        if not self._exec_run_id:
            return
        with _diagnostic_lock:
            if (
                len(_active_root_spans) >= _MAX_BUFFERED_RUNS
                and self._exec_run_id not in _active_root_spans
            ):
                _active_root_spans.popitem(last=False)
            _active_root_spans[self._exec_run_id] = root_span
            _active_root_spans.move_to_end(self._exec_run_id)
            pending = _pending_span_events.pop(self._exec_run_id, [])
        for event, payload in pending:
            _add_span_event(root_span, event, payload)

    def _flush_and_release_root_span(self, cb_run_id: Any) -> None:
        root_span = self._root_cb_runs.pop(cb_run_id, None)
        if not self._exec_run_id:
            return
        with _diagnostic_lock:
            _active_root_spans.pop(self._exec_run_id, None)
            pending = _pending_span_events.pop(self._exec_run_id, [])
        if root_span is not None:
            for event, payload in pending:
                _add_span_event(root_span, event, payload)
            _flush_run_events_to_trace_tags(root_span, self._exec_run_id)

    def _enrich_trace(self) -> None:
        """Inject session_id, user, client_request_id and tags into active MLflow trace."""
        try:
            import mlflow

            session_id = str(self._metadata.get("thread_id") or "")
            user_id = str(self._metadata.get("user_id") or "")
            trace_id = str(
                self._metadata.get("platform_trace_id")
                or self._metadata.get("request_id")
                or ""
            )

            custom_tags = {
                "graph_id": self._graph_id,
                "project_id": str(self._metadata.get("project_id") or ""),
                "tenant_id": str(self._metadata.get("tenant_id") or ""),
                "model_id": str(self._metadata.get("model_id") or ""),
                "platform_trace_id": trace_id,
            }
            if self._exec_run_id:
                custom_tags["run_id"] = self._exec_run_id
            if session_id:
                custom_tags["mlflow.session_id"] = session_id

            mlflow.update_current_trace(
                session_id=session_id if session_id else None,
                user=user_id if user_id else None,
                client_request_id=trace_id if trace_id else None,
                tags=custom_tags,
                metadata={
                    **{k: str(v) for k, v in self._metadata.items() if v is not None},
                    "runtime.package_sha256": STARTUP_PACKAGE_DIGEST,
                },
            )
        except Exception as err:
            logger.debug(
                "runtime_mlflow_enrich_trace_silent_fallback", extra={"error": str(err)}
            )

    def on_chain_end(
        self, outputs: dict[str, Any], *, run_id: Any, **kwargs: Any
    ) -> Any:
        if self._tracer is None:
            return None
        try:
            self._flush_and_release_root_span(run_id)
            parent = self._internal_chain_runs.pop(run_id, None)
            if parent is not None:
                outputs = _chain_state_reference(outputs, parent)
                if "inputs" in kwargs:
                    kwargs["inputs"] = _chain_state_reference(kwargs["inputs"], parent)
            result = self._tracer.on_chain_end(outputs, run_id=run_id, **kwargs)
            if parent is None:
                _flush_async_traces()
            return result
        except Exception as err:
            logger.warning(
                "runtime_mlflow_on_chain_end_failed", extra={"error": str(err)}
            )
            return None

    def on_chain_error(
        self, error: BaseException, *, run_id: Any, **kwargs: Any
    ) -> Any:
        if self._tracer is None:
            return None
        try:
            self._flush_and_release_root_span(run_id)
            parent = self._internal_chain_runs.pop(run_id, None)
            if parent is not None and "inputs" in kwargs:
                kwargs["inputs"] = _chain_state_reference(kwargs["inputs"], parent)
            result = self._tracer.on_chain_error(error, run_id=run_id, **kwargs)
            if parent is None:
                _flush_async_traces()
            return result
        except Exception as err:
            logger.warning(
                "runtime_mlflow_on_chain_error_failed", extra={"error": str(err)}
            )
            return None

    def on_llm_start(self, *args: Any, **kwargs: Any) -> Any:
        if self._tracer is None:
            return None
        try:
            return self._tracer.on_llm_start(*args, **kwargs)
        except Exception as err:
            logger.warning(
                "runtime_mlflow_on_llm_start_failed", extra={"error": str(err)}
            )
            return None

    def on_llm_end(self, *args: Any, **kwargs: Any) -> Any:
        if self._tracer is None:
            return None
        try:
            return self._tracer.on_llm_end(*args, **kwargs)
        except Exception as err:
            logger.warning(
                "runtime_mlflow_on_llm_end_failed", extra={"error": str(err)}
            )
            return None

    def on_llm_error(self, *args: Any, **kwargs: Any) -> Any:
        if self._tracer is None:
            return None
        try:
            return self._tracer.on_llm_error(*args, **kwargs)
        except Exception as err:
            logger.warning(
                "runtime_mlflow_on_llm_error_failed", extra={"error": str(err)}
            )
            return None

    def on_tool_start(self, *args: Any, **kwargs: Any) -> Any:
        if self._tracer is None:
            return None
        try:
            return self._tracer.on_tool_start(*args, **kwargs)
        except Exception as err:
            logger.warning(
                "runtime_mlflow_on_tool_start_failed", extra={"error": str(err)}
            )
            return None

    def on_tool_end(self, *args: Any, **kwargs: Any) -> Any:
        if self._tracer is None:
            return None
        try:
            return self._tracer.on_tool_end(*args, **kwargs)
        except Exception as err:
            logger.warning(
                "runtime_mlflow_on_tool_end_failed", extra={"error": str(err)}
            )
            return None

    def on_tool_error(self, *args: Any, **kwargs: Any) -> Any:
        if self._tracer is None:
            return None
        try:
            return self._tracer.on_tool_error(*args, **kwargs)
        except Exception as err:
            logger.warning(
                "runtime_mlflow_on_tool_error_failed", extra={"error": str(err)}
            )
            return None


def create_mlflow_callback(
    *,
    graph_id: str,
    bound_metadata: Mapping[str, Any] | None = None,
) -> BaseCallbackHandler | None:
    """Create an enriched fail-soft MLflow callback if enabled."""
    if not is_mlflow_enabled():
        return None
    if not initialize_mlflow():
        return None
    return MLflowFailSoftCallback(graph_id=graph_id, bound_metadata=bound_metadata)
