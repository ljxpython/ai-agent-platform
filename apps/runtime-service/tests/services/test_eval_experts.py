"""Tests for eval_copilot and eval_diagnosis LangGraph expert graphs."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json

from runtime_service.graphs import eval_copilot, eval_diagnosis
from runtime_service.services import eval_shared
from runtime_service.services.eval_copilot.agent import (
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
