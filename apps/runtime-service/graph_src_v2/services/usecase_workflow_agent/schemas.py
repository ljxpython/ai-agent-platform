from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

WorkflowStage = Literal[
    "workflow_initialized",
    "requirement_analysis",
    "reviewed_candidate_usecases",
    "awaiting_user_confirmation",
    "persisted",
]

DEFAULT_AGENT_NAME = "usecase_workflow_agent"
DEFAULT_WORKFLOW_TYPE = "usecase_generation"


@dataclass(frozen=True)
class UsecaseWorkflowServiceConfig:
    workflow_type: str = DEFAULT_WORKFLOW_TYPE
    require_explicit_confirmation: bool = True
    interaction_data_service_url: str | None = None
    interaction_data_service_token: str | None = None
    interaction_data_service_timeout_seconds: int = 10


class RequirementAnalysisPayload(dict[str, Any]):
    pass


class UsecaseDraftPayload(dict[str, Any]):
    pass


class UsecaseReviewPayload(dict[str, Any]):
    pass


def build_workflow_snapshot(
    *,
    workflow_type: str,
    stage: WorkflowStage,
    summary: str,
    payload: dict[str, Any],
    persistable: bool,
    next_action: str,
) -> dict[str, Any]:
    normalized_summary = str(summary).strip() or str(stage)
    normalized_next_action = str(next_action).strip() or "continue"
    return {
        "workflow_type": workflow_type,
        "stage": stage,
        "summary": normalized_summary,
        "persistable": persistable,
        "next_action": normalized_next_action,
        "payload": payload,
    }
