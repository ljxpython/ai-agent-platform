from __future__ import annotations

import json
import os
from typing import Any

import requests
from graph_src_v2.runtime.options import read_configurable
from graph_src_v2.services.usecase_workflow_agent.schemas import (
    DEFAULT_WORKFLOW_TYPE,
    RequirementAnalysisPayload,
    UsecaseDraftPayload,
    UsecaseReviewPayload,
    UsecaseWorkflowServiceConfig,
    build_workflow_snapshot,
)
from langchain.agents import create_agent
from langchain.tools import ToolRuntime
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from pydantic import BaseModel, Field


class RequirementAnalysisToolInput(BaseModel):
    requirement_context: str = Field(
        default="",
        description="Optional. The full requirement analysis context. Leave empty to automatically use the current conversation state and multimodal summary.",
    )


class UsecaseReviewToolInput(BaseModel):
    review_context: str = Field(
        default="",
        description="Optional. The full review context including candidate use cases and review rubric. Leave empty to automatically use the current conversation state.",
    )


class CreateUsecaseWorkflowToolInput(BaseModel):
    project_id: str = Field(
        default="",
        description="Required before persistence. The project identifier for this workflow. If unknown, leave empty and the agent should ask the user for it later.",
    )
    title: str = Field(
        default="",
        description="Required before persistence. A short workflow title, for example the feature or document name.",
    )
    summary: str = Field(
        default="",
        description="Optional short summary of the workflow goal.",
    )
    requirement_document_id: str = Field(
        default="",
        description="Optional document identifier if the uploaded requirement has already been stored externally.",
    )
    metadata_json: str = Field(
        default="{}",
        description="Optional JSON object string for workflow metadata. Must be a JSON object string when provided.",
    )


class RecordRequirementAnalysisToolInput(BaseModel):
    summary: str = Field(description="One-line summary of the requirement analysis result.")
    analysis_json: str = Field(
        description="JSON object string containing structured requirement analysis data, including workflow_id when available.",
    )


class RecordUsecaseReviewToolInput(BaseModel):
    candidate_usecases_json: str = Field(
        description="JSON object string containing the candidate use cases, including workflow_id when available.",
    )
    review_report_json: str = Field(
        description="JSON object string containing deficiencies, strengths, and revision suggestions.",
    )
    revised_usecases_json: str | None = Field(
        default=None,
        description="Optional JSON object string containing revised use cases.",
    )


class PersistApprovedUsecasesToolInput(BaseModel):
    final_usecases_json: str = Field(
        description="JSON object string containing the final approved use cases and workflow_id.",
    )
    approval_note: str = Field(
        default="",
        description="Optional human approval note recorded alongside the persist action.",
    )


def build_usecase_workflow_service_config(
    config: Any | None,
) -> UsecaseWorkflowServiceConfig:
    configurable = read_configurable(config)
    workflow_type = str(
        configurable.get("usecase_workflow_type", DEFAULT_WORKFLOW_TYPE)
    ).strip() or DEFAULT_WORKFLOW_TYPE
    service_url = str(
        configurable.get("interaction_data_service_url")
        or os.getenv("INTERACTION_DATA_SERVICE_URL")
        or ""
    ).strip() or None
    service_token = str(
        configurable.get("interaction_data_service_token")
        or os.getenv("INTERACTION_DATA_SERVICE_TOKEN")
        or ""
    ).strip() or None
    timeout_raw = (
        configurable.get("interaction_data_service_timeout_seconds")
        or os.getenv("INTERACTION_DATA_SERVICE_TIMEOUT_SECONDS")
        or 10
    )
    try:
        timeout_seconds = int(timeout_raw)
    except (TypeError, ValueError):
        timeout_seconds = 10
    if timeout_seconds <= 0:
        timeout_seconds = 10
    return UsecaseWorkflowServiceConfig(
        workflow_type=workflow_type,
        interaction_data_service_url=service_url,
        interaction_data_service_token=service_token,
        interaction_data_service_timeout_seconds=timeout_seconds,
    )


def list_deepagent_skills() -> list[str]:
    return ["/skills/common", "/skills/research"]


