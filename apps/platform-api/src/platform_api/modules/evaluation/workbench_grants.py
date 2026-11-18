"""Independent purpose grants for explicitly shared work-item material."""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from platform_api.core.db import session_scope
from platform_api.core.errors import ConflictError, ForbiddenError
from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
from platform_api.modules.evaluation.delegation import require_action
from platform_api.modules.evaluation.models import EvaluationExport
from platform_api.modules.evaluation.service import audit, digest, lock_packages


class GrantBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    grant_id: UUID
    purpose: Literal["evaluation_assistance", "regression"]
    expires_in_hours: int = Field(default=24, ge=1, le=24)
    synthetic_attestation: bool = False
    material_consent: bool = False


def create_grant(factory, actor, project_id, item, body, model_route):
    require_action(actor, project_id, "grant")
    if item["project_id"] != project_id or not model_route:
        raise ForbiddenError(
            code="evaluation_grant_scope", message="资料项目或受管模型尚未确认。"
        )
    data_class = item.get("data_class", "synthetic")
    if data_class not in {"synthetic", "business"} or not (
        body.material_consent
        if data_class == "business"
        else body.synthetic_attestation
    ):
        raise ForbiddenError(
            code="evaluation_material_consent", message="请确认当前资料的评测用途。"
        )
    payload = {
        "source_kind": "work_item",
        "work_item_id": item["id"],
        "agent_id": item["agent_id"],
        "purpose": body.purpose,
        "data_class": data_class,
        "model_route": model_route,
        "allowed_fields": [
            "description",
            "fixture",
            "proposal",
            "evaluation_results",
            "source_materials",
        ],
        "allow_synthetic_revisions": True,
        "content_hash": item["material_hash"],
        "policy_version": "workbench-material-v2",
        "source_threads": [m["thread_id"] for m in item.get("source_materials", [])],
        "retention_policy": "local-synthetic-20261114",
        **(
            {"source_export_id": item["source_export_id"]}
            if item.get("source_export_id")
            else {}
        ),
    }
    binding = digest(
        {**payload, "hours": body.expires_in_hours, "actor": actor.user_id}
    )
    with session_scope(factory) as session:
        agent = session.get(AgentRecord, UUID(item["agent_id"]))
        if (
            agent is None
            or str(agent.project_id) != project_id
            or agent.status != "active"
        ):
            raise ForbiddenError(
                code="evaluation_agent_denied",
                message="被测Agent不属于当前项目或已停用。",
            )
        prior = session.get(EvaluationExport, str(body.grant_id))
        if prior:
            if prior.digest != binding or prior.project_id != project_id:
                raise ConflictError(
                    code="evaluation_grant_conflict", message="授权编号已用于其他内容。"
                )
            return {
                "grant_id": prior.export_id,
                "status": prior.status,
                "expires_at": prior.expires_at.isoformat(),
            }
        expiry = datetime.now(UTC) + timedelta(hours=body.expires_in_hours)
        session.add(
            EvaluationExport(
                export_id=str(body.grant_id),
                event_id=item["id"],
                project_id=project_id,
                actor_id=actor.user_id,
                digest=binding,
                status="ready",
                payload=payload,
                receipt={},
                expires_at=expiry,
            )
        )
        audit(
            session,
            actor,
            project_id,
            str(body.grant_id),
            "evaluation.workbench.authorized",
            retention_policy=payload["retention_policy"],
        )
        return {
            "grant_id": str(body.grant_id),
            "status": "ready",
            "expires_at": expiry.isoformat(),
        }


def validate_scope(session, export, actor, project_id):
    from dataclasses import replace

    from platform_api.modules.iam.domain.roles import ProjectRole

    actor = replace(
        actor,
        project_roles={
            project_id: tuple(
                ProjectRole.from_db(role).value
                for role in actor.project_role_set(project_id)
            )
        },
    )
    require_action(actor, project_id, "grant")
    from platform_api.modules.evaluation.service import authorize

    for thread_id in export.payload.get("source_threads", []):
        authorize(session, actor, project_id, thread_id, "read")
    if export.payload.get("source_export_id"):
        from platform_api.modules.evaluation.service import _authorized_package

        source = _authorized_package(
            session, project_id, export.payload["source_export_id"]
        )
        if source.get("purpose") != "quality_inspection":
            raise ForbiddenError(
                code="evaluation_source_scope", message="来源不是获准的质量巡检。"
            )
    agent = session.get(AgentRecord, UUID(export.payload["agent_id"]))
    if agent is None or str(agent.project_id) != project_id or agent.status != "active":
        raise ForbiddenError(
            code="evaluation_agent_denied", message="授权所指Agent已不可用。"
        )


