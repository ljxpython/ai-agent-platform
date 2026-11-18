"""Supply authorized Session evidence. Test case authoring belongs to EvalFlow."""

import json
import logging
import types
from datetime import UTC, datetime
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response, status
from pydantic import AwareDatetime, BaseModel, Field, model_validator

from platform_api.core.context.models import ActorContext
from platform_api.core.errors import PlatformApiError
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.modules.evaluation.delegation import require_action
from platform_api.modules.evaluation.privacy import (
    prepare_business_material,
    require_synthetic,
)
from platform_api.modules.evaluation.service import digest
from platform_api.modules.evaluation.workbench import enabled, forward
from platform_api.modules.runtime_gateway.presentation.http import (
    _require_project_id,
    get_runtime_gateway_service,
)

router = APIRouter(
    prefix="/api/evaluation/materials",
    tags=["evaluation-materials"],
    dependencies=[Depends(enabled)],
)


class MaterialRequest(BaseModel):
    request_id: UUID
    thread_ids: list[UUID] = Field(min_length=1, max_length=20)
    title: str = Field(min_length=1, max_length=120)
    synthetic_attestation: bool = False
    data_class: Literal["synthetic", "business"] = "synthetic"
    material_consent: bool = False
    auto_generate: bool = False
    async_mode: bool = True

    @model_validator(mode="after")
    def consented(self):
        if not (
            self.material_consent
            if self.data_class == "business"
            else self.synthetic_attestation
        ):
            raise ValueError("请确认有权将所选会话用于评测；自动整理还会使用受管模型。")
        return self


class SessionQuery(BaseModel):
    agent_id: UUID
    since: AwareDatetime | None = None
    until: AwareDatetime | None = None
    feedback: Literal["all", "positive", "negative", "none"] = "all"
    status: Literal["all", "idle", "busy", "interrupted", "error"] = "all"
    offset: int = Field(default=0, ge=0, le=10000)

    @model_validator(mode="after")
    def ordered_dates(self):
        if self.since and self.until and self.since > self.until:
            raise ValueError("开始时间不能晚于结束时间。")
        return self


def feedback_by_thread(factory, actor, project_id, thread_ids):
    from sqlalchemy import select

    from platform_api.core.db import session_scope
    from platform_api.modules.evaluation.models import FeedbackEvent

    latest = {}
    with session_scope(factory) as session:
        events = session.scalars(
            select(FeedbackEvent)
            .where(
                FeedbackEvent.project_id == project_id,
                FeedbackEvent.actor_id == actor.user_id,
                FeedbackEvent.thread_id.in_(thread_ids),
            )
            .order_by(FeedbackEvent.revision.desc())
        )
        for event in events:
            latest.setdefault(
                (event.thread_id, event.message_id), event.payload.get("rating")
            )
    ratings = {}
    for (thread_id, _), rating in latest.items():
        if rating in {"positive", "negative"}:
            ratings.setdefault(thread_id, set()).add(rating)
    return ratings


@router.post("/sessions")
async def list_material_sessions(
    request: Request,
    body: SessionQuery,
    actor: ActorContext = Depends(get_actor_context),
    gateway=Depends(get_runtime_gateway_service),
):
    from starlette.concurrency import run_in_threadpool

    project_id = _require_project_id(request)
    require_action(actor, project_id, "create")
    rows = await gateway.search_threads(
        actor=actor,
        project_id=project_id,
        payload={
            "metadata": {"agent_id": str(body.agent_id)},
            "offset": body.offset,
            "limit": 100,
            "sort_by": "created_at",
            "sort_order": "desc",
            **({"status": body.status} if body.status != "all" else {}),
        },
    )
    ratings = await run_in_threadpool(
        feedback_by_thread,
        request.app.state.db_session_factory,
        actor,
        project_id,
        [row["thread_id"] for row in rows],
    )
    selected = []
    for row in rows:
        created = (
            datetime.fromisoformat(row["created_at"]) if row.get("created_at") else None
        )
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        if (body.since and (not created or created < body.since)) or (
            body.until and (not created or created > body.until)
        ):
            continue
        feedback = sorted(ratings.get(row["thread_id"], set()))
        if (
            body.feedback == "none"
            and feedback
            or body.feedback not in {"all", "none"}
            and body.feedback not in feedback
        ):
            continue
        selected.append(
            {
                "thread_id": row["thread_id"],
                "title": row.get("metadata", {}).get("title") or row["thread_id"],
                "created_at": row.get("created_at"),
                "status": row.get("status"),
                "feedback": feedback,
            }
        )
    return {
        "items": selected,
        "scanned": len(rows),
        "next_offset": body.offset + 100
        if len(rows) == 100 and body.offset < 10000
        else None,
        "limited": body.offset == 10000 and len(rows) == 100,
        "notice": "按当前项目和Agent筛选有权查看的会话；反馈仅指你自己的有效反馈。每批检查100条，可继续查找。",
    }


