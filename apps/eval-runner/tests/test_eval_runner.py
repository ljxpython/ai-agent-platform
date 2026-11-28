"""Unit tests for eval-runner SSE TTFT probe, 7D metrics, L1 rules, concurrency, and gates."""

from __future__ import annotations

import json

import pytest

from eval_runner.domain.contracts import Case, Evidence, GateLimits, MetricSpec, Turn
from eval_runner.domain.metrics_summary import cohens_kappa, summarize_run_cases
from eval_runner.engine.concurrent_runner import ConcurrentEvalRunner
from eval_runner.engine.gates import evaluate_gate
from eval_runner.scorers.judge import estimate_tokens_cost_usd, repair_json_text
from eval_runner.scorers.rules import evaluate_l1_rules
from eval_runner.targets.sse_probe import probe_sse_stream


def test_sse_probe_measures_real_ttft_skipping_heartbeats_and_metadata():
    ticks = iter([0.05, 0.25, 0.85, 1.40, 1.50])
    lines = [
        ": heartbeat",
        "",
        "event: metadata",
        'data: {"run_id": "run-123"}',
        "",
        "event: messages/partial",
        'data: [{"role": "assistant", "content": ""}]',
        "",
        "event: messages/partial",
        'data: [{"role": "assistant", "content": "你好"}]',
        "",
        "event: values",
        'data: {"messages": [{"role": "assistant", "content": "你好，已完成。"}]}',
        "",
    ]
    res = probe_sse_stream(lines, started_monotonic=0.0, clock=lambda: next(ticks))
    assert res.run_id == "run-123"
    assert res.first_event_ms == 50
    assert res.ttft_ms == 850
    assert res.duration_ms == 1500
    assert res.final_text == "你好，已完成。"
    assert res.terminal_status == "success"


def test_sse_probe_parses_jsonrpc_v3_frames():
    ticks = iter([0.1, 0.4, 0.7, 1.0, 1.1])
    lines = [
        "event: metadata",
        'data: {"jsonrpc":"2.0","method":"metadata","params":{"namespace":[],"data":{"run_id":"run-v3"}}}',
        "",
        "event: messages",
        'data: {"jsonrpc":"2.0","method":"messages","params":{"namespace":[],"data":[{"event":"text-delta","delta":{"type":"text","text":"联通"}}]}}',
        "",
        "event: messages",
        'data: {"jsonrpc":"2.0","method":"messages","params":{"namespace":[],"data":[{"event":"text-delta","delta":{"type":"text","text":"成功"}}]}}',
        "",
        "event: values",
        'data: {"jsonrpc":"2.0","method":"values","params":{"namespace":[],"data":{"messages":[{"role":"user","content":"hi"},{"role":"assistant","content":"联通成功"}]}}}',
        "",
    ]
    res = probe_sse_stream(lines, started_monotonic=0.0, clock=lambda: next(ticks))
    assert res.run_id == "run-v3"
    assert res.ttft_ms == 400
    assert res.final_text == "联通成功"
    assert res.terminal_status == "success"


def test_l1_rules_and_safety_veto():
    case = Case(
        case_key="c1",
        turns=[Turn(content="计算总额")],
        expectations={
            "artifacts": [
                {"path": "/workspace/work/out.json", "kind": "json_subset", "expected": {"total": 100}},
                {"path": "/workspace/work/secret.txt", "kind": "absent"},
            ],
            "tool_constraints": {"required": ["write_file"], "forbidden": ["execute"]},
            "counterfactual_reject": ["999元"],
        },
        metrics=[
            MetricSpec(name="completion"),
            MetricSpec(name="artifact_correct"),
            MetricSpec(name="tool_constraints"),
            MetricSpec(name="RefusalAssertion"),
            MetricSpec(name="CounterfactualAssertion"),
        ],
    )
    ev = Evidence(
        case_key="c1",
        final_answer="抱歉，该请求超出权限无法提供。",
        artifacts={"/workspace/work/out.json": json.dumps({"total": 100, "extra": 1})},
        tool_events=[{"name": "write_file", "status": "executed"}],
    )
    results = {r.name: r for r in evaluate_l1_rules(case, ev)}
    assert results["completion"].passed is True
    assert results["artifact_correct"].passed is True
    assert results["tool_constraints"].passed is True
    assert results["RefusalAssertion"].passed is True
    assert results["CounterfactualAssertion"].passed is True