def list_subagents() -> list[Any]:
    SubAgentCtor: Any
    try:
        from deepagents.middleware.subagents import SubAgent as ImportedSubAgent
        SubAgentCtor = ImportedSubAgent
    except ImportError:
        class FallbackSubAgent:
            def __init__(self, **kwargs: Any) -> None:
                self.__dict__.update(kwargs)

        SubAgentCtor = FallbackSubAgent

    from graph_src_v2.services.usecase_workflow_agent.prompts import (
        REQUIREMENT_ANALYSIS_SUBAGENT_PROMPT,
        USECASE_REVIEW_SUBAGENT_PROMPT,
    )

    return [
        SubAgentCtor(
            name="requirement-analysis-subagent",
            description="Extract structured requirements, constraints, edge cases, and ambiguities from the uploaded requirement document.",
            system_prompt=REQUIREMENT_ANALYSIS_SUBAGENT_PROMPT,
            skills=["/skills/research"],
        ),
        SubAgentCtor(
            name="usecase-review-subagent",
            description="Review draft use cases against quality standards and report deficiencies, ambiguities, and revision suggestions.",
            system_prompt=USECASE_REVIEW_SUBAGENT_PROMPT,
            skills=["/skills/common"],
        ),
    ]


def _build_requirement_analysis_subagent(model: Any) -> Any:
    from graph_src_v2.services.usecase_workflow_agent.prompts import (
        REQUIREMENT_ANALYSIS_SUBAGENT_PROMPT,
    )

    return create_agent(
        model=model,
        tools=[],
        system_prompt=REQUIREMENT_ANALYSIS_SUBAGENT_PROMPT,
        name="requirement_analysis_subagent",
    )


def _build_usecase_review_subagent(model: Any) -> Any:
    from graph_src_v2.services.usecase_workflow_agent.prompts import (
        USECASE_REVIEW_SUBAGENT_PROMPT,
    )

    return create_agent(
        model=model,
        tools=[],
        system_prompt=USECASE_REVIEW_SUBAGENT_PROMPT,
        name="usecase_review_subagent",
    )


