"""Project-authorized target snapshots and runs across the HTTP boundary."""

import hashlib
import json
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from platform_api.build_info import STARTUP_MANIFEST
from platform_api.core.errors import (
    BadRequestError,
    ConflictError,
    ServiceUnavailableError,
)
from platform_api.modules.agents.application import AssistantsService
from platform_api.modules.runtime_catalog.infra.sqlalchemy.models import (
    RuntimeCatalogModelRecord,
)
from platform_api.modules.runtime_policies.application import (
    RuntimePolicyOverlayService,
)

EVALUABLE_GRAPHS: frozenset[str] = frozenset(
    {"dearflow_agent", "showcase_demo", "reference_agent", "workflow_demo"}
)

_DEFAULT_GRAPH_FEATURES: dict[str, dict[str, bool]] = {
    "dearflow_agent": {
        "workspace_files": True,
        "clarification": True,
        "plan_mode": True,
    },
    "showcase_demo": {
        "workspace_files": True,
        "clarification": False,
        "plan_mode": True,
    },
    "reference_agent": {
        "workspace_files": False,
        "clarification": False,
        "plan_mode": True,
    },
    "workflow_demo": {
        "workspace_files": False,
        "clarification": False,
        "plan_mode": False,
    },
}


class Parameters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    temperature: float = Field(default=0.0, ge=0, le=2, allow_inf_nan=False)
    max_tokens: int = Field(default=4096, ge=1, le=32768)
    top_p: float = Field(default=1.0, gt=0, le=1, allow_inf_nan=False)


class TargetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: UUID
    model_id: UUID
    parameters: Parameters = Field(default_factory=Parameters)


class EvaluationRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: dict
    run: dict


def fingerprint(value):
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def configured_target(gateway, actor, project_id, spec):
    gateway._authorize(actor=actor, project_id=project_id, write=True)
    factory = gateway._require_session_factory()
    item = AssistantsService(
        session_factory=factory, schema_provider=None
    ).get_assistant(actor=actor, assistant_id=str(spec.agent_id))
    if (
        item.project_id != project_id
        or item.graph_id not in EVALUABLE_GRAPHS
        or item.status != "active"
    ):
        raise BadRequestError(
            code="evaluation_target_invalid",
            message="评测Agent不属于当前项目、未启用或不支持评测。",
        )
    gateway._assert_runtime_target_allowed(
        project_id=project_id, assistant_id=item.graph_id
    )
    policies = RuntimePolicyOverlayService(
        session_factory=factory, runtime_base_url=gateway._runtime_id
    )
    models = policies.list_model_policies(actor=actor, project_id=project_id).items
    graphs = policies.list_graph_policies(actor=actor, project_id=project_id).items
    model = next(
        (m for m in models if m.model_id == str(spec.model_id) and m.policy.is_enabled),
        None,
    )
    graph = next(
        (g for g in graphs if g.graph_id == item.graph_id and g.policy.is_enabled), None
    )
    if not model or not graph:
        raise BadRequestError(
            code="evaluation_resource_denied", message="评测模型或图未授权。"
        )
    agent = item.model_dump(
        mode="json",
        include={
            "id",
            "project_id",
            "name",
            "graph_id",
            "status",
            "context",
            "model_resilience",
        },
    )
    tool_policy = policies.resolve_tool_overrides(
        project_id=project_id, user_id=actor.user_id, graph_id=item.graph_id
    )
    with factory() as session:
        connection = session.get(RuntimeCatalogModelRecord, spec.model_id)
        if connection is None or not connection.enabled:
            raise BadRequestError(
                code="evaluation_resource_denied", message="评测模型连接不可用。"
            )
        connection_revision = str(connection.updated_at)
    return agent, {
        "model": model.model_dump(mode="json"),
        "model_connection_revision": connection_revision,
        "graph": graph.model_dump(mode="json", exclude={"last_synced_at"}),
        "tool_policy": tool_policy,
    }


async def snapshot(gateway, actor, project_id, spec):
    agent, resources = await run_in_threadpool(
        configured_target, gateway, actor, project_id, spec
    )
    runtime = await gateway.evaluation_capabilities(
        project_id=project_id, graph_id=agent["graph_id"]
    )
    if (
        runtime.get("schema") != "evaluation-runtime/v1"
        or runtime.get("available") is not True
        or STARTUP_MANIFEST["package_sha256"] == "unavailable"
    ):
        raise ServiceUnavailableError(
            code="evaluation_contract_unavailable",
            message="执行环境缺少可用的评测版本与证据契约。",
        )
    resources["runtime"] = runtime
    context = {
        **agent["context"],
        **spec.parameters.model_dump(),
        "model_id": str(spec.model_id),
        "execution_mode": "standard",
    }
    result = {
        "schema": "evaluation-target/v1",
        "spec": spec.model_dump(mode="json"),
        "agent": agent,
        "agent_hash": fingerprint(agent),
        "resources": resources,
        "resource_hash": fingerprint(resources),
        "context": context,
        "deployment": {
            "platform": dict(STARTUP_MANIFEST),
            "runtime": runtime["manifest"],
        },
    }
    result["config_hash"] = fingerprint(result)
    return result


