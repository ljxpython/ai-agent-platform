"""Database-backed polling worker connecting platform-api eval_* tables and ConcurrentEvalRunner."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, text

from eval_runner.domain.contracts import Case, Evidence, GateLimits
from eval_runner.engine.concurrent_runner import ConcurrentEvalRunner
from eval_runner.scorers.deepeval_adapter import DEEPEVAL_METRICS, evaluate_l2_deepeval
from eval_runner.scorers.judge import (
    JudgeBudget,
    PlatformJudgeLLM,
    estimate_tokens_cost_usd,
)
from eval_runner.targets.platform_client import (
    InternalExecutionClient,
    PlatformModelResolver,
)

logger = logging.getLogger(__name__)


def build_platform_executors(
    *,
    base_url: str,
    internal_secret: str,
    run_id: str,
    target_project_id: str,
    judge_model_id: str | None = None,
):
    """Build real SSE turn executor and optional DeepEval L2 judge scorer."""
    exec_client = InternalExecutionClient(base_url, internal_secret)
    resolver = PlatformModelResolver(base_url, internal_secret)

    def _execute(case: Case, attempt_idx: int) -> Evidence:
        turns = [t.content for t in case.turns if t.content.strip()]
        if not turns and case.simulation:
            goal = str(case.simulation.get("goal") or "").strip()
            if goal:
                turns = [goal]
        if not turns:
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
        ttft_ms: int | None = None
        total_duration = 0
        final_answer = ""
        terminal_status = "success"
        error_category = "none"

        for prompt in turns:
            transcript.append({"role": "user", "content": prompt})
            thread_id, probe = exec_client.execute_turn(
                run_id=run_id,
                content=prompt,
                thread_id=thread_id,
            )
            if probe.run_id:
                trace_ids.append(probe.run_id)
            if ttft_ms is None and probe.ttft_ms is not None:
                ttft_ms = probe.ttft_ms
            total_duration += probe.duration_ms
            if probe.final_text:
                final_answer = probe.final_text
            transcript.append(
                {
                    "role": "assistant",
                    "content": probe.final_text,
                    "ttft_ms": probe.ttft_ms,
                    "duration_ms": probe.duration_ms,
                    "run_id": probe.run_id,
                }
            )
            if probe.terminal_status != "success":
                terminal_status = probe.terminal_status
                error_category = probe.error_category if probe.error_category != "none" else "runtime_error"
                break

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

        return Evidence(
            case_key=case.case_key,
            attempt_idx=attempt_idx,
            thread_id=thread_id,
            trace_ids=trace_ids,
            final_answer=final_answer,
            tool_events=transcript,
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
                    "required_capabilities": c.get("required_capabilities", []),
                    "turns": c.get("turns", []),
                    "simulation": c.get("simulation"),
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

        def _on_checkpoint(item: dict[str, Any]) -> None:
            rc_id = row_id_by_key.get((item["case_key"], item["attempt_idx"]))
            if not rc_id:
                return
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
            )
            if score_l2_fn is None:
                score_l2_fn = auto_l2

        def _default_exec(case: Case, attempt_idx: int) -> Evidence:
            return Evidence(case_key=case.case_key, attempt_idx=attempt_idx, final_answer="ok")

        runner = ConcurrentEvalRunner(
            concurrency=max(1, min(5, int(run_row["concurrency"] or 3))),
            is_paused=_is_paused,
            on_checkpoint=_on_checkpoint,
        )
        out = runner.run_batch(
            cases=batch,
            execute_fn=execute_fn or _default_exec,
            score_l2_fn=score_l2_fn,
            limits=limits,
        )
    except Exception as exc:
        logger.exception("eval run %s aborted with unexpected error", run_id)
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
        conn.execute(
            text(
                "UPDATE eval_runs SET status = :status, gate_exit_code = :code, "
                "summary_metrics_json = :summary, finished_at = :finished_at WHERE id = :id"
            ),
            {
                "id": run_id,
                "status": final_status,
                "code": out["gate"]["exit_code"],
                "summary": json.dumps(out["summary"], ensure_ascii=False),
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
