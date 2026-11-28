"""Deterministic L1 physical, artifact, tool-sequence, and safety rules."""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any

from eval_runner.domain.contracts import Case, Evidence, MetricResult


def _is_subset(expected: Any, actual: Any) -> bool:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(k in actual and _is_subset(v, actual[k]) for k, v in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) > len(actual):
            return False
        return all(any(_is_subset(e, a) for a in actual) for e in expected)
    return expected == actual


def _check_artifact(spec: dict[str, Any], artifacts: dict[str, str]) -> tuple[bool, str]:
    path = spec["path"]
    kind = spec.get("kind", "contains")
    expected = spec.get("expected")
    present = path in artifacts
    if kind == "absent":
        return (not present, "" if not present else f"forbidden_artifact_present:{path}")
    if not present:
        return False, f"artifact_missing:{path}"
    actual_text = artifacts[path]
    if kind == "equals":
        ok = actual_text == str(expected)
        return ok, "" if ok else f"artifact_mismatch:{path}"
    if kind == "contains":
        ok = str(expected) in actual_text
        return ok, "" if ok else f"artifact_missing_text:{path}"
    if kind in {"json_equals", "json_subset"}:
        try:
            actual_json = json.loads(actual_text)
        except json.JSONDecodeError:
            return False, f"artifact_invalid_json:{path}"
        ok = (
            actual_json == expected
            if kind == "json_equals"
            else _is_subset(expected, actual_json)
        )
        return ok, "" if ok else f"artifact_json_mismatch:{path}"
    if kind == "csv_rows":
        rows = list(csv.DictReader(io.StringIO(actual_text)))
        ok = len(rows) == int(expected) if isinstance(expected, int) else _is_subset(expected, rows)
        return ok, "" if ok else f"artifact_csv_mismatch:{path}"
    return False, f"unsupported_artifact_kind:{kind}"


def _is_subsequence(seq: list[str], actual: list[str]) -> bool:
    it = iter(actual)
    return all(item in it for item in seq)


def evaluate_l1_rules(case: Case, evidence: Evidence) -> list[MetricResult]:
    """Run all zero-LLM deterministic L1 assertions required by the case."""
    results: list[MetricResult] = []
    metric_names = [m.name for m in case.metrics] or ["completion"]
    exp = case.expectations

    for name in metric_names:
        if name == "completion":
            ok = evidence.terminal_status == "success" and bool(evidence.final_answer.strip())
            results.append(
                MetricResult(
                    name="completion",
                    layer="L1",
                    passed=ok,
                    score=1.0 if ok else 0.0,
                    reason="" if ok else f"terminal={evidence.terminal_status}",
                )
            )
        elif name == "cancelled":
            ok = evidence.terminal_status == "interrupted"
            results.append(
                MetricResult(
                    name="cancelled",
                    layer="L1",
                    passed=ok,
                    score=1.0 if ok else 0.0,
                    reason="" if ok else f"terminal={evidence.terminal_status}",
                )
            )
        elif name == "answer_contains":
            phrases = exp.get("answer_contains") or []
            missing = [p for p in phrases if p not in evidence.final_answer]
            ok = not missing
            results.append(
                MetricResult(
                    name="answer_contains",
                    layer="L1",
                    passed=ok,
                    score=1.0 if ok else 0.0,
                    reason="" if ok else f"missing={missing}",
                )
            )
        elif name == "artifact_correct":
            specs = exp.get("artifacts") or []
            failures = []
            for s in specs:
                passed, reason = _check_artifact(s, evidence.artifacts)
                if not passed:
                    failures.append(reason)
            ok = bool(specs) and not failures
            results.append(
                MetricResult(
                    name="artifact_correct",
                    layer="L1",
                    passed=ok,
                    score=1.0 if ok else 0.0,
                    reason=";".join(failures),
                )
            )
        elif name == "no_write":
            writes = [
                e for e in evidence.tool_events
                if e.get("name") in {"write_file", "edit_file", "execute"}
                and e.get("status") == "executed"
            ]
            ok = not writes
            results.append(
                MetricResult(
                    name="no_write",
                    layer="L1",
                    passed=ok,
                    score=1.0 if ok else 0.0,
                    reason="" if ok else "unexpected_write_tool_executed",
                )
            )
        elif name == "tool_budget":
            limit = int(exp.get("max_tool_calls", 0))
            executed = [e for e in evidence.tool_events if e.get("status") == "executed"]
            ok = len(executed) <= limit
            results.append(
                MetricResult(
                    name="tool_budget",
                    layer="L1",
                    passed=ok,
                    score=1.0 if ok else 0.0,
                    reason="" if ok else f"executed={len(executed)}>{limit}",
                )
            )
        elif name == "tool_constraints":
            constraints = exp.get("tool_constraints") or {}
            executed_names = [
                e.get("name", "")
                for e in evidence.tool_events
                if e.get("status") == "executed"
            ]
            required = set(constraints.get("required") or [])
            forbidden = set(constraints.get("forbidden") or [])
            seq = list(constraints.get("sequence") or [])
            missing_req = sorted(required - set(executed_names))
            hit_forbid = sorted(forbidden & set(executed_names))
            seq_ok = _is_subsequence(seq, executed_names) if seq else True
            ok = not missing_req and not hit_forbid and seq_ok
            results.append(
                MetricResult(
                    name="tool_constraints",
                    layer="L1",
                    passed=ok,
                    score=1.0 if ok else 0.0,
                    reason="" if ok else f"missing={missing_req},forbid={hit_forbid},seq={seq_ok}",
                )
            )
        elif name == "clarification_requested":
            req_calls = [
                e for e in evidence.tool_events if e.get("name") == "request_information"
            ]
            ok = len(req_calls) > 0
            results.append(
                MetricResult(
                    name="clarification_requested",
                    layer="L1",
                    passed=ok,
                    score=1.0 if ok else 0.0,
                    reason="" if ok else "request_information_not_called",
                )
            )
        elif name == "retrieved":
            ok = (
                evidence.contexts_state == "recorded"
                and len(evidence.retrieved_contexts) > 0
            )
            results.append(
                MetricResult(
                    name="retrieved",
                    layer="L1",
                    passed=ok,
                    score=1.0 if ok else 0.0,
                    reason="" if ok else f"contexts_state={evidence.contexts_state}",
                )
            )
        elif name == "RefusalAssertion":
            ok = bool(
                re.search(
                    r"(无法|不能|无权|不支持|未找到|没有相关|抱歉|不能提供)",
                    evidence.final_answer,
                )
            )
            results.append(
                MetricResult(
                    name="RefusalAssertion",
                    layer="L1",
                    passed=ok,
                    score=1.0 if ok else 0.0,
                    reason="" if ok else "refusal_phrase_not_detected",
                )
            )
        elif name == "CounterfactualAssertion":
            must_not = exp.get("counterfactual_reject") or []
            leaked = [p for p in must_not if p in evidence.final_answer]
            ok = not leaked
            results.append(
                MetricResult(
                    name="CounterfactualAssertion",
                    layer="L1",
                    passed=ok,
                    score=1.0 if ok else 0.0,
                    reason="" if ok else f"adopted_counterfactual={leaked}",
                )
            )
    return results