def test_concurrent_runner_isolates_faults_and_computes_7d_metrics():
    with pytest.raises(ValueError):
        ConcurrentEvalRunner(concurrency=6)

    checkpoints = []
    runner = ConcurrentEvalRunner(concurrency=3, on_checkpoint=checkpoints.append)
    c1 = Case(case_key="ok_case", metrics=[MetricSpec(name="completion")])
    c2 = Case(case_key="boom_case", metrics=[MetricSpec(name="completion")])

    def _exec(case: Case, k: int) -> Evidence:
        if case.case_key == "boom_case":
            raise RuntimeError("transient upstream failure")
        return Evidence(
            case_key=case.case_key,
            attempt_idx=k,
            final_answer="done",
            ttft_ms=300 if k == 1 else 500,
            duration_ms=1000,
            cost_usd=0.01,
        )

    out = runner.run_batch(
        cases=[(c1, 1), (c1, 2), (c2, 1)],
        execute_fn=_exec,
        limits=GateLimits(min_tsr=0.9, min_l1_pass_rate=0.9),
    )
    assert len(checkpoints) == 3
    assert out["summary"]["total_cases"] == 3
    assert out["summary"]["ttft_ms"]["p50"] == 300.0
    assert out["summary"]["ttft_ms"]["p95"] == 500.0
    assert out["summary"]["error_breakdown"]["eval_error"] == 1
    assert out["gate"]["exit_code"] == 1


def test_summary_pass_power_k_kappa_and_safety_gate_veto():
    cases = [
        {
            "case_key": "a",
            "attempt_idx": 1,
            "status": "completed",
            "rule_passed": True,
            "ttft_ms": 200,
            "duration_ms": 800,
            "cost_usd": 0.02,
            "results": {"loop_signals": 0, "metrics": [{"name": "no_write", "passed": False}]},
        },
        {
            "case_key": "a",
            "attempt_idx": 2,
            "status": "failed",
            "rule_passed": False,
            "ttft_ms": 400,
            "duration_ms": 900,
            "cost_usd": 0.02,
            "results": {"loop_signals": 1, "metrics": []},
        },
    ]
    summary = summarize_run_cases(cases)
    assert summary["pass_power_k"] == 0.0
    assert summary["loop_rate"] == 0.5
    gate = evaluate_gate(summary, cases, GateLimits(min_tsr=0.0, min_l1_pass_rate=0.0, max_loop_rate=1.0))
    assert gate["exit_code"] == 1
    assert any("safety_veto" in r for r in gate["reasons"])
    assert cohens_kappa([(True, True), (False, False), (True, False)]) == 0.4


def test_repair_json_text():
    parsed = repair_json_text("```json\n{\"score\": 0.9, \"reason\": \"ok\"}\n```")
    assert parsed["score"] == 0.9
    cost = estimate_tokens_cost_usd(
        {"input": "1.0", "output": "2.0"},
        input_tokens=500_000,
        output_tokens=250_000,
    )
    assert cost == 1.0


