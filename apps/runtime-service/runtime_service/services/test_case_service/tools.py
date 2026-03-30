from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from runtime_service.integrations import (
    InteractionDataServiceClient,
    build_interaction_data_service_config,
)
from runtime_service.runtime.context import RuntimeContext
from runtime_service.services.test_case_service.document_persistence import (
    _coerce_string_list,
    _get_runtime_state,
    _resolve_batch_id,
    _resolve_project_id,
    _resolve_runtime_meta,
    collect_persisted_document_ids,
    persist_runtime_documents,
)
from runtime_service.services.test_case_service.schemas import (
    PersistTestCaseItem,
    TestCaseServiceConfig,
)

TEST_CASES_PATH = "/api/test-case-service/test-cases"


def _merge_content_json(
    item: PersistTestCaseItem,
    *,
    bundle_title: str,
    bundle_summary: str,
    quality_review: dict[str, Any],
    export_format: str | None,
    runtime_meta: dict[str, Any],
    batch_id: str,
    source_document_ids: list[str],
) -> dict[str, Any]:
    content = dict(item.content_json)
    content.setdefault("case_id", item.case_id)
    content.setdefault("title", item.title)
    content.setdefault("description", item.description)
    content.setdefault("module_name", item.module_name)
    content.setdefault("priority", item.priority)
    content.setdefault("test_type", item.test_type)
    content.setdefault("design_technique", item.design_technique)
    content.setdefault("preconditions", list(item.preconditions))
    content.setdefault("steps", list(item.steps))
    content.setdefault("test_data", dict(item.test_data))
    content.setdefault("expected_results", list(item.expected_results))
    content.setdefault("remarks", item.remarks)
    meta = content.get("meta") if isinstance(content.get("meta"), dict) else {}
    meta.update(
        {
            "bundle_title": bundle_title,
            "bundle_summary": bundle_summary,
            "quality_review": quality_review,
            "export_format": export_format,
            "batch_id": batch_id,
            "source_document_ids": source_document_ids,
            **runtime_meta,
        }
    )
    content["meta"] = meta
    return content


def _build_test_case_payloads(
    *,
    items: list[PersistTestCaseItem],
    project_id: str,
    batch_id: str,
    source_document_ids: list[str],
    bundle_title: str,
    bundle_summary: str,
    quality_review: dict[str, Any],
    export_format: str | None,
    runtime_meta: dict[str, Any],
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for item in items:
        content_json = _merge_content_json(
            item,
            bundle_title=bundle_title,
            bundle_summary=bundle_summary,
            quality_review=quality_review,
            export_format=export_format,
            runtime_meta=runtime_meta,
            batch_id=batch_id,
            source_document_ids=source_document_ids,
        )
        payloads.append(
            {
                "project_id": project_id,
                "batch_id": batch_id,
                "case_id": item.case_id,
                "title": item.title,
                "description": item.description,
                "status": item.status,
                "module_name": item.module_name,
                "priority": item.priority,
                "source_document_ids": source_document_ids,
                "content_json": content_json,
            }
        )
    return payloads


def build_test_case_service_tools(service_config: TestCaseServiceConfig) -> list[Any]:
    @tool(
        "persist_test_case_results",
        description=(
            "Persist the final formatted test cases and uploaded requirement documents to "
            "interaction-data-service. Use this only after requirement analysis, strategy, "
            "test-case design, quality review, and output formatting are complete."
        ),
    )
    def persist_test_case_results(
        bundle_title: str,
        runtime: ToolRuntime[RuntimeContext | Mapping[str, Any] | None, dict[str, Any]],
        bundle_summary: str = "",
        test_cases: list[PersistTestCaseItem] | None = None,
        quality_review: dict[str, Any] | None = None,
        export_format: str | None = None,
    ) -> str:
        if not service_config.persistence_enabled:
            return json.dumps(
                {
                    "status": "skipped_persistence_disabled",
                    "reason": "test_case_persistence_enabled=false",
                },
                ensure_ascii=False,
            )
        normalized_cases = test_cases or []
        if not normalized_cases:
            return json.dumps(
                {
                    "status": "skipped_empty_test_cases",
                    "reason": "no_test_cases",
                },
                ensure_ascii=False,
            )
        project_id = _resolve_project_id(runtime, service_config)
        batch_id = _resolve_batch_id(runtime)
        runtime_meta = _resolve_runtime_meta(runtime)
        state = _get_runtime_state(runtime)
        client = InteractionDataServiceClient(build_interaction_data_service_config(runtime.config))
        if not client.is_configured:
            return json.dumps(
                {
                    "status": "skipped_remote_not_configured",
                    "project_id": project_id,
                    "batch_id": batch_id,
                    "test_case_count": len(normalized_cases),
                },
                ensure_ascii=False,
            )
        document_outcome = persist_runtime_documents(
            runtime=runtime,
            state=state,
            service_config=service_config,
            client=client,
        )
        if isinstance(state, dict):
            state["multimodal_attachments"] = document_outcome.attachments
        source_document_ids = collect_persisted_document_ids(
            {"multimodal_attachments": document_outcome.attachments}
        )
        if not source_document_ids and document_outcome.persisted_documents:
            source_document_ids = _coerce_string_list(
                [item.get("id") for item in document_outcome.persisted_documents]
            )
        quality_payload = quality_review or {}
        test_case_payloads = _build_test_case_payloads(
            items=normalized_cases,
            project_id=project_id,
            batch_id=batch_id,
            source_document_ids=source_document_ids,
            bundle_title=bundle_title,
            bundle_summary=bundle_summary,
            quality_review=quality_payload,
            export_format=export_format,
            runtime_meta=runtime_meta,
        )
        persisted_test_cases = [client.post_json(TEST_CASES_PATH, payload) for payload in test_case_payloads]
        return json.dumps(
            {
                "status": "persisted",
                "project_id": project_id,
                "batch_id": batch_id,
                "document_status": document_outcome.status,
                "persisted_document_count": len(source_document_ids),
                "persisted_document_ids": source_document_ids,
                "persisted_test_case_count": len(persisted_test_cases),
                "persisted_test_case_ids": _coerce_string_list(
                    [item.get("id") for item in persisted_test_cases]
                ),
            },
            ensure_ascii=False,
        )

    return [persist_test_case_results]


__all__ = ["build_test_case_service_tools"]