def revoke_grant(factory, actor, project_id, grant_id):
    require_action(actor, project_id, "revoke")
    from sqlalchemy import select

    with session_scope(factory) as session:
        grant = session.scalar(
            select(EvaluationExport)
            .where(EvaluationExport.export_id == str(grant_id))
            .with_for_update()
        )
        if (
            not grant
            or grant.project_id != project_id
            or grant.payload.get("source_kind") != "work_item"
        ):
            raise ForbiddenError(
                code="evaluation_grant_denied", message="无权撤销该授权。"
            )
        grant.status = "revoked"
        audit(
            session,
            actor,
            project_id,
            str(grant_id),
            "evaluation.workbench.revoked",
            retention_policy=grant.payload.get("retention_policy"),
        )
        return {"grant_id": str(grant_id), "status": "revoked"}


def bind_execution_thread(factory, project_id, grants, thread_id, agent_id, graph_id):
    """Bind before sending any fixture or input to the evaluated Agent."""
    from platform_api.modules.evaluation.service import _authorized_package

    if not isinstance(grants, dict) or set(grants) != {
        "evaluation_assistance",
        "regression",
    }:
        raise ForbiddenError(
            code="evaluation_execution_scope",
            message="评测运行必须关联两个独立用途授权。",
        )
    with session_scope(factory) as session:
        item_ids = set()
        rows = []
        lock_packages(session, grants.values())
        for purpose, identifier in grants.items():
            package = _authorized_package(session, project_id, str(UUID(identifier)))
            if (
                package.get("source_kind") != "work_item"
                or package.get("purpose") != purpose
                or package.get("agent_id") != agent_id
                or not package.get("work_item_id")
            ):
                raise ForbiddenError(
                    code="evaluation_execution_scope",
                    message="运行与资料用途、Agent不匹配。",
                )
            item_ids.add(package["work_item_id"])
            rows.append(session.get(EvaluationExport, str(identifier)))
        agent = session.get(AgentRecord, UUID(agent_id))
        if len(item_ids) != 1 or agent is None or agent.graph_id != graph_id:
            raise ForbiddenError(
                code="evaluation_execution_scope",
                message="运行与工作项或执行图不匹配。",
            )
        for row in rows:
            executions = {
                **row.receipt.get("execution_threads", {}),
                thread_id: graph_id,
            }
            row.receipt = {**row.receipt, "execution_threads": executions}


def check_assistant_thread(factory, project_id, thread_id):
    from sqlalchemy import select

    from platform_api.modules.evaluation.service import _authorized_package

    with session_scope(factory) as session:
        grants = session.scalars(
            select(EvaluationExport).where(
                EvaluationExport.project_id == project_id,
                EvaluationExport.payload["source_kind"].as_string() == "work_item",
            )
        ).all()
        grants = [
            grant
            for grant in grants
            if thread_id in grant.receipt.get("assistant_threads", [])
            or thread_id in grant.receipt.get("execution_threads", {})
        ]
        lock_packages(session, [grant.export_id for grant in grants])
        registered = False
        for grant in grants:
            assistant = thread_id in grant.receipt.get("assistant_threads", [])
            if assistant or thread_id in grant.receipt.get("execution_threads", {}):
                _authorized_package(session, project_id, grant.export_id)
                registered = registered or assistant
        return registered


def assistant_thread_ids(factory, project_id):
    from sqlalchemy import select

    with session_scope(factory) as session:
        receipts = session.scalars(
            select(EvaluationExport.receipt).where(
                EvaluationExport.project_id == project_id,
                EvaluationExport.payload["source_kind"].as_string() == "work_item",
            )
        ).all()
        return {
            thread_id
            for receipt in receipts
            for thread_id in [
                *receipt.get("assistant_threads", []),
                *receipt.get("execution_threads", {}),
            ]
        }
