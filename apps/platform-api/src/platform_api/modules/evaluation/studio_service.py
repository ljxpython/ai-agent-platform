"""Sync SQLAlchemy control-plane service for native evaluation studio."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from platform_api.core.db import session_scope
from platform_api.core.errors import BadRequestError, ConflictError, NotFoundError
from platform_api.modules.evaluation.models import (
    EvalCase,
    EvalHumanReview,
    EvalPatrolSchedule,
    EvalRun,
    EvalRunCase,
    EvalSandboxProject,
    EvalSuite,
    EvalSuiteVersion,
)
from platform_api.modules.evaluation.targets import infer_case_required_capabilities
from platform_api.modules.projects.models import ProjectRecord


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
        run = EvalRun(
            id=str(uuid4()),
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
            summary_metrics_json={"total_cases": len(cases) * body.repeat_k},
            created_by=actor_id,
        )
        session.add(run)
        incompatible = incompatible_keys or set()
        for case in cases:
            for attempt_idx in range(1, body.repeat_k + 1):
                status = (
                    "skipped_incompatible"
                    if case["case_key"] in incompatible
                    else "pending"
                )
                session.add(
                    EvalRunCase(
                        id=str(uuid4()),
                        run_id=run.id,
                        case_key=case["case_key"],
                        attempt_idx=attempt_idx,
                        status=status,
                    )
                )
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
        return {
            "items": [
                {
                    **_serialize_run(r),
                    "suite_name": suite_names.get(r.suite_id),
                    "target_project_name": project_names.get(r.target_project_id),
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
        return {
            "run": _serialize_run(run),
            "cases": [_serialize_run_case(c) for c in cases],
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
