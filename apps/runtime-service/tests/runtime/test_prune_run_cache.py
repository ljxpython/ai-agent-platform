"""The maintenance boundary must preserve unknown, recent and live runs."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "prune_run_cache", Path(__file__).parents[2] / "scripts/prune_run_cache.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_prune_boundary():
    for status in ("running", "pending", "interrupted", "unknown"):
        assert not module.expired_terminal((status, 7200), 3600)
    assert not module.expired_terminal(None, 3600)
    assert not module.expired_terminal(("success", 3599), 3600)
    assert module.expired_terminal(("success", 3600), 3600)
    assert module.expired_terminal(("error", 7200), 3600)
    assert module.cache_identity("other:run-stream:a:b", "runtime") is None
    assert module.cache_identity("runtime:run-stream:a:b", "runtime") is None