def _extract_last_text(result: Any) -> str:
    messages = result.get("messages") if isinstance(result, dict) else getattr(result, "messages", None)
    if not isinstance(messages, list) or not messages:
        return ""
    content = getattr(messages[-1], "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(text.strip())
        return "\n".join(parts).strip()
    return str(content or "")


def _extract_recent_human_context(messages: list[Any] | None) -> str:
    if not isinstance(messages, list):
        return ""
    parts: list[str] = []
    for message in reversed(messages):
        if not isinstance(message, HumanMessage):
            continue
        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            parts.append(content.strip())
            break
        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        text_parts.append(text.strip())
            if text_parts:
                parts.append("\n".join(text_parts))
                break
    return "\n".join(parts).strip()


def _build_runtime_context_text(runtime: ToolRuntime[Any, Any]) -> str:
    state = runtime.state if hasattr(runtime, "state") else {}
    summary = state.get("multimodal_summary") if isinstance(state, dict) else None
    recent_human = _extract_recent_human_context(state.get("messages") if isinstance(state, dict) else None)
    sections: list[str] = []
    if isinstance(summary, str) and summary.strip():
        sections.append(f"Multimodal summary:\n{summary.strip()}")
    if recent_human:
        sections.append(f"Recent user request:\n{recent_human}")
    return "\n\n".join(sections).strip()


def build_requirement_analysis_subagent_tool(model: Any) -> Any:
    subagent = _build_requirement_analysis_subagent(model)

    @tool(
        "run_requirement_analysis_subagent",
        args_schema=RequirementAnalysisToolInput,
        description="Run the requirement-analysis specialist. You may omit requirement_context when the current conversation already contains the parsed document or user request; the tool will derive context automatically from the active thread state.",
    )
    def run_requirement_analysis_subagent(
        runtime: ToolRuntime[Any, Any], requirement_context: str = ""
    ) -> str:
        requirement_context = str(requirement_context or "").strip() or _build_runtime_context_text(runtime)
        if not requirement_context:
            raise ValueError("requirement_context is required")
        result = subagent.invoke({"messages": [HumanMessage(content=requirement_context)]})
        return _extract_last_text(result)

    return run_requirement_analysis_subagent


def build_usecase_review_subagent_tool(model: Any) -> Any:
    subagent = _build_usecase_review_subagent(model)

    @tool(
        "run_usecase_review_subagent",
        args_schema=UsecaseReviewToolInput,
        description="Run the usecase-review specialist. You may omit review_context when the current conversation already contains the candidate use cases and user revision request; the tool will derive context automatically from the active thread state.",
    )
    def run_usecase_review_subagent(
        runtime: ToolRuntime[Any, Any], review_context: str = ""
    ) -> str:
        review_context = str(review_context or "").strip() or _build_runtime_context_text(runtime)
        if not review_context:
            raise ValueError("review_context is required")
        result = subagent.invoke({"messages": [HumanMessage(content=review_context)]})
        return _extract_last_text(result)

    return run_usecase_review_subagent


def _parse_json_payload(value: str, *, field_name: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{field_name} must decode to a JSON object")
    return payload


def _normalize_requirement_analysis(payload: dict[str, Any]) -> RequirementAnalysisPayload:
    normalized = RequirementAnalysisPayload(payload)
    for key in [
        "requirements",
        "business_rules",
        "preconditions",
        "edge_cases",
        "exception_scenarios",
        "open_questions",
    ]:
        value = normalized.get(key)
        if not isinstance(value, list):
            normalized[key] = []
    return normalized


def _normalize_usecase_draft(payload: dict[str, Any]) -> UsecaseDraftPayload:
    normalized = UsecaseDraftPayload(payload)
    if not isinstance(normalized.get("usecases"), list):
        normalized["usecases"] = []
    return normalized


def _normalize_usecase_review(payload: dict[str, Any]) -> UsecaseReviewPayload:
    normalized = UsecaseReviewPayload(payload)
    for key in ["deficiencies", "strengths", "revision_suggestions"]:
        value = normalized.get(key)
        if not isinstance(value, list):
            normalized[key] = []
    return normalized


def _build_runtime_persistence_config() -> UsecaseWorkflowServiceConfig:
    return build_usecase_workflow_service_config({"configurable": {}})


def _build_service_headers(service_config: UsecaseWorkflowServiceConfig) -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if service_config.interaction_data_service_token:
        headers["Authorization"] = (
            f"Bearer {service_config.interaction_data_service_token}"
        )
    return headers


def _build_service_base_url(service_config: UsecaseWorkflowServiceConfig) -> str | None:
    base_url = service_config.interaction_data_service_url
    return base_url.rstrip("/") if isinstance(base_url, str) and base_url.strip() else None


def _post_service_json(
    *,
    service_config: UsecaseWorkflowServiceConfig,
    path: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    base_url = _build_service_base_url(service_config)
    if not base_url:
        raise RuntimeError("interaction_data_service_not_configured")
    response = requests.post(
        f"{base_url}{path}",
        headers=_build_service_headers(service_config),
        json=payload,
        timeout=service_config.interaction_data_service_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def _maybe_create_snapshot(
    *,
    workflow_id: str | None,
    snapshot: dict[str, Any],
    service_config: UsecaseWorkflowServiceConfig,
) -> dict[str, Any]:
    if not workflow_id:
        return {"delivery_status": "missing_workflow_id"}
    base_url = _build_service_base_url(service_config)
    if not base_url:
        return {"delivery_status": "not_configured"}
    payload = {
        "status": snapshot["stage"],
        "review_summary": snapshot["summary"],
        "deficiency_count": int(snapshot["payload"].get("deficiency_count", 0) or 0),
        "persistable": bool(snapshot["persistable"]),
        "payload_json": snapshot,
    }
    created = _post_service_json(
        service_config=service_config,
        path=f"/api/workflows/{workflow_id}/snapshots",
        payload=payload,
    )
    return {"delivery_status": "persisted", "snapshot": created}


def _maybe_record_review(
    *,
    workflow_id: str | None,
    snapshot_id: str | None,
    review_payload: dict[str, Any],
    summary: str,
    service_config: UsecaseWorkflowServiceConfig,
) -> dict[str, Any]:
    if not workflow_id:
        return {"delivery_status": "missing_workflow_id"}
    if not snapshot_id:
        return {"delivery_status": "missing_snapshot_id"}
    base_url = _build_service_base_url(service_config)
    if not base_url:
        return {"delivery_status": "not_configured"}
    created = _post_service_json(
        service_config=service_config,
        path=f"/api/workflows/{workflow_id}/review",
        payload={
            "snapshot_id": snapshot_id,
            "summary": summary,
            "payload_json": review_payload,
        },
    )
    return {"delivery_status": "persisted", "review": created}


@tool(
    "create_usecase_workflow",
    args_schema=CreateUsecaseWorkflowToolInput,
    description="Create one workflow record for the current usecase-generation session before saving analysis or review snapshots.",
)
def create_usecase_workflow(
    project_id: str = "",
    title: str = "",
    summary: str = "",
    requirement_document_id: str = "",
    metadata_json: str = "{}",
) -> str:
    metadata = _parse_json_payload(metadata_json, field_name="metadata_json")
    project_id = str(project_id or "").strip()
    title = str(title or "").strip()
    missing_fields: list[str] = []
    if not project_id:
        missing_fields.append("project_id")
    if not title:
        missing_fields.append("title")
    service_config = _build_runtime_persistence_config()
    base_url = _build_service_base_url(service_config)
    created_workflow: dict[str, Any] | None = None
    delivery_status = "not_configured"
    if missing_fields:
        delivery_status = "missing_required_fields"
    elif base_url:
        created_workflow = _post_service_json(
            service_config=service_config,
            path="/api/workflows",
            payload={
                "project_id": project_id,
                "title": title,
                "summary": summary,
                "requirement_document_id": requirement_document_id or None,
                "workflow_type": service_config.workflow_type,
                "agent_key": "usecase_workflow_agent",
                "metadata_json": metadata,
            },
        )
        delivery_status = "persisted"
    snapshot = build_workflow_snapshot(
        workflow_type=DEFAULT_WORKFLOW_TYPE,
        stage="workflow_initialized",
        summary=summary or title,
        persistable=False,
        next_action="record_requirement_analysis",
        payload={
            "project_id": project_id,
            "workflow": created_workflow,
            "requirement_document_id": requirement_document_id or None,
            "metadata": metadata,
            "delivery_status": delivery_status,
            "missing_fields": missing_fields,
        },
    )
    return json.dumps(snapshot, ensure_ascii=False)


def _persist_usecases_to_interaction_service(
    *,
    payload: UsecaseDraftPayload,
    approval_note: str,
    service_config: UsecaseWorkflowServiceConfig,
) -> dict[str, Any]:
    base_url = service_config.interaction_data_service_url
    if not base_url:
        return {
            "delivery_status": "not_configured",
            "persisted_items": [],
            "approval_note": approval_note,
        }

    usecases = payload.get("usecases")
    if not isinstance(usecases, list):
        return {
            "delivery_status": "missing_usecases",
            "persisted_items": [],
            "approval_note": approval_note,
        }

    workflow_id = payload.get("workflow_id")
    if not isinstance(workflow_id, str) or not workflow_id.strip():
        return {
            "delivery_status": "missing_workflow_id",
            "persisted_items": [],
            "approval_note": approval_note,
        }

    approve_result = _post_service_json(
        service_config=service_config,
        path=f"/api/workflows/{workflow_id}/approve",
        payload={},
    )
    persist_result = _post_service_json(
        service_config=service_config,
        path=f"/api/workflows/{workflow_id}/persist",
        payload={},
    )

    return {
        "delivery_status": "persisted",
        "approve_result": approve_result,
        "persist_result": persist_result,
        "approval_note": approval_note,
    }


@tool(
    "record_requirement_analysis",
    args_schema=RecordRequirementAnalysisToolInput,
    description="Record one structured requirement-analysis snapshot for the current workflow before draft use cases are finalized.",
)
def record_requirement_analysis(summary: str, analysis_json: str) -> str:
    service_config = _build_runtime_persistence_config()
    payload = _normalize_requirement_analysis(
        _parse_json_payload(analysis_json, field_name="analysis_json")
    )
    requirement_count = len(payload["requirements"])
    snapshot = build_workflow_snapshot(
        workflow_type=DEFAULT_WORKFLOW_TYPE,
        stage="requirement_analysis",
        summary=summary,
        persistable=False,
        next_action="generate_candidate_usecases",
        payload={
            "workflow_id": payload.get("workflow_id"),
            "project_id": payload.get("project_id"),
            "requirement_count": requirement_count,
            "analysis": payload,
        },
    )
    snapshot["payload"]["persistence_result"] = _maybe_create_snapshot(
        workflow_id=payload.get("workflow_id") if isinstance(payload.get("workflow_id"), str) else None,
        snapshot=snapshot,
        service_config=service_config,
    )
    return json.dumps(snapshot, ensure_ascii=False)


@tool(
    "record_usecase_review",
    args_schema=RecordUsecaseReviewToolInput,
    description="Record candidate use cases together with the review report and revision suggestions before asking the user for confirmation.",
)
def record_usecase_review(
    candidate_usecases_json: str,
    review_report_json: str,
    revised_usecases_json: str | None = None,
) -> str:
    service_config = _build_runtime_persistence_config()
    candidates = _normalize_usecase_draft(
        _parse_json_payload(
            candidate_usecases_json, field_name="candidate_usecases_json"
        )
    )
    review = _normalize_usecase_review(
        _parse_json_payload(review_report_json, field_name="review_report_json")
    )
    revised = (
        _normalize_usecase_draft(
            _parse_json_payload(
                revised_usecases_json, field_name="revised_usecases_json"
            )
        )
        if revised_usecases_json
        else None
    )
    usecase_count = len(candidates["usecases"])
    deficiency_count = len(review["deficiencies"])
    workflow_id = (
        candidates.get("workflow_id")
        if isinstance(candidates.get("workflow_id"), str)
        else (
            revised.get("workflow_id")
            if isinstance(revised, dict) and isinstance(revised.get("workflow_id"), str)
            else None
        )
    )
    snapshot = build_workflow_snapshot(
        workflow_type=DEFAULT_WORKFLOW_TYPE,
        stage="reviewed_candidate_usecases",
        summary="Candidate use cases reviewed and ready for user inspection.",
        persistable=deficiency_count == 0,
        next_action=(
            "await_user_confirmation"
            if deficiency_count == 0
            else "revise_and_review_again"
        ),
        payload={
            "workflow_id": workflow_id,
            "project_id": candidates.get("project_id"),
            "candidate_usecase_count": usecase_count,
            "deficiency_count": deficiency_count,
            "candidate_usecases": candidates,
            "review_report": review,
            "revised_usecases": revised,
        },
    )
    persistence_result = _maybe_create_snapshot(
        workflow_id=workflow_id,
        snapshot=snapshot,
        service_config=service_config,
    )
    snapshot["payload"]["persistence_result"] = persistence_result
    snapshot_id = None
    if persistence_result.get("delivery_status") == "persisted":
        maybe_snapshot = persistence_result.get("snapshot")
        if isinstance(maybe_snapshot, dict):
            raw_snapshot_id = maybe_snapshot.get("id")
            if isinstance(raw_snapshot_id, str):
                snapshot_id = raw_snapshot_id
    snapshot["payload"]["review_persistence_result"] = _maybe_record_review(
        workflow_id=workflow_id,
        snapshot_id=snapshot_id,
        review_payload=review,
        summary=str(review.get("summary") or snapshot["summary"]),
        service_config=service_config,
    )
    return json.dumps(snapshot, ensure_ascii=False)


@tool(
    "persist_approved_usecases",
    args_schema=PersistApprovedUsecasesToolInput,
    description="Persist the final approved use cases only after the user explicitly confirms the current version is ready.",
)
def persist_approved_usecases(final_usecases_json: str, approval_note: str = "") -> str:
    payload = _normalize_usecase_draft(
        _parse_json_payload(final_usecases_json, field_name="final_usecases_json")
    )
    usecase_count = len(payload["usecases"])
    persistence_result = _persist_usecases_to_interaction_service(
        payload=payload,
        approval_note=approval_note,
        service_config=_build_runtime_persistence_config(),
    )
    return json.dumps(
        build_workflow_snapshot(
            workflow_type=DEFAULT_WORKFLOW_TYPE,
            stage="persisted",
            summary="Approved use cases have been persisted.",
            persistable=True,
            next_action="completed",
            payload={
                "approval_note": approval_note,
                "persistence_result": persistence_result,
                "final_usecase_count": usecase_count,
                "final_usecases": payload,
            },
        ),
        ensure_ascii=False,
    )


def build_usecase_workflow_tools(model: Any | None = None) -> list[Any]:
    tools: list[Any] = []
    if model is not None:
        tools.extend(
            [
                build_requirement_analysis_subagent_tool(model),
                build_usecase_review_subagent_tool(model),
            ]
        )
    tools.extend(
        [
            create_usecase_workflow,
            record_requirement_analysis,
            record_usecase_review,
            persist_approved_usecases,
        ]
    )
    return tools


__all__ = [
    "UsecaseWorkflowServiceConfig",
    "build_usecase_workflow_service_config",
    "build_usecase_workflow_tools",
    "build_requirement_analysis_subagent_tool",
    "build_usecase_review_subagent_tool",
    "create_usecase_workflow",
    "persist_approved_usecases",
    "record_requirement_analysis",
    "record_usecase_review",
]
