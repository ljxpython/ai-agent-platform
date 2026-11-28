"""Shared evaluation target verification and execution evidence hooks across graphs."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

from runtime_service.observability.evaluation_target import assert_target, capabilities
from runtime_service.observability.execution_evidence import record_execution

EVALUABLE_GRAPHS: frozenset[str] = frozenset(
    {
        "dearflow_agent",
        "showcase_demo",
        "reference_agent",
        "workflow_demo",
    }
)


async def verify_evaluation_target(config: Mapping[str, Any], facts: Any) -> None:
    """Validate optional evaluation-target/v1 snapshot before graph execution."""
    await asyncio.to_thread(assert_target, config, facts)


async def record_evaluation_execution(
    config: Mapping[str, Any],
    resolved: Any,
    facts: Any,
    graph_id: str,
    workspace_root: Any = None,
) -> None:
    """Persist initial execution evidence when evaluation evidence is enabled."""
    await asyncio.to_thread(
        record_execution,
        config,
        resolved,
        facts,
        graph_id,
        workspace_root,
    )


async def read_evaluation_capabilities(
    tenant_id: str,
    project_id: str,
    graph_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Return evaluation capabilities merged with graph feature flags."""
    base = await asyncio.to_thread(capabilities, tenant_id, project_id)
    return {
        **base,
        "graph_features": {
            "workspace_files": bool(graph_result.get("files")),
            "clarification": bool(graph_result.get("clarification_field_types")),
            "plan_mode": bool(graph_result.get("plan_mode")),
        },
    }
