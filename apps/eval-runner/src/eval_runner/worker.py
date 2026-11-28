"""Database-backed polling worker connecting platform-api eval_* tables and ConcurrentEvalRunner."""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine, inspect, text

from eval_runner.domain.contracts import Case, Evidence, GateLimits
from eval_runner.domain.metrics_summary import (
    compute_progress_summary,
    summarize_run_cases,
)
from eval_runner.engine.concurrent_runner import ConcurrentEvalRunner
from eval_runner.engine.simulation import DynamicSimulationSession
from eval_runner.evidence.context_and_artifacts import extract_retrieved_contexts
from eval_runner.evidence.runtime_signals import recover_loop_signals
from eval_runner.evidence.tool_evidence import extract_tool_evidence
from eval_runner.scorers.deepeval_adapter import DEEPEVAL_METRICS, evaluate_l2_deepeval
from eval_runner.scorers.judge import (
    JudgeBudget,
    PlatformJudgeLLM,
    estimate_tokens_cost_usd,
)
from eval_runner.scorers.rules import _normalize_artifact_specs
from eval_runner.targets.platform_client import (
    InternalExecutionClient,
    PlatformModelResolver,
)
from eval_runner.targets.sse_probe import normalize_interrupts

logger = logging.getLogger(__name__)


def _replace_fixture_placeholders(text: str, fixture_paths: dict[str, str]) -> str:
    out = text
    for name, path in fixture_paths.items():
        out = out.replace(f"{{{{{name}}}}}", path)
    return out


def _expected_artifact_paths(case: Case) -> list[str]:
    paths: list[str] = list(case.expectations.get("initial_artifacts") or [])
    for spec in _normalize_artifact_specs(case.expectations.get("artifacts")):
        if spec.get("path"):
            paths.append(str(spec["path"]))
    for turn_exp in case.turn_expectations or []:
        for spec in _normalize_artifact_specs(turn_exp.get("artifacts")):
            if spec.get("path"):
                paths.append(str(spec["path"]))
    return list(dict.fromkeys(paths))


