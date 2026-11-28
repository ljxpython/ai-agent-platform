"""Sync SQLAlchemy control-plane service for native evaluation studio."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, select

from platform_api.core.db import session_scope
from platform_api.core.errors import BadRequestError, ConflictError, NotFoundError
from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
from platform_api.modules.evaluation.models import (
    EvalCase,
    EvalHumanReview,
    EvalPatrolSchedule,
    EvalRun,
    EvalRunCase,
    EvalRunLog,
    EvalSandboxProject,
    EvalSuite,
    EvalSuiteVersion,
)
from platform_api.modules.evaluation.targets import (
    _DEFAULT_GRAPH_FEATURES,
    infer_case_required_capabilities,
)
from platform_api.modules.projects.models import ProjectRecord
from platform_api.modules.runtime_catalog.infra.sqlalchemy.models import (
    RuntimeCatalogModelRecord,
)


def _extract_case_preview(case: EvalCase) -> dict[str, Any]:
    turns = case.turns_json if isinstance(case.turns_json, list) else []
    sim = case.simulation_json if isinstance(case.simulation_json, dict) else None
    exp = case.expectations_json if isinstance(case.expectations_json, dict) else {}
    question = ""
    if turns:
        question = str(turns[0].get("content") or "")
    elif sim:
        question = str(sim.get("goal") or "")
    expected_answer = str(exp.get("expected_answer") or "")
    return {
        "id": case.id,
        "case_key": case.case_key,
        "split": case.split,
        "mode": "simulation" if sim else "fixed",
        "question": question,
        "ground_truth": expected_answer,
        "metrics_count": len(case.metrics_json or []),
    }


def _hash_payload(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _serialize_suite(row: EvalSuite) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "suite_type": row.suite_type,
        "owner_project_id": row.owner_project_id,
        "source_project_id": row.source_project_id,
        "default_graph_id": row.default_graph_id,
        "created_by": row.created_by,
        "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_case(row: EvalCase) -> dict[str, Any]:
    return {
        "id": row.id,
        "suite_id": row.suite_id,
        "case_key": row.case_key,
        "split": row.split,
        "schema_version": row.schema_version,
        "required_capabilities": row.required_capabilities_json,
        "turns": row.turns_json,
        "simulation": row.simulation_json,
        "expectations": row.expectations_json,
        "metrics": row.metrics_json,
        "metadata": row.metadata_json,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_version(row: EvalSuiteVersion) -> dict[str, Any]:
    return {
        "id": row.id,
        "suite_id": row.suite_id,
        "version_num": row.version_num,
        "content_hash": row.content_hash,
        "case_count": len(row.frozen_cases_json),
        "published_by": row.published_by,
        "published_at": row.published_at.isoformat() if row.published_at else None,
    }


def _serialize_run(row: EvalRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "suite_id": row.suite_id,
        "version_id": row.version_id,
        "owner_project_id": row.owner_project_id,
        "target_project_id": row.target_project_id,
        "target_graph_id": row.target_graph_id,
        "target_agent_id": row.target_agent_id,
        "target_model_id": row.target_model_id,
        "judge_model_id": row.judge_model_id,
        "embedding_model_id": row.embedding_model_id,
        "matrix_group_id": row.matrix_group_id,
        "mode": row.mode,
        "concurrency": row.concurrency,
        "repeat_k": row.repeat_k,
        "status": row.status,
        "gate_exit_code": row.gate_exit_code,
        "summary_metrics": row.summary_metrics_json,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
    }


def _serialize_run_case(row: EvalRunCase) -> dict[str, Any]:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "case_key": row.case_key,
        "attempt_idx": row.attempt_idx,
        "status": row.status,
        "thread_id": row.thread_id,
        "trace_ids": row.trace_ids_json,
        "rule_passed": row.rule_passed,
        "overall_score": row.overall_score,
        "duration_ms": row.duration_ms,
        "ttft_ms": row.ttft_ms,
        "token_usage": row.token_usage_json,
        "cost_usd": row.cost_usd,
        "error_category": row.error_category,
        "evidence_path": row.evidence_path,
        "results": row.results_json,
    }


def list_suites(
    factory, *, project_id: str, include_archived: bool = False
) -> dict[str, Any]:
    with session_scope(factory) as session:
        stmt = select(EvalSuite).where(EvalSuite.owner_project_id == project_id)
        if not include_archived:
            stmt = stmt.where(EvalSuite.archived_at.is_(None))
        suites = session.scalars(stmt.order_by(EvalSuite.updated_at.desc())).all()
        project_names: dict[str, str] = {
            str(p.id): p.name for p in session.scalars(select(ProjectRecord)).all()
        }
        items = []
        for suite in suites:
            suite_cases = session.scalars(
                select(EvalCase)
                .where(EvalCase.suite_id == suite.id)
                .order_by(EvalCase.case_key.asc())
            ).all()
            latest_ver = session.scalars(
                select(EvalSuiteVersion)
                .where(EvalSuiteVersion.suite_id == suite.id)
                .order_by(EvalSuiteVersion.version_num.desc())
            ).first()
            suite_runs = session.scalars(
                select(EvalRun)
                .where(EvalRun.suite_id == suite.id)
                .order_by(EvalRun.created_at.desc())
            ).all()
            scores = [
                float(
                    r.summary_metrics_json.get(
                        "overall_score", r.summary_metrics_json.get("tsr_pass_at_1")
                    )
                )
                for r in suite_runs
                if isinstance(r.summary_metrics_json, dict)
                and (
                    r.summary_metrics_json.get("overall_score") is not None
                    or r.summary_metrics_json.get("tsr_pass_at_1") is not None
                )
            ]
            items.append(
                {
                    **_serialize_suite(suite),
                    "owner_project_name": project_names.get(suite.owner_project_id),
                    "source_project_name": (
                        project_names.get(suite.source_project_id)
                        if suite.source_project_id
                        else None
                    ),
                    "case_count": len(suite_cases),
                    "sample_cases": [_extract_case_preview(c) for c in suite_cases[:3]],
                    "runs_count": len(suite_runs),
                    "best_score": max(scores) if scores else None,
                    "latest_score": scores[0] if scores else None,
                    "latest_version": _serialize_version(latest_ver)
                    if latest_ver
                    else None,
                }
            )
        return {"items": items}


def archive_suite(factory, *, project_id: str, suite_id: str) -> dict[str, Any]:
    with session_scope(factory) as session:
        suite = session.get(EvalSuite, suite_id)
        if suite is None or suite.owner_project_id != project_id:
            raise NotFoundError(code="eval_suite_not_found", message="评测集不存在。")
        suite.archived_at = datetime.now(UTC)
        session.flush()
        return {"archived": True, "suite_id": suite_id}


def import_cases(
    factory, *, project_id: str, suite_id: str, items: list[Any]
) -> dict[str, Any]:
    saved = [
        upsert_case(factory, project_id=project_id, suite_id=suite_id, body=item)
        for item in items
    ]
    return {"imported": len(saved), "items": saved}


def create_suite(factory, *, project_id: str, actor_id: str, body) -> dict[str, Any]:
    with session_scope(factory) as session:
        row = EvalSuite(
            id=str(uuid4()),
            name=body.name.strip(),
            description=body.description,
            suite_type=body.suite_type,
            owner_project_id=project_id,
            source_project_id=body.source_project_id,
            default_graph_id=body.default_graph_id,
            created_by=actor_id,
        )
        session.add(row)
        session.flush()
        return _serialize_suite(row)


def get_suite_detail(factory, *, project_id: str, suite_id: str) -> dict[str, Any]:
    with session_scope(factory) as session:
        suite = session.get(EvalSuite, suite_id)
        if suite is None or suite.owner_project_id != project_id:
            raise NotFoundError(code="eval_suite_not_found", message="评测集不存在。")
        cases = session.scalars(
            select(EvalCase)
            .where(EvalCase.suite_id == suite_id)
            .order_by(EvalCase.case_key.asc())
        ).all()
        versions = session.scalars(
            select(EvalSuiteVersion)
            .where(EvalSuiteVersion.suite_id == suite_id)
            .order_by(EvalSuiteVersion.version_num.desc())
        ).all()
        return {
            "suite": _serialize_suite(suite),
            "cases": [_serialize_case(c) for c in cases],
            "versions": [_serialize_version(v) for v in versions],
        }


def upsert_case(factory, *, project_id: str, suite_id: str, body) -> dict[str, Any]:
    with session_scope(factory) as session:
        suite = session.get(EvalSuite, suite_id)
        if suite is None or suite.owner_project_id != project_id:
            raise NotFoundError(code="eval_suite_not_found", message="评测集不存在。")
        existing = session.scalars(
            select(EvalCase).where(
                EvalCase.suite_id == suite_id, EvalCase.case_key == body.case_key
            )
        ).first()
        req_caps = body.required_capabilities or infer_case_required_capabilities(
            body.model_dump(mode="json")
        )
        if existing is None:
            row = EvalCase(
                id=str(uuid4()),
                suite_id=suite_id,
                case_key=body.case_key,
                split=body.split,
                schema_version=body.schema_version,
                required_capabilities_json=req_caps,
                turns_json=body.turns,
                simulation_json=body.simulation,
                expectations_json=body.expectations,
                metrics_json=body.metrics,
                metadata_json=body.metadata,
            )
            session.add(row)
            session.flush()
            return _serialize_case(row)
        existing.split = body.split
        existing.schema_version = body.schema_version
        existing.required_capabilities_json = req_caps
        existing.turns_json = body.turns
        existing.simulation_json = body.simulation
        existing.expectations_json = body.expectations
        existing.metrics_json = body.metrics
        existing.metadata_json = body.metadata
        session.flush()
        return _serialize_case(existing)


def delete_case(
    factory, *, project_id: str, suite_id: str, case_key: str
) -> dict[str, Any]:
    with session_scope(factory) as session:
        suite = session.get(EvalSuite, suite_id)
        if suite is None or suite.owner_project_id != project_id:
            raise NotFoundError(code="eval_suite_not_found", message="评测集不存在。")
        row = session.scalars(
            select(EvalCase).where(
                EvalCase.suite_id == suite_id, EvalCase.case_key == case_key
            )
        ).first()
        if row is None:
            raise NotFoundError(code="eval_case_not_found", message="测试用例不存在。")
        session.delete(row)
        return {"deleted": True, "case_key": case_key}


def publish_suite_version(
    factory, *, project_id: str, suite_id: str, actor_id: str
) -> dict[str, Any]:
    with session_scope(factory) as session:
        suite = session.get(EvalSuite, suite_id)
        if suite is None or suite.owner_project_id != project_id:
            raise NotFoundError(code="eval_suite_not_found", message="评测集不存在。")
        cases = session.scalars(
            select(EvalCase)
            .where(EvalCase.suite_id == suite_id)
            .order_by(EvalCase.case_key.asc())
        ).all()
        if not cases:
            raise BadRequestError(
                code="eval_suite_empty", message="空评测集无法发布冻结版本。"
            )
        frozen = [_serialize_case(c) for c in cases]
        latest = session.scalars(
            select(EvalSuiteVersion)
            .where(EvalSuiteVersion.suite_id == suite_id)
            .order_by(EvalSuiteVersion.version_num.desc())
        ).first()
        next_num = (latest.version_num if latest else 0) + 1
        version = EvalSuiteVersion(
            id=str(uuid4()),
            suite_id=suite_id,
            version_num=next_num,
            content_hash=_hash_payload(frozen),
            frozen_cases_json=frozen,
            published_by=actor_id,
        )
        session.add(version)
        session.flush()
        return _serialize_version(version)


def _compute_progress_dict(cases: list[EvalRunCase]) -> dict[str, Any]:
    counts = {
        "completed": 0,
        "failed": 0,
        "error": 0,
        "running": 0,
        "pending": 0,
        "paused": 0,
        "cancelled": 0,
        "skipped_incompatible": 0,
    }
    for c in cases:
        st = c.status or "pending"
        if st in counts:
            counts[st] += 1
        else:
            counts["pending"] += 1
    total = len(cases)
    active_total = total - counts["skipped_incompatible"]
    done = counts["completed"] + counts["failed"] + counts["error"]
    denom = active_total if active_total > 0 else total
    percent = int(round((done / denom) * 100)) if denom > 0 else 0
    return {
        "total": total,
        "active_total": active_total,
        "done": done,
        **counts,
        "percent": min(100, max(0, percent)),
    }


def create_run_record(
    factory,
    *,
    owner_project_id: str,
    actor_id: str,
    body,
    target_snapshot: dict[str, Any],
    incompatible_keys: set[str] | None = None,
    matrix_group_id: str | None = None,
) -> dict[str, Any]:
    with session_scope(factory) as session:
        suite = session.get(EvalSuite, str(body.suite_id))
        if suite is None or suite.owner_project_id != owner_project_id:
            raise NotFoundError(code="eval_suite_not_found", message="评测集不存在。")
        version = session.get(EvalSuiteVersion, str(body.version_id))
        if version is None or version.suite_id != suite.id:
            raise NotFoundError(
                code="eval_version_not_found", message="评测集冻结版本不存在。"
            )
        selected_keys = (
            set(body.case_keys) if getattr(body, "case_keys", None) else None
        )
        cases = [
            c
            for c in version.frozen_cases_json
            if selected_keys is None or c["case_key"] in selected_keys
        ]
        if not cases:
            raise BadRequestError(
                code="eval_cases_empty", message="没有可执行的测试用例。"
            )
        run_id = str(uuid4())
        incompatible = incompatible_keys or set()
        run_case_rows: list[EvalRunCase] = []
        for case in cases:
            for attempt_idx in range(1, body.repeat_k + 1):
                status = (
                    "skipped_incompatible"
                    if case["case_key"] in incompatible
                    else "pending"
                )
                row = EvalRunCase(
                    id=str(uuid4()),
                    run_id=run_id,
                    case_key=case["case_key"],
                    attempt_idx=attempt_idx,
                    status=status,
                )
                run_case_rows.append(row)
                session.add(row)
        run = EvalRun(
            id=run_id,
            suite_id=suite.id,
            version_id=version.id,
            owner_project_id=owner_project_id,
            target_project_id=body.target_project_id,
            target_graph_id=target_snapshot["agent"]["graph_id"],
            target_agent_id=str(target_snapshot["agent"]["id"]),
            target_model_id=str(target_snapshot["spec"]["model_id"]),
            target_snapshot_json=target_snapshot,
            judge_model_id=str(body.judge_model_id) if body.judge_model_id else None,
            embedding_model_id=(
                str(body.embedding_model_id) if body.embedding_model_id else None
            ),
            matrix_group_id=matrix_group_id,
            mode=getattr(body, "mode", "regression"),
            concurrency=body.concurrency,
            repeat_k=body.repeat_k,
            status="queued",
            summary_metrics_json={
                "total_cases": len(cases) * body.repeat_k,
                "progress": _compute_progress_dict(run_case_rows),
            },
            created_by=actor_id,
        )
        session.add(run)
        session.flush()
        return _serialize_run(run)


def list_runs(
    factory, *, project_id: str, suite_id: str | None = None
) -> dict[str, Any]:
    with session_scope(factory) as session:
        stmt = select(EvalRun).where(EvalRun.owner_project_id == project_id)
        if suite_id:
            stmt = stmt.where(EvalRun.suite_id == suite_id)
        rows = session.scalars(stmt.order_by(EvalRun.created_at.desc())).all()
        suite_names = {
            s.id: s.name
            for s in session.scalars(
                select(EvalSuite).where(EvalSuite.owner_project_id == project_id)
            ).all()
        }
        project_names = {
            str(p.id): p.name for p in session.scalars(select(ProjectRecord)).all()
        }
        version_ids = {r.version_id for r in rows if r.version_id}
        version_nums = (
            {
                v.id: v.version_num
                for v in session.scalars(
                    select(EvalSuiteVersion).where(EvalSuiteVersion.id.in_(version_ids))
                ).all()
            }
            if version_ids
            else {}
        )
        model_names = {
            str(m.id): m.display_name
            for m in session.scalars(select(RuntimeCatalogModelRecord)).all()
        }
        return {
            "items": [
                {
                    **_serialize_run(r),
                    "suite_name": suite_names.get(r.suite_id),
                    "target_project_name": project_names.get(r.target_project_id),
                    "version_num": version_nums.get(r.version_id),
                    "target_model_name": model_names.get(r.target_model_id),
                    "judge_model_name": (
                        model_names.get(r.judge_model_id) if r.judge_model_id else None
                    ),
                }
                for r in rows
            ]
        }


def get_run_execution_target(factory, *, run_id: str) -> dict[str, Any]:
    with session_scope(factory) as session:
        run = session.get(EvalRun, run_id)
        if run is None:
            raise NotFoundError(
                code="eval_run_not_found", message="评测运行记录不存在。"
            )
        return _serialize_run(run)


def get_run_detail(factory, *, project_id: str, run_id: str) -> dict[str, Any]:
    with session_scope(factory) as session:
        run = session.get(EvalRun, run_id)
        if run is None or run.owner_project_id != project_id:
            raise NotFoundError(
                code="eval_run_not_found", message="评测运行记录不存在。"
            )
        cases = session.scalars(
            select(EvalRunCase)
            .where(EvalRunCase.run_id == run_id)
            .order_by(EvalRunCase.case_key.asc(), EvalRunCase.attempt_idx.asc())
        ).all()
        suite = session.get(EvalSuite, run.suite_id)
        version = session.get(EvalSuiteVersion, run.version_id)
        model_names = {
            str(m.id): m.display_name
            for m in session.scalars(select(RuntimeCatalogModelRecord)).all()
        }
        return {
            "run": {
                **_serialize_run(run),
                "suite_name": suite.name if suite else None,
                "version_num": version.version_num if version else None,
                "target_model_name": model_names.get(run.target_model_id),
                "judge_model_name": (
                    model_names.get(run.judge_model_id) if run.judge_model_id else None
                ),
            },
            "cases": [_serialize_run_case(c) for c in cases],
        }


def delete_run(factory, *, project_id: str, run_id: str) -> dict[str, Any]:
    with session_scope(factory) as session:
        run = session.get(EvalRun, run_id)
        if run is None or run.owner_project_id != project_id:
            raise NotFoundError(
                code="eval_run_not_found", message="评测运行记录不存在。"
            )
        if run.status in {"queued", "running", "rescoring"}:
            raise ConflictError(
                code="eval_run_active_cannot_delete",
                message="任务正在队列或执行中，请先暂停或中止后再删除。",
            )
        patrols = session.scalars(
            select(EvalPatrolSchedule).where(EvalPatrolSchedule.last_run_id == run_id)
        ).all()
        for p in patrols:
            p.last_run_id = None
        case_ids_subq = select(EvalRunCase.id).where(EvalRunCase.run_id == run_id)
        session.execute(
            delete(EvalHumanReview).where(
                EvalHumanReview.run_case_id.in_(case_ids_subq)
            )
        )
        session.execute(delete(EvalRunCase).where(EvalRunCase.run_id == run_id))
        session.execute(delete(EvalRunLog).where(EvalRunLog.run_id == run_id))
        session.delete(run)
        session.flush()
        return {"deleted": True, "run_id": run_id}


def get_run_logs(
    factory,
    *,
    project_id: str,
    run_id: str,
    after_seq: int = 0,
    limit: int = 200,
    case_key: str | None = None,
    level: str | None = None,
) -> dict[str, Any]:
    with session_scope(factory) as session:
        run = session.get(EvalRun, run_id)
        if run is None or run.owner_project_id != project_id:
            raise NotFoundError(
                code="eval_run_not_found", message="评测运行记录不存在。"
            )
        clamped_limit = max(1, min(500, int(limit or 200)))
        stmt = (
            select(EvalRunLog)
            .where(EvalRunLog.run_id == run_id)
            .where(EvalRunLog.seq > after_seq)
        )
        if case_key:
            stmt = stmt.where(EvalRunLog.case_key == case_key)
        if level:
            stmt = stmt.where(EvalRunLog.level == level)
        rows = session.scalars(
            stmt.order_by(EvalRunLog.seq.asc()).limit(clamped_limit)
        ).all()
        summary = (
            run.summary_metrics_json
            if isinstance(run.summary_metrics_json, dict)
            else {}
        )
        progress = summary.get("progress")
        if not isinstance(progress, dict):
            cases = session.scalars(
                select(EvalRunCase).where(EvalRunCase.run_id == run_id)
            ).all()
            progress = _compute_progress_dict(cases)
        last_seq = rows[-1].seq if rows else after_seq
        return {
            "run_id": run_id,
            "status": run.status,
            "progress": progress,
            "logs": [
                {
                    "seq": r.seq,
                    "level": r.level,
                    "case_key": r.case_key,
                    "message": r.message,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ],
            "last_seq": last_seq,
        }


def control_run(
    factory, *, project_id: str, run_id: str, action: str
) -> dict[str, Any]:
    with session_scope(factory) as session:
        run = session.get(EvalRun, run_id)
        if run is None or run.owner_project_id != project_id:
            raise NotFoundError(
                code="eval_run_not_found", message="评测运行记录不存在。"
            )
        cases = session.scalars(
            select(EvalRunCase).where(EvalRunCase.run_id == run_id)
        ).all()
        if action == "pause":
            if run.status not in {"queued", "running"}:
                raise ConflictError(
                    code="eval_run_invalid_state",
                    message="仅队列中或运行中的任务可暂停。",
                )
            run.status = "paused"
        elif action == "cancel":
            run.status = "cancelled"
            run.finished_at = datetime.now(UTC)
            for c in cases:
                if c.status == "pending":
                    c.status = "cancelled"
        elif action == "resume":
            if run.status not in {"paused", "cancelled", "failed", "error"}:
                raise ConflictError(
                    code="eval_run_invalid_state",
                    message="当前状态不支持继续未完成任务。",
                )
            for c in cases:
                if c.status in {"paused", "cancelled"}:
                    c.status = "pending"
            run.status = "queued"
            run.finished_at = None
        elif action == "retry_failed":
            reset = 0
            for c in cases:
                if c.status in {"failed", "error"}:
                    c.status = "pending"
                    c.error_category = None
                    reset += 1
            if reset == 0:
                raise BadRequestError(
                    code="eval_no_failed_cases", message="没有可重跑的失败或异常用例。"
                )
            run.status = "queued"
            run.finished_at = None
        elif action == "rescore":
            run.status = "rescoring"
            run.finished_at = None
        prev_summary = (
            dict(run.summary_metrics_json)
            if isinstance(run.summary_metrics_json, dict)
            else {}
        )
        prev_summary["progress"] = _compute_progress_dict(cases)
        run.summary_metrics_json = prev_summary
        session.flush()
        return _serialize_run(run)


def _extract_frozen_case_meta(frozen_cases: Any) -> dict[str, dict[str, Any]]:
    meta: dict[str, dict[str, Any]] = {}
    if not isinstance(frozen_cases, list):
        return meta
    for raw in frozen_cases:
        if not isinstance(raw, dict):
            continue
        key = str(raw.get("case_key") or "")
        if not key:
            continue
        turns = raw.get("turns") if isinstance(raw.get("turns"), list) else []
        sim = raw.get("simulation") if isinstance(raw.get("simulation"), dict) else None
        exp = (
            raw.get("expectations") if isinstance(raw.get("expectations"), dict) else {}
        )
        question = ""
        if turns and isinstance(turns[0], dict):
            question = str(turns[0].get("content") or "")
        elif sim:
            question = str(sim.get("goal") or "")
        meta[key] = {
            "question": question,
            "expected_answer": str(exp.get("expected_answer") or ""),
            "mode": "simulation" if sim else "fixed",
        }
    return meta


def _serialize_compare_side(rc: EvalRunCase | None) -> dict[str, Any] | None:
    if rc is None:
        return None
    res = rc.results_json if isinstance(rc.results_json, dict) else {}
    return {
        "status": rc.status,
        "rule_passed": rc.rule_passed,
        "overall_score": rc.overall_score,
        "ttft_ms": rc.ttft_ms,
        "duration_ms": rc.duration_ms,
        "cost_usd": rc.cost_usd,
        "token_usage": rc.token_usage_json
        if isinstance(rc.token_usage_json, dict)
        else {},
        "error_category": rc.error_category,
        "final_answer": res.get("final_answer"),
        "metrics": res.get("metrics") if isinstance(res.get("metrics"), list) else [],
        "timing_breakdown": (
            res.get("timing_breakdown")
            if isinstance(res.get("timing_breakdown"), dict)
            else {}
        ),
        "transcript": res.get("transcript")
        if isinstance(res.get("transcript"), list)
        else [],
        "thread_id": rc.thread_id,
        "trace_ids": rc.trace_ids_json if isinstance(rc.trace_ids_json, list) else [],
    }


def compare_runs(
    factory, *, project_id: str, baseline_id: str, candidate_id: str
) -> dict[str, Any]:
    with session_scope(factory) as session:
        base = session.get(EvalRun, baseline_id)
        cand = session.get(EvalRun, candidate_id)
        if (
            base is None
            or cand is None
            or base.owner_project_id != project_id
            or cand.owner_project_id != project_id
        ):
            raise NotFoundError(
                code="eval_run_not_found", message="对比运行记录不存在。"
            )
        base_ver = session.get(EvalSuiteVersion, base.version_id)
        cand_ver = session.get(EvalSuiteVersion, cand.version_id)
        base_meta = _extract_frozen_case_meta(
            base_ver.frozen_cases_json if base_ver else []
        )
        cand_meta = _extract_frozen_case_meta(
            cand_ver.frozen_cases_json if cand_ver else []
        )
        suite_names = {
            s.id: s.name
            for s in session.scalars(
                select(EvalSuite).where(
                    EvalSuite.id.in_({base.suite_id, cand.suite_id})
                )
            ).all()
        }
        project_names = {
            str(p.id): p.name for p in session.scalars(select(ProjectRecord)).all()
        }
        base_cases = {
            (c.case_key, c.attempt_idx): c
            for c in session.scalars(
                select(EvalRunCase).where(EvalRunCase.run_id == baseline_id)
            ).all()
        }
        cand_cases = {
            (c.case_key, c.attempt_idx): c
            for c in session.scalars(
                select(EvalRunCase).where(EvalRunCase.run_id == candidate_id)
            ).all()
        }
        regressed, improved, unchanged = [], [], []
        for key in sorted(set(base_cases) | set(cand_cases)):
            b = base_cases.get(key)
            c = cand_cases.get(key)
            b_ok = bool(b and b.status == "completed" and b.rule_passed is not False)
            c_ok = bool(c and c.status == "completed" and c.rule_passed is not False)
            meta = cand_meta.get(key[0]) or base_meta.get(key[0]) or {}
            b_res = b.results_json if b and isinstance(b.results_json, dict) else {}
            c_res = c.results_json if c and isinstance(c.results_json, dict) else {}
            expected_answer = (
                meta.get("expected_answer")
                or c_res.get("expected_answer")
                or b_res.get("expected_answer")
                or ""
            )
            item = {
                "case_key": key[0],
                "attempt_idx": key[1],
                "mode": meta.get("mode", "fixed"),
                "question": meta.get("question") or "",
                "expected_answer": expected_answer,
                "baseline_score": b.overall_score if b else None,
                "candidate_score": c.overall_score if c else None,
                "baseline_status": b.status if b else None,
                "candidate_status": c.status if c else None,
                "baseline_ttft_ms": b.ttft_ms if b else None,
                "candidate_ttft_ms": c.ttft_ms if c else None,
                "baseline_duration_ms": b.duration_ms if b else None,
                "candidate_duration_ms": c.duration_ms if c else None,
                "baseline": _serialize_compare_side(b),
                "candidate": _serialize_compare_side(c),
            }
            if b_ok and not c_ok:
                regressed.append(item)
            elif not b_ok and c_ok:
                improved.append(item)
            elif (
                b is not None
                and c is not None
                and isinstance(b.overall_score, (int, float))
                and isinstance(c.overall_score, (int, float))
                and abs(c.overall_score - b.overall_score) >= 0.05
            ):
                if c.overall_score < b.overall_score:
                    regressed.append(item)
                else:
                    improved.append(item)
            else:
                unchanged.append(item)
        return {
            "compatible": base.version_id == cand.version_id,
            "baseline": {
                **_serialize_run(base),
                "suite_name": suite_names.get(base.suite_id),
                "target_project_name": project_names.get(base.target_project_id),
            },
            "candidate": {
                **_serialize_run(cand),
                "suite_name": suite_names.get(cand.suite_id),
                "target_project_name": project_names.get(cand.target_project_id),
            },
            "counts": {
                "regressed": len(regressed),
                "improved": len(improved),
                "unchanged": len(unchanged),
            },
            "regressed": regressed,
            "improved": improved,
            "unchanged": unchanged,
        }


def submit_human_review(
    factory, *, project_id: str, run_case_id: str, actor_id: str, body
) -> dict[str, Any]:
    with session_scope(factory) as session:
        rc = session.get(EvalRunCase, run_case_id)
        if rc is None:
            raise NotFoundError(
                code="eval_run_case_not_found", message="运行用例不存在。"
            )
        run = session.get(EvalRun, rc.run_id)
        if run is None or run.owner_project_id != project_id:
            raise NotFoundError(
                code="eval_run_case_not_found", message="运行用例不存在。"
            )
        judge_verdict = (
            "pass"
            if rc.status == "completed"
            and rc.rule_passed is not False
            and (rc.overall_score is None or rc.overall_score >= 0.6)
            else "fail"
        )
        review = EvalHumanReview(
            id=str(uuid4()),
            run_case_id=run_case_id,
            reviewer_id=actor_id,
            human_verdict=body.human_verdict,
            reason=body.reason,
            aligned_with_judge=(body.human_verdict == judge_verdict),
        )
        session.add(review)
        session.flush()
        return {
            "id": review.id,
            "run_case_id": review.run_case_id,
            "human_verdict": review.human_verdict,
            "aligned_with_judge": review.aligned_with_judge,
        }


def set_sandbox_flag(
    factory, *, project_id: str, actor_id: str, is_sandbox: bool
) -> dict[str, Any]:
    with session_scope(factory) as session:
        row = session.get(EvalSandboxProject, project_id)
        if row is None:
            row = EvalSandboxProject(
                project_id=project_id, is_sandbox=is_sandbox, updated_by=actor_id
            )
            session.add(row)
        else:
            row.is_sandbox = is_sandbox
            row.updated_by = actor_id
        session.flush()
        return {"project_id": row.project_id, "is_sandbox": row.is_sandbox}


def list_patrols(factory, *, project_id: str) -> dict[str, Any]:
    with session_scope(factory) as session:
        rows = session.scalars(
            select(EvalPatrolSchedule)
            .where(EvalPatrolSchedule.owner_project_id == project_id)
            .order_by(EvalPatrolSchedule.created_at.desc())
        ).all()
        return {
            "items": [
                {
                    "id": r.id,
                    "name": r.name,
                    "suite_id": r.suite_id,
                    "version_id": r.version_id,
                    "target_project_id": r.target_project_id,
                    "target_graph_id": r.target_graph_id,
                    "judge_model_id": r.judge_model_id,
                    "cron_expr": r.cron_expr,
                    "enabled": r.enabled,
                    "notify_channels": r.notify_channels_json,
                    "last_run_id": r.last_run_id,
                }
                for r in rows
            ]
        }


def create_patrol(factory, *, project_id: str, actor_id: str, body) -> dict[str, Any]:
    with session_scope(factory) as session:
        row = EvalPatrolSchedule(
            id=str(uuid4()),
            name=body.name.strip(),
            suite_id=str(body.suite_id),
            version_id=str(body.version_id),
            owner_project_id=project_id,
            target_project_id=body.target_project_id,
            target_graph_id=body.target_graph_id,
            judge_model_id=str(body.judge_model_id) if body.judge_model_id else None,
            cron_expr=body.cron_expr,
            enabled=body.enabled,
            notify_channels_json=body.notify_channels,
            created_by=actor_id,
        )
        session.add(row)
        session.flush()
        return {"id": row.id, "name": row.name, "enabled": row.enabled}


def read_diagnosis_evidence_slice(
    factory,
    *,
    project_id: str,
    run_id: str,
    ref: str,
    offset: int = 0,
    limit: int = 14000,
) -> dict[str, Any]:
    """Return bounded, paginated diagnosis evidence for runtime-service eval_diagnosis."""
    detail = get_run_detail(factory, project_id=project_id, run_id=run_id)
    if ref == "overview":
        payload = {"run": detail["run"], "case_count": len(detail["cases"])}
    elif ref == "list_cases":
        payload = [
            {
                "case_key": c["case_key"],
                "attempt_idx": c["attempt_idx"],
                "status": c["status"],
                "rule_passed": c["rule_passed"],
                "overall_score": c["overall_score"],
                "ttft_ms": c["ttft_ms"],
                "error_category": c["error_category"],
            }
            for c in detail["cases"][:500]
        ]
    elif ref.startswith("case:"):
        key = ref.removeprefix("case:")
        matches = [c for c in detail["cases"] if c["case_key"] == key]
        if not matches:
            raise NotFoundError(
                code="eval_case_not_found", message="未找到该用例证据。"
            )
        payload = matches
    else:
        raise BadRequestError(code="eval_ref_invalid", message="不支持的证据引用。")
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    return {
        "reference": ref if not offset else f"{ref}@{offset}",
        "offset": offset,
        "total_characters": len(text),
        "truncated": offset + limit < len(text),
        "content": text[offset : offset + limit],
    }


COPILOT_KNOWN_METRICS: frozenset[str] = frozenset(
    {
        "completion",
        "answer_contains",
        "artifact_correct",
        "protected_unchanged",
        "approval",
        "cross_project_denied",
        "tool_constraints",
        "clarification_requested",
        "retrieved",
        "turn_expectations",
        "tool_budget",
        "no_write",
        "RefusalAssertion",
        "CounterfactualAssertion",
        "Faithfulness",
        "ContextualRecall",
        "ContextualPrecision",
        "ConversationalGEval",
        "KnowledgeRetention",
        "ToolCorrectness",
        "ArgumentCorrectness",
        "StepEfficiency",
        "EvidenceBoundary",
        "BusinessFacts",
        "RecommendationGrounding",
        "TaskCompletion",
    }
)

_COPILOT_USER_MODES: frozenset[str] = frozenset(
    {
        "cooperative",
        "terse",
        "impatient_reversal",
        "skeptical_challenger",
        "ambiguous_changer",
    }
)
_COPILOT_ARTIFACT_KINDS: frozenset[str] = frozenset(
    {"equals", "contains", "json_equals", "json_subset", "csv_rows", "absent"}
)
_COPILOT_INTERRUPT_KEYS: frozenset[str] = frozenset(
    {
        "clarification_mode",
        "plan_review_policy",
        "max_plan_rejections",
        "tool_approval_policy",
    }
)
_RAG_METRICS: frozenset[str] = frozenset(
    {"retrieved", "Faithfulness", "ContextualRecall", "ContextualPrecision"}
)

GRAPH_KNOWN_TOOLS: dict[str, list[str]] = {
    "dearflow_agent": [
        "request_plan_review",
        "update_plan",
        "ls",
        "read_file",
        "glob",
        "grep",
        "write_file",
        "edit_file",
        "execute",
        "background_execute",
        "background_task",
        "cancel_background_task",
        "search_memory",
        "manage_memory",
        "list_skills",
        "review_skill_package",
        "find_skills",
        "deploy_preview",
        "fetch_web_guidelines",
        "request_information",
        "present_artifacts",
        "parse_document",
        "search_web",
        "fetch_page",
        "github_query",
        "arxiv_search",
        "write_todos",
        "task",
        "generate_image",
        "edit_image",
        "get_media_task",
    ],
    "showcase_demo": [
        "ls",
        "read_file",
        "write_file",
        "edit_file",
        "execute",
        "parse_document",
    ],
    "reference_agent": ["search_knowledge"],
    "workflow_demo": [],
}


_CASE_UPSERT_ALLOWED_KEYS = frozenset(
    {
        "case_key",
        "split",
        "schema_version",
        "required_capabilities",
        "turns",
        "simulation",
        "expectations",
        "metrics",
        "metadata",
    }
)


def normalize_copilot_case_dict(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize top-level fixture/expectations aliases, extra keys, and types into CaseUpsert-compatible dict."""
    item = dict(raw)
    turns = list(item.get("turns") or [])
    exp = (
        dict(item.get("expectations") or {})
        if isinstance(item.get("expectations"), dict)
        else {}
    )

    top_answer = item.pop("expected_answer", None)
    if top_answer is not None and "expected_answer" not in exp:
        exp["expected_answer"] = str(top_answer)

    top_artifacts = item.pop("expected_artifacts", None)
    if top_artifacts is None:
        top_artifacts = item.pop("artifacts", None)
    if top_artifacts is not None and not exp.get("artifacts"):
        if isinstance(top_artifacts, list):
            norm_arts: list[Any] = []
            for entry in top_artifacts:
                if isinstance(entry, str) and entry.strip():
                    norm_arts.append(
                        {
                            "path": entry.strip(),
                            "kind": "contains",
                            "expected": str(exp.get("expected_answer") or ""),
                        }
                    )
                elif isinstance(entry, dict):
                    norm_arts.append(entry)
            exp["artifacts"] = norm_arts
        elif isinstance(top_artifacts, dict):
            exp["artifacts"] = top_artifacts

    top_tc = item.pop("tool_constraints", None)
    top_protected = item.pop("protected_files", None)
    tc_obj = (
        dict(exp.get("tool_constraints") or {})
        if isinstance(exp.get("tool_constraints"), dict)
        else {}
    )
    if isinstance(top_tc, dict):
        tc_obj.update(top_tc)
    protected_list: list[str] = []
    if isinstance(top_protected, list):
        protected_list.extend(str(x) for x in top_protected if x)
    if isinstance(tc_obj.get("protected_files"), list):
        protected_list.extend(str(x) for x in tc_obj.pop("protected_files") if x)
    if tc_obj:
        clean_tc = {
            k: v
            for k, v in tc_obj.items()
            if k in {"required", "forbidden", "sequence", "arg_subsets"}
        }
        if clean_tc:
            exp["tool_constraints"] = clean_tc

    top_fixture = item.pop("fixture", None)
    fixture_map: dict[str, str] = (
        {str(k): str(v) for k, v in top_fixture.items()}
        if isinstance(top_fixture, dict)
        else {}
    )
    for pf in protected_list:
        fname = pf.rsplit("/", 1)[-1]
        if fname and fname not in fixture_map:
            fixture_map[fname] = f"Protected file baseline: {pf}\n"
    if fixture_map:
        if turns and isinstance(turns[0], dict):
            first = dict(turns[0])
            merged = dict(first.get("fixture") or {})
            merged.update(fixture_map)
            first["fixture"] = merged
            turns[0] = first
        elif item.get("simulation") and isinstance(item["simulation"], dict):
            goal = str(item["simulation"].get("goal") or "完成任务")
            turns = [{"role": "user", "content": goal, "fixture": fixture_map}]

    if exp:
        item["expectations"] = exp
    item["turns"] = turns
    if "schema_version" in item and item["schema_version"] is not None:
        item["schema_version"] = str(item["schema_version"])
    meta = (
        dict(item.get("metadata") or {})
        if isinstance(item.get("metadata"), dict)
        else {}
    )
    for extra_k in [k for k in list(item.keys()) if k not in _CASE_UPSERT_ALLOWED_KEYS]:
        meta[extra_k] = item.pop(extra_k)
    item["metadata"] = meta
    return item


