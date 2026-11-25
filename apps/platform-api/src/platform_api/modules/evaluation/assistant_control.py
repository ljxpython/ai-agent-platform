"""Stop/delete only registered evaluation assistant threads, without reading their contents."""

from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy import select

from platform_api.core.db import session_scope
from platform_api.core.errors import ForbiddenError, NotFoundError
from platform_api.core.security import create_runtime_delegation_token
from platform_api.modules.evaluation.models import EvaluationExport
from platform_api.modules.evaluation.service import lock_packages
from platform_api.modules.projects.models import ProjectRecord

SUBJECT = "platform-evaluation-maintenance"


def control_grants(session, project_id, thread_id):
    rows = session.scalars(
        select(EvaluationExport).where(
            EvaluationExport.project_id == project_id,
            EvaluationExport.payload["source_kind"].as_string() == "work_item",
        )
    ).all()
    rows = [
        row
        for row in rows
        if thread_id in row.receipt.get("assistant_threads", [])
        or thread_id in row.receipt.get("execution_threads", {})
    ]
    lock_packages(session, [row.export_id for row in rows])
    return rows


def closed(row, session):
    expiry = (
        row.expires_at.replace(tzinfo=UTC)
        if row.expires_at.tzinfo is None
        else row.expires_at
    )
    if row.status not in {"ready", "sent"} or expiry <= datetime.now(UTC):
        return True
    from platform_api.modules.evaluation.service import _authorized_package

    try:
        _authorized_package(session, row.project_id, row.export_id)
    except (ForbiddenError, NotFoundError):
        return True
    return False


def control_allowed(factory, project_id, thread_id, *, delete=False):
    with session_scope(factory) as session:
        rows = control_grants(session, project_id, thread_id)
        return bool(rows) and (
            any(closed(row, session) for row in rows)
            or (
                not delete
                and any(
                    thread_id in row.receipt.get("stop_requests", {}) for row in rows
                )
            )
        )


def request_stop(factory, project_id, thread_id, actor_id):
    with session_scope(factory) as session:
        rows = control_grants(session, project_id, thread_id)
        if not rows:
            raise ForbiddenError(
                code="evaluation_thread_denied", message="助手会话未登记。"
            )
        for row in rows:
            stops = {
                **row.receipt.get("stop_requests", {}),
                thread_id: {"requested_by": actor_id},
            }
            row.receipt = {**row.receipt, "stop_requests": stops}


def control(factory, settings, project_id, thread_id, *, delete=False):
    if not control_allowed(factory, project_id, thread_id, delete=delete):
        raise ForbiddenError(
            code="evaluation_control_denied", message="没有已登记的停止或撤权依据。"
        )
    with session_scope(factory) as session:
        project = session.get(ProjectRecord, UUID(project_id))
        if not project:
            raise ValueError("evaluation_project_missing")
        tenant_id = str(project.tenant_id)
        rows = control_grants(session, project_id, thread_id)
        graph_id = next(
            (
                row.receipt["execution_threads"][thread_id]
                for row in rows
                if thread_id in row.receipt.get("execution_threads", {})
            ),
            "evaluation_assistant",
        )

    def headers(operation):
        token = create_runtime_delegation_token(
            subject=SUBJECT,
            role="platform_maintenance",
            tenant_id=tenant_id,
            project_id=project_id,
            permissions=[],
            policy_version="evaluation-control-v1",
            allowed_model_ids=["platform:no-enabled-model"],
            tool_overrides={},
            tool_policy_version="evaluation-control-v1",
            scope={
                "tenant_id": tenant_id,
                "project_id": project_id,
                "thread_id": thread_id,
                "assistant_id": graph_id,
                "operation": operation,
            },
            settings=settings,
        )
        return {"authorization": "Bearer " + token}

    with httpx.Client(
        base_url=settings.langgraph_upstream_url, timeout=10, trust_env=False
    ) as client:
        response = client.post(
            f"/internal/threads/{UUID(thread_id)}/cancel",
            json={},
            headers={
                **headers("thread-stop"),
                "Idempotency-Key": "evaluation-control:" + thread_id,
            },
        )
        response.raise_for_status()
        receipt = response.json()
        stopped = receipt.get("execution_stopped") is True and receipt.get("phase") in {
            "stopped",
            "no_active_run",
        }
        if delete and stopped:
            response = client.delete(
                f"/threads/{UUID(thread_id)}", headers=headers("thread-delete")
            )
            if response.status_code != 404:
                response.raise_for_status()
            with session_scope(factory) as session:
                for row in control_grants(session, project_id, thread_id):
                    row.receipt = {
                        **row.receipt,
                        "cleaned_threads": sorted(
                            set(row.receipt.get("cleaned_threads", [])) | {thread_id}
                        ),
                    }
            receipt["deleted"] = True
        return receipt


def sweep(factory, settings, project_id):
    with session_scope(factory) as session:
        rows = session.scalars(
            select(EvaluationExport).where(
                EvaluationExport.project_id == project_id,
                EvaluationExport.payload["source_kind"].as_string() == "work_item",
            )
        ).all()
        lock_packages(session, [row.export_id for row in rows])
        invalid = [row for row in rows if closed(row, session)]
        for row in invalid:
            if row.status in {"ready", "sent"}:
                row.status = "expired"
        targets = {
            thread
            for row in invalid
            for thread in [
                *row.receipt.get("assistant_threads", []),
                *row.receipt.get("execution_threads", {}),
            ]
            if thread not in row.receipt.get("cleaned_threads", [])
        }
    count = 0
    for thread in sorted(targets)[:100]:
        receipt = control(factory, settings, project_id, thread, delete=True)
        count += bool(receipt.get("deleted"))
    return count
