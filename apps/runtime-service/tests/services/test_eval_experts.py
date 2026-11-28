"""Tests for eval_copilot and eval_diagnosis LangGraph expert graphs."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json

from runtime_service.graphs import eval_copilot, eval_diagnosis
from runtime_service.services import eval_shared
from runtime_service.services.eval_copilot.agent import (
    _normalize_upload_path,
    list_skill_topics,
    read_skill_content,
    safe_calculate,
    validate_case_draft,
)


def test_expert_graphs_support_schema_only_introspection():
    g1 = asyncio.run(eval_copilot.get_agent({}))
    g2 = asyncio.run(eval_diagnosis.get_agent({}))
    assert g1 is not None
    assert g2 is not None


def test_copilot_calculator_and_case_validation():
    assert safe_calculate("(100 + 25) * 0.8") == "100.0"
    ok = validate_case_draft(
        json.dumps(
            {
                "case_key": "case_1",
                "split": "dev",
                "turns": [{"role": "user", "content": "hi"}],
                "metrics": [{"name": "completion"}],
            }
        )
    )
    assert ok == {"valid": True, "errors": []}
    bad = validate_case_draft(json.dumps({"case_key": "", "metrics": []}))
    assert bad["valid"] is False
    assert "case_key_required" in bad["errors"]

    anti_pitfall = validate_case_draft(
        json.dumps(
            {
                "case_key": "COP-PIT-1",
                "turns": [{"role": "user", "content": "读取 {{missing.csv}} 并计算"}],
                "expectations": {
                    "artifacts": [
                        {
                            "path": "/workspace/work/out.csv",
                            "kind": "contains",
                            "expected": "x",
                        }
                    ],
                    "tool_constraints": {"required": ["magic_tool"]},
                },
                "metrics": ["completion", "Faithfulness"],
            }
        ),
        graph_id="dearflow_agent",
    )
    assert anti_pitfall["valid"] is False
    assert any(
        "unknown_tools_for_dearflow_agent:magic_tool" in e
        for e in anti_pitfall["errors"]
    )
    assert any(
        "undeclared_fixture_placeholders:missing.csv" in e
        for e in anti_pitfall["errors"]
    )
    assert any(
        "non_rag_case_with_rag_metrics:Faithfulness" in e
        for e in anti_pitfall["errors"]
    )
    assert "artifact_correct" in " ".join(anti_pitfall["errors"])

    wrapped = validate_case_draft(
        '```json\n{"case": {"case_key": "COP-WRAP-1", "turns": [{"role": "user", "content": "hi"}], "metrics": ["completion"]}}\n```'
    )
    assert wrapped == {"valid": True, "errors": []}

    bad_role = validate_case_draft(
        {
            "case_key": "COP-BAD-ROLE",
            "turns": [
                {"role": "user", "content": "我要退款"},
                {"role": "assistant", "content": "请问原因"},
            ],
            "metrics": ["completion"],
        }
    )
    assert bad_role["valid"] is False
    assert any("invalid_turn_role:1:assistant" in e for e in bad_role["errors"])


def test_copilot_skills_and_upload_path_guard():
    from runtime_service.runtime.capabilities import graph_capabilities, graph_tools

    topics = {item["topic"] for item in list_skill_topics()}
    assert {
        "case-v3-schema",
        "multi-turn-simulation",
        "metrics-and-anti-pitfalls",
        "code-and-tool-scenarios",
    } <= topics
    assert "ambiguous_changer" in read_skill_content("multi-turn-simulation")
    assert _normalize_upload_path("spec.md") == "/workspace/uploads/spec.md"
    assert (
        _normalize_upload_path("/workspace/uploads/a.csv") == "/workspace/uploads/a.csv"
    )
    assert graph_capabilities("eval_copilot")["files"] is True
    assert "read_file" in graph_tools("eval_copilot")
    assert "write_file" in graph_tools("eval_copilot")


def test_eval_internal_post_signs_hmac_headers(monkeypatch):
    monkeypatch.setenv(
        "PLATFORM_RUNTIME_MODEL_CONFIG_URL",
        "http://127.0.0.1:2142/api/runtime/internal/model-config",
    )
    monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", "sec-123")
    captured = {}

    class _FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True}

    class _FakeClient:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, url, *, content, headers):
            captured["url"] = url
            captured["content"] = content
            captured["headers"] = headers
            return _FakeResp()

    monkeypatch.setattr(eval_shared.httpx, "Client", _FakeClient)
    res = eval_shared.eval_internal_post(
        "diagnosis-evidence",
        "/api/evaluation/internal/diagnosis-evidence",
        {"project_id": "p1", "run_id": "r1", "ref": "overview"},
    )
    assert res == {"ok": True}
    assert (
        captured["url"]
        == "http://127.0.0.1:2142/api/evaluation/internal/diagnosis-evidence"
    )
    expected_sig = hmac.new(
        b"sec-123",
        b"\n".join(
            [
                b"diagnosis-evidence",
                captured["headers"]["x-eval-time"].encode(),
                captured["content"],
            ]
        ),
        hashlib.sha256,
    ).hexdigest()
    assert captured["headers"]["x-eval-signature"] == expected_sig
