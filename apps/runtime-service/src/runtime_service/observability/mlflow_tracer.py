"""Fail-soft MLflow GenAI Tracing & Sessions adapter for Runtime Service graphs."""

from __future__ import annotations

import logging
import os
import threading
from collections.abc import Mapping
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

logger = logging.getLogger(__name__)

_DEFAULT_EXPERIMENT_NAME = "ai-agent-platform-traces"
_mlflow_initialized = False
_mlflow_lock = threading.Lock()


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
        self._tracer = None
        self.raise_error = False

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

            self._tracer = MlflowLangchainTracer()
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
            result = self._tracer.on_chain_start(
                serialized,
                inputs,
                run_id=run_id,
                parent_run_id=parent_run_id,
                tags=tags,
                metadata=metadata,
                **kwargs,
            )
            # 仅在 Root Chain 启动时注入 session_id 与 platform_trace_id
            if parent_run_id is None:
                self._enrich_trace()
            return result
        except Exception as err:
            logger.warning(
                "runtime_mlflow_on_chain_start_failed", extra={"error": str(err)}
            )
            return None

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
            if session_id:
                custom_tags["mlflow.session_id"] = session_id

            mlflow.update_current_trace(
                session_id=session_id if session_id else None,
                user=user_id if user_id else None,
                client_request_id=trace_id if trace_id else None,
                tags=custom_tags,
                metadata={
                    k: str(v) for k, v in self._metadata.items() if v is not None
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
            return self._tracer.on_chain_end(outputs, run_id=run_id, **kwargs)
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
            return self._tracer.on_chain_error(error, run_id=run_id, **kwargs)
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
