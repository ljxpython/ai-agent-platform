from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from runtime_service.observability import mlflow_tracer, with_tracing


class _Graph:
    def __init__(self) -> None:
        self.bound: dict[str, object] | None = None

    def with_config(self, config: dict[str, object]) -> _Graph:
        self.bound = config
        return self


def test_provider_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRACING_PROVIDER", raising=False)
    assert mlflow_tracer.get_tracing_provider() == "langfuse"
    assert mlflow_tracer.is_langfuse_enabled() is True
    assert mlflow_tracer.is_mlflow_enabled() is False

    monkeypatch.setenv("TRACING_PROVIDER", "mlflow")
    assert mlflow_tracer.get_tracing_provider() == "mlflow"
    assert mlflow_tracer.is_langfuse_enabled() is False
    assert mlflow_tracer.is_mlflow_enabled() is True

    monkeypatch.setenv("TRACING_PROVIDER", "both")
    assert mlflow_tracer.get_tracing_provider() == "both"
    assert mlflow_tracer.is_langfuse_enabled() is True
    assert mlflow_tracer.is_mlflow_enabled() is True

    monkeypatch.setenv("TRACING_PROVIDER", "none")
    assert mlflow_tracer.get_tracing_provider() == "none"
    assert mlflow_tracer.is_langfuse_enabled() is False
    assert mlflow_tracer.is_mlflow_enabled() is False


def test_mlflow_callback_binding(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRACING_PROVIDER", "mlflow")
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://test-mlflow:5000")
    monkeypatch.setattr(mlflow_tracer, "_mlflow_initialized", True)

    graph = _Graph()
    config = {
        "configurable": {
            "thread_id": "thread-123",
            "run_id": "run-456",
        }
    }
    trusted_meta = {
        "user_id": "user-789",
        "project_id": "project-abc",
        "platform_trace_id": "trace-999",
    }

    with (
        patch("mlflow.set_experiment") as mock_set_exp,
        patch(
            "mlflow.langchain.langchain_tracer.MlflowLangchainTracer"
        ) as mock_tracer_cls,
    ):
        mock_tracer_instance = MagicMock()
        mock_tracer_cls.return_value = mock_tracer_instance

        with_tracing(
            graph,
            config,
            graph_id="test_agent",
            trusted_metadata=trusted_meta,
        )
        mock_set_exp.assert_called_once_with("project-project-abc")

    assert graph.bound is not None
    callbacks = graph.bound["callbacks"]
    callback_names = [type(item).__name__ for item in callbacks]
    assert "MLflowFailSoftCallback" in callback_names

    # 验证 MLflowFailSoftCallback 的 metadata 保存与会话 enrichment
    mlflow_cb = next(
        c for c in callbacks if type(c).__name__ == "MLflowFailSoftCallback"
    )
    assert mlflow_cb._metadata.get("thread_id") == "thread-123"
    assert mlflow_cb._metadata.get("user_id") == "user-789"
    assert mlflow_cb._metadata.get("platform_trace_id") == "trace-999"

    with patch("mlflow.update_current_trace") as mock_update_trace:
        mlflow_cb.on_chain_start(
            {"name": "agent"},
            {"input": "hello"},
            run_id="call-1",
            parent_run_id=None,
        )
        mock_update_trace.assert_called_once()
        _, kwargs = mock_update_trace.call_args
        assert kwargs["session_id"] == "thread-123"
        assert kwargs["user"] == "user-789"
        assert kwargs["client_request_id"] == "trace-999"
        assert kwargs["tags"]["mlflow.session_id"] == "thread-123"
        assert kwargs["tags"]["project_id"] == "project-abc"


def test_mlflow_fail_soft_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRACING_PROVIDER", "mlflow")
    monkeypatch.setattr(mlflow_tracer, "_mlflow_initialized", True)

    with patch(
        "mlflow.langchain.langchain_tracer.MlflowLangchainTracer"
    ) as mock_tracer_cls:
        mock_tracer = MagicMock()
        mock_tracer.on_chain_start.side_effect = RuntimeError(
            "network timeout to mlflow"
        )
        mock_tracer_cls.return_value = mock_tracer

        cb = mlflow_tracer.MLflowFailSoftCallback(
            graph_id="faulty_agent",
            bound_metadata={"thread_id": "t1"},
        )
        # 不应抛出异常，返回 None
        result = cb.on_chain_start({"name": "foo"}, {}, run_id="r1")
        assert result is None
