"""Scheduled patrol cron evaluation, misfire handling, and baseline regression checks."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from croniter import croniter

from eval_runner.domain.contracts import GateLimits
from eval_runner.engine.gates import evaluate_gate


def compute_next_run_at(
    cron_expr: str, tz_name: str = "Asia/Shanghai", *, after: datetime | None = None
) -> datetime:
    """Compute next trigger timestamp in UTC strictly after `after` (skipping misfire backlog)."""
    expr = " ".join((cron_expr or "").strip().split())
    if len(expr.split(" ")) != 5 or not croniter.is_valid(expr):
        raise ValueError(f"Invalid 5-field cron expression: {cron_expr!r}")
    tz = ZoneInfo(tz_name or "Asia/Shanghai")
    base_utc = (after or datetime.now(UTC)).astimezone(UTC)
    nxt_local = croniter(expr, base_utc.astimezone(tz)).get_next(datetime)
    if nxt_local.tzinfo is None:
        nxt_local = nxt_local.replace(tzinfo=tz)
    return nxt_local.astimezone(UTC)


def evaluate_patrol_outcome(
    summary: dict[str, Any],
    case_records: list[dict[str, Any]],
    *,
    gate_config: dict[str, Any] | None = None,
    baseline_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate absolute gate limits and relative regression against baseline run."""
    cfg = dict(gate_config or {})
    limits = GateLimits(
        min_tsr=float(cfg.get("min_tsr", 0.70)),
        min_l1_pass_rate=float(cfg.get("min_l1_pass_rate", 0.90)),
        max_loop_rate=float(cfg.get("max_loop_rate", 0.10)),
        max_p95_ttft_ms=(
            int(cfg["max_p95_ttft_ms"])
            if cfg.get("max_p95_ttft_ms") is not None
            else None
        ),
    )
    gate = evaluate_gate(summary, case_records, limits)
    reasons = list(gate.get("reasons") or [])

    drop_threshold = float(cfg.get("regression_drop_threshold", 0.05))
    ttft_spike_ratio = float(cfg.get("ttft_spike_ratio", 0.50))
    regression_reasons: list[str] = []

    if baseline_summary and gate["exit_code"] != 2:
        cur_tsr = summary.get("tsr_pass_at_1")
        base_tsr = baseline_summary.get("tsr_pass_at_1")
        if (
            isinstance(cur_tsr, (int, float))
            and isinstance(base_tsr, (int, float))
            and drop_threshold > 0
            and (float(base_tsr) - float(cur_tsr)) >= drop_threshold
        ):
            regression_reasons.append(
                f"tsr_regression:{round(float(base_tsr) * 100)}%->{round(float(cur_tsr) * 100)}%"
            )

        cur_score = summary.get("overall_score")
        base_score = baseline_summary.get("overall_score")
        if (
            isinstance(cur_score, (int, float))
            and isinstance(base_score, (int, float))
            and drop_threshold > 0
            and (float(base_score) - float(cur_score)) >= drop_threshold
        ):
            regression_reasons.append(
                f"score_regression:{round(float(base_score) * 100)}%->{round(float(cur_score) * 100)}%"
            )

        cur_p95 = (summary.get("ttft_ms") or {}).get("p95")
        base_p95 = (baseline_summary.get("ttft_ms") or {}).get("p95")
        if (
            isinstance(cur_p95, (int, float))
            and isinstance(base_p95, (int, float))
            and base_p95 > 0
            and ttft_spike_ratio > 0
            and ((float(cur_p95) - float(base_p95)) / float(base_p95)) >= ttft_spike_ratio
        ):
            regression_reasons.append(
                f"ttft_p95_spike:{int(base_p95)}ms->{int(cur_p95)}ms"
            )

    all_reasons = reasons + regression_reasons
    if gate["exit_code"] == 2:
        verdict = "infra_error"
    elif gate["exit_code"] == 1:
        verdict = "failed"
    elif regression_reasons:
        verdict = "degraded"
    else:
        verdict = "passed"

    tsr_pct = round(float(summary.get("tsr_pass_at_1") or 0.0) * 100)
    score_pct = round(float(summary.get("overall_score") or 0.0) * 100)
    p95_val = (summary.get("ttft_ms") or {}).get("p95")
    p95_part = f" · TTFT P95 {int(p95_val)}ms" if p95_val is not None else ""
    if verdict == "passed":
        summary_text = f"巡检通过 · TSR {tsr_pct}% · 综合分 {score_pct}%{p95_part}"
    else:
        reason_str = ", ".join(all_reasons[:4]) if all_reasons else verdict
        summary_text = f"巡检异常 ({verdict}) · TSR {tsr_pct}% · 综合分 {score_pct}%{p95_part} · 原因: {reason_str}"

    return {
        "verdict": verdict,
        "summary_text": summary_text,
        "reasons": all_reasons,
        "metrics_snapshot": {
            "tsr_pass_at_1": summary.get("tsr_pass_at_1"),
            "overall_score": summary.get("overall_score"),
            "l1_pass_rate": summary.get("l1_pass_rate"),
            "loop_rate": summary.get("loop_rate"),
            "ttft_p95_ms": p95_val,
        },
    }
