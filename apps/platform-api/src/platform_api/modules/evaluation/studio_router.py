"""Control-plane HTTP routes for native evaluation studio and internal HMAC bridges."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from starlette.concurrency import run_in_threadpool

from platform_api.core.context.models import ActorContext
from platform_api.core.errors import BadRequestError, ForbiddenError
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.modules.evaluation import studio_service, targets
from platform_api.modules.evaluation.studio_schemas import (
    CaseImportRequest,
    CaseUpsert,
    ExpertThreadCreateRequest,
    ExpertTurnStreamRequest,
    HumanReviewCreate,
    MatrixCreate,
    PatrolCreate,
    PublishVersionRequest,
    ReadinessRequest,
    RunControlRequest,
    RunCreate,
    SandboxFlagRequest,
    SessionsToSuiteRequest,
    SuiteCreate,
)
from platform_api.modules.iam.application import (
    AuthorizationRequest,
    IamPolicyEngine,
    PermissionCode,
)
from platform_api.modules.identity.actors import load_user_actor
from platform_api.modules.runtime_catalog.application import RuntimeCatalogService
from platform_api.modules.runtime_catalog.infra import (
    SqlAlchemyRuntimeCatalogRepository,
)
from platform_api.modules.runtime_catalog.presentation.http import (
    get_runtime_catalog_service,
)
from platform_api.modules.runtime_gateway.application.service import (
    RuntimeGatewayService,
)
from platform_api.modules.runtime_gateway.presentation.http import (
    _require_project_id,
    _runtime_sse_response,
    build_runtime_gateway_service,
    get_runtime_gateway_service,
)

router = APIRouter(prefix="/api/evaluation", tags=["evaluation-studio"])


def _authorize_project(
    request: Request,
    actor: ActorContext,
    permission: str,
    *,
    project_id: str | None = None,
) -> str:
    pid = project_id or _require_project_id(request)
    IamPolicyEngine().require(
        actor=actor,
        authorization=AuthorizationRequest(permission=permission, project_id=pid),
    )
    return pid


def _verify_internal_hmac(request: Request, purpose: str, raw_body: bytes) -> None:
    secret = request.app.state.settings.runtime_delegation_secret
    stamp = request.headers.get("x-eval-time", "")
    signature = request.headers.get("x-eval-signature", "")
    try:
        timely = abs(time.time() - int(stamp)) <= 60
    except ValueError:
        timely = False
    message = b"\n".join([purpose.encode(), stamp.encode(), raw_body])
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    if not secret or not timely or not hmac.compare_digest(signature, expected):
        raise ForbiddenError(
            code="evaluation_internal_signature_invalid",
            message="Invalid evaluation internal signature",
        )


@router.get("/studio/suites")
def list_suites(
    request: Request,
    include_archived: bool = False,
    actor: ActorContext = Depends(get_actor_context),
) -> dict[str, Any]:
    pid = _authorize_project(request, actor, PermissionCode.PROJECT_EVALUATION_READ)
    return studio_service.list_suites(
        request.app.state.db_session_factory,
        project_id=pid,
        include_archived=include_archived,
    )


@router.post("/studio/suites", status_code=201)
def create_suite(
    request: Request,
    body: SuiteCreate,
    actor: ActorContext = Depends(get_actor_context),
) -> dict[str, Any]:
    pid = _authorize_project(request, actor, PermissionCode.PROJECT_EVALUATION_MANAGE)
    return studio_service.create_suite(
        request.app.state.db_session_factory,
        project_id=pid,
        actor_id=actor.user_id or "unknown",
        body=body,
    )


@router.delete("/studio/suites/{suite_id}")
def delete_suite(
    request: Request,
    suite_id: UUID,
    actor: ActorContext = Depends(get_actor_context),
) -> dict[str, Any]:
    pid = _authorize_project(request, actor, PermissionCode.PROJECT_EVALUATION_MANAGE)
    return studio_service.archive_suite(
        request.app.state.db_session_factory,
        project_id=pid,
        suite_id=str(suite_id),
    )


@router.post("/studio/suites/from-sessions", status_code=201)
async def create_suite_from_sessions(
    request: Request,
    body: SessionsToSuiteRequest,
    actor: ActorContext = Depends(get_actor_context),
    gateway: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> dict[str, Any]:
    pid = _authorize_project(request, actor, PermissionCode.PROJECT_EVALUATION_MANAGE)
    source_pid = body.source_project_id or pid
    suite = await run_in_threadpool(
        studio_service.create_suite,
        request.app.state.db_session_factory,
        project_id=pid,
        actor_id=actor.user_id or "unknown",
        body=SuiteCreate(
            name=body.name,
            description=body.description or f"由 {len(body.thread_ids)} 条会话脱敏沉淀",
            suite_type=body.suite_type,
            source_project_id=source_pid,
            default_graph_id=body.default_graph_id,
        ),
    )
    imported_cases: list[CaseUpsert] = []
    for idx, raw_tid in enumerate(body.thread_ids, start=1):
        question = ""
        expected_answer = ""
        try:
            state = await gateway.get_thread_state(
                actor=actor,
                project_id=source_pid,
                thread_id=raw_tid,
                params={},
            )
            messages = (
                state.get("values", {}).get("messages", [])
                if isinstance(state, dict)
                else []
            )
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                role = str(msg.get("role") or msg.get("type") or "")
                content = msg.get("content")
                text_val = (
                    content
                    if isinstance(content, str)
                    else json.dumps(content, ensure_ascii=False)
                    if content is not None
                    else ""
                )
                if not question and role in {"human", "user"} and text_val.strip():
                    question = text_val.strip()[:2000]
                elif role in {"ai", "assistant"} and text_val.strip():
                    expected_answer = text_val.strip()[:4000]
        except Exception:
            question = f"基于会话 {raw_tid[:8]} 的回归问题"
        imported_cases.append(
            CaseUpsert(
                case_key=f"session_{idx:03d}_{raw_tid[:6]}",
                split="dev",
                turns=[
                    {
                        "role": "user",
                        "content": question or f"会话 {raw_tid[:8]} 测试指令",
                    }
                ],
                expectations={"expected_answer": expected_answer}
                if expected_answer
                else {},
                metrics=[{"name": "completion"}],
                metadata={"source_thread_id": raw_tid, "source_project_id": source_pid},
            )
        )
    if imported_cases:
        await run_in_threadpool(
            studio_service.import_cases,
            request.app.state.db_session_factory,
            project_id=pid,
            suite_id=suite["id"],
            items=imported_cases,
        )
    return await run_in_threadpool(
        studio_service.get_suite_detail,
        request.app.state.db_session_factory,
        project_id=pid,
        suite_id=suite["id"],
    )


@router.post("/studio/suites/{suite_id}/cases/import")
def import_suite_cases(
    request: Request,
    suite_id: UUID,
    body: CaseImportRequest,
    actor: ActorContext = Depends(get_actor_context),
) -> dict[str, Any]:
    pid = _authorize_project(request, actor, PermissionCode.PROJECT_EVALUATION_MANAGE)
    return studio_service.import_cases(
        request.app.state.db_session_factory,
        project_id=pid,
        suite_id=str(suite_id),
        items=body.items,
    )


@router.get("/studio/suites/{suite_id}")
def get_suite(
    request: Request,
    suite_id: UUID,
    actor: ActorContext = Depends(get_actor_context),
) -> dict[str, Any]:
    pid = _authorize_project(request, actor, PermissionCode.PROJECT_EVALUATION_READ)
    return studio_service.get_suite_detail(
        request.app.state.db_session_factory,
        project_id=pid,
        suite_id=str(suite_id),
    )


@router.put("/studio/suites/{suite_id}/cases")
def upsert_case(
    request: Request,
    suite_id: UUID,
    body: CaseUpsert,
    actor: ActorContext = Depends(get_actor_context),
) -> dict[str, Any]:
    pid = _authorize_project(request, actor, PermissionCode.PROJECT_EVALUATION_MANAGE)
    return studio_service.upsert_case(
        request.app.state.db_session_factory,
        project_id=pid,
        suite_id=str(suite_id),
        body=body,
    )


@router.delete("/studio/suites/{suite_id}/cases/{case_key}")
def delete_case(
    request: Request,
    suite_id: UUID,
    case_key: str,
    actor: ActorContext = Depends(get_actor_context),
) -> dict[str, Any]:
    pid = _authorize_project(request, actor, PermissionCode.PROJECT_EVALUATION_MANAGE)
    return studio_service.delete_case(
        request.app.state.db_session_factory,
        project_id=pid,
        suite_id=str(suite_id),
        case_key=case_key,
    )


@router.post("/studio/suites/{suite_id}/publish", status_code=201)
def publish_suite(
    request: Request,
    suite_id: UUID,
    _body: PublishVersionRequest,
    actor: ActorContext = Depends(get_actor_context),
) -> dict[str, Any]:
    pid = _authorize_project(request, actor, PermissionCode.PROJECT_EVALUATION_MANAGE)
    return studio_service.publish_suite_version(
        request.app.state.db_session_factory,
        project_id=pid,
        suite_id=str(suite_id),
        actor_id=actor.user_id or "unknown",
    )


@router.post("/studio/readiness")
async def readiness_check(
    request: Request,
    body: ReadinessRequest,
    actor: ActorContext = Depends(get_actor_context),
    gateway: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> dict[str, Any]:
    pid = _authorize_project(request, actor, PermissionCode.PROJECT_EVALUATION_EXECUTE)
    detail = await run_in_threadpool(
        studio_service.get_suite_detail,
        request.app.state.db_session_factory,
        project_id=pid,
        suite_id=str(body.suite_id),
    )
    return await targets.check_readiness(
        gateway,
        request.app.state.db_session_factory,
        actor=actor,
        target_project_id=body.target_project_id,
        agent_id=body.agent_id,
        model_id=body.model_id,
        judge_model_id=body.judge_model_id,
        embedding_model_id=body.embedding_model_id,
        suite_cases=detail["cases"],
        eval_project_id=request.app.state.settings.evaluation_project_id,
    )


@router.post("/studio/runs", status_code=201)
async def create_run(
    request: Request,
    body: RunCreate,
    actor: ActorContext = Depends(get_actor_context),
    gateway: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> dict[str, Any]:
    pid = _authorize_project(request, actor, PermissionCode.PROJECT_EVALUATION_EXECUTE)
    detail = await run_in_threadpool(
        studio_service.get_suite_detail,
        request.app.state.db_session_factory,
        project_id=pid,
        suite_id=str(body.suite_id),
    )
    readiness = await targets.check_readiness(
        gateway,
        request.app.state.db_session_factory,
        actor=actor,
        target_project_id=body.target_project_id,
        agent_id=body.agent_id,
        model_id=body.model_id,
        judge_model_id=body.judge_model_id,
        embedding_model_id=body.embedding_model_id,
        suite_cases=detail["cases"],
        eval_project_id=request.app.state.settings.evaluation_project_id,
    )
    if not readiness["is_sandbox"] and not body.confirm_non_sandbox:
        raise BadRequestError(
            code="eval_non_sandbox_confirmation_required",
            message=readiness["sandbox_warning"] or "请确认在非专用靶场项目执行评测。",
        )
    if readiness["missing_models"]:
        raise BadRequestError(
            code="eval_model_unavailable",
            message="所选裁判或向量模型不可用。",
        )
    incompatible_keys = {c["case_key"] for c in readiness["incompatible_cases"]}
    if incompatible_keys and not body.skip_incompatible:
        raise BadRequestError(
            code="eval_graph_capability_mismatch",
            message="存在与目标Agent能力不兼容的用例，请确认跳过或切换Agent。",
        )
    snap = await targets.snapshot(
        gateway,
        actor,
        body.target_project_id,
        targets.TargetRequest(agent_id=body.agent_id, model_id=body.model_id),
    )
    return await run_in_threadpool(
        studio_service.create_run_record,
        request.app.state.db_session_factory,
        owner_project_id=pid,
        actor_id=actor.user_id or "unknown",
        body=body,
        target_snapshot=snap,
        incompatible_keys=incompatible_keys if body.skip_incompatible else None,
    )


@router.post("/studio/runs/matrix", status_code=201)
async def create_matrix_runs(
    request: Request,
    body: MatrixCreate,
    actor: ActorContext = Depends(get_actor_context),
    gateway: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> dict[str, Any]:
    pid = _authorize_project(request, actor, PermissionCode.PROJECT_EVALUATION_EXECUTE)
    group_id = str(uuid4())
    runs = []
    for variant in body.variants:
        single = RunCreate(
            suite_id=body.suite_id,
            version_id=body.version_id,
            target_project_id=body.target_project_id,
            agent_id=variant.agent_id,
            model_id=variant.model_id,
            judge_model_id=body.judge_model_id,
            embedding_model_id=body.embedding_model_id,
            mode="matrix",
            concurrency=body.concurrency,
            repeat_k=body.repeat_k,
            confirm_non_sandbox=body.confirm_non_sandbox,
            skip_incompatible=True,
        )
        snap = await targets.snapshot(
            gateway,
            actor,
            body.target_project_id,
            targets.TargetRequest(agent_id=variant.agent_id, model_id=variant.model_id),
        )
        run = await run_in_threadpool(
            studio_service.create_run_record,
            request.app.state.db_session_factory,
            owner_project_id=pid,
            actor_id=actor.user_id or "unknown",
            body=single,
            target_snapshot=snap,
            matrix_group_id=group_id,
        )
        runs.append(run)
    return {"matrix_group_id": group_id, "runs": runs}


@router.get("/studio/runs")
def list_runs(
    request: Request,
    suite_id: UUID | None = None,
    actor: ActorContext = Depends(get_actor_context),
) -> dict[str, Any]:
    pid = _authorize_project(request, actor, PermissionCode.PROJECT_EVALUATION_READ)
    return studio_service.list_runs(
        request.app.state.db_session_factory,
        project_id=pid,
        suite_id=str(suite_id) if suite_id else None,
    )


@router.get("/studio/runs/compare")
def compare_runs(
    request: Request,
    baseline_id: UUID,
    candidate_id: UUID,
    actor: ActorContext = Depends(get_actor_context),
) -> dict[str, Any]:
    pid = _authorize_project(request, actor, PermissionCode.PROJECT_EVALUATION_READ)
    return studio_service.compare_runs(
        request.app.state.db_session_factory,
        project_id=pid,
        baseline_id=str(baseline_id),
        candidate_id=str(candidate_id),
    )


@router.get("/studio/runs/{run_id}")
def get_run(
    request: Request,
    run_id: UUID,
    actor: ActorContext = Depends(get_actor_context),
) -> dict[str, Any]:
    pid = _authorize_project(request, actor, PermissionCode.PROJECT_EVALUATION_READ)
    return studio_service.get_run_detail(
        request.app.state.db_session_factory,
        project_id=pid,
        run_id=str(run_id),
    )


@router.post("/studio/runs/{run_id}/control")
def control_run(
    request: Request,
    run_id: UUID,
    body: RunControlRequest,
    actor: ActorContext = Depends(get_actor_context),
) -> dict[str, Any]:
    pid = _authorize_project(request, actor, PermissionCode.PROJECT_EVALUATION_EXECUTE)
    return studio_service.control_run(
        request.app.state.db_session_factory,
        project_id=pid,
        run_id=str(run_id),
        action=body.action,
    )


@router.post("/studio/run-cases/{run_case_id}/review", status_code=201)
def review_run_case(
    request: Request,
    run_case_id: UUID,
    body: HumanReviewCreate,
    actor: ActorContext = Depends(get_actor_context),
) -> dict[str, Any]:
    pid = _authorize_project(request, actor, PermissionCode.PROJECT_EVALUATION_REVIEW)
    return studio_service.submit_human_review(
        request.app.state.db_session_factory,
        project_id=pid,
        run_case_id=str(run_case_id),
        actor_id=actor.user_id or "unknown",
        body=body,
    )


@router.put("/studio/sandbox")
def set_sandbox(
    request: Request,
    body: SandboxFlagRequest,
    actor: ActorContext = Depends(get_actor_context),
) -> dict[str, Any]:
    pid = _authorize_project(request, actor, PermissionCode.PROJECT_EVALUATION_MANAGE)
    return studio_service.set_sandbox_flag(
        request.app.state.db_session_factory,
        project_id=pid,
        actor_id=actor.user_id or "unknown",
        is_sandbox=body.is_sandbox,
    )


@router.get("/studio/patrols")
def list_patrols(
    request: Request,
    actor: ActorContext = Depends(get_actor_context),
) -> dict[str, Any]:
    pid = _authorize_project(request, actor, PermissionCode.PROJECT_EVALUATION_READ)
    return studio_service.list_patrols(
        request.app.state.db_session_factory, project_id=pid
    )


@router.post("/studio/patrols", status_code=201)
def create_patrol(
    request: Request,
    body: PatrolCreate,
    actor: ActorContext = Depends(get_actor_context),
) -> dict[str, Any]:
    pid = _authorize_project(request, actor, PermissionCode.PROJECT_EVALUATION_MANAGE)
    return studio_service.create_patrol(
        request.app.state.db_session_factory,
        project_id=pid,
        actor_id=actor.user_id or "unknown",
        body=body,
    )


@router.post("/internal/judge-model-config")
async def internal_judge_model_config(
    request: Request,
    catalog: RuntimeCatalogService = Depends(get_runtime_catalog_service),
) -> dict[str, Any]:
    raw = await request.body()
    _verify_internal_hmac(request, "judge-model-config", raw)
    payload = json.loads(raw or b"{}")
    project_id = str(payload.get("project_id") or "")
    model_id = str(payload.get("model_id") or "")
    if not project_id or not model_id:
        raise BadRequestError(
            code="eval_model_params_required",
            message="project_id and model_id required",
        )

    def _resolve():
        with request.app.state.db_session_factory() as session:
            repo = SqlAlchemyRuntimeCatalogRepository(session)
            return catalog._model_connection(repo, model_id, project_id)

    return await run_in_threadpool(_resolve)


@router.post("/internal/copilot-context")
async def internal_copilot_context(request: Request) -> dict[str, Any]:
    raw = await request.body()
    _verify_internal_hmac(request, "copilot-context", raw)
    payload = json.loads(raw or b"{}")
    return await run_in_threadpool(
        studio_service.get_suite_detail,
        request.app.state.db_session_factory,
        project_id=str(payload["project_id"]),
        suite_id=str(payload["suite_id"]),
    )


@router.post("/internal/diagnosis-evidence")
async def internal_diagnosis_evidence(request: Request) -> dict[str, Any]:
    raw = await request.body()
    _verify_internal_hmac(request, "diagnosis-evidence", raw)
    payload = json.loads(raw or b"{}")
    return await run_in_threadpool(
        studio_service.read_diagnosis_evidence_slice,
        request.app.state.db_session_factory,
        project_id=str(payload["project_id"]),
        run_id=str(payload["run_id"]),
        ref=str(payload.get("ref") or "overview"),
        offset=int(payload.get("offset") or 0),
    )


@router.post("/studio/experts/threads", status_code=201)
async def create_expert_thread(
    request: Request,
    body: ExpertThreadCreateRequest,
    actor: ActorContext = Depends(get_actor_context),
    gateway: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    perm = (
        PermissionCode.PROJECT_EVALUATION_MANAGE
        if body.graph_id == "eval_copilot"
        else PermissionCode.PROJECT_EVALUATION_READ
    )
    pid = _authorize_project(request, actor, perm)
    return await gateway.create_thread(
        actor=actor,
        project_id=pid,
        payload={
            "graph_id": body.graph_id,
            "metadata": {
                "graph_id": body.graph_id,
                "title": body.title or f"{body.graph_id} 会话",
                "eval_expert": True,
            },
        },
    )


@router.post("/studio/experts/threads/{thread_id}/stream")
async def stream_expert_turn(
    request: Request,
    thread_id: str,
    body: ExpertTurnStreamRequest,
    actor: ActorContext = Depends(get_actor_context),
    gateway: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    perm = (
        PermissionCode.PROJECT_EVALUATION_MANAGE
        if body.graph_id == "eval_copilot"
        else PermissionCode.PROJECT_EVALUATION_READ
    )
    pid = _authorize_project(request, actor, perm)
    resolved_model_id = body.model_id
    if not resolved_model_id:

        def _pick_default_model():
            from sqlalchemy import select

            from platform_api.modules.runtime_catalog.infra.sqlalchemy.models import (
                RuntimeCatalogModelRecord,
            )

            with request.app.state.db_session_factory() as session:
                rows = session.scalars(
                    select(RuntimeCatalogModelRecord).where(
                        RuntimeCatalogModelRecord.enabled.is_(True)
                    )
                ).all()
            safe = [r for r in rows if "broken" not in (r.model_name or "").lower()]
            pick = next(
                (
                    r
                    for r in safe
                    if (r.provider or "").lower() == "xiaok"
                    and "deepseek" in (r.model_name or "").lower()
                ),
                None,
            ) or (safe[0] if safe else None)
            return str(pick.id) if pick else None

        resolved_model_id = await run_in_threadpool(_pick_default_model)

    payload: dict[str, Any] = {
        "assistant_id": body.graph_id,
        "input": {"messages": [{"role": "user", "content": body.content}]},
        "stream_mode": ["messages", "values"],
    }
    if resolved_model_id:
        payload["context"] = {"model_id": resolved_model_id}
    stream = await gateway.stream_thread_run(
        actor=actor,
        project_id=pid,
        thread_id=thread_id,
        payload=payload,
        idempotency_key=request.headers.get("Idempotency-Key") or str(uuid4()),
    )
    return _runtime_sse_response(
        request, stream, thread_id=thread_id, stream_kind="run", protocol=False
    )


@router.post("/internal/execute-turn")
async def internal_execute_turn(request: Request) -> Any:
    raw = await request.body()
    _verify_internal_hmac(request, "execute-turn", raw)
    payload = json.loads(raw or b"{}")
    run_id = str(payload.get("run_id") or "")
    content = str(payload.get("content") or "")
    thread_id = payload.get("thread_id")
    if not run_id or not content:
        raise BadRequestError(
            code="eval_execute_turn_invalid", message="run_id and content are required"
        )
    run_info = await run_in_threadpool(
        studio_service.get_run_execution_target,
        request.app.state.db_session_factory,
        run_id=run_id,
    )
    target_pid = str(run_info["target_project_id"])
    actor = await run_in_threadpool(
        load_user_actor,
        session_factory=request.app.state.db_session_factory,
        user_id=str(run_info["created_by"]),
        project_id=target_pid,
    )
    if actor is None:
        raise ForbiddenError(
            code="eval_actor_unavailable", message="评测创建者已无目标项目运行权限。"
        )
    gateway = build_runtime_gateway_service(request, actor, target_pid)
    resolved_thread_id = str(thread_id) if thread_id else ""
    if not resolved_thread_id:
        created = await gateway.create_thread(
            actor=actor,
            project_id=target_pid,
            payload={
                "graph_id": run_info["target_graph_id"],
                "metadata": {
                    "graph_id": run_info["target_graph_id"],
                    "eval_run_id": run_id,
                },
            },
        )
        resolved_thread_id = str(created["thread_id"])
    run_payload: dict[str, Any] = {
        "assistant_id": run_info["target_graph_id"],
        "input": {"messages": [{"role": "user", "content": content}]},
        "context": {"model_id": str(run_info["target_model_id"])},
        "stream_mode": ["messages", "values"],
    }
    stream = await gateway.stream_thread_run(
        actor=actor,
        project_id=target_pid,
        thread_id=resolved_thread_id,
        payload=run_payload,
        idempotency_key=f"eval:{run_id}:{uuid4()}",
    )
    return _runtime_sse_response(
        request,
        stream,
        thread_id=resolved_thread_id,
        stream_kind="run",
        protocol=False,
        extra_headers={"x-eval-thread-id": resolved_thread_id},
    )


@router.post("/internal/thread-usage")
async def internal_thread_usage(request: Request) -> dict[str, Any]:
    raw = await request.body()
    _verify_internal_hmac(request, "thread-usage", raw)
    payload = json.loads(raw or b"{}")
    run_id = str(payload.get("run_id") or "")
    thread_id = str(payload.get("thread_id") or "")
    if not run_id or not thread_id:
        raise BadRequestError(
            code="eval_thread_usage_invalid",
            message="run_id and thread_id are required",
        )
    run_info = await run_in_threadpool(
        studio_service.get_run_execution_target,
        request.app.state.db_session_factory,
        run_id=run_id,
    )
    target_pid = str(run_info["target_project_id"])
    actor = await run_in_threadpool(
        load_user_actor,
        session_factory=request.app.state.db_session_factory,
        user_id=str(run_info["created_by"]),
        project_id=target_pid,
    )
    if actor is None:
        return {"availability": "unavailable", "tokens": {}, "cost": {}}
    gateway = build_runtime_gateway_service(request, actor, target_pid)
    try:
        return await gateway.get_thread_usage(
            actor=actor,
            project_id=target_pid,
            thread_id=thread_id,
            request_id=f"eval-usage:{run_id}:{thread_id}",
        )
    except Exception:  # noqa: BLE001
        return {"availability": "unavailable", "tokens": {}, "cost": {}}