async def snapshot(gateway, actor, project_id, thread_id, data_class="synthetic"):
    scope = {"actor": actor, "project_id": project_id, "thread_id": thread_id}
    thread = await gateway.get_thread(**scope)
    state = await gateway.get_thread_state(**scope, params={})
    cutoff = state.get("checkpoint") or {}
    captured_at = datetime.now(UTC)
    checkpoints, before, complete = [], cutoff or None, False
    for _ in range(20):
        page = await gateway.get_thread_history(
            **scope, payload={"limit": 100, **({"before": before} if before else {})}
        )
        if not isinstance(page, list):
            raise ValueError("会话历史接口格式不完整。")
        checkpoints.extend(page)
        if len(page) < 100:
            complete = True
            break
        next_cursor = page[-1].get("checkpoint")
        if not next_cursor or next_cursor == before:
            break
        before = next_cursor
    # History is paged strictly before the frozen checkpoint; append that exact state last.
    if cutoff and checkpoints:
        checkpoints.insert(0, state)
    messages = {}
    for checkpoint in reversed(checkpoints):
        for message in checkpoint.get("values", {}).get("messages", []):
            if not isinstance(message, dict):
                continue
            record = {
                key: message[key]
                for key in (
                    "id",
                    "role",
                    "type",
                    "content",
                    "tool_calls",
                    "tool_call_id",
                    "name",
                )
                if key in message
            }
            key = message.get("id") or digest(record)
            messages[key] = record
    if not checkpoints:
        complete = False
        for message in state.get("values", {}).get("messages", []):
            if isinstance(message, dict):
                record = {
                    key: message[key]
                    for key in (
                        "id",
                        "role",
                        "type",
                        "content",
                        "tool_calls",
                        "tool_call_id",
                        "name",
                    )
                    if key in message
                }
                messages[message.get("id") or digest(record)] = record
    runs, runs_complete = [], False
    for offset in range(0, 2000, 100):
        page = await gateway.list_thread_runs(
            **scope, params={"limit": 100, "offset": offset}
        )
        if not isinstance(page, list):
            break
        for row in page:
            if (
                row.get("created_at")
                and datetime.fromisoformat(row["created_at"]) > captured_at
            ):
                continue
            runs.append(
                {
                    key: row[key]
                    for key in ("run_id", "status", "created_at", "updated_at")
                    if key in row
                }
            )
        if len(page) < 100:
            runs_complete = True
            break
    latest = await gateway.get_thread_state(**scope, params={})
    changed = latest.get("checkpoint") != cutoff
    environment = {
        "status": "initial_state_unavailable",
        "initial_files": {},
        "notice": "历史文件初态尚未采集。可评历史回答，或补充初始文件后隔离回归；不复制结束产物。",
    }
    captured = []
    if hasattr(gateway, "get_thread_execution_evidence"):
        for run in sorted(runs, key=lambda r: r.get("created_at", "")):
            try:
                execution = await gateway.get_thread_execution_evidence(
                    **scope, run_id=run["run_id"]
                )
                captured.append(
                    {"run_id": run["run_id"], "manifest": execution["manifest"]}
                )
            except (PlatformApiError, ValueError, KeyError):
                continue
    if captured:
        first_run = min(runs, key=lambda r: r.get("created_at", ""))["run_id"]
        first = next(
            (
                c["manifest"].get("environment")
                for c in captured
                if c["run_id"] == first_run
            ),
            None,
        )
        environment["run_snapshots"] = captured
        if first:
            environment = {
                **first,
                "run_snapshots": captured,
                "notice": "这些是执行前的上传文本快照；其他工作区文件和私人记忆未采集，外部资源版本需核查。",
            }
        seen_files = dict(environment["initial_files"])
        additions = []
        for entry in captured:
            files = entry["manifest"].get("environment", {}).get("initial_files", {})
            added = {
                path: content
                for path, content in files.items()
                if path not in seen_files
            }
            changed_files = [
                path
                for path, content in files.items()
                if path in seen_files and seen_files[path] != content
            ]
            if added or changed_files:
                additions.append(
                    {
                        "before_run_id": entry["run_id"],
                        "files": added,
                        "changed_paths": changed_files,
                    }
                )
            seen_files.update(files)
        environment["later_uploads"] = additions
    value = {
        "thread_id": thread_id,
        "agent_id": thread.get("metadata", {}).get("agent_id"),
        "title": thread.get("metadata", {}).get("title", thread_id),
        "captured_at": captured_at.isoformat(),
        "cutoff": cutoff,
        "messages": list(messages.values()),
        "runs": runs,
        "history_complete": complete,
        "runs_complete": runs_complete,
        "changed_during_capture": changed,
        "environment": environment,
        "missing": ([] if complete else ["历史页不完整，不能声称已获得完整原文"])
        + ([] if runs_complete else ["运行清单未完整获取"])
        + (["采集期间会话发生变化，请重新选择截止点"] if changed else []),
    }
    if data_class == "business":
        value, privacy = prepare_business_material(value)
        value["privacy"] = privacy
    else:
        require_synthetic(json.dumps(value, ensure_ascii=False, default=str))
    value["data_class"] = data_class
    value["content_hash"] = digest(
        {key: part for key, part in value.items() if key != "captured_at"}
    )
    return value


