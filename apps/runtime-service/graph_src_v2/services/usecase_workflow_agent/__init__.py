from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["graph"]


def __getattr__(name: str) -> Any:
    if name != "graph":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module("graph_src_v2.services.usecase_workflow_agent.graph")
    value = getattr(module, name)
    globals()[name] = value
    return value
