import json
from unittest.mock import Mock

from runtime_service.observability import logging as module


def test_private_metric_has_run_identity_and_no_config_secrets(monkeypatch):
    sink = Mock()
    monkeypatch.setattr(module, "_context_metrics", sink)
    monkeypatch.setattr(
        module,
        "get_config",
        lambda: {
            "metadata": {"run_id": "run-1", "langgraph_checkpoint_ns": "tools:child"},
            "configurable": {"secret": "private-token"},
        },
    )
    module.log_context_metric({"event": "test", "visible_chars": 3})
    payload = json.loads(sink.info.call_args.args[0])
    assert payload == {
        "run_id": "run-1",
        "checkpoint_ns": "tools:child",
        "event": "test",
        "visible_chars": 3,
    }
    sink.info.side_effect = RuntimeError("logging unavailable")
    module.log_context_metric({"event": "test"})


def test_private_metric_outside_graph_does_not_require_config(monkeypatch):
    sink = Mock()
    monkeypatch.setattr(module, "_context_metrics", sink)

    def unavailable():
        raise RuntimeError("no graph")

    monkeypatch.setattr(module, "get_config", unavailable)
    module.log_context_metric({"event": "test"})
    assert json.loads(sink.info.call_args.args[0])["run_id"] is None