async def validate_target(gateway, actor, project_id, expected):
    try:
        spec = TargetRequest.model_validate(expected["spec"])
        payload = {
            k: v
            for k, v in expected.items()
            if k not in {"config_hash", "profile_id", "name", "source", "differences"}
        }
        valid = (
            expected["schema"] == "evaluation-target/v1"
            and fingerprint(payload) == expected["config_hash"]
        )
    except (KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise BadRequestError(
            code="evaluation_target_invalid", message="评测目标快照无效。"
        )
    current = await snapshot(gateway, actor, project_id, spec)
    if current["config_hash"] != expected["config_hash"]:
        raise ConflictError(
            code="evaluation_target_changed",
            message="评测目标已变化，请重新创建评测任务。",
        )


async def create_run(gateway, actor, project_id, thread_id, body, key):
    if not key:
        raise BadRequestError(
            code="idempotency_key_required", message="评测运行必须提供幂等标识。"
        )
    await validate_target(gateway, actor, project_id, body.target)
    if body.run.get("assistant_id") != body.target["agent"]["graph_id"]:
        raise BadRequestError(
            code="evaluation_target_invalid", message="运行Agent与评测目标不一致。"
        )
    payload = dict(body.run)
    if "command" not in payload:
        if payload.get("context") != body.target["context"]:
            raise BadRequestError(
                code="evaluation_target_invalid", message="运行参数与评测目标不一致。"
            )
    return await gateway.create_thread_run(
        actor=actor,
        project_id=project_id,
        thread_id=thread_id,
        payload=payload,
        idempotency_key=key,
        evaluation_target=body.target,
    )


def infer_case_required_capabilities(case: dict) -> list[str]:
    """Infer capability tags required by a case from explicit tags or assertions."""
    explicit = list(case.get("required_capabilities") or [])
    required = set(str(x) for x in explicit if x)
    expectations = case.get("expectations") or {}
    if expectations.get("artifacts") or case.get("fixture"):
        required.add("workspace_files")
    for turn in case.get("turns") or []:
        if isinstance(turn, dict) and turn.get("fixture"):
            required.add("workspace_files")
    metrics = case.get("metrics") or []
    for metric in metrics:
        name = metric.get("name") if isinstance(metric, dict) else str(metric)
        if name in {"artifact_correct", "no_write", "protected_unchanged"}:
            required.add("workspace_files")
        if name == "clarification_requested":
            required.add("clarification")
    return sorted(required)


async def check_readiness(
    gateway,
    session_factory,
    *,
    actor,
    target_project_id: str,
    agent_id: UUID,
    model_id: UUID,
    judge_model_id: UUID | None = None,
    embedding_model_id: UUID | None = None,
    suite_cases: list[dict] | None = None,
    eval_project_id: str = "",
) -> dict:
    """Validate target project, graph capability match, models, and sandbox risk."""
    from platform_api.modules.evaluation.models import EvalSandboxProject

    spec = TargetRequest(agent_id=agent_id, model_id=model_id)
    agent, _ = await run_in_threadpool(
        configured_target, gateway, actor, target_project_id, spec
    )
    runtime = await gateway.evaluation_capabilities(
        project_id=target_project_id, graph_id=agent["graph_id"]
    )
    graph_features = runtime.get("graph_features") or _DEFAULT_GRAPH_FEATURES.get(
        agent["graph_id"],
        {"workspace_files": False, "clarification": False, "plan_mode": False},
    )

    def _check_db():
        with session_factory() as session:
            sandbox_row = session.get(EvalSandboxProject, target_project_id)
            is_sandbox = bool(
                (sandbox_row and sandbox_row.is_sandbox)
                or (eval_project_id and target_project_id == eval_project_id)
            )
            missing_models = []
            for label, mid in (
                ("judge_model", judge_model_id),
                ("embedding_model", embedding_model_id),
            ):
                if mid is not None:
                    rec = session.get(RuntimeCatalogModelRecord, mid)
                    if rec is None or not rec.enabled:
                        missing_models.append(label)
            return is_sandbox, missing_models

    is_sandbox, missing_models = await run_in_threadpool(_check_db)
    incompatible_cases = []
    for case in suite_cases or []:
        req = infer_case_required_capabilities(case)
        missing_caps = [cap for cap in req if not graph_features.get(cap, False)]
        if missing_caps:
            incompatible_cases.append(
                {
                    "case_key": case.get("case_key", ""),
                    "missing_capabilities": missing_caps,
                }
            )
    ready = len(missing_models) == 0 and len(incompatible_cases) == 0
    return {
        "ready": ready,
        "target_project_id": target_project_id,
        "graph_id": agent["graph_id"],
        "graph_features": graph_features,
        "is_sandbox": is_sandbox,
        "sandbox_warning": (
            None
            if is_sandbox
            else "所选项目不是专用评测靶场，评测将写入该项目的会话、预算与 MLflow 追踪记录，请确认后执行。"
        ),
        "missing_models": missing_models,
        "incompatible_cases": incompatible_cases,
    }