def validate_copilot_case_draft(
    raw_item: dict[str, Any], *, graph_id: str | None = None
) -> dict[str, Any]:
    """Validate Case v3 Schema plus anti-pitfall checks matching eval-runner rules."""
    import re

    data = normalize_copilot_case_dict(raw_item)
    errors: list[str] = []
    warnings: list[str] = []

    case_key = str(data.get("case_key") or "").strip()
    if not case_key:
        errors.append("case_key_required")
    elif not re.fullmatch(r"[a-zA-Z0-9_.-]{1,128}", case_key):
        errors.append(f"invalid_case_key_format:{case_key}")

    split = data.get("split", "dev")
    if split not in {"dev", "holdout"}:
        errors.append(f"invalid_split:{split}")

    turns = data.get("turns") or []
    sim = data.get("simulation")
    if not turns and not sim:
        errors.append("turns_or_simulation_required")
    for idx, t in enumerate(turns):
        if not isinstance(t, dict):
            errors.append(f"turn_must_be_object:{idx}")
            continue
        role = str(t.get("role") or "user")
        if role not in {"user", "system"}:
            errors.append(
                f"invalid_turn_role:{idx}:{role}（turns[].role 仅允许 'user' 或 'system'）"
            )

    if isinstance(sim, dict):
        if not str(sim.get("goal") or "").strip():
            errors.append("simulation_goal_required")
        umode = str(sim.get("user_mode") or "cooperative")
        if umode not in _COPILOT_USER_MODES:
            errors.append(f"invalid_user_mode:{umode}")
        max_turns = sim.get("max_turns", 6)
        if not isinstance(max_turns, int) or not (1 <= max_turns <= 20):
            errors.append("simulation_max_turns_must_be_1_to_20")
        strat = sim.get("interrupt_strategy") or {}
        if isinstance(strat, dict):
            unknown_strat = sorted(set(strat) - _COPILOT_INTERRUPT_KEYS)
            if unknown_strat:
                errors.append(
                    f"unsupported_interrupt_strategy_keys:{','.join(unknown_strat)}"
                )

    metrics_raw = data.get("metrics") or []
    if not isinstance(metrics_raw, list) or not metrics_raw:
        errors.append("metrics_required")
        metric_names: list[str] = []
    else:
        metric_names = [
            str(m.get("name") if isinstance(m, dict) else m).strip()
            for m in metrics_raw
            if (m.get("name") if isinstance(m, dict) else m)
        ]
        unknown_metrics = [m for m in metric_names if m not in COPILOT_KNOWN_METRICS]
        if unknown_metrics:
            errors.append(f"unsupported_metrics:{','.join(unknown_metrics)}")

    exp = data.get("expectations") if isinstance(data.get("expectations"), dict) else {}
    arts = exp.get("artifacts")
    has_non_absent_artifact = False
    if isinstance(arts, list):
        for idx, spec in enumerate(arts):
            if not isinstance(spec, dict) or not spec.get("path"):
                errors.append(f"artifact_path_required:{idx}")
                continue
            kind = str(spec.get("kind") or "contains")
            if kind not in _COPILOT_ARTIFACT_KINDS:
                errors.append(f"unsupported_artifact_kind:{kind}")
            if kind != "absent":
                has_non_absent_artifact = True
    elif isinstance(arts, dict):
        for _p, rule in arts.items():
            if isinstance(rule, dict) and not rule.get("absent"):
                has_non_absent_artifact = True

    tc = (
        exp.get("tool_constraints")
        if isinstance(exp.get("tool_constraints"), dict)
        else {}
    )
    allowed_tools = GRAPH_KNOWN_TOOLS.get(graph_id or "dearflow_agent", [])
    if tc and allowed_tools:
        declared_tools: list[str] = []
        for k in ("required", "forbidden", "sequence"):
            vals = tc.get(k) or []
            if isinstance(vals, list):
                declared_tools.extend(str(x) for x in vals if x)
        if isinstance(tc.get("arg_subsets"), dict):
            declared_tools.extend(str(k) for k in tc["arg_subsets"])
        bad_tools = sorted(t for t in set(declared_tools) if t not in allowed_tools)
        if bad_tools:
            errors.append(
                f"unknown_tools_for_{graph_id or 'dearflow_agent'}:{','.join(bad_tools)}"
            )

    # Anti-pitfall checks: fixture placeholders, RAG guard, missing protected_unchanged/artifact_correct
    declared_fixtures: set[str] = set()
    for t in turns:
        if isinstance(t, dict) and isinstance(t.get("fixture"), dict):
            declared_fixtures.update(str(k) for k in t["fixture"])
    if isinstance(sim, dict):
        df = sim.get("delayed_fixtures")
        if isinstance(df, list):
            for entry in df:
                if isinstance(entry, dict) and isinstance(entry.get("files"), dict):
                    declared_fixtures.update(str(k) for k in entry["files"])
        elif isinstance(df, dict):
            for files_map in df.values():
                if isinstance(files_map, dict):
                    declared_fixtures.update(str(k) for k in files_map)

    all_prompt_text = " ".join(
        [str(t.get("content") or "") for t in turns if isinstance(t, dict)]
        + ([str(sim.get("goal") or "")] if isinstance(sim, dict) else [])
    )
    placeholders = set(re.findall(r"\{\{([^{}]+)\}\}", all_prompt_text))
    missing_placeholders = sorted(p for p in placeholders if p not in declared_fixtures)
    if missing_placeholders:
        errors.append(
            f"undeclared_fixture_placeholders:{','.join(missing_placeholders)}"
        )

    rag_selected = [m for m in metric_names if m in _RAG_METRICS]
    if rag_selected:
        rag_intent_words = ("rag", "知识库", "检索", "search_knowledge", "文档召回")
        mentions_rag = any(w in all_prompt_text.lower() for w in rag_intent_words) or (
            graph_id == "reference_agent"
        )
        if not mentions_rag:
            errors.append(
                f"non_rag_case_with_rag_metrics:{','.join(rag_selected)}（非知识库检索题选这些指标会在运行期触发 contexts_state 熔断必败，请移除）"
            )

    if declared_fixtures and "protected_unchanged" not in metric_names:
        warnings.append(
            "已挂载初始 fixture 夹具，建议补充 protected_unchanged 指标保护原文件。"
        )
    if has_non_absent_artifact and "artifact_correct" not in metric_names:
        errors.append(
            "expectations.artifacts 已配置目标产物校验，必须勾选 artifact_correct。"
        )
    if isinstance(sim, dict) and "ConversationalGEval" not in metric_names:
        warnings.append("已启用中文动态多轮仿真，建议勾选 ConversationalGEval。")

    return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}


