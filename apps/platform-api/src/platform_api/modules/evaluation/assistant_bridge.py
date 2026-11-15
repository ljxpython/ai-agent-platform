"""Start one managed assistant Run and serve only its current authorized material."""

import hashlib
import hmac
import json
import time
from datetime import UTC, datetime
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

from platform_api.core.errors import ForbiddenError
from platform_api.modules.evaluation import service
from platform_api.modules.evaluation.delegation import require_action
from platform_api.modules.evaluation.router import source_access
from platform_api.modules.evaluation.workbench_grants import bind_assistant_thread
from platform_api.modules.identity.actors import load_user_actor

router = APIRouter(prefix="/api/evaluation/internal")


class AdvanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    actor_id: UUID
    work_item_id: UUID
    target_id: UUID
    kind: Literal["assistant", "result"]


@router.post("/workbench/advance", dependencies=[Depends(source_access)])
async def advance_saved_request(request: Request, body: AdvanceRequest):
    """Continue a persisted user request, never accept a new prompt from the scheduler."""
    from dataclasses import replace

    from platform_api.core.context.models import ProjectContext, TenantContext
    from platform_api.core.db import session_scope
    from platform_api.modules.evaluation.workbench import enabled, forward
    from platform_api.modules.projects.models import ProjectRecord
    from platform_api.modules.runtime_gateway.presentation.http import (
        get_runtime_gateway_service,
    )

    enabled(request)
    project_id = str(body.project_id)
    factory = request.app.state.db_session_factory
    actor = await run_in_threadpool(
        load_user_actor,
        session_factory=factory,
        user_id=str(body.actor_id),
        project_id=project_id,
    )
    require_action(actor, project_id, "generate")
    item = await forward(
        request, actor, project_id, "read", str(body.work_item_id), uuid4(), {}
    )
    entries = (
        item.get("assistant_jobs", [])
        if body.kind == "assistant"
        else item.get("operations", [])
    )
    target = next(
        (entry for entry in entries if entry["id"] == str(body.target_id)), None
    )
    if not target or target["created_by"] != actor.user_id:
        raise ForbiddenError(
            code="evaluation_saved_request_denied",
            message="后台请求不属于已登记的发起人。",
        )
    if body.kind == "result":
        result = next(
            (r for r in item["results"] if r["task_id"] == target.get("task_id")), None
        )
        if (
            not result
            or result["status"] not in {"passed", "failed", "error", "cancelled"}
            or not result["evidence"]
        ):
            return {"status": "no_result"}
        job_id = uuid5(NAMESPACE_URL, "evaluation-explanation:" + target["id"])
        existing = next(
            (j for j in item["assistant_jobs"] if j["id"] == str(job_id)), None
        )
        if existing and existing["status"] not in {"reserved", "running", "cancelling"}:
            return {"status": existing["status"]}
        item = await forward(
            request,
            actor,
            project_id,
            "explain",
            item["id"],
            job_id,
            {"task_id": result["task_id"]},
        )
    else:
        job_id = body.target_id
    with session_scope(factory) as session:
        project = session.get(ProjectRecord, body.project_id)
        tenant_id = str(project.tenant_id)
    request.state.platform_context = replace(
        request.state.platform_context,
        actor=actor,
        project=ProjectContext(project_id=project_id),
        tenant=TenantContext(tenant_id=tenant_id),
    )
    gateway = get_runtime_gateway_service(request, actor)
    item = await start_assistant(request, actor, project_id, item, job_id, gateway)
    await reconcile_assistant(request, actor, project_id, item, gateway)
    return {"status": "checked"}


class AssistantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID
    actor_id: UUID
    thread_id: UUID
    work_item_id: UUID
    job_id: UUID
    operation: Literal["read", "validate", "complete"]
    payload: dict


