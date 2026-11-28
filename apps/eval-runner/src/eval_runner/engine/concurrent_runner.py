"""Concurrent case execution pool with checkpoints, pause/resume, and fault isolation."""

from __future__ import annotations

import logging
import threading
import time
import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from eval_runner.domain.contracts import Case, Evidence, GateLimits
from eval_runner.domain.metrics_summary import summarize_run_cases
from eval_runner.engine.gates import evaluate_gate
from eval_runner.scorers.rules import evaluate_l1_rules

logger = logging.getLogger(__name__)


class ConcurrentEvalRunner:
    """Execute evaluation cases concurrently (1..5) without cross-case failure contagion."""

    def __init__(
        self,
        *,
        concurrency: int = 3,
        max_judge_concurrency: int = 3,
        is_paused: Callable[[], bool] | None = None,
        on_checkpoint: Callable[[dict[str, Any]], None] | None = None,
    ):
        if not 1 <= concurrency <= 5:
            raise ValueError("concurrency must be within 1..5")
        self.concurrency = concurrency
        self.judge_semaphore = threading.Semaphore(max_judge_concurrency)
        self.is_paused = is_paused or (lambda: False)
        self.on_checkpoint = on_checkpoint or (lambda _row: None)

    def run_batch(
        self,
        *,
        cases: list[tuple[Case, int]],
        execute_fn: Callable[[Case, int], Evidence],
        score_l2_fn: Callable[[Case, Evidence], list[dict[str, Any]]] | None = None,
        limits: GateLimits | None = None,
    ) -> dict[str, Any]:
        records: list[dict[str, Any]] = []

        def _worker(item: tuple[Case, int]) -> dict[str, Any]:
            case, attempt_idx = item
            if self.is_paused():
                row = {
                    "case_key": case.case_key,
                    "attempt_idx": attempt_idx,
                    "status": "paused",
                }
                self.on_checkpoint(row)
                return row
            try:
                evidence = execute_fn(case, attempt_idx)
                l1 = [m.model_dump() for m in evaluate_l1_rules(case, evidence)]
                l2: list[dict[str, Any]] = []
                judge_ms = 0
                if score_l2_fn is not None and evidence.error_category == "none":
                    t_judge = time.monotonic()
                    with self.judge_semaphore:
                        l2 = score_l2_fn(case, evidence)
                    judge_ms = max(0, int(round((time.monotonic() - t_judge) * 1000)))
                elif evidence.judge_duration_ms:
                    judge_ms = evidence.judge_duration_ms
                all_metrics = l1 + l2
                rule_passed = all(m["passed"] for m in l1) if l1 else True
                overall = (
                    round(sum(m["score"] for m in all_metrics) / len(all_metrics), 4)
                    if all_metrics
                    else 1.0
                )
                all_passed = rule_passed and all(m["passed"] for m in all_metrics)
                status = (
                    "error"
                    if evidence.error_category in {"runtime_error", "stream_timeout", "eval_error"}
                    else ("completed" if all_passed else "failed")
                )
                generation_ms = (
                    max(0, evidence.duration_ms - evidence.ttft_ms)
                    if evidence.ttft_ms is not None
                    else None
                )
                timing_breakdown = {
                    "ttft_ms": evidence.ttft_ms,
                    "generation_ms": generation_ms,
                    "agent_duration_ms": evidence.duration_ms,
                    "judge_ms": judge_ms if (l2 or evidence.judge_duration_ms) else None,
                    "total_ms": evidence.duration_ms + judge_ms,
                }
                a_usage = evidence.usage if isinstance(evidence.usage, dict) else {}
                j_usage = evidence.judge_usage if isinstance(evidence.judge_usage, dict) else {}
                a_in = a_usage.get("input_tokens")
                a_out = a_usage.get("output_tokens")
                a_tot = a_usage.get("total_tokens")
                j_in = j_usage.get("input_tokens")
                j_out = j_usage.get("output_tokens")
                j_tot = j_usage.get("total_tokens")
                in_vals = [v for v in (a_in, j_in) if isinstance(v, (int, float))]
                out_vals = [v for v in (a_out, j_out) if isinstance(v, (int, float))]
                tot_vals = [v for v in (a_tot, j_tot) if isinstance(v, (int, float))]
                agent_cost = float(evidence.cost_usd or 0.0)
                judge_cost = float(j_usage.get("cost_usd") or 0.0)
                total_cost = round(agent_cost + judge_cost, 8)
                combined_usage: dict[str, Any] = {}
                if in_vals or out_vals or tot_vals or a_usage or j_usage:
                    combined_usage = {
                        "input_tokens": int(sum(in_vals)) if in_vals else None,
                        "output_tokens": int(sum(out_vals)) if out_vals else None,
                        "total_tokens": int(sum(tot_vals)) if tot_vals else None,
                        "agent_tokens": int(a_tot) if isinstance(a_tot, (int, float)) else None,
                        "judge_tokens": int(j_tot) if isinstance(j_tot, (int, float)) else None,
                        "agent_cost_usd": agent_cost,
                        "judge_cost_usd": judge_cost,
                        "availability": a_usage.get("availability"),
                    }
                row = {
                    "case_key": case.case_key,
                    "attempt_idx": attempt_idx,
                    "status": status,
                    "thread_id": evidence.thread_id,
                    "trace_ids": evidence.trace_ids,
                    "rule_passed": rule_passed,
                    "overall_score": overall,
                    "duration_ms": evidence.duration_ms,
                    "ttft_ms": evidence.ttft_ms,
                    "token_usage": combined_usage,
                    "cost_usd": total_cost,
                    "error_category": (
                        evidence.error_category
                        if evidence.error_category != "none"
                        else ("none" if all_passed else "fail")
                    ),
                    "results": {
                        "metrics": all_metrics,
                        "loop_signals": evidence.loop_signals,
                        "final_answer": evidence.final_answer,
                        "expected_answer": case.expectations.get("expected_answer")
                        or case.expectations.get("rubric"),
                        "tool_events": evidence.tool_events,
                        "artifacts": evidence.artifacts,
                        "retrieved_contexts": evidence.retrieved_contexts,
                        "contexts_state": evidence.contexts_state,
                        "approval_snapshots": evidence.approval_snapshots,
                        "simulation": (evidence.checks or {}).get("simulation"),
                        "transcript": (evidence.checks or {}).get("transcript") or evidence.tool_events,
                        "timing_breakdown": timing_breakdown,
                    },
                }
            except Exception as exc:  # noqa: BLE001
                logger.exception("eval case execution failed: %s", case.case_key)
                row = {
                    "case_key": case.case_key,
                    "attempt_idx": attempt_idx,
                    "status": "error",
                    "rule_passed": False,
                    "overall_score": 0.0,
                    "error_category": "eval_error",
                    "results": {
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                        "metrics": [],
                    },
                }
            self.on_checkpoint(row)
            return row

        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            futures = [pool.submit(_worker, item) for item in cases]
            for fut in as_completed(futures):
                records.append(fut.result())

        summary = summarize_run_cases(records)
        gate = evaluate_gate(summary, records, limits=limits)
        return {"summary": summary, "gate": gate, "cases": records}