def notify_conversion_result(
    session_factory,
    user_id: str,
    project_id: str,
    title: str,
    item_id: str | None,
    evalflow_web_url: str | None,
    error_message: str | None = None,
):
    from platform_api.core.db import session_scope
    from platform_api.modules.notifications.repository import (
        SqlAlchemyNotificationsRepository,
    )
    from platform_api.modules.notifications.schemas import (
        NotificationCategory,
        NotificationLevel,
    )
    from platform_api.modules.notifications.service import NotificationService

    try:
        with session_scope(session_factory) as session:
            repo = SqlAlchemyNotificationsRepository(session)
            service = NotificationService(repository=repo)
            if error_message:
                clean_err = str(error_message).strip().rstrip("。，, .")
                service.create_notification(
                    title=f"评测集【{title}】转换未完成",
                    content=f"会话转评测集处理异常：{clean_err}，请稍后重试。",
                    level=NotificationLevel.WARNING,
                    category=NotificationCategory.EVAL,
                    recipient_user_id=UUID(user_id) if user_id else None,
                    project_id=UUID(project_id) if project_id else None,
                )
            else:
                url = (
                    f"{evalflow_web_url.rstrip('/')}/#/authoring/{item_id}"
                    if evalflow_web_url and item_id
                    else None
                )
                service.create_notification(
                    title=f"评测集【{title}】已生成完毕",
                    content="会话历史与执行证据已处理完毕，AI 建议用例草稿已就绪，点击即可前往查看与调整。",
                    level=NotificationLevel.INFO,
                    category=NotificationCategory.EVAL,
                    recipient_user_id=UUID(user_id) if user_id else None,
                    project_id=UUID(project_id) if project_id else None,
                    action_url=url,
                )
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning(
            "Failed to emit conversion notification: %s", exc
        )