def copilot_list_suites(factory, *, project_id: str) -> dict[str, Any]:
    return list_suites(factory, project_id=project_id, include_archived=False)


def _safe_uuid(value: str) -> Any:
    from uuid import UUID

    try:
        return UUID(str(value))
    except (ValueError, TypeError):
        return None


def copilot_list_capabilities(factory, *, project_id: str) -> dict[str, Any]:
    pid_uuid = _safe_uuid(project_id)
    with session_scope(factory) as session:
        agents = (
            session.scalars(
                select(AgentRecord)
                .where(AgentRecord.project_id == pid_uuid)
                .order_by(AgentRecord.created_at.desc())
            ).all()
            if pid_uuid is not None
            else []
        )
        models = session.scalars(
            select(RuntimeCatalogModelRecord).where(
                RuntimeCatalogModelRecord.enabled.is_(True)
            )
        ).all()
    return {
        "graphs": {
            gid: {
                "features": _DEFAULT_GRAPH_FEATURES.get(gid, {}),
                "tools": GRAPH_KNOWN_TOOLS.get(gid, []),
            }
            for gid in sorted(_DEFAULT_GRAPH_FEATURES)
        },
        "project_agents": [
            {
                "id": str(a.id),
                "name": a.name,
                "graph_id": a.graph_id,
                "status": a.status,
            }
            for a in agents
            if a.graph_id in _DEFAULT_GRAPH_FEATURES
        ],
        "enabled_models": [
            {
                "id": str(m.id),
                "provider": m.provider,
                "model_name": m.model_name,
                "display_name": m.display_name,
            }
            for m in models
            if "broken" not in (m.model_name or "").lower()
        ],
        "known_metrics": sorted(COPILOT_KNOWN_METRICS),
    }