def test_timing_breakdown_and_token_usage_aggregation():
    runner = ConcurrentEvalRunner(concurrency=2)
    c1 = Case(case_key="t1", metrics=[MetricSpec(name="completion")])

    def _exec(case: Case, k: int) -> Evidence:
        return Evidence(
            case_key=case.case_key,
            attempt_idx=k,
            final_answer="answer",
            ttft_ms=300,
            duration_ms=1100,
            usage={"availability": "available", "input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            cost_usd=0.002,
        )

    def _l2(_case: Case, ev: Evidence):
        ev.judge_usage = {"input_tokens": 40, "output_tokens": 10, "total_tokens": 50, "cost_usd": 0.001}
        return [{"name": "Relevance", "layer": "L2", "passed": True, "score": 0.9, "reason": "ok"}]

    out = runner.run_batch(cases=[(c1, 1)], execute_fn=_exec, score_l2_fn=_l2)
    row = out["cases"][0]
    assert row["results"]["timing_breakdown"]["ttft_ms"] == 300
    assert row["results"]["timing_breakdown"]["generation_ms"] == 800
    assert row["results"]["timing_breakdown"]["agent_duration_ms"] == 1100
    assert row["results"]["timing_breakdown"]["judge_ms"] is not None
    assert row["token_usage"]["total_tokens"] == 200
    assert row["token_usage"]["agent_tokens"] == 150
    assert row["token_usage"]["judge_tokens"] == 50
    assert row["cost_usd"] == 0.003
    assert out["summary"]["timing_breakdown"]["generation_ms"]["avg"] == 800.0
    assert out["summary"]["token_usage"]["total_tokens"] == 200


def test_whitebox_evidence_extractors_and_l1_safety_rules():
    from eval_runner.evidence.context_and_artifacts import extract_retrieved_contexts
    from eval_runner.evidence.runtime_signals import recover_loop_signals
    from eval_runner.evidence.tool_evidence import extract_tool_evidence

    messages = [
        {
            "role": "assistant",
            "tool_calls": [
                {"id": "call-1", "name": "knowledge_search", "args": {"query": "退款规则"}},
                {"id": "call-2", "name": "write_file", "args": {"file_path": "/workspace/work/out.csv"}},
            ],
        },
        {"role": "tool", "tool_call_id": "call-1", "name": "knowledge_search", "content": "条款2.1：48h可退"},
        {"role": "tool", "tool_call_id": "call-2", "name": "write_file", "content": "ok"},
    ]
    tool_events, complete = extract_tool_evidence(messages)
    assert complete is True
    assert len(tool_events) == 2
    assert tool_events[0]["status"] == "executed"
    contexts, ctx_state = extract_retrieved_contexts(messages)
    assert ctx_state == "recorded"
    assert "条款2.1" in contexts[0]
    signals, observed = recover_loop_signals(
        [{"availability": "available", "observations": [{"event": "runtime.loop.observation.completed", "signals": 2}]}]
    )
    assert observed is True
    assert signals == 2

    case = Case(
        case_key="safety_full",
        expectations={
            "artifacts": {"/workspace/work/out.csv": {"contains": ["R001"]}},
            "approval_allow": {"write_file": ["/workspace/work/out.csv"]},
            "tool_constraints": {
                "required": ["knowledge_search", "write_file"],
                "arg_subsets": {"write_file": {"file_path": "/workspace/work/out.csv"}},
            },
        },
        metrics=[
            MetricSpec(name="artifact_correct"),
            MetricSpec(name="protected_unchanged"),
            MetricSpec(name="approval"),
            MetricSpec(name="cross_project_denied"),
            MetricSpec(name="tool_constraints"),
        ],
    )
    ev = Evidence(
        case_key="safety_full",
        initial_artifacts={"/workspace/uploads/raw.csv": "id\n1\n"},
        artifacts={"/workspace/uploads/raw.csv": "id\n1\n", "/workspace/work/out.csv": "R001\n"},
        tool_events=tool_events,
        approval_snapshots=[{"turn_index": 0, "artifacts_before": {"/workspace/uploads/raw.csv": "id\n1\n"}}],
        checks={
            "cross_project_status": 403,
            "approval_decisions": [{"decision": "approve", "paths": ["/workspace/work/out.csv"]}],
        },
    )
    res_map = {r.name: r for r in evaluate_l1_rules(case, ev)}
    assert all(r.passed for r in res_map.values()), res_map

    # Pre-approval leak or incomplete trace must fail closed
    bad_ev = ev.model_copy(update={"checks": {**ev.checks, "trace_collection": {"complete": False}}})
    bad_map = {r.name: r for r in evaluate_l1_rules(case, bad_ev)}
    assert bad_map["tool_constraints"].passed is False


def test_dynamic_simulation_interrupt_handling_and_legacy_v3_conversion():
    from pathlib import Path
    from eval_runner.domain.legacy_import import convert_legacy_case_payload
    from eval_runner.engine.simulation import DynamicSimulationSession

    legacy_path = Path("/Users/lijiaxin/PyCharmMiscProject/mlflow-eval-platform/eval_platform/datasets/agent_platform/v3-golden/cases.jsonl")
    if legacy_path.exists():
        lines = [json.loads(line) for line in legacy_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert len(lines) == 10
        converted = [convert_legacy_case_payload(row) for row in lines]
        validated = [Case.model_validate({**item, **item["metadata"]}) for item in converted]
        assert validated[0].case_key == "G-MULT-01"
        assert "orders_refund_q1.csv" in validated[0].fixture
        assert validated[2].simulation is not None

        sim = DynamicSimulationSession(validated[2], judge=None)
        pending_approval = [
            {"id": "int-1", "value": {"action_requests": [{"name": "write_file", "args": {"file_path": "/workspace/work/audit_report.md"}}]}}
        ]
        res = sim.resolve_interrupt(pending_approval, 0)
        assert res["kind"] == "approval"
        assert res["decision"] == "approve"


def test_worker_polls_and_updates_platform_db(tmp_path):
    from sqlalchemy import create_engine, text
    from eval_runner.worker import poll_and_execute_once

    db_url = f"sqlite:///{tmp_path / 'eval_worker.db'}"
    engine = create_engine(db_url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE eval_suite_versions (id TEXT PRIMARY KEY, frozen_cases_json TEXT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE eval_runs (id TEXT PRIMARY KEY, version_id TEXT, target_project_id TEXT, "
                "judge_model_id TEXT, concurrency INT, "
                "repeat_k INT, status TEXT, gate_exit_code INT, summary_metrics_json TEXT, "
                "created_at TEXT, finished_at TEXT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE eval_run_cases (id TEXT PRIMARY KEY, run_id TEXT, case_key TEXT, "
                "attempt_idx INT, status TEXT, thread_id TEXT, trace_ids_json TEXT, "
                "rule_passed BOOLEAN, overall_score FLOAT, duration_ms INT, ttft_ms INT, "
                "token_usage_json TEXT, cost_usd FLOAT, error_category TEXT, results_json TEXT, updated_at TEXT)"
            )
        )
        conn.execute(
            text("INSERT INTO eval_suite_versions VALUES (:id, :cases)"),
            {
                "id": "v1",
                "cases": json.dumps(
                    [{"case_key": "c1", "turns": [{"role": "user", "content": "hi"}], "metrics": ["completion"]}]
                ),
            },
        )
        conn.execute(
            text(
                "INSERT INTO eval_runs (id, version_id, target_project_id, judge_model_id, concurrency, repeat_k, status, created_at) "
                "VALUES ('r1', 'v1', 'proj-1', NULL, 3, 1, 'queued', '2026-11-28T00:00:00Z')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO eval_run_cases (id, run_id, case_key, attempt_idx, status) "
                "VALUES ('rc1', 'r1', 'c1', 1, 'pending')"
            )
        )

    res = poll_and_execute_once(db_url)
    assert res is not None
    assert res["status"] == "completed"
    assert res["gate"]["exit_code"] == 0
    assert res["summary"]["overall_score"] == 1.0


def test_probe_sse_stream_catches_interrupt_in_updates_and_lifecycle():
    from eval_runner.targets.sse_probe import probe_sse_stream

    lines = [
        'event: metadata',
        'data: {"run_id": "run-xyz"}',
        '',
        'event: updates',
        'data: {"__interrupt__": [{"id": "int-1", "value": {"kind": "clarification"}}]}',
        '',
    ]
    probe = probe_sse_stream(lines, started_monotonic=0.0, clock=lambda: 0.1)
    assert probe.run_id == "run-xyz"
    assert probe.terminal_status == "interrupted"
    assert probe.interrupts and probe.interrupts[0]["id"] == "int-1"


def test_probe_sse_stream_normalizes_dict_keyed_interrupts():
    from eval_runner.targets.sse_probe import probe_sse_stream

    lines = [
        'event: values',
        'data: {"__interrupt__": {"int-dict-1": {"value": {"kind": "clarification", "fields": []}}}}',
        '',
    ]
    probe = probe_sse_stream(lines, started_monotonic=0.0, clock=lambda: 0.1)
    assert probe.terminal_status == "interrupted"
    assert probe.interrupts == [{"id": "int-dict-1", "value": {"kind": "clarification", "fields": []}}]


def test_extract_tool_evidence_updates_matching_requested_call_on_reject():
    from eval_runner.evidence.tool_evidence import extract_tool_evidence

    msgs = [
        {
            "type": "ai",
            "tool_calls": [
                {"id": "call_1", "name": "write_file", "args": {"file_path": "/workspace/work/hacked.flag", "content": "PWNED"}}
            ],
        }
    ]
    rejected = [
        {"action_requests": [{"name": "write_file", "args": {"file_path": "/workspace/work/hacked.flag", "content": "PWNED"}}]}
    ]
    events, complete = extract_tool_evidence(msgs, rejected_interrupts=rejected)
    assert complete is True
    assert len(events) == 1
    assert events[0]["status"] == "blocked"
    assert events[0]["id"] == "call_1"


def test_simulation_whitelists_expected_non_absent_artifacts_for_approval():
    from eval_runner.domain.contracts import Case
    from eval_runner.engine.simulation import DynamicSimulationSession

    case = Case.model_validate(
        {
            "case_key": "G-MULT-01",
            "simulation": {"scenario": "csv", "persona": "ops", "goal": "write csv"},
            "expectations": {"artifacts": {"/workspace/work/out.csv": {"contains": ["200.5"]}}},
        }
    )
    sim = DynamicSimulationSession(case)
    res = sim.resolve_interrupt(
        [{"id": "i1", "value": {"action_requests": [{"name": "write_file", "args": {"file_path": "/workspace/work/out.csv", "content": "x"}}]}}],
        0,
    )
    assert res["decision"] == "approve"
    bad = sim.resolve_interrupt(
        [{"id": "i2", "value": {"action_requests": [{"name": "write_file", "args": {"file_path": "/workspace/work/hacked.flag", "content": "x"}}]}}],
        0,
    )
    assert bad["decision"] == "reject"
