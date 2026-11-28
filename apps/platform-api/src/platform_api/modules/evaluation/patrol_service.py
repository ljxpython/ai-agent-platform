"""Patrol schedule management, Cron preview, dispatch prep, and alert state service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from sqlalchemy import select, update

from platform_api.core.db import session_scope
from platform_api.core.errors import (
    BadRequestError,
    ConflictError,
    NotFoundError,
)
from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
from platform_api.modules.evaluation.models import (
    EvalPatrolSchedule,
    EvalRun,
    EvalSandboxProject,
    EvalSuite,
    EvalSuiteVersion,
)
from platform_api.modules.evaluation.targets import EVALUABLE_GRAPHS
from platform_api.modules.projects.models import ProjectRecord
from platform_api.modules.runtime_catalog.infra.sqlalchemy.models import (
    RuntimeCatalogModelRecord,
)

ACTIVE_RUN_STATUSES = frozenset({"queued", "running", "rescoring", "paused"})


def validate_cron_and_timezone(cron_expr: str, tz_name: str) -> tuple[str, ZoneInfo]:
    """Validate 5-field cron expression and IANA timezone."""
    expr = " ".join((cron_expr or "").strip().split())
    if len(expr.split(" ")) != 5 or not croniter.is_valid(expr):
        raise BadRequestError(
            code="eval_patrol_cron_invalid",
            message="Cron 表达式必须为合法的 5 段标准格式（分 时 日 月 周）。",
        )
    try:
        tz = ZoneInfo(tz_name or "Asia/Shanghai")
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise BadRequestError(
            code="eval_patrol_timezone_invalid",
            message=f"无效的 IANA 时区: {tz_name}",
        ) from exc
    return expr, tz


def compute_next_run_at(
    cron_expr: str, tz_name: str, *, after: datetime | None = None
) -> datetime:
    """Compute next trigger UTC datetime strictly after the given timestamp."""
    expr, tz = validate_cron_and_timezone(cron_expr, tz_name)
    base_utc = (after or datetime.now(UTC)).astimezone(UTC)
    local_base = base_utc.astimezone(tz)
    nxt_local = croniter(expr, local_base).get_next(datetime)
    if nxt_local.tzinfo is None:
        nxt_local = nxt_local.replace(tzinfo=tz)
    return nxt_local.astimezone(UTC)


def preview_cron_runs(
    cron_expr: str, tz_name: str = "Asia/Shanghai", count: int = 5
) -> dict[str, Any]:
    """Return next N local & UTC execution timestamps for Cron preview."""
    expr, tz = validate_cron_and_timezone(cron_expr, tz_name)
    local_now = datetime.now(UTC).astimezone(tz)
    it = croniter(expr, local_now)
    next_local: list[str] = []
    next_utc: list[str] = []
    for _ in range(max(1, min(10, int(count)))):
        dt = it.get_next(datetime)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        next_local.append(dt.isoformat())
        next_utc.append(dt.astimezone(UTC).isoformat())
    return {
        "cron_expr": expr,
        "timezone": tz.key,
        "next_runs": next_local,
        "next_runs_utc": next_utc,
    }


def _serialize_patrol(
    row: EvalPatrolSchedule,
    *,
    suite_name: str | None = None,
    target_project_name: str | None = None,
    target_agent_name: str | None = None,
    target_model_name: str | None = None,
    judge_model_name: str | None = None,
    last_run: EvalRun | None = None,
) -> dict[str, Any]:
    last_score = None
    if last_run and isinstance(last_run.summary_metrics_json, dict):
        val = last_run.summary_metrics_json.get(
            "overall_score", last_run.summary_metrics_json.get("tsr_pass_at_1")
        )
        if isinstance(val, (int, float)):
            last_score = float(val)
    return {
        "id": row.id,
        "name": row.name,
        "suite_id": row.suite_id,
        "suite_name": suite_name,
        "version_id": row.version_id,
        "version_policy": row.version_policy,
        "owner_project_id": row.owner_project_id,
        "target_project_id": row.target_project_id,
        "target_project_name": target_project_name,
        "target_graph_id": row.target_graph_id,
        "target_agent_id": row.target_agent_id,
        "target_agent_name": target_agent_name,
        "target_model_id": row.target_model_id,
        "target_model_name": target_model_name,
        "judge_model_id": row.judge_model_id,
        "judge_model_name": judge_model_name,
        "embedding_model_id": row.embedding_model_id,
        "case_keys": list(row.case_keys_json or []),
        "concurrency": row.concurrency,
        "repeat_k": row.repeat_k,
        "skip_incompatible": row.skip_incompatible,
        "confirm_non_sandbox": row.confirm_non_sandbox,
        "cron_expr": row.cron_expr,
        "timezone": row.timezone,
        "enabled": row.enabled,
        "concurrency_policy": row.concurrency_policy,
        "gate_config": dict(row.gate_config_json or {}),
        "notify_channels": list(row.notify_channels_json or []),
        "notify_on_recovery": row.notify_on_recovery,
        "next_run_at": row.next_run_at.isoformat() if row.next_run_at else None,
        "last_triggered_at": (
            row.last_triggered_at.isoformat() if row.last_triggered_at else None
        ),
        "last_status": row.last_status,
        "last_message": row.last_message,
        "consecutive_failures": row.consecutive_failures,
        "last_run_id": row.last_run_id,
        "last_run_status": last_run.status if last_run else None,
        "last_run_gate_exit_code": last_run.gate_exit_code if last_run else None,
        "last_run_score": last_score,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _enrich_patrols(session, rows: list[EvalPatrolSchedule]) -> list[dict[str, Any]]:
    if not rows:
        return []
    suite_ids = {r.suite_id for r in rows}
    suite_names = {
        s.id: s.name
        for s in session.scalars(
            select(EvalSuite).where(EvalSuite.id.in_(suite_ids))
        ).all()
    }
    project_names = {
        str(p.id): p.name for p in session.scalars(select(ProjectRecord)).all()
    }
    agent_names = {
        str(a.id): a.name for a in session.scalars(select(AgentRecord)).all()
    }
    model_names = {
        str(m.id): m.display_name
        for m in session.scalars(select(RuntimeCatalogModelRecord)).all()
    }
    run_ids = {r.last_run_id for r in rows if r.last_run_id}
    runs_by_id = (
        {
            run.id: run
            for run in session.scalars(
                select(EvalRun).where(EvalRun.id.in_(run_ids))
            ).all()
        }
        if run_ids
        else {}
    )
    return [
        _serialize_patrol(
            r,
            suite_name=suite_names.get(r.suite_id),
            target_project_name=project_names.get(r.target_project_id),
            target_agent_name=(
                agent_names.get(r.target_agent_id) if r.target_agent_id else None
            ),
            target_model_name=(
                model_names.get(r.target_model_id) if r.target_model_id else None
            ),
            judge_model_name=(
                model_names.get(r.judge_model_id) if r.judge_model_id else None
            ),
            last_run=runs_by_id.get(r.last_run_id) if r.last_run_id else None,
        )
        for r in rows
    ]


def _resolve_target_graph(
    session,
    *,
    target_project_id: str,
    target_agent_id: str | None,
    target_graph_id: str | None,
) -> str:
    if target_agent_id:
        from uuid import UUID

        try:
            agent_uuid = UUID(str(target_agent_id))
        except ValueError:
            agent_uuid = None
        agent = session.get(AgentRecord, agent_uuid) if agent_uuid else None
        if (
            agent is None
            or str(agent.project_id) != target_project_id
            or agent.graph_id not in EVALUABLE_GRAPHS
        ):
            raise BadRequestError(
                code="evaluation_target_invalid",
                message="巡检目标 Agent 不属于目标项目或不支持评测。",
            )
        return agent.graph_id
    if target_graph_id and target_graph_id in EVALUABLE_GRAPHS:
        return target_graph_id
    raise BadRequestError(
        code="evaluation_target_invalid",
        message="请提供有效的巡检目标 Agent 或 Graph。",
    )


def _validate_version_binding(
    session, *, suite_id: str, version_policy: str, version_id: str | None
) -> str | None:
    if version_policy == "pinned":
        if not version_id:
            raise BadRequestError(
                code="eval_patrol_version_required",
                message="锁定版本模式下必须指定已发布版本。",
            )
        ver = session.get(EvalSuiteVersion, version_id)
        if ver is None or ver.suite_id != suite_id:
            raise NotFoundError(
                code="eval_version_not_found", message="指定的评测集冻结版本不存在。"
            )
        return ver.id
    if version_id:
        ver = session.get(EvalSuiteVersion, version_id)
        if ver is None or ver.suite_id != suite_id:
            raise NotFoundError(
                code="eval_version_not_found", message="指定的评测集冻结版本不存在。"
            )
        return ver.id
    return None


def list_patrols(factory, *, project_id: str) -> dict[str, Any]:
    with session_scope(factory) as session:
        rows = session.scalars(
            select(EvalPatrolSchedule)
            .where(EvalPatrolSchedule.owner_project_id == project_id)
            .order_by(EvalPatrolSchedule.created_at.desc())
        ).all()
        return {"items": _enrich_patrols(session, list(rows))}


def create_patrol(factory, *, project_id: str, actor_id: str, body) -> dict[str, Any]:
    expr, _ = validate_cron_and_timezone(body.cron_expr, body.timezone)
    with session_scope(factory) as session:
        suite = session.get(EvalSuite, str(body.suite_id))
        if suite is None or suite.owner_project_id != project_id:
            raise NotFoundError(code="eval_suite_not_found", message="评测集不存在。")

        resolved_graph = _resolve_target_graph(
            session,
            target_project_id=body.target_project_id,
            target_agent_id=str(body.target_agent_id) if body.target_agent_id else None,
            target_graph_id=body.target_graph_id,
        )
        resolved_ver = _validate_version_binding(
            session,
            suite_id=suite.id,
            version_policy=body.version_policy,
            version_id=str(body.version_id) if body.version_id else None,
        )
        sandbox_row = session.get(EvalSandboxProject, body.target_project_id)
        is_sandbox = bool(sandbox_row and sandbox_row.is_sandbox)
        if body.target_agent_id and not is_sandbox and not body.confirm_non_sandbox:
            raise BadRequestError(
                code="eval_non_sandbox_confirmation_required",
                message="目标项目非专用评测靶场，请确认风险后再创建定时巡检。",
            )

        next_run = compute_next_run_at(expr, body.timezone) if body.enabled else None
        row = EvalPatrolSchedule(
            id=str(uuid4()),
            name=body.name.strip(),
            suite_id=suite.id,
            version_id=resolved_ver,
            version_policy=body.version_policy,
            owner_project_id=project_id,
            target_project_id=body.target_project_id,
            target_graph_id=resolved_graph,
            target_agent_id=(
                str(body.target_agent_id) if body.target_agent_id else None
            ),
            target_model_id=(
                str(body.target_model_id) if body.target_model_id else None
            ),
            judge_model_id=str(body.judge_model_id) if body.judge_model_id else None,
            embedding_model_id=(
                str(body.embedding_model_id) if body.embedding_model_id else None
            ),
            case_keys_json=list(body.case_keys or []),
            concurrency=body.concurrency,
            repeat_k=body.repeat_k,
            skip_incompatible=body.skip_incompatible,
            confirm_non_sandbox=body.confirm_non_sandbox,
            cron_expr=expr,
            timezone=body.timezone,
            enabled=body.enabled,
            concurrency_policy=body.concurrency_policy,
            gate_config_json=body.gate_config.model_dump(mode="json"),
            notify_channels_json=list(body.notify_channels or []),
            notify_on_recovery=body.notify_on_recovery,
            next_run_at=next_run,
            last_status="idle",
            last_message="",
            consecutive_failures=0,
            created_by=actor_id,
        )
        session.add(row)
        session.flush()
        return _enrich_patrols(session, [row])[0]


def update_patrol(
    factory, *, project_id: str, schedule_id: str, body
) -> dict[str, Any]:
    with session_scope(factory) as session:
        row = session.get(EvalPatrolSchedule, schedule_id)
        if row is None or row.owner_project_id != project_id:
            raise NotFoundError(
                code="eval_patrol_not_found", message="定时巡检配置不存在。"
            )
        fields = body.model_fields_set
        if "name" in fields and body.name is not None:
            row.name = body.name.strip()
        if "target_project_id" in fields and body.target_project_id is not None:
            row.target_project_id = body.target_project_id
        if "target_agent_id" in fields:
            row.target_agent_id = (
                str(body.target_agent_id) if body.target_agent_id else None
            )
        if "target_graph_id" in fields and body.target_graph_id is not None:
            row.target_graph_id = body.target_graph_id
        if "target_agent_id" in fields or "target_project_id" in fields:
            row.target_graph_id = _resolve_target_graph(
                session,
                target_project_id=row.target_project_id,
                target_agent_id=row.target_agent_id,
                target_graph_id=row.target_graph_id,
            )
        if "target_model_id" in fields:
            row.target_model_id = (
                str(body.target_model_id) if body.target_model_id else None
            )
        if "judge_model_id" in fields:
            row.judge_model_id = (
                str(body.judge_model_id) if body.judge_model_id else None
            )
        if "embedding_model_id" in fields:
            row.embedding_model_id = (
                str(body.embedding_model_id) if body.embedding_model_id else None
            )
        if "version_policy" in fields and body.version_policy is not None:
            row.version_policy = body.version_policy
        if "version_id" in fields:
            row.version_id = str(body.version_id) if body.version_id else None
        if "version_policy" in fields or "version_id" in fields:
            row.version_id = _validate_version_binding(
                session,
                suite_id=row.suite_id,
                version_policy=row.version_policy,
                version_id=row.version_id,
            )
        if "case_keys" in fields and body.case_keys is not None:
            row.case_keys_json = list(body.case_keys)
        if "concurrency" in fields and body.concurrency is not None:
            row.concurrency = body.concurrency
        if "repeat_k" in fields and body.repeat_k is not None:
            row.repeat_k = body.repeat_k
        if "skip_incompatible" in fields and body.skip_incompatible is not None:
            row.skip_incompatible = body.skip_incompatible
        if "confirm_non_sandbox" in fields and body.confirm_non_sandbox is not None:
            row.confirm_non_sandbox = body.confirm_non_sandbox
        if "concurrency_policy" in fields and body.concurrency_policy is not None:
            row.concurrency_policy = body.concurrency_policy
        if "gate_config" in fields and body.gate_config is not None:
            row.gate_config_json = body.gate_config.model_dump(mode="json")
        if "notify_channels" in fields and body.notify_channels is not None:
            row.notify_channels_json = list(body.notify_channels)
        if "notify_on_recovery" in fields and body.notify_on_recovery is not None:
            row.notify_on_recovery = body.notify_on_recovery

        recompute = False
        if "cron_expr" in fields and body.cron_expr is not None:
            row.cron_expr = body.cron_expr
            recompute = True
        if "timezone" in fields and body.timezone is not None:
            row.timezone = body.timezone
            recompute = True
        if "enabled" in fields and body.enabled is not None:
            row.enabled = body.enabled
            recompute = True

        expr, _ = validate_cron_and_timezone(row.cron_expr, row.timezone)
        row.cron_expr = expr
        if recompute:
            row.next_run_at = (
                compute_next_run_at(row.cron_expr, row.timezone)
                if row.enabled
                else None
            )

        session.flush()
        return _enrich_patrols(session, [row])[0]


def delete_patrol(factory, *, project_id: str, schedule_id: str) -> dict[str, Any]:
    with session_scope(factory) as session:
        row = session.get(EvalPatrolSchedule, schedule_id)
        if row is None or row.owner_project_id != project_id:
            raise NotFoundError(
                code="eval_patrol_not_found", message="定时巡检配置不存在。"
            )
        session.execute(
            update(EvalRun)
            .where(EvalRun.patrol_schedule_id == schedule_id)
            .values(patrol_schedule_id=None)
        )
        session.delete(row)
        session.flush()
        return {"deleted": True, "id": schedule_id}


def load_patrol_dispatch_context(
    factory,
    *,
    schedule_id: str,
    project_id: str | None = None,
    advance_schedule: bool = False,
) -> dict[str, Any]:
    """Load patrol config, check Forbid concurrency & resolve frozen version."""
    with session_scope(factory) as session:
        row = session.get(EvalPatrolSchedule, schedule_id)
        if row is None or (project_id and row.owner_project_id != project_id):
            raise NotFoundError(
                code="eval_patrol_not_found", message="定时巡检配置不存在。"
            )
        if not row.target_agent_id or not row.target_model_id:
            raise BadRequestError(
                code="eval_patrol_target_incomplete",
                message="巡检配置缺少目标 Agent 或目标模型，请先编辑补全。",
            )
        if advance_schedule:
            row.next_run_at = (
                compute_next_run_at(row.cron_expr, row.timezone)
                if row.enabled
                else None
            )

        if row.concurrency_policy == "forbid" and row.last_run_id:
            last_run = session.get(EvalRun, row.last_run_id)
            if last_run and last_run.status in ACTIVE_RUN_STATUSES:
                if advance_schedule:
                    row.last_triggered_at = datetime.now(UTC)
                    row.last_status = "skipped_overlap"
                    row.last_message = f"上一轮巡检 #{last_run.id[:8]} 仍在执行 ({last_run.status})，本次按 Forbid 策略跳过。"
                    session.flush()
                    return {
                        "overlap_skipped": True,
                        "active_run_id": last_run.id,
                        "schedule": _serialize_patrol(row),
                    }
                raise ConflictError(
                    code="eval_patrol_run_active",
                    message=f"上一轮巡检 #{last_run.id[:8]} 仍在执行中，请等待完成或暂停后再试。",
                )

        if row.version_policy == "pinned" and row.version_id:
            ver = session.get(EvalSuiteVersion, row.version_id)
        else:
            ver = session.scalars(
                select(EvalSuiteVersion)
                .where(EvalSuiteVersion.suite_id == row.suite_id)
                .order_by(EvalSuiteVersion.version_num.desc())
            ).first()
        if ver is None:
            raise BadRequestError(
                code="eval_version_not_found",
                message="评测集尚未发布冻结版本，无法执行定时巡检。",
            )

        return {
            "overlap_skipped": False,
            "schedule": _serialize_patrol(row),
            "resolved_version_id": ver.id,
            "resolved_version_num": ver.version_num,
        }


def mark_patrol_dispatched(
    factory,
    *,
    schedule_id: str,
    run_id: str,
    note: str = "巡检任务已入队执行",
) -> dict[str, Any]:
    with session_scope(factory) as session:
        row = session.get(EvalPatrolSchedule, schedule_id)
        if row is None:
            raise NotFoundError(
                code="eval_patrol_not_found", message="定时巡检配置不存在。"
            )
        row.last_run_id = run_id
        row.last_triggered_at = datetime.now(UTC)
        row.last_status = "running"
        row.last_message = note[:1000]
        session.flush()
        return _enrich_patrols(session, [row])[0]


def mark_patrol_blocked(factory, *, schedule_id: str, reason: str) -> dict[str, Any]:
    with session_scope(factory) as session:
        row = session.get(EvalPatrolSchedule, schedule_id)
        if row is None:
            raise NotFoundError(
                code="eval_patrol_not_found", message="定时巡检配置不存在。"
            )
        row.last_triggered_at = datetime.now(UTC)
        row.last_status = "blocked"
        row.last_message = reason[:1000]
        row.consecutive_failures = int(row.consecutive_failures or 0) + 1
        threshold = int(
            (row.gate_config_json or {}).get("consecutive_alert_threshold") or 1
        )
        session.flush()
        return {
            "schedule": _serialize_patrol(row),
            "should_alert": row.consecutive_failures >= threshold,
        }


def record_patrol_report(
    factory,
    *,
    schedule_id: str,
    run_id: str,
    verdict: str,
    summary_text: str,
) -> dict[str, Any]:
    with session_scope(factory) as session:
        row = session.get(EvalPatrolSchedule, schedule_id)
        if row is None:
            raise NotFoundError(
                code="eval_patrol_not_found", message="定时巡检配置不存在。"
            )
        prev_failures = int(row.consecutive_failures or 0)
        prev_status = row.last_status
        row.last_run_id = run_id
        row.last_status = verdict
        row.last_message = (summary_text or "")[:1000]
        if verdict == "passed":
            row.consecutive_failures = 0
            should_alert = False
            should_recover = bool(prev_failures > 0 and row.notify_on_recovery)
        else:
            row.consecutive_failures = prev_failures + 1
            threshold = int(
                (row.gate_config_json or {}).get("consecutive_alert_threshold") or 1
            )
            should_alert = row.consecutive_failures >= threshold
            should_recover = False
        session.flush()
        return {
            "schedule": _serialize_patrol(row),
            "prev_status": prev_status,
            "should_alert": should_alert,
            "should_recover": should_recover,
        }
