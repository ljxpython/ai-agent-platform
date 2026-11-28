"""7D whitepaper summary metrics: TSR, Pass^k, TTFT percentiles, Loop Rate, Error分层, Kappa."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


def percentile(values: list[int | float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    idx = math.ceil((p / 100.0) * len(ordered)) - 1
    idx = max(0, min(idx, len(ordered) - 1))
    return float(ordered[idx])


def cohens_kappa(pairs: list[tuple[bool, bool]]) -> float | None:
    """Compute Cohen's Kappa between human verdicts and judge verdicts."""
    if not pairs:
        return None
    n = len(pairs)
    po = sum(1 for h, j in pairs if h == j) / n
    h_pos = sum(1 for h, _ in pairs if h) / n
    j_pos = sum(1 for _, j in pairs if j) / n
    pe = h_pos * j_pos + (1.0 - h_pos) * (1.0 - j_pos)
    if pe >= 1.0 - 1e-9:
        return 1.0 if po >= 1.0 - 1e-9 else 0.0
    return round((po - pe) / (1.0 - pe), 4)


def compute_progress_summary(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute real-time case status progress counts and percentage."""
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
        st = str(c.get("status") or "pending")
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


def summarize_run_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate 7D whitepaper metrics across all case attempts in a run."""
    active = [c for c in cases if c.get("status") != "skipped_incompatible"]
    total = len(active)
    if total == 0:
        return {
            "total_cases": 0,
            "tsr_pass_at_1": 0.0,
            "l1_pass_rate": 0.0,
            "loop_rate": 0.0,
            "ttft_ms": {"p50": None, "p95": None, "p99": None},
            "duration_ms": {"p50": None, "p95": None, "p99": None},
            "error_breakdown": {
                "fail": 0,
                "runtime_error": 0,
                "stream_timeout": 0,
                "eval_error": 0,
            },
            "metrics_breakdown": {},
            "total_cost_usd": 0.0,
            "pass_power_k": None,
        }

    passed_attempts = sum(
        1
        for c in active
        if c.get("status") == "completed" and c.get("rule_passed") is not False
    )
    l1_passed = sum(1 for c in active if c.get("rule_passed") is True)
    loop_hits = sum(
        1 for c in active if (c.get("results") or {}).get("loop_signals", 0) > 0
    )
    ttfts = [c["ttft_ms"] for c in active if isinstance(c.get("ttft_ms"), (int, float))]
    durations = [
        c["duration_ms"] for c in active if isinstance(c.get("duration_ms"), (int, float))
    ]
    breakdown = {"fail": 0, "runtime_error": 0, "stream_timeout": 0, "eval_error": 0}
    for c in active:
        cat = c.get("error_category")
        if cat in breakdown:
            breakdown[cat] += 1
        elif c.get("status") == "failed":
            breakdown["fail"] += 1
        elif c.get("status") == "error":
            breakdown["eval_error"] += 1

    by_case: dict[str, list[bool]] = defaultdict(list)
    for c in active:
        ok = c.get("status") == "completed" and c.get("rule_passed") is not False
        by_case[c["case_key"]].append(ok)
    max_k = max((len(v) for v in by_case.values()), default=1)
    pass_power_k = (
        round(sum(1 for v in by_case.values() if all(v)) / len(by_case), 4)
        if max_k > 1 and by_case
        else None
    )

    total_cost = round(sum(float(c.get("cost_usd") or 0.0) for c in active), 6)
    scored_vals = [
        float(c["overall_score"])
        for c in active
        if isinstance(c.get("overall_score"), (int, float))
    ]
    overall_score = round(sum(scored_vals) / len(scored_vals), 4) if scored_vals else 0.0

    def _timing_stats(vals: list[int | float]) -> dict[str, float | None]:
        if not vals:
            return {"avg": None, "p50": None, "p95": None}
        return {
            "avg": round(sum(vals) / len(vals), 1),
            "p50": percentile(vals, 50),
            "p95": percentile(vals, 95),
        }

    gen_vals = [
        float(tb["generation_ms"])
        for c in active
        for tb in [(c.get("results") or {}).get("timing_breakdown") or {}]
        if isinstance(tb.get("generation_ms"), (int, float))
    ]
    judge_vals = [
        float(tb["judge_ms"])
        for c in active
        for tb in [(c.get("results") or {}).get("timing_breakdown") or {}]
        if isinstance(tb.get("judge_ms"), (int, float))
    ]
    tok_totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "agent_tokens": 0, "judge_tokens": 0}
    has_token_data = False
    for c in active:
        tu = c.get("token_usage") or {}
        if isinstance(tu, dict) and isinstance(tu.get("total_tokens"), (int, float)):
            has_token_data = True
            for k in tok_totals:
                if isinstance(tu.get(k), (int, float)):
                    tok_totals[k] += int(tu[k])

    metric_groups: dict[str, dict[str, Any]] = {}
    for c in active:
        m_list = (c.get("results") or {}).get("metrics") or []
        if not isinstance(m_list, list):
            continue
        for m in m_list:
            if not isinstance(m, dict) or not m.get("name"):
                continue
            m_name = str(m["name"])
            bucket = metric_groups.setdefault(
                m_name,
                {"layer": str(m.get("layer") or "L1"), "scores": [], "passed": []},
            )
            if isinstance(m.get("score"), (int, float)):
                bucket["scores"].append(float(m["score"]))
            if isinstance(m.get("passed"), bool):
                bucket["passed"].append(m["passed"])

    metrics_breakdown = {
        name: {
            "layer": grp["layer"],
            "avg_score": (
                round(sum(grp["scores"]) / len(grp["scores"]), 4)
                if grp["scores"]
                else None
            ),
            "pass_rate": (
                round(sum(1 for p in grp["passed"] if p) / len(grp["passed"]), 4)
                if grp["passed"]
                else None
            ),
            "sample_count": max(len(grp["scores"]), len(grp["passed"])),
        }
        for name, grp in sorted(metric_groups.items())
    }

    return {
        "total_cases": total,
        "overall_score": overall_score,
        "tsr_pass_at_1": round(passed_attempts / total, 4),
        "l1_pass_rate": round(l1_passed / total, 4),
        "loop_rate": round(loop_hits / total, 4),
        "ttft_ms": {
            "p50": percentile(ttfts, 50),
            "p95": percentile(ttfts, 95),
            "p99": percentile(ttfts, 99),
        },
        "duration_ms": {
            "avg": round(sum(durations) / len(durations), 1) if durations else None,
            "p50": percentile(durations, 50),
            "p95": percentile(durations, 95),
            "p99": percentile(durations, 99),
        },
        "timing_breakdown": {
            "ttft_ms": _timing_stats(ttfts),
            "generation_ms": _timing_stats(gen_vals),
            "agent_duration_ms": _timing_stats(durations),
            "judge_ms": _timing_stats(judge_vals),
        },
        "token_usage": tok_totals if has_token_data else None,
        "error_breakdown": breakdown,
        "metrics_breakdown": metrics_breakdown,
        "total_cost_usd": total_cost,
        "pass_power_k": pass_power_k,
    }
