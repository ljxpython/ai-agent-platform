"""Control-plane HTTP routes for native evaluation studio and internal HMAC bridges."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from starlette.concurrency import run_in_threadpool

from platform_api.core.context.models import ActorContext
from platform_api.core.errors import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    PlatformApiError,
)
from platform_api.entrypoints.http.dependencies import get_actor_context
from platform_api.modules.evaluation import studio_service, targets
from platform_api.modules.evaluation.studio_schemas import (
    CaseImportRequest,
    CaseUpsert,
    ExpertRespondRequest,
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
    detail = await run_in_threadpool(
        studio_service.get_suite_detail,
        request.app.state.db_session_factory,
        project_id=str(payload["project_id"]),
        suite_id=str(payload["suite_id"]),
    )
    filter_keys = set(str(k) for k in (payload.get("case_keys") or []) if k)
    if filter_keys:
        detail["cases"] = [
            c for c in detail["cases"] if c.get("case_key") in filter_keys
        ]
    return detail


@router.post("/internal/copilot-suites")
async def internal_copilot_suites(request: Request) -> dict[str, Any]:
    raw = await request.body()
    _verify_internal_hmac(request, "copilot-suites", raw)
    payload = json.loads(raw or b"{}")
    return await run_in_threadpool(
        studio_service.copilot_list_suites,
        request.app.state.db_session_factory,
        project_id=str(payload["project_id"]),
    )


@router.post("/internal/copilot-capabilities")
async def internal_copilot_capabilities(request: Request) -> dict[str, Any]:
    raw = await request.body()
    _verify_internal_hmac(request, "copilot-capabilities", raw)
    payload = json.loads(raw or b"{}")
    return await run_in_threadpool(
        studio_service.copilot_list_capabilities,
        request.app.state.db_session_factory,
        project_id=str(payload["project_id"]),
    )


@router.post("/internal/copilot-failures")
async def internal_copilot_failures(request: Request) -> dict[str, Any]:
    raw = await request.body()
    _verify_internal_hmac(request, "copilot-failures", raw)
    payload = json.loads(raw or b"{}")
    return await run_in_threadpool(
        studio_service.copilot_list_failures,
        request.app.state.db_session_factory,
        project_id=str(payload["project_id"]),
        suite_id=payload.get("suite_id"),
        run_id=payload.get("run_id"),
        limit=min(50, max(1, int(payload.get("limit") or 20))),
    )


@router.post("/internal/copilot-save-cases")
async def internal_copilot_save_cases(request: Request) -> dict[str, Any]:
    raw = await request.body()
    _verify_internal_hmac(request, "copilot-save-cases", raw)
    payload = json.loads(raw or b"{}")
    return await run_in_threadpool(
        studio_service.copilot_save_cases,
        request.app.state.db_session_factory,
        project_id=str(payload["project_id"]),
        suite_id=str(payload["suite_id"]),
        items=list(payload.get("items") or []),
        mode=str(payload.get("mode") or "create_only"),
    )


@router.post("/internal/copilot-trial-run")
async def internal_copilot_trial_run(
    request: Request,
) -> dict[str, Any]:
    raw = await request.body()
    _verify_internal_hmac(request, "copilot-trial-run", raw)
    payload = json.loads(raw or b"{}")
    project_id = str(payload["project_id"])
    actor_id = str(payload.get("actor_id") or "copilot")
    suite_id = str(payload["suite_id"])
    case_keys = [str(k) for k in (payload.get("case_keys") or []) if k]
    if not case_keys or len(case_keys) > 5:
        raise BadRequestError(
            code="copilot_trial_case_limit",
            message="单次授权试跑必须指定 1 到 5 道题目。",
        )
    prep = await run_in_threadpool(
        studio_service.copilot_prepare_trial_version,
        request.app.state.db_session_factory,
        project_id=project_id,
        suite_id=suite_id,
        actor_id=actor_id,
        case_keys=case_keys,
        target_project_id=payload.get("target_project_id"),
        agent_id=payload.get("agent_id"),
        model_id=payload.get("model_id"),
        judge_model_id=payload.get("judge_model_id"),
    )
    actor = await run_in_threadpool(
        load_user_actor,
        session_factory=request.app.state.db_session_factory,
        user_id=actor_id,
        project_id=prep["target_project_id"],
    )
    if actor is None:
        raise ForbiddenError(code="copilot_actor_not_found", message="操作用户不存在。")
    gateway = build_runtime_gateway_service(request, actor, prep["target_project_id"])
    snap = await targets.snapshot(
        gateway,
        actor,
        prep["target_project_id"],
        targets.TargetRequest(
            agent_id=UUID(prep["agent_id"]),
            model_id=UUID(prep["model_id"]),
        ),
    )
    if payload.get("copilot_thread_id"):
        snap["copilot_thread_id"] = str(payload["copilot_thread_id"])
    snap["copilot_trial"] = True
    run_body = RunCreate(
        suite_id=UUID(suite_id),
        version_id=UUID(prep["version"]["id"]),
        target_project_id=prep["target_project_id"],
        agent_id=UUID(prep["agent_id"]),
        model_id=UUID(prep["model_id"]),
        judge_model_id=UUID(prep["judge_model_id"]),
        mode="regression",
        concurrency=1,
        repeat_k=1,
        confirm_non_sandbox=True,
        skip_incompatible=True,
        case_keys=case_keys,
    )
    return await run_in_threadpool(
        studio_service.create_run_record,
        request.app.state.db_session_factory,
        owner_project_id=project_id,
        actor_id=actor_id,
        body=run_body,
        target_snapshot=snap,
    )


@router.post("/internal/copilot-run-status")
async def internal_copilot_run_status(request: Request) -> dict[str, Any]:
    raw = await request.body()
    _verify_internal_hmac(request, "copilot-run-status", raw)
    payload = json.loads(raw or b"{}")
    return await run_in_threadpool(
        studio_service.copilot_run_status,
        request.app.state.db_session_factory,
        project_id=str(payload["project_id"]),
        run_id=str(payload["run_id"]),
        case_key=payload.get("case_key"),
    )


@router.post("/internal/copilot-control-run")
async def internal_copilot_control_run(request: Request) -> dict[str, Any]:
    raw = await request.body()
    _verify_internal_hmac(request, "copilot-control-run", raw)
    payload = json.loads(raw or b"{}")
    action = str(payload.get("action") or "cancel")
    if action not in {"cancel", "pause"}:
        raise BadRequestError(
            code="copilot_control_action_invalid",
            message="仅支持 cancel 或 pause 操作。",
        )
    return await run_in_threadpool(
        studio_service.copilot_control_run,
        request.app.state.db_session_factory,
        project_id=str(payload["project_id"]),
        run_id=str(payload["run_id"]),
        action=action,
        copilot_thread_id=payload.get("copilot_thread_id"),
        require_own=bool(payload.get("require_own", False)),
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


@router.get("/studio/experts/threads")
async def list_expert_threads(
    request: Request,
    graph_id: Literal["eval_copilot", "eval_diagnosis"] = "eval_copilot",
    ref_id: str | None = None,
    limit: int = 20,
    actor: ActorContext = Depends(get_actor_context),
    gateway: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> dict[str, Any]:
    perm = (
        PermissionCode.PROJECT_EVALUATION_MANAGE
        if graph_id == "eval_copilot"
        else PermissionCode.PROJECT_EVALUATION_READ
    )
    pid = _authorize_project(request, actor, perm)
    capped = max(1, min(limit, 50))
    rows = await gateway.search_threads(
        actor=actor,
        project_id=pid,
        payload={
            "limit": capped,
            "offset": 0,
            "sort_by": "updated_at",
            "sort_order": "desc",
            "metadata": {"graph_id": graph_id, "eval_expert": True},
            "select": ["thread_id", "metadata", "status", "created_at", "updated_at"],
        },
    )
    items = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        row_ref = meta.get("ref_id")
        if ref_id and row_ref and str(row_ref) != str(ref_id):
            continue
        items.append(
            {
                "thread_id": str(row.get("thread_id") or ""),
                "title": str(meta.get("title") or f"{graph_id} 会话"),
                "ref_id": str(row_ref) if row_ref else None,
                "status": str(row.get("status") or "idle"),
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
            }
        )
    return {"items": items}


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
    meta: dict[str, Any] = {
        "graph_id": body.graph_id,
        "title": body.title or f"{body.graph_id} 会话",
        "eval_expert": True,
    }
    if body.ref_id:
        meta["ref_id"] = body.ref_id
    return await gateway.create_thread(
        actor=actor,
        project_id=pid,
        payload={
            "graph_id": body.graph_id,
            "metadata": meta,
        },
    )


def _extract_expert_message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for blk in content:
            if (
                isinstance(blk, dict)
                and blk.get("type") == "text"
                and isinstance(blk.get("text"), str)
            ):
                parts.append(blk["text"])
        return "".join(parts)
    return ""


def _serialize_expert_messages(raw_messages: Any) -> list[dict[str, str]]:
    if not isinstance(raw_messages, list):
        return []
    out: list[dict[str, str]] = []
    for idx, msg in enumerate(raw_messages):
        if not isinstance(msg, dict):
            continue
        raw_role = str(msg.get("role") or msg.get("type") or "").lower()
        if raw_role in {"human", "user"}:
            role = "user"
        elif raw_role in {"ai", "assistant"}:
            role = "assistant"
        else:
            continue
        text = _extract_expert_message_text(msg.get("content")).strip()
        if not text:
            continue
        if role == "user":
            # 去掉自动注入的上下文关联与附件提示头，还原用户原始输入展示
            cleaned_lines = [
                line
                for line in text.splitlines()
                if not line.startswith("[上下文关联ID:")
                and not line.startswith("[已挂载本轮参考资料")
                and not line.startswith("- ")
            ]
            text = "\n".join(cleaned_lines).strip() or text
        out.append(
            {
                "id": str(msg.get("id") or f"hist-{idx}"),
                "role": role,
                "content": text,
            }
        )
    return out


async def _load_expert_interrupts(
    gateway: RuntimeGatewayService,
    *,
    actor: ActorContext,
    project_id: str,
    thread_id: str,
) -> tuple[str | None, Any, list[dict[str, str]]]:
    state = await gateway.get_thread_state(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        params={"subgraphs": False},
    )
    status = state.get("status") if isinstance(state, dict) else None
    values = state.get("values") if isinstance(state, dict) else {}
    messages = _serialize_expert_messages(
        values.get("messages") if isinstance(values, dict) else []
    )
    raw_ints: Any = state.get("interrupts") if isinstance(state, dict) else None
    if not raw_ints and isinstance(state, dict):
        task_ints: list[Any] = []
        for task in state.get("tasks") or []:
            if isinstance(task, dict) and task.get("interrupts"):
                task_ints.extend(task["interrupts"])
        if task_ints:
            raw_ints = task_ints
    if not raw_ints:
        try:
            thread_row = await gateway.get_thread(
                actor=actor, project_id=project_id, thread_id=thread_id
            )
            if isinstance(thread_row, dict):
                status = status or thread_row.get("status")
                if thread_row.get("interrupts"):
                    raw_ints = thread_row.get("interrupts")
        except Exception:  # noqa: BLE001
            pass
    return status, raw_ints or [], messages


@router.get("/studio/experts/threads/{thread_id}/state")
async def get_expert_thread_state(
    request: Request,
    thread_id: str,
    actor: ActorContext = Depends(get_actor_context),
    gateway: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> dict[str, Any]:
    pid = _authorize_project(request, actor, PermissionCode.PROJECT_EVALUATION_READ)
    status, interrupts, messages = await _load_expert_interrupts(
        gateway, actor=actor, project_id=pid, thread_id=thread_id
    )
    return {
        "thread_id": thread_id,
        "status": status,
        "interrupts": interrupts,
        "messages": messages,
    }


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
    try:
        _status, pending_ints, _msgs = await _load_expert_interrupts(
            gateway, actor=actor, project_id=pid, thread_id=thread_id
        )
        if pending_ints:
            raise ConflictError(
                code="expert_interrupt_pending",
                message="当前会话存在待处理的人工授权确认，请先点击「允许执行」或「拒绝」。",
            )
    except ConflictError:
        raise
    except Exception:  # noqa: BLE001
        pass
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
            pick = (
                next(
                    (
                        r
                        for r in safe
                        if (r.provider or "").lower() == "chickener"
                        and "deepseek" in (r.model_name or "").lower()
                    ),
                    None,
                )
                or next(
                    (
                        r
                        for r in safe
                        if (r.provider or "").lower() == "xiaok"
                        and "deepseek" in (r.model_name or "").lower()
                    ),
                    None,
                )
                or (safe[0] if safe else None)
            )
            return str(pick.id) if pick else None

        resolved_model_id = await run_in_threadpool(_pick_default_model)

    payload: dict[str, Any] = {
        "assistant_id": body.graph_id,
        "input": {"messages": [{"role": "user", "content": body.content}]},
        "stream_mode": ["messages", "values", "updates"],
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


@router.post("/studio/experts/threads/{thread_id}/respond")
async def respond_expert_interrupt(
    request: Request,
    thread_id: str,
    body: ExpertRespondRequest,
    actor: ActorContext = Depends(get_actor_context),
    gateway: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> Any:
    perm = (
        PermissionCode.PROJECT_EVALUATION_MANAGE
        if body.graph_id == "eval_copilot"
        else PermissionCode.PROJECT_EVALUATION_READ
    )
    pid = _authorize_project(request, actor, perm)
    idem_key = request.headers.get("Idempotency-Key") or str(uuid4())
    resume_map = (
        body.command.get("resume")
        if isinstance(body.command, dict) and "resume" in body.command
        else body.command
    )
    resumed = await gateway.send_thread_command(
        actor=actor,
        project_id=pid,
        thread_id=thread_id,
        payload={
            "id": 0,
            "method": "input.respond",
            "params": {
                "resume": resume_map,
                "assistant_id": body.graph_id,
            },
        },
        idempotency_key=idem_key,
    )
    resumed_run_id = str((resumed.get("result") or {}).get("run_id") or "")
    stream = await gateway.join_thread_run_stream(
        actor=actor,
        project_id=pid,
        thread_id=thread_id,
        run_id=resumed_run_id,
        params={
            "stream_mode": ["messages", "values", "updates"],
            "stream_resumable": True,
        },
    )
    return _runtime_sse_response(
        request, stream, thread_id=thread_id, stream_kind="run", protocol=False
    )


@router.post("/studio/experts/threads/{thread_id}/upload")
async def upload_expert_material(
    request: Request,
    thread_id: str,
    file_name: str = "material.txt",
    actor: ActorContext = Depends(get_actor_context),
    gateway: RuntimeGatewayService = Depends(get_runtime_gateway_service),
) -> dict[str, Any]:
    pid = _authorize_project(request, actor, PermissionCode.PROJECT_EVALUATION_MANAGE)
    data = await request.body()
    if not data:
        raise BadRequestError(
            code="eval_upload_empty", message="上传的参考资料不能为空。"
        )
    if len(data) > 10 * 1024 * 1024:
        raise BadRequestError(
            code="eval_upload_too_large", message="单份参考资料不能超过 10MB。"
        )
    digest = hashlib.sha256(data).hexdigest()
    safe_name = (file_name or "material.txt").strip() or "material.txt"
    content_type = request.headers.get("content-type") or _fixture_content_type(
        safe_name
    )

    async def _body(chunk: bytes = data):
        yield chunk

    return await gateway.upload_thread_file(
        actor=actor,
        project_id=pid,
        thread_id=thread_id,
        sha256=digest,
        content_type=content_type,
        content_length=len(data),
        body=_body(),
        file_name=safe_name,
    )


async def _load_eval_execution_context(request: Request, run_id: str):
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
    return run_info, target_pid, actor, gateway


def _fixture_content_type(name: str) -> str:
    lower = name.lower()
    if lower.endswith(".csv"):
        return "text/csv"
    if lower.endswith(".json"):
        return "application/json"
    if lower.endswith(".md"):
        return "text/markdown"
    return "text/plain"


@router.post("/internal/execute-turn")
async def internal_execute_turn(request: Request) -> Any:
    raw = await request.body()
    _verify_internal_hmac(request, "execute-turn", raw)
    payload = json.loads(raw or b"{}")
    run_id = str(payload.get("run_id") or "")
    content = str(payload.get("content") or "")
    command = payload.get("command")
    context_overrides = payload.get("context")
    thread_id = payload.get("thread_id")
    idem_key = str(payload.get("idempotency_key") or f"eval:{run_id}:{uuid4()}")
    if not run_id or (not content and command is None):
        raise BadRequestError(
            code="eval_execute_turn_invalid",
            message="run_id and (content or command) are required",
        )
    run_info, target_pid, actor, gateway = await _load_eval_execution_context(
        request, run_id
    )
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
    ctx: dict[str, Any] = {"model_id": str(run_info["target_model_id"])}
    if isinstance(context_overrides, dict):
        ctx.update(context_overrides)
    if command is not None:
        if not resolved_thread_id:
            raise BadRequestError(
                code="eval_resume_thread_required",
                message="thread_id is required when resuming an interrupt",
            )
        resume_map = (
            command.get("resume")
            if isinstance(command, dict) and "resume" in command
            else command
        )
        resumed = await gateway.send_thread_command(
            actor=actor,
            project_id=target_pid,
            thread_id=resolved_thread_id,
            payload={
                "id": 0,
                "method": "input.respond",
                "params": {
                    "resume": resume_map,
                    "assistant_id": run_info["target_graph_id"],
                },
            },
            idempotency_key=idem_key,
        )
        resumed_run_id = str((resumed.get("result") or {}).get("run_id") or "")
        stream = await gateway.join_thread_run_stream(
            actor=actor,
            project_id=target_pid,
            thread_id=resolved_thread_id,
            run_id=resumed_run_id,
            params={
                "stream_mode": ["messages", "values", "updates"],
                "stream_resumable": True,
            },
        )
    else:
        run_payload: dict[str, Any] = {
            "assistant_id": run_info["target_graph_id"],
            "context": ctx,
            "stream_mode": ["messages", "values", "updates"],
        }
        if content:
            run_payload["input"] = {"messages": [{"role": "user", "content": content}]}
        stream = await gateway.stream_thread_run(
            actor=actor,
            project_id=target_pid,
            thread_id=resolved_thread_id,
            payload=run_payload,
            idempotency_key=idem_key,
        )
    return _runtime_sse_response(
        request,
        stream,
        thread_id=resolved_thread_id,
        stream_kind="run",
        protocol=False,
        extra_headers={
            "x-eval-thread-id": resolved_thread_id,
            "x-eval-idempotency-key": idem_key,
        },
    )


@router.post("/internal/thread-setup")
async def internal_thread_setup(request: Request) -> dict[str, Any]:
    raw = await request.body()
    _verify_internal_hmac(request, "thread-setup", raw)
    payload = json.loads(raw or b"{}")
    run_id = str(payload.get("run_id") or "")
    thread_id = payload.get("thread_id")
    fixtures = payload.get("fixtures") or {}
    ensure_workspace = bool(payload.get("ensure_workspace", False))
    if not run_id:
        raise BadRequestError(code="eval_setup_invalid", message="run_id is required")
    run_info, target_pid, actor, gateway = await _load_eval_execution_context(
        request, run_id
    )
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
    upload_map = dict(fixtures) if isinstance(fixtures, dict) else {}
    if not upload_map and ensure_workspace:
        upload_map["evaluation-workspace.txt"] = "Synthetic evaluation workspace.\n"
    fixture_paths: dict[str, str] = {}
    initial_artifacts: dict[str, str] = {}
    for name, text_content in upload_map.items():
        data = str(text_content).encode("utf-8")
        digest = hashlib.sha256(data).hexdigest()

        async def _body(chunk: bytes = data):
            yield chunk

        try:
            ref = await gateway.upload_thread_file(
                actor=actor,
                project_id=target_pid,
                thread_id=resolved_thread_id,
                sha256=digest,
                content_type=_fixture_content_type(str(name)),
                content_length=len(data),
                body=_body(),
                file_name=str(name),
            )
            path = str(ref.get("path") or ref.get("file_path") or "")
            if path:
                fixture_paths[str(name)] = path
                initial_artifacts[path] = str(text_content)
        except Exception:  # noqa: BLE001
            continue
    return {
        "thread_id": resolved_thread_id,
        "fixture_paths": fixture_paths,
        "initial_artifacts": initial_artifacts,
    }


@router.post("/internal/thread-evidence")
async def internal_thread_evidence(request: Request) -> dict[str, Any]:
    raw = await request.body()
    _verify_internal_hmac(request, "thread-evidence", raw)
    payload = json.loads(raw or b"{}")
    run_id = str(payload.get("run_id") or "")
    thread_id = str(payload.get("thread_id") or "")
    run_ids = [str(r) for r in (payload.get("run_ids") or []) if r]
    artifact_paths = [str(p) for p in (payload.get("artifact_paths") or []) if p]
    if not run_id or not thread_id:
        raise BadRequestError(
            code="eval_evidence_invalid", message="run_id and thread_id are required"
        )
    _run_info, target_pid, actor, gateway = await _load_eval_execution_context(
        request, run_id
    )
    state: dict[str, Any] = {}
    try:
        raw_state = await gateway.get_thread_state(
            actor=actor,
            project_id=target_pid,
            thread_id=thread_id,
            params={"subgraphs": True},
        )
        if isinstance(raw_state, dict):
            state = raw_state
    except Exception:  # noqa: BLE001
        state = {}

    thread_runs: list[dict[str, Any]] = []
    try:
        raw_runs = await gateway.list_thread_runs(
            actor=actor,
            project_id=target_pid,
            thread_id=thread_id,
            params={"limit": 20},
        )
        if isinstance(raw_runs, list):
            thread_runs = raw_runs
        elif isinstance(raw_runs, dict) and isinstance(raw_runs.get("items"), list):
            thread_runs = raw_runs["items"]
    except Exception:  # noqa: BLE001
        thread_runs = []

    workspace_files: list[str] = []
    for res_name in ("workspace/tree", "artifacts"):
        try:
            res = await gateway.thread_workspace(
                actor=actor,
                project_id=target_pid,
                thread_id=thread_id,
                resource=res_name,
                path="/workspace",
                limit=100,
            )
            entries = (
                res.get("items") or res.get("entries") or res.get("artifacts") or []
            )
            for item in entries:
                p = item.get("path") if isinstance(item, dict) else item
                if isinstance(p, str) and p.startswith("/workspace/"):
                    is_dir = isinstance(item, dict) and item.get("is_dir") is True
                    if not is_dir and p not in workspace_files:
                        workspace_files.append(p)
        except Exception:  # noqa: BLE001
            continue

    candidate_paths: list[str] = []
    for p in [*artifact_paths, *workspace_files]:
        if p.startswith("/workspace/") and p not in candidate_paths:
            candidate_paths.append(p)
    artifacts: dict[str, str] = {}
    artifact_read_errors: dict[str, str] = {}
    for path in candidate_paths[:40]:
        try:
            file_payload = await gateway.thread_workspace(
                actor=actor,
                project_id=target_pid,
                thread_id=thread_id,
                resource="workspace/content",
                path=path,
            )
            chunks: list[bytes] = []
            total_bytes = 0
            async for chunk in file_payload.body:
                total_bytes += len(chunk)
                if total_bytes > 512 * 1024:
                    break
                chunks.append(chunk)
            artifacts[path] = b"".join(chunks).decode("utf-8", errors="replace")
        except PlatformApiError as exc:
            if exc.status_code != 404:
                artifact_read_errors[path] = exc.code or str(exc)
        except Exception as exc:  # noqa: BLE001
            artifact_read_errors[path] = type(exc).__name__

    diagnostics: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    for rid in run_ids[:20]:
        try:
            diag = await gateway.get_thread_run_diagnostics(
                actor=actor,
                project_id=target_pid,
                thread_id=thread_id,
                run_id=rid,
                request_id=f"eval-diag:{run_id}:{rid}",
            )
            if isinstance(diag, dict):
                diagnostics.append(diag)
        except Exception:  # noqa: BLE001
            pass
        try:
            rec = await gateway.get_thread_execution_evidence(
                actor=actor,
                project_id=target_pid,
                thread_id=thread_id,
                run_id=rid,
            )
            if isinstance(rec, dict):
                receipts.append(rec)
        except Exception:  # noqa: BLE001
            pass

    return {
        "thread_id": thread_id,
        "state": state,
        "runs": thread_runs,
        "workspace_files": workspace_files,
        "artifacts": artifacts,
        "artifact_read_errors": artifact_read_errors,
        "diagnostics": diagnostics,
        "execution_receipts": receipts,
    }


@router.post("/internal/cross-project-probe")
async def internal_cross_project_probe(request: Request) -> dict[str, Any]:
    raw = await request.body()
    _verify_internal_hmac(request, "cross-project-probe", raw)
    payload = json.loads(raw or b"{}")
    run_id = str(payload.get("run_id") or "")
    thread_id = str(payload.get("thread_id") or "")
    probe_pid = str(payload.get("isolation_project_id") or "")
    if not run_id or not thread_id:
        raise BadRequestError(
            code="eval_probe_invalid", message="run_id and thread_id are required"
        )
    run_info, target_pid, actor, gateway = await _load_eval_execution_context(
        request, run_id
    )
    if not probe_pid or probe_pid == target_pid:
        owner_pid = str(run_info.get("owner_project_id") or "")
        probe_pid = owner_pid if owner_pid and owner_pid != target_pid else str(uuid4())
    try:
        await gateway.get_thread_state(
            actor=actor,
            project_id=probe_pid,
            thread_id=thread_id,
            params={},
        )
        return {"probe_project_id": probe_pid, "status_code": 200, "denied": False}
    except PlatformApiError as exc:
        return {
            "probe_project_id": probe_pid,
            "status_code": exc.status_code,
            "denied": exc.status_code in {403, 404},
        }


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
    try:
        _run_info, target_pid, actor, gateway = await _load_eval_execution_context(
            request, run_id
        )
    except ForbiddenError:
        return {"availability": "unavailable", "tokens": {}, "cost": {}}
    try:
        return await gateway.get_thread_usage(
            actor=actor,
            project_id=target_pid,
            thread_id=thread_id,
            request_id=f"eval-usage:{run_id}:{thread_id}",
        )
    except Exception:  # noqa: BLE001
        return {"availability": "unavailable", "tokens": {}, "cost": {}}