async def process_materials_background(
    app_state,
    actor: ActorContext,
    project_id: str,
    gateway,
    body: MaterialRequest,
    item_id: str,
    submission: dict,
    title: str,
):
    logger = logging.getLogger(__name__)
    req_proxy = types.SimpleNamespace(app=types.SimpleNamespace(state=app_state))
    evalflow_url = getattr(app_state.settings, "evaluation_web_url", None)
    try:
        materials, failures = [], []
        for identifier in dict.fromkeys(body.thread_ids):
            try:
                materials.append(
                    await snapshot(
                        gateway, actor, project_id, str(identifier), body.data_class
                    )
                )
            except (PlatformApiError, ValueError) as exc:
                failures.append(
                    {
                        "thread_id": str(identifier),
                        "reason": getattr(exc, "message", str(exc)),
                    }
                )
        if not materials:
            error_desc = "未成功采集到所选会话资料"
            if failures:
                error_desc += "：" + "; ".join(
                    f"{f.get('thread_id', '')}: {f.get('reason', '')}" for f in failures
                )
            notify_conversion_result(
                app_state.db_session_factory,
                actor.user_id,
                project_id,
                title,
                None,
                evalflow_url,
                error_message=error_desc,
            )
            return

        agents = {m["agent_id"] for m in materials}
        if len(agents) != 1 or None in agents:
            notify_conversion_result(
                app_state.db_session_factory,
                actor.user_id,
                project_id,
                title,
                None,
                evalflow_url,
                error_message="请选择同一个Agent的会话，且需有明确Agent关联。",
            )
            return

        receipt = {
            "status": "partial" if failures else "delivered",
            "materials": [
                {
                    key: m[key]
                    for key in (
                        "thread_id",
                        "title",
                        "content_hash",
                        "missing",
                        "environment",
                    )
                }
                for m in materials
            ],
            "failures": failures,
        }
        item = await forward(
            req_proxy,
            actor,
            project_id,
            "create",
            item_id,
            body.request_id,
            {
                "title": title,
                "description": "根据已选Agent会话整理评测题目与评分建议，保留来源，独立核对预期；用户确认后再发布和运行。",
                "agent_id": next(iter(agents)),
                "source_materials": materials,
                "authoring": True,
                "material_submission": {"scope": submission, "receipt": receipt},
                "data_class": body.data_class,
                "material_consent": body.material_consent,
                "synthetic_attestation": body.synthetic_attestation,
                "share_with_project_reviewers": True,
            },
        )
        await finish_conversion(req_proxy, actor, project_id, body, item, receipt)
        notify_conversion_result(
            app_state.db_session_factory,
            actor.user_id,
            project_id,
            title,
            item["id"],
            evalflow_url,
        )
        logger.info(
            "Successfully converted session materials async for item %s", item_id
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to process materials conversion in background: %s", exc
        )
        notify_conversion_result(
            app_state.db_session_factory,
            actor.user_id,
            project_id,
            title,
            None,
            evalflow_url,
            error_message=getattr(exc, "message", str(exc)),
        )


@router.post("/send")
async def send_materials(
    request: Request,
    body: MaterialRequest,
    actor: ActorContext = Depends(get_actor_context),
    gateway=Depends(get_runtime_gateway_service),
    background_tasks: BackgroundTasks = None,  # type: ignore[assignment]
    response: Response = None,  # type: ignore[assignment]
):
    project_id = _require_project_id(request)
    require_action(actor, project_id, "create")
    if body.auto_generate:
        require_action(actor, project_id, "grant")
        require_action(actor, project_id, "generate")
    item_id = str(
        uuid5(
            NAMESPACE_URL,
            "session-materials:"
            + project_id
            + ":"
            + actor.user_id
            + ":"
            + str(body.request_id),
        )
    )
    title = (
        prepare_business_material(body.title)[0]
        if body.data_class == "business"
        else body.title
    )
    submission = {
        "title": title,
        "thread_ids": sorted({str(t) for t in body.thread_ids}),
        "data_class": body.data_class,
        "auto_generate": body.auto_generate,
    }
    previous = await forward(
        request, actor, project_id, "read", item_id, body.request_id, {"optional": True}
    )
    if previous.get("id"):
        if previous.get("material_submission", {}).get("scope") != submission:
            from platform_api.core.errors import ConflictError

            raise ConflictError(
                code="evaluation_material_conflict",
                message="该提交编号已经用于其他资料，不能覆盖。",
            )
        receipt = previous["material_submission"]["receipt"]
        return {
            **await finish_conversion(
                request, actor, project_id, body, previous, receipt
            ),
            "reused": True,
        }
    if body.async_mode and background_tasks is not None:
        if response is not None:
            response.status_code = status.HTTP_202_ACCEPTED
        background_tasks.add_task(
            process_materials_background,
            app_state=request.app.state,
            actor=actor,
            project_id=project_id,
            gateway=gateway,
            body=body,
            item_id=item_id,
            submission=submission,
            title=title,
        )
        return {
            "status": "accepted",
            "message": "评测集转换任务已提交后台处理，完成后将通过系统通知告知。",
            "task_id": item_id,
            "item_id": item_id,
            "request_id": str(body.request_id),
            "title": title,
        }

    materials, failures = [], []
    for identifier in dict.fromkeys(body.thread_ids):
        try:
            materials.append(
                await snapshot(
                    gateway, actor, project_id, str(identifier), body.data_class
                )
            )
        except (PlatformApiError, ValueError) as exc:
            failures.append(
                {
                    "thread_id": str(identifier),
                    "reason": getattr(exc, "message", str(exc)),
                }
            )
    if not materials:
        return {"status": "failed", "failures": failures, "materials": []}
    agents = {m["agent_id"] for m in materials}
    if len(agents) != 1 or None in agents:
        return {
            "status": "failed",
            "failures": failures
            + [{"reason": "请选择同一个Agent的会话，且需有明确Agent关联。"}],
            "materials": [],
        }
    receipt = {
        "status": "partial" if failures else "delivered",
        "materials": [
            {
                key: m[key]
                for key in (
                    "thread_id",
                    "title",
                    "content_hash",
                    "missing",
                    "environment",
                )
            }
            for m in materials
        ],
        "failures": failures,
    }
    item = await forward(
        request,
        actor,
        project_id,
        "create",
        item_id,
        body.request_id,
        {
            "title": title,
            "description": "根据已选Agent会话整理评测题目与评分建议，保留来源，独立核对预期；用户确认后再发布和运行。",
            "agent_id": next(iter(agents)),
            "source_materials": materials,
            "authoring": True,
            "material_submission": {"scope": submission, "receipt": receipt},
            "data_class": body.data_class,
            "material_consent": body.material_consent,
            "synthetic_attestation": body.synthetic_attestation,
            "share_with_project_reviewers": True,
        },
    )
    return await finish_conversion(request, actor, project_id, body, item, receipt)


