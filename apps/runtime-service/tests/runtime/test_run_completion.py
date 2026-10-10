import asyncio

import pytest
from langgraph.errors import GraphRecursionError

from runtime_service.run_completion.projector import project_terminal_outcome
from runtime_service.runtime.auth import _optional_callback_context
from runtime_service.runtime.errors import RuntimeAuthError, RuntimeErrorBase


@pytest.mark.parametrize(
    "code",
    [
        "provider_rate_limited",
        "provider_overloaded",
        "context_too_long",
        "model_unavailable",
        "provider_auth_failed",
        "provider_access_denied",
        "provider_timeout",
        "provider_unavailable",
        "model_call_failed",
    ],
)
def test_provider_categories_are_safe_final_codes(code):
    error = RuntimeErrorBase(code, "CANARY-private-provider")
    assert project_terminal_outcome(error) == {
        "reason_code": "runtime_execution_failed",
        "model_error_code": code,
    }


@pytest.mark.parametrize(
    "code",
    [
        "runtime.model.retry_exhausted",
        "runtime.model.retry_budget_exceeded",
        "runtime.model.stream_interrupted",
        "runtime.model.provider_rejected",
        "runtime.model.fallback_incompatible",
        "runtime.workspace.unavailable",
        "runtime.workspace.execution_unavailable",
        "runtime.workspace.backend_invalid",
        "runtime.workspace.image_invalid",
        "runtime.workspace.execution_outcome_unknown",
    ],
)
def test_runtime_categories_reject_unknown_provider_detail(code):
    error = RuntimeErrorBase(code, "CANARY-private-provider")
    error.model_error_code = "CANARY-secret"
    assert project_terminal_outcome(error) == {
        "reason_code": code,
        "model_error_code": None,
    }


def test_projection_is_pure_and_uses_only_final_safe_codes():
    assert project_terminal_outcome(GraphRecursionError("CANARY-private")) == {
        "reason_code": "runtime_graph_step_limit_reached",
        "model_error_code": None,
    }
    final = RuntimeErrorBase("runtime.model.retry_exhausted", "CANARY-provider")
    final.model_error_code = "provider_overloaded"
    result = project_terminal_outcome(final)
    assert result["reason_code"] == "runtime.model.retry_exhausted"
    assert result["model_error_code"] == "provider_overloaded"
    assert "CANARY" not in str(result)
    assert project_terminal_outcome(RuntimeError("CANARY-provider")) == {
        "reason_code": "runtime_execution_failed",
        "model_error_code": None,
    }
    assert project_terminal_outcome(asyncio.CancelledError()) == {}


@pytest.mark.parametrize(
    "value",
    [
        {"origin_ref": "x\n"},
        {"origin_ref": "not-a-uuid"},
        {"origin_ref": "1", "url": "https://example.com"},
    ],
)
def test_invalid_trusted_callback_claim_rejected(value):
    with pytest.raises(RuntimeAuthError):
        _optional_callback_context({"callback_context": value})