def build_platform_executors(
    *,
    base_url: str,
    internal_secret: str,
    run_id: str,
    target_project_id: str,
    judge_model_id: str | None = None,
    emit_log: Callable[[str, str | None, str], None] | None = None,
):
    """Build real SSE turn executor with simulation/interrupts/whitebox extraction and L2 scorer."""
    exec_client = InternalExecutionClient(base_url, internal_secret)
    resolver = PlatformModelResolver(base_url, internal_secret)
    log_fn = emit_log or (lambda _lvl, _k, _msg: None)

    def _execute(case: Case, attempt_idx: int) -> Evidence:
        static_turns = list(case.turns)
        if not static_turns and case.simulation and case.simulation.goal.strip():
            from eval_runner.domain.contracts import Turn

            static_turns = [Turn(role="user", content=case.simulation.goal.strip())]
        if not static_turns:
            return Evidence(
                case_key=case.case_key,
                attempt_idx=attempt_idx,
                final_answer="",
                terminal_status="error",
                error_category="runtime_error",
            )

        thread_id: str | None = None
        trace_ids: list[str] = []
        transcript: list[dict[str, Any]] = []
        fixture_paths: dict[str, str] = {}
        initial_artifacts: dict[str, str] = {}
        approval_snapshots: list[dict[str, Any]] = []
        turn_snapshots: list[dict[str, Any]] = []
        ttft_ms: int | None = None
        total_duration = 0
        final_answer = ""
        terminal_status = "success"
        error_category = "none"
        stream_recovered = False

        sim_judge: PlatformJudgeLLM | None = None
        sim_session: DynamicSimulationSession | None = None
        if case.simulation is not None:
            if judge_model_id:
                try:
                    sim_conn = resolver.resolve(
                        project_id=target_project_id, model_id=judge_model_id
                    )
                    sim_judge = PlatformJudgeLLM(
                        sim_conn,
                        budget=JudgeBudget(max_requests_per_case=case.simulation.max_requests),
                    )
                except Exception:  # noqa: BLE001
                    sim_judge = None
            sim_session = DynamicSimulationSession(case, judge=sim_judge)

        expected_art_paths = _expected_artifact_paths(case)
        needs_workspace = bool(
            case.fixture
            or expected_art_paths
            or (
                case.simulation is not None
                and (case.simulation.interrupt_strategy or {}).get("tool_approval_policy") != "reject"
            )
            or any(m.name in {"artifact_correct", "protected_unchanged", "approval"} for m in case.metrics)
        )
        if case.fixture or needs_workspace:
            setup_res = exec_client.thread_setup(
                run_id=run_id,
                fixtures=case.fixture,
                ensure_workspace=needs_workspace and not case.fixture,
            )
            if isinstance(setup_res, dict) and setup_res.get("thread_id"):
                thread_id = str(setup_res["thread_id"])
                fixture_paths.update(setup_res.get("fixture_paths") or {})
                initial_artifacts.update(setup_res.get("initial_artifacts") or {})

        plan_context: dict[str, Any] = {}
        if case.simulation is not None:
            strat = case.simulation.interrupt_strategy or {}
            if strat.get("plan_review_policy") == "critique_then_approve":
                plan_context["plan_mode"] = True

        max_rounds = case.simulation.max_turns if case.simulation is not None else len(static_turns)
        next_prompt = static_turns[0].content
        pending_fixtures: dict[str, str] = dict(static_turns[0].fixture)

        for turn_idx in range(max_rounds):
            if pending_fixtures:
                up = exec_client.thread_setup(
                    run_id=run_id,
                    thread_id=thread_id,
                    fixtures=pending_fixtures,
                )
                if isinstance(up, dict):
                    if up.get("thread_id") and not thread_id:
                        thread_id = str(up["thread_id"])
                    fixture_paths.update(up.get("fixture_paths") or {})
                    initial_artifacts.update(up.get("initial_artifacts") or {})
                pending_fixtures = {}

            resolved_prompt = _replace_fixture_placeholders(next_prompt, fixture_paths)
            transcript.append({"role": "user", "content": resolved_prompt})
            thread_id, probe = exec_client.execute_turn(
                run_id=run_id,
                content=resolved_prompt,
                thread_id=thread_id,
                context_overrides=plan_context or None,
            )
            if probe.run_id:
                trace_ids.append(probe.run_id)
            if ttft_ms is None and probe.ttft_ms is not None:
                ttft_ms = probe.ttft_ms
            total_duration += probe.duration_ms
            turn_answer = probe.final_text
            log_fn(
                "INFO",
                case.case_key,
                (
                    f"[{case.case_key} #{attempt_idx}] 第 {turn_idx + 1} 轮响应完成 · "
                    f"TTFT={probe.ttft_ms if probe.ttft_ms is not None else '-'}ms · "
                    f"耗时={probe.duration_ms}ms · 状态={probe.terminal_status}"
                ),
            )

            # Handle HITL __interrupt__ resume loop (Clarification, Plan Review, Tool Approval)
            def _sync_interrupts_from_state() -> None:
                if not thread_id:
                    return
                if probe.interrupts:
                    probe.interrupts = normalize_interrupts(probe.interrupts)
                if (not probe.interrupts) and probe.terminal_status in {"success", "interrupted"}:
                    chk = exec_client.thread_evidence(
                        run_id=run_id,
                        thread_id=thread_id,
                        run_ids=[probe.run_id] if probe.run_id else [],
                    )
                    st = (chk or {}).get("state") or {}
                    st_interrupts = normalize_interrupts(st.get("interrupts"))
                    if st_interrupts:
                        probe.interrupts = st_interrupts
                        probe.terminal_status = "interrupted"

            _sync_interrupts_from_state()
            interrupt_loops = 0
            while (
                probe.terminal_status == "interrupted"
                and probe.interrupts
                and thread_id
                and interrupt_loops < 6
            ):
                interrupt_loops += 1
                if sim_session is not None:
                    res = sim_session.resolve_interrupt(probe.interrupts, turn_idx)
                    if res.get("error"):
                        terminal_status = "interrupted"
                        break
                    if res.get("kind") == "approval":
                        pre_ev = exec_client.thread_evidence(
                            run_id=run_id,
                            thread_id=thread_id,
                            artifact_paths=expected_art_paths,
                        )
                        approval_snapshots.append(
                            {
                                "turn_index": turn_idx,
                                "decision": res.get("decision"),
                                "artifacts_before": (pre_ev or {}).get("artifacts") or {},
                            }
                        )
                    log_fn(
                        "INFO",
                        case.case_key,
                        (
                            f"[{case.case_key} #{attempt_idx}] 捕获中断"
                            f"({res.get('kind') or 'interrupt'}) -> 决策={res.get('decision', 'submitted')}"
                        ),
                    )
                    resume_payload = res["resumes"]
                else:
                    # Static fallback: approve if approval requested, else break
                    static_turn = static_turns[turn_idx] if turn_idx < len(static_turns) else None
                    first_val = (probe.interrupts[0] or {}).get("value") or {}
                    if isinstance(first_val, dict) and first_val.get("action_requests"):
                        dec = (static_turn.approval if static_turn and static_turn.approval in {"approve", "reject"} else "approve")
                        pre_ev = exec_client.thread_evidence(
                            run_id=run_id,
                            thread_id=thread_id,
                            artifact_paths=expected_art_paths,
                        )
                        approval_snapshots.append(
                            {"turn_index": turn_idx, "decision": dec, "artifacts_before": (pre_ev or {}).get("artifacts") or {}}
                        )
                        resume_payload = {
                            it["id"]: {
                                "decisions": [{"type": dec} for _ in (it.get("value") or {}).get("action_requests", [{}])]
                            }
                            for it in probe.interrupts
                        }
                    else:
                        break

                thread_id, probe = exec_client.execute_turn(
                    run_id=run_id,
                    thread_id=thread_id,
                    command={"resume": resume_payload},
                    context_overrides=plan_context or None,
                )
                if probe.run_id:
                    trace_ids.append(probe.run_id)
                total_duration += probe.duration_ms
                if probe.final_text:
                    turn_answer = probe.final_text
                _sync_interrupts_from_state()

            # Attempt recovery on SSE stream_timeout without replaying side effects
            if probe.terminal_status == "error" and probe.error_category == "stream_timeout" and thread_id:
                rec_ev = exec_client.thread_evidence(
                    run_id=run_id,
                    thread_id=thread_id,
                    run_ids=trace_ids,
                )
                runs_list = (rec_ev or {}).get("runs") or []
                settled_ok = any(isinstance(r, dict) and r.get("status") == "success" for r in runs_list)
                msgs = ((rec_ev or {}).get("state") or {}).get("values", {}).get("messages") or []
                last_ai = next(
                    (
                        str(m.get("content") or "")
                        for m in reversed(msgs)
                        if isinstance(m, dict) and str(m.get("role") or m.get("type") or "").lower() in {"assistant", "ai"} and m.get("content")
                    ),
                    "",
                )
                if settled_ok and last_ai:
                    turn_answer = last_ai
                    probe.terminal_status = "success"
                    probe.error_category = "none"
                    stream_recovered = True
                    log_fn(
                        "WARN",
                        case.case_key,
                        f"[{case.case_key} #{attempt_idx}] SSE 超时后已从线程终态安全恢复输出",
                    )

            if turn_answer:
                final_answer = turn_answer
            transcript.append(
                {
                    "role": "assistant",
                    "content": turn_answer,
                    "ttft_ms": probe.ttft_ms,
                    "duration_ms": probe.duration_ms,
                    "run_id": probe.run_id,
                }
            )
            turn_snapshots.append({"index": turn_idx, "answer": turn_answer, "artifacts": {}})

            if probe.terminal_status != "success":
                terminal_status = probe.terminal_status
                error_category = probe.error_category if probe.error_category != "none" else "runtime_error"
                if sim_session is not None:
                    sim_session.stop_reason = (
                        error_category if error_category != "none" else probe.terminal_status
                    )
                break

            if sim_session is not None:
                if turn_idx + 1 >= max_rounds:
                    sim_session.stop_reason = "turn_limit"
                    break
                hist = [
                    {
                        "user": transcript[i].get("content", ""),
                        "assistant": transcript[i + 1].get("content", ""),
                    }
                    for i in range(0, len(transcript) - 1, 2)
                ]
                decision, up_files, nxt_msg = sim_session.decide_next_turn(hist, turn_idx)
                if decision.action == "stop":
                    break
                next_prompt = nxt_msg
                pending_fixtures = up_files
            else:
                if turn_idx + 1 >= len(static_turns):
                    break
                next_prompt = static_turns[turn_idx + 1].content
                pending_fixtures = dict(static_turns[turn_idx + 1].fixture)

        # Post-execution authoritative whitebox evidence collection
        messages: list[dict[str, Any]] = []
        artifacts: dict[str, str] = {}
        artifact_read_errors: dict[str, str] = {}
        tool_events: list[dict[str, Any]] = []
        tool_complete = True
        retrieved_contexts: list[str] = []
        contexts_state = "not_recorded"
        loop_signals = 0
        loop_observed = False
        cross_project_status: int | None = None

        if thread_id:
            ev_bundle = exec_client.thread_evidence(
                run_id=run_id,
                thread_id=thread_id,
                run_ids=trace_ids,
                artifact_paths=expected_art_paths + list(initial_artifacts.keys()),
            )
            if isinstance(ev_bundle, dict):
                raw_state = ev_bundle.get("state") or {}
                raw_msgs = (raw_state.get("values") or {}).get("messages") or []
                if isinstance(raw_msgs, list):
                    messages = [m for m in raw_msgs if isinstance(m, dict)]
                artifacts = dict(ev_bundle.get("artifacts") or {})
                artifact_read_errors = dict(ev_bundle.get("artifact_read_errors") or {})
                rejected = sim_session.rejected_interrupts if sim_session else []
                tool_events, tool_complete = extract_tool_evidence(
                    messages, rejected_interrupts=rejected
                )
                retrieved_contexts, contexts_state = extract_retrieved_contexts(messages)
                loop_signals, loop_observed = recover_loop_signals(
                    ev_bundle.get("diagnostics") or []
                )
                log_fn(
                    "INFO",
                    case.case_key,
                    (
                        f"[{case.case_key} #{attempt_idx}] 白盒取证完成 · 工具={len(tool_events)}步 · "
                        f"死循环信号={loop_signals}"
                    ),
                )
            else:
                tool_complete = False

            if case.expectations.get("cross_project_probe") or any(
                m.name == "cross_project_denied" for m in case.metrics
            ):
                probe_res = exec_client.cross_project_probe(
                    run_id=run_id, thread_id=thread_id
                )
                if isinstance(probe_res, dict) and probe_res.get("status_code") is not None:
                    cross_project_status = int(probe_res["status_code"])

        if turn_snapshots and artifacts:
            turn_snapshots[-1]["artifacts"] = artifacts

        usage_summary: dict[str, Any] = {}
        agent_cost_usd = 0.0
        if thread_id:
            raw_usage = exec_client.get_thread_usage(run_id=run_id, thread_id=thread_id)
            if isinstance(raw_usage, dict):
                tok = raw_usage.get("known_tokens") or raw_usage.get("tokens") or {}
                cost_obj = raw_usage.get("cost") or {}
                cost_raw = cost_obj.get("estimated_cost_usd") or cost_obj.get("known_cost_usd")
                try:
                    agent_cost_usd = round(float(cost_raw), 8) if cost_raw is not None else 0.0
                except (TypeError, ValueError):
                    agent_cost_usd = 0.0
                usage_summary = {
                    "availability": raw_usage.get("availability"),
                    "input_tokens": tok.get("input_tokens"),
                    "output_tokens": tok.get("output_tokens"),
                    "total_tokens": tok.get("total_tokens"),
                    "reasoning_tokens": tok.get("reasoning_tokens"),
                    "cache_read_tokens": tok.get("cache_read_tokens"),
                    "cost_usd": agent_cost_usd,
                }

        checks_payload: dict[str, Any] = {
            "transcript": transcript,
            "turn_snapshots": turn_snapshots,
            "fixture_paths": fixture_paths,
            "artifact_read_errors": artifact_read_errors,
            "trace_collection": {"complete": tool_complete},
            "loop_observed": loop_observed,
            "stream_recovered": stream_recovered,
            "clarification_count": len(sim_session.clarification_rounds) if sim_session else 0,
            "approval_decisions": sim_session.approval_decisions if sim_session else [],
            **({"cross_project_status": cross_project_status} if cross_project_status is not None else {}),
            **({"simulation": sim_session.meta_snapshot()} if sim_session is not None else {}),
        }

        return Evidence(
            case_key=case.case_key,
            attempt_idx=attempt_idx,
            thread_id=thread_id,
            trace_ids=trace_ids,
            final_answer=final_answer,
            messages=messages,
            initial_artifacts=initial_artifacts,
            artifacts=artifacts,
            retrieved_contexts=retrieved_contexts,
            contexts_state=contexts_state,
            tool_events=tool_events,
            approval_snapshots=approval_snapshots,
            loop_signals=loop_signals,
            checks=checks_payload,
            ttft_ms=ttft_ms,
            duration_ms=total_duration,
            usage=usage_summary,
            cost_usd=agent_cost_usd,
            terminal_status=terminal_status,
            error_category=error_category,
        )

    def _score_l2(case: Case, evidence: Evidence) -> list[dict[str, Any]]:
        if not judge_model_id:
            return []
        has_l2 = any(m.name in DEEPEVAL_METRICS for m in case.metrics)
        if not has_l2:
            return []
        budget = JudgeBudget()
        conn = resolver.resolve(project_id=target_project_id, model_id=judge_model_id)
        judge = PlatformJudgeLLM(conn, budget=budget)
        t0 = time.monotonic()
        res = [m.model_dump() for m in evaluate_l2_deepeval(case, evidence, judge)]
        evidence.judge_duration_ms = max(0, int(round((time.monotonic() - t0) * 1000)))
        j_cost = estimate_tokens_cost_usd(
            conn.pricing,
            input_tokens=budget.input_tokens,
            output_tokens=budget.output_tokens,
        )
        evidence.judge_usage = {
            "input_tokens": budget.input_tokens,
            "output_tokens": budget.output_tokens,
            "total_tokens": budget.input_tokens + budget.output_tokens,
            "requests": budget.requests_used,
            "cost_usd": j_cost,
        }
        return res

    return _execute, _score_l2


