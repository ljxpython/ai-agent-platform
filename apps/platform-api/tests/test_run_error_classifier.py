"""Unit tests for run_error_classifier."""

from platform_api.modules.runtime_gateway.application.run_error_classifier import (
    classify_run_error,
)


class MockRateLimitError(Exception):
    status_code = 429


class MockOverloadedError(Exception):
    status_code = 529


class GraphRecursionError(Exception):
    pass


class SandboxConnectionError(Exception):
    pass


def test_classify_exact_code():
    res = classify_run_error(error_code="context_too_long")
    assert res["reason_code"] == "context_too_long"
    assert "窗口上限" in res["reason_text"]
    assert "开启新对话" in res["follow_up"]


def test_classify_from_exception_class_and_status():
    res_rl = classify_run_error(exc=MockRateLimitError("Rate limited"))
    assert res_rl["reason_code"] == "provider_rate_limited"
    assert "配额超限" in res_rl["follow_up"]

    res_ol = classify_run_error(exc=MockOverloadedError("Overloaded"))
    assert res_ol["reason_code"] == "provider_overloaded"

    res_rec = classify_run_error(exc=GraphRecursionError("Recursion limit 25 reached"))
    assert res_rec["reason_code"] == "step_limit"
    assert "拆分为小步骤" in res_rec["follow_up"]

    res_sb = classify_run_error(exc=SandboxConnectionError("Sandbox dead"))
    assert res_sb["reason_code"] == "sandbox_unreachable"


def test_classify_from_haystack_inference():
    res1 = classify_run_error(
        error_code="runtime.execution_failed",
        raw_message="429 Too Many Requests from upstream",
    )
    assert res1["reason_code"] == "provider_rate_limited"

    res2 = classify_run_error(
        raw_message="Prompt is too long or context_length_exceeded"
    )
    assert res2["reason_code"] == "context_too_long"

    res3 = classify_run_error(raw_message="Model call timed out after 60s")
    assert res3["reason_code"] == "provider_timeout"


def test_classify_fallback_default():
    res = classify_run_error(error_code="some_unknown_weird_error")
    assert res["reason_code"] == "some_unknown_weird_error"
    assert "可点击【查看排障详情】" in res["follow_up"]
