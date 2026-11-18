import json
from pathlib import Path

from sqlalchemy import select

from platform_api.core.errors import ForbiddenError
from platform_api.modules.platform_assistant.models import AssistantEvidenceRecord


def save_evidence(factory, actor, project_id, evidence_id, body, correlation, data):
    if "assistant_thread_id" not in correlation or body.operation in {
        "authorize",
        "record_citations",
    }:
        return
    with factory.begin() as session:
        session.add(
            AssistantEvidenceRecord(
                evidence_id=evidence_id,
                project_id=project_id,
                actor_id=actor.user_id,
                thread_id=correlation["assistant_thread_id"],
                run_id=correlation["assistant_run_id"],
                operation=body.operation,
                source={
                    "database_id": body.database_id,
                    "revision": data.get("revision"),
                    "target_thread_id": str(body.target_thread_id)
                    if body.target_thread_id
                    else None,
                    "document_id": body.document_id,
                },
            )
        )


def require_history_access(factory, settings, actor, project_id, thread_id, access):
    from platform_api.modules.platform_assistant.service import (
        require_target_project,
        sources,
    )

    if access.get("owner_user_id") != actor.user_id:
        raise ForbiddenError(
            code="assistant_private_history",
            message="助手资料与个人授权绑定，仅会话本人可读取。",
        )
    available = sources(settings, actor, project_id)
    with factory() as session:
        records = session.scalars(
            select(AssistantEvidenceRecord).where(
                AssistantEvidenceRecord.thread_id == thread_id,
                AssistantEvidenceRecord.project_id == project_id,
            )
        ).all()
    from platform_api.modules.runtime_policies.application.service import (
        RuntimePolicyOverlayService,
    )

    policy = RuntimePolicyOverlayService(
        session_factory=factory, runtime_base_url=settings.langgraph_upstream_url
    ).resolve_tool_overrides(
        project_id=project_id, user_id=actor.user_id, graph_id="platform_assistant"
    )["tool_overrides"]
    for record in records:
        source = record.source
        allowed = True
        if record.operation in {"sql_schema", "sql_query"}:
            dataset = available.get(source["database_id"])
            allowed = dataset is not None and dataset.revision == source["revision"]
        elif record.operation == "source":
            allowed = actor.user_id in settings.assistant_source_users
            root = settings.assistant_source_root
            try:
                revision = (
                    str(
                        json.loads((Path(root) / "manifest.json").read_text())[
                            "revision"
                        ]
                    )
                    if root
                    else "platform-assistant-v1"
                )
                allowed = allowed and revision == source["revision"]
            except (OSError, ValueError, KeyError, TypeError):
                allowed = False
        elif record.operation in {"diagnostics", "logs"}:
            if source["target_thread_id"]:
                try:
                    require_target_project(factory, actor, source["target_thread_id"])
                except ForbiddenError:
                    allowed = False
            else:
                allowed = actor.user_id in settings.assistant_log_users
        tool = {
            "sql_schema": "sql_db_schema",
            "sql_query": "sql_db_query",
            "source": "search_source",
            "documents": "search_documents",
            "diagnostics": "read_run_diagnostics",
            "logs": "read_run_logs"
            if source.get("target_thread_id")
            else "search_project_logs",
            "authorize_search": "search_public_web",
        }.get(record.operation)
        allowed = allowed and policy.get(tool) is not False
        if not allowed:
            raise ForbiddenError(
                code="assistant_history_source_revoked",
                message="此会话曾引用的资料权限或数据范围已变更，请新建助手会话。",
            )


def check_citations(factory, actor, project_id, thread_id, ids):
    with factory() as session:
        rows = session.scalars(
            select(AssistantEvidenceRecord).where(
                AssistantEvidenceRecord.evidence_id.in_([str(x) for x in ids]),
                AssistantEvidenceRecord.actor_id == actor.user_id,
                AssistantEvidenceRecord.project_id == project_id,
                AssistantEvidenceRecord.thread_id == thread_id,
            )
        ).all()
        return {
            "cited_evidence_ids": [r.evidence_id for r in rows],
            "unverified_count": len(ids) - len(rows),
        }