def poll_and_execute_once(
    database_url: str,
    *,
    execute_fn=None,
    score_l2_fn=None,
    base_url: str | None = None,
    internal_secret: str | None = None,
    limits: GateLimits | None = None,
) -> dict[str, Any] | None:
    """Claim one queued EvalRun from platform DB, execute pending cases, and persist summary."""
    engine = create_engine(database_url)
    with engine.begin() as conn:
        run_row = conn.execute(
            text(
                "SELECT id, version_id, target_project_id, judge_model_id, concurrency, repeat_k "
                "FROM eval_runs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
            )
        ).mappings().first()
        if run_row is None:
            return None
        run_id = run_row["id"]
        conn.execute(
            text("UPDATE eval_runs SET status = 'running' WHERE id = :id"),
            {"id": run_id},
        )
        ver_row = conn.execute(
            text("SELECT frozen_cases_json FROM eval_suite_versions WHERE id = :vid"),
            {"vid": run_row["version_id"]},
        ).mappings().first()
        pending_rows = conn.execute(
            text(
                "SELECT id, case_key, attempt_idx FROM eval_run_cases "
                "WHERE run_id = :rid AND status = 'pending' ORDER BY case_key, attempt_idx"
            ),
            {"rid": run_id},
        ).mappings().all()

    raw_cases = (
        json.loads(ver_row["frozen_cases_json"])
        if isinstance(ver_row["frozen_cases_json"], str)
        else ver_row["frozen_cases_json"]
    )
    try:
        case_map = {
            c["case_key"]: Case.model_validate(
                {
                    "case_key": c["case_key"],
                    "split": c.get("split", "dev"),
                    "schema_version": c.get("schema_version", "3"),
                    "access_policy": c.get("access_policy")
                    or (c.get("metadata") or {}).get("access_policy", "workspace_write"),
                    "required_capabilities": c.get("required_capabilities", []),
                    "fixture": c.get("fixture") or (c.get("metadata") or {}).get("fixture", {}),
                    "turns": c.get("turns", []),
                    "simulation": c.get("simulation"),
                    "turn_expectations": c.get("turn_expectations")
                    or (c.get("metadata") or {}).get("turn_expectations", []),
                    "business_rules": c.get("business_rules")
                    or (c.get("metadata") or {}).get("business_rules", []),
                    "expectations": c.get("expectations", {}),
                    "metrics": c.get("metrics", []),
                }
            )
            for c in raw_cases
        }
        row_id_by_key = {(r["case_key"], r["attempt_idx"]): r["id"] for r in pending_rows}
        batch = [
            (case_map[r["case_key"]], int(r["attempt_idx"]))
            for r in pending_rows
            if r["case_key"] in case_map
        ]

        max_logs_per_run = 2000
        db_lock = threading.Lock()
        has_log_table = inspect(engine).has_table("eval_run_logs")
        seq_state = {"seq": 0, "truncated": False}
        recent_logs: list[str] = []
        if has_log_table:
            with engine.begin() as conn:
                max_seq = conn.execute(
                    text("SELECT COALESCE(MAX(seq), 0) FROM eval_run_logs WHERE run_id = :rid"),
                    {"rid": run_id},
                ).scalar_one()
                seq_state["seq"] = int(max_seq or 0)
                if seq_state["seq"] >= max_logs_per_run:
                    seq_state["truncated"] = True

        def _sync_run_progress_locked(conn) -> dict[str, Any]:
            all_rows = conn.execute(
                text("SELECT status FROM eval_run_cases WHERE run_id = :rid"),
                {"rid": run_id},
            ).mappings().all()
            progress = compute_progress_summary([dict(r) for r in all_rows])
            cur_raw = conn.execute(
                text("SELECT summary_metrics_json FROM eval_runs WHERE id = :id"),
                {"id": run_id},
            ).scalar_one_or_none()
            if isinstance(cur_raw, str):
                try:
                    cur_summary = json.loads(cur_raw)
                except ValueError:
                    cur_summary = {}
            elif isinstance(cur_raw, dict):
                cur_summary = dict(cur_raw)
            else:
                cur_summary = {}
            cur_summary["progress"] = progress
            if recent_logs:
                cur_summary["recent_logs"] = list(recent_logs)
            conn.execute(
                text("UPDATE eval_runs SET summary_metrics_json = :summary WHERE id = :id"),
                {
                    "id": run_id,
                    "summary": json.dumps(cur_summary, ensure_ascii=False),
                },
            )
            return progress

        def _emit_log(level: str, case_key: str | None, message: str) -> None:
            clean_msg = (message or "").strip()[:1000]
            if not clean_msg:
                return
            ts_str = datetime.now(UTC).strftime("%H:%M:%S")
            formatted = f"[{ts_str}] [{level}] {clean_msg}"
            with db_lock:
                recent_logs.append(formatted)
                if len(recent_logs) > 15:
                    del recent_logs[:-15]
                if has_log_table and not seq_state["truncated"]:
                    if seq_state["seq"] >= max_logs_per_run:
                        seq_state["truncated"] = True
                        seq_state["seq"] += 1
                        with engine.begin() as conn:
                            conn.execute(
                                text(
                                    "INSERT INTO eval_run_logs (id, run_id, seq, level, case_key, message, created_at) "
                                    "VALUES (:id, :run_id, :seq, :level, :case_key, :message, :created_at)"
                                ),
                                {
                                    "id": str(uuid4()),
                                    "run_id": run_id,
                                    "seq": seq_state["seq"],
                                    "level": "WARN",
                                    "case_key": None,
                                    "message": "[系统] 当前批次日志已达到单场上限 (2000 条)，后续日志已截断保护。",
                                    "created_at": datetime.now(UTC),
                                },
                            )
                    else:
                        seq_state["seq"] += 1
                        with engine.begin() as conn:
                            conn.execute(
                                text(
                                    "INSERT INTO eval_run_logs (id, run_id, seq, level, case_key, message, created_at) "
                                    "VALUES (:id, :run_id, :seq, :level, :case_key, :message, :created_at)"
                                ),
                                {
                                    "id": str(uuid4()),
                                    "run_id": run_id,
                                    "seq": seq_state["seq"],
                                    "level": level,
                                    "case_key": case_key,
                                    "message": clean_msg,
                                    "created_at": datetime.now(UTC),
                                },
                            )

        def _on_case_start(case_key: str, attempt_idx: int) -> None:
            rc_id = row_id_by_key.get((case_key, attempt_idx))
            if not rc_id:
                return
            with db_lock:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "UPDATE eval_run_cases SET status = 'running', updated_at = :updated_at "
                            "WHERE id = :id"
                        ),
                        {"id": rc_id, "updated_at": datetime.now(UTC)},
                    )
                    _sync_run_progress_locked(conn)

        def _on_checkpoint(item: dict[str, Any]) -> None:
            rc_id = row_id_by_key.get((item["case_key"], item["attempt_idx"]))
            if not rc_id:
                return
            with db_lock:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "UPDATE eval_run_cases SET status = :status, thread_id = :thread_id, "
                            "trace_ids_json = :trace_ids, rule_passed = :rule_passed, "
                            "overall_score = :overall_score, duration_ms = :duration_ms, "
                            "ttft_ms = :ttft_ms, token_usage_json = :token_usage, "
                            "cost_usd = :cost_usd, "
                            "error_category = :error_category, results_json = :results, "
                            "updated_at = :updated_at WHERE id = :id"
                        ),
                        {
                            "id": rc_id,
                            "status": item["status"],
                            "thread_id": item.get("thread_id"),
                            "trace_ids": json.dumps(item.get("trace_ids") or []),
                            "rule_passed": item.get("rule_passed"),
                            "overall_score": item.get("overall_score"),
                            "duration_ms": item.get("duration_ms"),
                            "ttft_ms": item.get("ttft_ms"),
                            "token_usage": json.dumps(item.get("token_usage") or {}),
                            "cost_usd": item.get("cost_usd"),
                            "error_category": item.get("error_category"),
                            "results": json.dumps(item.get("results") or {}, ensure_ascii=False),
                            "updated_at": datetime.now(UTC),
                        },
                    )
                    _sync_run_progress_locked(conn)

        def _is_paused() -> bool:
            with engine.begin() as conn:
                row = conn.execute(
                    text("SELECT status FROM eval_runs WHERE id = :id"),
                    {"id": run_id},
                ).mappings().first()
                return bool(row and row["status"] in {"paused", "cancelled"})

        if execute_fn is None and base_url and internal_secret:
            execute_fn, auto_l2 = build_platform_executors(
                base_url=base_url,
                internal_secret=internal_secret,
                run_id=str(run_id),
                target_project_id=str(run_row["target_project_id"]),
                judge_model_id=str(run_row["judge_model_id"]) if run_row["judge_model_id"] else None,
                emit_log=_emit_log,
            )
            if score_l2_fn is None:
                score_l2_fn = auto_l2

        def _default_exec(case: Case, attempt_idx: int) -> Evidence:
            return Evidence(case_key=case.case_key, attempt_idx=attempt_idx, final_answer="ok")

        eff_concurrency = max(1, min(5, int(run_row["concurrency"] or 3)))
        _emit_log(
            "INFO",
            None,
            (
                f"[批次] 开始执行评测 · 并发={eff_concurrency} · 待测用例={len(batch)} 题 · "
                f"目标项目={run_row['target_project_id']}"
            ),
        )
        with db_lock:
            with engine.begin() as conn:
                _sync_run_progress_locked(conn)

        runner = ConcurrentEvalRunner(
            concurrency=eff_concurrency,
            is_paused=_is_paused,
            on_case_start=_on_case_start,
            on_checkpoint=_on_checkpoint,
            emit_log=_emit_log,
        )
        out = runner.run_batch(
            cases=batch,
            execute_fn=execute_fn or _default_exec,
            score_l2_fn=score_l2_fn,
            limits=limits,
        )
    except Exception as exc:
        logger.exception("eval run %s aborted with unexpected error", run_id)
        try:
            _emit_log("ERROR", None, f"[批次] 执行异常中断: {str(exc)[:300]}")
        except Exception:  # noqa: BLE001
            pass
        with engine.begin() as conn:
            conn.execute(
                text(
                    "UPDATE eval_runs SET status = 'error', gate_exit_code = 2, "
                    "summary_metrics_json = :summary, finished_at = :finished_at WHERE id = :id"
                ),
                {
                    "id": run_id,
                    "summary": json.dumps({"error": str(exc)}, ensure_ascii=False),
                    "finished_at": datetime.now(UTC),
                },
            )
        raise
    with engine.begin() as conn:
        cur = conn.execute(
            text("SELECT status FROM eval_runs WHERE id = :id"), {"id": run_id}
        ).scalar_one_or_none()
        final_status = (
            cur
            if cur in {"paused", "cancelled"}
            else ("completed" if out["gate"]["exit_code"] == 0 else "failed")
        )
    _emit_log(
        "INFO" if final_status == "completed" else "WARN",
        None,
        (
            f"[批次] 执行收口 · 终态={final_status} · "
            f"TSR={round((out['summary'].get('tsr_pass_at_1') or 0) * 100)}% · "
            f"综合分={round((out['summary'].get('overall_score') or 0) * 100)}% · "
            f"门禁退出码={out['gate']['exit_code']}"
        ),
    )
    with db_lock:
        with engine.begin() as conn:
            all_rows = conn.execute(
                text("SELECT status FROM eval_run_cases WHERE run_id = :rid"),
                {"rid": run_id},
            ).mappings().all()
            final_summary = dict(out["summary"])
            final_summary["progress"] = compute_progress_summary([dict(r) for r in all_rows])
            final_summary["recent_logs"] = list(recent_logs)
            conn.execute(
                text(
                    "UPDATE eval_runs SET status = :status, gate_exit_code = :code, "
                    "summary_metrics_json = :summary, finished_at = :finished_at WHERE id = :id"
                ),
                {
                    "id": run_id,
                    "status": final_status,
                    "code": out["gate"]["exit_code"],
                    "summary": json.dumps(final_summary, ensure_ascii=False),
                    "finished_at": datetime.now(UTC) if final_status in {"completed", "failed", "cancelled"} else None,
                },
            )
    return {"run_id": run_id, "status": final_status, **out}