def copilot_list_failures(
    factory,
    *,
    project_id: str,
    suite_id: str | None = None,
    run_id: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    with session_scope(factory) as session:
        if run_id:
            run = session.get(EvalRun, run_id)
            if run is None or run.owner_project_id != project_id:
                raise NotFoundError(
                    code="eval_run_not_found", message="评测运行记录不存在。"
                )
            runs = [run]
        else:
            stmt = select(EvalRun).where(EvalRun.owner_project_id == project_id)
            if suite_id:
                stmt = stmt.where(EvalRun.suite_id == suite_id)
            runs = session.scalars(
                stmt.order_by(EvalRun.created_at.desc()).limit(5)
            ).all()
        items: list[dict[str, Any]] = []
        for run in runs:
            bad_cases = session.scalars(
                select(EvalRunCase)
                .where(
                    EvalRunCase.run_id == run.id,
                    EvalRunCase.status.in_(["failed", "error"]),
                )
                .order_by(EvalRunCase.case_key.asc())
            ).all()
            for rc in bad_cases:
                res = rc.results_json if isinstance(rc.results_json, dict) else {}
                failed_metrics = [
                    {"name": m.get("name"), "reason": m.get("reason")}
                    for m in (res.get("metrics") or [])
                    if isinstance(m, dict) and not m.get("passed", True)
                ]
                items.append(
                    {
                        "run_id": run.id,
                        "suite_id": run.suite_id,
                        "case_key": rc.case_key,
                        "status": rc.status,
                        "error_category": rc.error_category,
                        "overall_score": rc.overall_score,
                        "failed_metrics": failed_metrics,
                    }
                )
                if len(items) >= limit:
                    return {"items": items}
        return {"items": items}


def copilot_save_cases(
    factory,
    *,
    project_id: str,
    suite_id: str,
    items: list[dict[str, Any]],
    mode: str = "create_only",
) -> dict[str, Any]:
    from pydantic import ValidationError

    from platform_api.modules.evaluation.studio_schemas import CaseUpsert

    if not items:
        raise BadRequestError(
            code="copilot_cases_empty", message="至少需要提供一道考题。"
        )
    with session_scope(factory) as session:
        suite = session.get(EvalSuite, suite_id)
        if suite is None or suite.owner_project_id != project_id:
            raise NotFoundError(code="eval_suite_not_found", message="评测集不存在。")
        graph_id = suite.default_graph_id
        existing_keys = set(
            session.scalars(
                select(EvalCase.case_key).where(EvalCase.suite_id == suite_id)
            ).all()
        )

    normalized_bodies: list[CaseUpsert] = []
    validation_errors: list[str] = []
    overwrite_keys: list[str] = []
    for raw in items:
        norm = normalize_copilot_case_dict(raw)
        chk = validate_copilot_case_draft(norm, graph_id=graph_id)
        if not chk["valid"]:
            validation_errors.extend(chk["errors"])
            continue
        try:
            body = CaseUpsert.model_validate(norm)
        except ValidationError as exc:
            validation_errors.append(
                f"schema_validation_error:{exc.errors()[0].get('loc')}:{exc.errors()[0].get('msg')}"
            )
            continue
        normalized_bodies.append(body)
        if body.case_key in existing_keys:
            overwrite_keys.append(body.case_key)

    if validation_errors:
        raise BadRequestError(
            code="copilot_case_validation_failed",
            message="; ".join(validation_errors),
        )
    if mode == "create_only":
        if overwrite_keys:
            raise ConflictError(
                code="copilot_overwrite_approval_required",
                message=f"以下题目已存在，需经用户批准后通过 update_existing_eval_cases 修改：{', '.join(overwrite_keys)}",
            )
        if len(normalized_bodies) >= 5:
            raise ConflictError(
                code="copilot_batch_approval_required",
                message="单次写入 5 题及以上需经用户批准确认，请调用 update_existing_eval_cases。",
            )

    created: list[str] = []
    updated: list[str] = []
    saved_items: list[dict[str, Any]] = []
    for body in normalized_bodies:
        if body.case_key in existing_keys:
            updated.append(body.case_key)
        else:
            created.append(body.case_key)
        saved_items.append(
            upsert_case(factory, project_id=project_id, suite_id=suite_id, body=body)
        )
    return {
        "suite_id": suite_id,
        "created": created,
        "updated": updated,
        "items": saved_items,
    }


def copilot_prepare_trial_version(
    factory,
    *,
    project_id: str,
    suite_id: str,
    actor_id: str,
    case_keys: list[str],
    target_project_id: str | None = None,
    agent_id: str | None = None,
    model_id: str | None = None,
    judge_model_id: str | None = None,
) -> dict[str, Any]:
    """Select trial cases, publish immutable snapshot, and resolve safe sandbox target & models."""
    with session_scope(factory) as session:
        suite = session.get(EvalSuite, suite_id)
        if suite is None or suite.owner_project_id != project_id:
            raise NotFoundError(code="eval_suite_not_found", message="评测集不存在。")
        all_cases = session.scalars(
            select(EvalCase)
            .where(EvalCase.suite_id == suite_id)
            .order_by(EvalCase.case_key.asc())
        ).all()
        by_key = {c.case_key: c for c in all_cases}
        missing = [k for k in case_keys if k not in by_key]
        if missing:
            raise NotFoundError(
                code="eval_case_not_found",
                message=f"以下待试跑题目不存在：{', '.join(missing)}",
            )
        sandbox_rows = session.scalars(
            select(EvalSandboxProject).where(EvalSandboxProject.is_sandbox.is_(True))
        ).all()
        sandbox_ids = {r.project_id for r in sandbox_rows}
        resolved_target_pid = target_project_id or (
            project_id
            if project_id in sandbox_ids
            else (next(iter(sandbox_ids), project_id))
        )
        target_uuid = _safe_uuid(resolved_target_pid)
        agents = (
            session.scalars(
                select(AgentRecord).where(
                    AgentRecord.project_id == target_uuid,
                    AgentRecord.status == "active",
                )
            ).all()
            if target_uuid is not None
            else []
        )
        proj_uuid = _safe_uuid(project_id)
        if not agents and resolved_target_pid != project_id and proj_uuid is not None:
            resolved_target_pid = project_id
            agents = session.scalars(
                select(AgentRecord).where(
                    AgentRecord.project_id == proj_uuid,
                    AgentRecord.status == "active",
                )
            ).all()

        picked_agent = None
        if agent_id:
            picked_agent = next((a for a in agents if str(a.id) == agent_id), None)
        if picked_agent is None:
            picked_agent = next(
                (a for a in agents if a.graph_id == suite.default_graph_id), None
            ) or next(
                (a for a in agents if a.graph_id in _DEFAULT_GRAPH_FEATURES), None
            )
        if picked_agent is None:
            raise BadRequestError(
                code="eval_trial_agent_unavailable",
                message="目标项目缺少可评测的活跃 Agent。",
            )

        models = session.scalars(
            select(RuntimeCatalogModelRecord).where(
                RuntimeCatalogModelRecord.enabled.is_(True)
            )
        ).all()
        safe_models = [
            m for m in models if "broken" not in (m.model_name or "").lower()
        ]
        picked_model = None
        if model_id:
            picked_model = next((m for m in safe_models if str(m.id) == model_id), None)
        if picked_model is None:
            picked_model = (
                next(
                    (
                        m
                        for m in safe_models
                        if (m.provider or "").lower() == "chickener"
                        and "deepseek" in (m.model_name or "").lower()
                    ),
                    None,
                )
                or next(
                    (
                        m
                        for m in safe_models
                        if (m.provider or "").lower() == "xiaok"
                        and "deepseek" in (m.model_name or "").lower()
                    ),
                    None,
                )
                or next(
                    (
                        m
                        for m in safe_models
                        if "deepseek" in (m.model_name or "").lower()
                    ),
                    None,
                )
                or (safe_models[0] if safe_models else None)
            )
        if picked_model is None:
            raise BadRequestError(
                code="eval_trial_model_unavailable",
                message="平台目录缺少可用大模型连接。",
            )
        picked_judge = None
        if judge_model_id:
            picked_judge = next(
                (m for m in safe_models if str(m.id) == judge_model_id), None
            )
        if picked_judge is None:
            picked_judge = picked_model

    version = publish_suite_version(
        factory, project_id=project_id, suite_id=suite_id, actor_id=actor_id
    )
    return {
        "version": version,
        "target_project_id": resolved_target_pid,
        "agent_id": str(picked_agent.id),
        "model_id": str(picked_model.id),
        "judge_model_id": str(picked_judge.id),
    }


def copilot_run_status(
    factory, *, project_id: str, run_id: str, case_key: str | None = None
) -> dict[str, Any]:
    detail = get_run_detail(factory, project_id=project_id, run_id=run_id)
    cases = detail["cases"]
    if case_key:
        cases = [c for c in cases if c["case_key"] == case_key]
    return {
        "run": detail["run"],
        "cases": [
            {
                "case_key": c["case_key"],
                "attempt_idx": c["attempt_idx"],
                "status": c["status"],
                "rule_passed": c["rule_passed"],
                "overall_score": c["overall_score"],
                "ttft_ms": c["ttft_ms"],
                "duration_ms": c["duration_ms"],
                "error_category": c["error_category"],
                "final_answer": (c.get("results") or {}).get("final_answer"),
                "metrics": (c.get("results") or {}).get("metrics") or [],
                "tool_events": (c.get("results") or {}).get("tool_events") or [],
                "artifacts": (c.get("results") or {}).get("artifacts") or {},
                "artifact_read_errors": (
                    (c.get("results") or {}).get("checks") or {}
                ).get("artifact_read_errors")
                or {},
                "simulation": (c.get("results") or {}).get("simulation") or {},
            }
            for c in cases
        ],
    }


def copilot_control_run(
    factory,
    *,
    project_id: str,
    run_id: str,
    action: str,
    copilot_thread_id: str | None = None,
    require_own: bool = False,
) -> dict[str, Any]:
    with session_scope(factory) as session:
        run = session.get(EvalRun, run_id)
        if run is None or run.owner_project_id != project_id:
            raise NotFoundError(
                code="eval_run_not_found", message="评测运行记录不存在。"
            )
        if require_own:
            snap = (
                run.target_snapshot_json
                if isinstance(run.target_snapshot_json, dict)
                else {}
            )
            if (
                not copilot_thread_id
                or snap.get("copilot_thread_id") != copilot_thread_id
            ):
                raise ConflictError(
                    code="copilot_external_run_approval_required",
                    message="该评测任务并非由当前出题会话发起，终止外部评测须经确认。",
                )
    return control_run(factory, project_id=project_id, run_id=run_id, action=action)
