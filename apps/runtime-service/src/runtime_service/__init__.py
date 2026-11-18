"""Greenfield Runtime Service package."""

from runtime_service.build_info import STARTUP_PACKAGE_DIGEST
from runtime_service.gateway_budget import (
    worker_guard as _budget_worker_guard,  # noqa: F401
)
from runtime_service.patches import apply_langgraph_patches

apply_langgraph_patches()

__all__ = ["apply_langgraph_patches", "STARTUP_PACKAGE_DIGEST"]