async def start_assistant(request, actor, project_id, item, job_id, gateway):
    from platform_api.modules.evaluation.workbench import forward

    job = next(j for j in item["assistant_jobs"] if j["id"] == str(job_id))
    if job["status"] not in {"reserved", "running"} or job.get("run_id"):
        return item
    package = await run_in_threadpool(
        service.authorized_package,
        request.app.state.db_session_factory,
        project_id,
        item["grants"]["evaluation_assistance"],
    )
    thread_id = str(
        uuid5(NAMESPACE_URL, "evaluation-assistant:" + project_id + ":" + job["id"])
    )
    await run_in_threadpool(
        bind_assistant_thread,
        request.app.state.db_session_factory,
        project_id,
        list(item["grants"].values()),
        thread_id,
    )
    await gateway.create_thread(
        actor=actor,
        project_id=project_id,
        reserved_thread_id=thread_id,
        payload={
            "graph_id": "evaluation_assistant",
            "metadata": {
                "graph_id": "evaluation_assistant",
                "title": "评测建议 · " + item["title"],
                "evaluation_work_item_id": item["id"],
                "evaluation_assistant_job_id": job["id"],
            },
        },
    )
    await forward(
        request,
        actor,
        project_id,
        "assistant_bind",
        item["id"],
        uuid5(NAMESPACE_URL, job["id"] + ":bind"),
        {"job_id": job["id"], "thread_id": thread_id},
    )
    result = await gateway.create_thread_run(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        idempotency_key="evaluation-assistant:" + job["id"],
        payload={
            "assistant_id": "evaluation_assistant",
            "input": {"work_item_id": item["id"], "job_id": job["id"]},
            "context": {"model_id": package["model_route"]},
        },
    )
    run_id = result.get("run_id") or result.get("result", {}).get("run_id")
    if not run_id:
        raise ValueError("助手运行回执缺少编号，请重试原请求核对。")
    return await forward(
        request,
        actor,
        project_id,
        "assistant_bind",
        item["id"],
        uuid5(NAMESPACE_URL, job["id"] + ":run"),
        {"job_id": job["id"], "thread_id": thread_id, "run_id": run_id},
    )


@router.post("/assistant")
async def assistant_material(request: Request, body: AssistantRequest):
    from platform_api.modules.evaluation.workbench import forward

    settings = request.app.state.settings
    timestamp = request.headers.get("x-evaluation-time", "")
    signature = request.headers.get("x-evaluation-signature", "")
    try:
        encoded = json.dumps(
            body.model_dump(mode="json"), ensure_ascii=False, sort_keys=True
        )
        expected = hmac.new(
            settings.runtime_delegation_secret.encode(),
            ("evaluation-assistant\n" + timestamp + "\n" + encoded).encode(),
            hashlib.sha256,
        ).hexdigest()
        valid = (
            settings.evaluation_workbench_enabled
            and settings.runtime_delegation_secret
            and abs(time.time() - int(timestamp)) <= 30
            and hmac.compare_digest(signature, expected)
        )
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise ForbiddenError(
            code="evaluation_assistant_denied", message="助手来源无法确认。"
        )
    project_id = str(body.project_id)
    actor = await run_in_threadpool(
        load_user_actor,
        session_factory=request.app.state.db_session_factory,
        user_id=str(body.actor_id),
        project_id=project_id,
    )
    require_action(actor, project_id, "generate")
    result = await forward(
        request,
        actor,
        project_id,
        "read",
        str(body.work_item_id),
        uuid4(),
        {"assistant_schema": True, "job_id": str(body.job_id)},
    )
    item = result["item"]
    job = next((j for j in item["assistant_jobs"] if j["id"] == str(body.job_id)), None)
    if (
        not job
        or job.get("thread_id") != str(body.thread_id)
        or job["created_by"] != actor.user_id
        or job["status"] not in {"reserved", "running", "completed"}
    ):
        raise ForbiddenError(
            code="evaluation_assistant_scope",
            message="助手与工作项、发起人或会话不匹配。",
        )
    package = await run_in_threadpool(
        service.authorized_package,
        request.app.state.db_session_factory,
        project_id,
        item["grants"]["evaluation_assistance"],
    )
    if job["status"] == "completed" and body.operation != "complete":
        raise ForbiddenError(
            code="evaluation_assistant_finished", message="此轮助手已结束。"
        )
    if body.operation == "validate":
        from platform_api.modules.evaluation.privacy import require_synthetic

        require_synthetic(json.dumps(body.payload, ensure_ascii=False))
        return await forward(
            request,
            actor,
            project_id,
            "read",
            item["id"],
            uuid4(),
            {
                "assistant_schema": True,
                "job_id": job["id"],
                "proposal": body.payload.get("proposal"),
            },
        )
    if body.operation == "complete":
        from platform_api.modules.evaluation.privacy import require_synthetic

        require_synthetic(json.dumps(body.payload, ensure_ascii=False))
        result = await forward(
            request,
            actor,
            project_id,
            "assistant_result",
            item["id"],
            uuid5(NAMESPACE_URL, job["id"] + ":complete"),
            {
                "job_id": job["id"],
                "thread_id": str(body.thread_id),
                "proposal": body.payload.get("proposal"),
                "model": {
                    "route": package["model_route"],
                    "prompt_version": "evaluation-assistant-v1",
                },
            },
        )
        return {"saved_revision": result["revision"]}
    evidence = next(
        (r["evidence"] for r in item["results"] if r["task_id"] == job.get("task_id")),
        {},
    )
    return {
        "title": item["title"],
        "description": item["description"],
        "fixture": item["fixture"],
        "feedback": job["feedback"],
        "intent": job["intent"],
        "today": datetime.now(UTC).date().isoformat(),
        "current_proposal": next(
            (
                v["proposal"]
                for v in item["versions"]
                if v["revision"] == job["base_revision"]
            ),
            None,
        )
        if job["intent"] in {"draft", "revise"}
        else None,
        "proposal_schema": result["proposal_schema"],
        "evidence": evidence,
        "scope": {
            "data_class": "synthetic",
            "purpose": "evaluation_assistance",
            "profile": item["profile"],
        },
    }