async def finish_conversion(request, actor, project_id, body, item, receipt):
    """Resume the same persisted conversion after a lost acknowledgement."""
    generation = "not_requested"
    error = None
    if body.auto_generate:
        from starlette.concurrency import run_in_threadpool

        from platform_api.modules.evaluation.workbench_grants import (
            GrantBody,
            create_grant,
        )

        grant_id = uuid5(NAMESPACE_URL, str(body.request_id) + ":materials-ai-grant")
        job_id = uuid5(NAMESPACE_URL, str(body.request_id) + ":materials-ai-draft")
        try:
            saved = await run_in_threadpool(
                create_grant,
                request.app.state.db_session_factory,
                actor,
                project_id,
                item,
                GrantBody(
                    grant_id=grant_id,
                    purpose="evaluation_assistance",
                    synthetic_attestation=body.synthetic_attestation,
                    material_consent=body.material_consent,
                ),
                request.app.state.settings.evaluation_assistant_model_route,
            )
            item = await forward(
                request,
                actor,
                project_id,
                "grant",
                item["id"],
                grant_id,
                {"grant_id": saved["grant_id"]},
            )
            item = await forward(
                request,
                actor,
                project_id,
                "generate",
                item["id"],
                job_id,
                {
                    "base_revision": 0,
                    "feedback": "根据收到的完整会话自动整理首版评测建议。保留业务轮次、明确口径、来源与环境缺失；"
                    "独立核对预期，不能把原回答直接当标准答案。优先生成可隔离重跑的代表性用例；"
                    "缺必要初态时改为历史回答评分并明确说明。只生成草稿，不发布、不运行。",
                },
            )
            generation = next(
                (
                    job["status"]
                    for job in item.get("assistant_jobs", [])
                    if job["id"] == str(job_id)
                ),
                "reserved",
            )
        except (PlatformApiError, ValueError, httpx.HTTPError):
            generation = "needs_retry"
            error = "会话资料已保存，AI整理启动回执尚未确认。请重试同一转换，或打开评测集查看；不会重新采集会话。"
    url = request.app.state.settings.evaluation_web_url
    return {
        **receipt,
        "item_id": item["id"],
        "generation_status": generation,
        "generation_error": error,
        "url": url.rstrip("/") + "/#/authoring/" + item["id"] if url else None,
    }