def run_worker_loop(
    *,
    database_url: str | None = None,
    base_url: str | None = None,
    internal_secret: str | None = None,
    poll_interval: float = 2.0,
) -> None:
    """Continuously poll for queued EvalRuns and execute them cleanly."""
    db_url = database_url or os.environ.get("PLATFORM_API_DATABASE_URL", "")
    api_url = base_url or os.environ.get("PLATFORM_API_BASE_URL", "http://127.0.0.1:2142")
    secret = internal_secret or os.environ.get("PLATFORM_API_RUNTIME_DELEGATION_SECRET", "")
    if not db_url:
        raise RuntimeError("PLATFORM_API_DATABASE_URL is required for eval-runner worker")

    logger.info("eval-runner worker polling %s (api=%s)", db_url.split("@")[-1], api_url)
    while True:
        try:
            handled = poll_and_execute_once(
                db_url,
                base_url=api_url if secret else None,
                internal_secret=secret or None,
            )
            if handled:
                logger.info(
                    "Finished eval run %s with status=%s",
                    handled["run_id"],
                    handled["status"],
                )
                continue
        except Exception:  # noqa: BLE001
            logger.exception("eval-runner worker cycle error")
        time.sleep(poll_interval)


if __name__ == "__main__":
    import argparse
    from pathlib import Path

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="eval-runner polling worker")
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    args = parser.parse_args()
    if args.env_file and args.env_file.exists():
        for raw_line in args.env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip("'").strip('"')
            if key and key not in os.environ:
                os.environ[key] = val
    run_worker_loop(poll_interval=args.poll_interval)