async def reconcile_assistant(request, actor, project_id, item, gateway):
    from platform_api.modules.evaluation.workbench import forward

    for job in item.get("assistant_jobs", []):
        if job["status"] not in {"running", "cancelling"}:
            continue
        # The gateway still checks the real caller's thread ACL; do not impersonate the owner.
        if job["created_by"] != actor.user_id and job["status"] != "cancelling":
            continue
        status = None
        if job["status"] == "cancelling":
            if not job.get("thread_id"):
                item = await forward(
                    request,
                    actor,
                    project_id,
                    "assistant_status",
                    item["id"],
                    uuid5(NAMESPACE_URL, job["id"] + ":terminal:cancelled"),
                    {"job_id": job["id"], "status": "cancelled"},
                )
                continue
            from platform_api.modules.evaluation.assistant_control import (
                control,
                request_stop,
            )

            await run_in_threadpool(
                request_stop,
                request.app.state.db_session_factory,
                project_id,
                job["thread_id"],
                actor.user_id,
            )
            receipt = await run_in_threadpool(
                control,
                request.app.state.db_session_factory,
                request.app.state.settings,
                project_id,
                job["thread_id"],
            )
            if receipt.get("execution_stopped") is True and receipt.get("phase") in {
                "stopped",
                "no_active_run",
            }:
                status = "cancelled"
        elif job.get("run_id"):
            run = await gateway.get_thread_run(
                actor=actor,
                project_id=project_id,
                thread_id=job["thread_id"],
                run_id=job["run_id"],
            )
            if run.get("status") in {
                "error",
                "timeout",
                "cancelled",
                "canceled",
                "success",
            }:
                current = await forward(
                    request, actor, project_id, "read", item["id"], uuid4(), {}
                )
                latest = next(
                    j for j in current["assistant_jobs"] if j["id"] == job["id"]
                )
                if latest["status"] == "completed":
                    item = current
                    continue
                status = (
                    "cancelled"
                    if run["status"] in {"cancelled", "canceled"}
                    else "error"
                )
        if status:
            item = await forward(
                request,
                actor,
                project_id,
                "assistant_status",
                item["id"],
                uuid5(NAMESPACE_URL, job["id"] + ":terminal:" + status),
                {"job_id": job["id"], "status": status},
            )
    return item
