from concurrent.futures import ThreadPoolExecutor

import pytest

from runtime_service.runtime.errors import RuntimeResolutionError
from runtime_service.runtime.token_budget import (
    MAX_SAFE_INTEGER,
    RunTokenBudget,
    TokenBudgetPolicy,
    resolve_token_budget_policy,
)


def test_default_disabled_and_enabled_usage_dependency(monkeypatch):
    monkeypatch.delenv("RUNTIME_TOKEN_BUDGET_ENABLED", raising=False)
    assert resolve_token_budget_policy() is None
    monkeypatch.setenv("RUNTIME_TOKEN_BUDGET_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "false")
    with pytest.raises(RuntimeResolutionError):
        resolve_token_budget_policy()
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_TOKEN_BUDGET_MAX_TOKENS", "101")
    assert resolve_token_budget_policy() == TokenBudgetPolicy(101, 81)


@pytest.mark.parametrize("raw", ["", "tru", "2"])
def test_invalid_switch_fails_closed(monkeypatch, raw):
    monkeypatch.setenv("RUNTIME_TOKEN_BUDGET_ENABLED", raw)
    with pytest.raises(RuntimeResolutionError):
        resolve_token_budget_policy()


@pytest.mark.parametrize(
    "raw", ["", "0", "-1", "True", "1.5", "NaN", str(MAX_SAFE_INTEGER + 1)]
)
def test_invalid_cap(monkeypatch, raw):
    monkeypatch.setenv("RUNTIME_TOKEN_BUDGET_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_USAGE_ENABLED", "true")
    monkeypatch.setenv("RUNTIME_TOKEN_BUDGET_MAX_TOKENS", raw)
    with pytest.raises(RuntimeResolutionError):
        resolve_token_budget_policy()


def test_incremental_dedup_quality_replacement_and_natural_completion():
    budget = RunTokenBudget(TokenBudgetPolicy(100, 80))
    budget.begin_call("one")
    assert budget.check() == "ok"
    budget.record_call("one", total_tokens=20, quality="partial")
    assert budget.check() == "unverifiable"
    budget.record_call("one", total_tokens=79, quality="reported")
    assert budget.check() == "ok" and budget.used_tokens == 79
    budget.record_call("one", total_tokens=1000, quality="reported")
    assert budget.used_tokens == 79
    budget.record_call("two", total_tokens=1, quality="reported")
    assert budget.check() == "approaching"
    budget.record_call("three", total_tokens=25, quality="derived_from_reported")
    assert budget.check() == "exhausted"
    assert budget.public_snapshot()["remaining_tokens"] == 0
    assert budget.public_snapshot()["stop_code"] is None
    budget.mark_stop("token_budget_exhausted")
    assert budget.public_snapshot()["stop_code"] == "token_budget_exhausted"


def test_restored_calls_do_not_double_count_and_new_run_is_independent():
    budget = RunTokenBudget(TokenBudgetPolicy(1000, 800))
    budget.load(
        policy=TokenBudgetPolicy(100, 80),
        used_tokens=80,
        unverifiable=False,
        stop_code=None,
        calls=[{"model_call_id": "one", "total_tokens": 80, "quality": "reported"}],
    )
    budget.record_call("one", total_tokens=80, quality="reported")
    assert budget.used_tokens == 80 and budget.policy.max_tokens == 100
    assert RunTokenBudget(TokenBudgetPolicy(100, 80)).used_tokens == 0


def test_concurrent_calls_and_notice_claims_are_idempotent():
    budget = RunTokenBudget(TokenBudgetPolicy(100, 80))
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(
            pool.map(
                lambda i: budget.record_call(
                    str(i % 20), total_tokens=1, quality="reported"
                ),
                range(1000),
            )
        )
        claims = list(
            pool.map(
                lambda _: budget.claim_notice("token_budget_approaching"), range(100)
            )
        )
    assert budget.used_tokens == 20 and sum(claims) == 1


@pytest.mark.parametrize("number", [None, True, -1, 1.5, MAX_SAFE_INTEGER + 1])
def test_unknown_numbers_cannot_be_reported_as_zero(number):
    budget = RunTokenBudget(TokenBudgetPolicy(100, 80))
    budget.record_call("one", total_tokens=number, quality="missing")
    assert budget.check() == "unverifiable"
    assert budget.public_snapshot()["remaining_tokens"] is None


def test_safe_integer_aggregate_overflow_keeps_facts_but_hides_unsafe_subtotal():
    budget = RunTokenBudget(
        TokenBudgetPolicy(MAX_SAFE_INTEGER, (MAX_SAFE_INTEGER * 4 + 4) // 5)
    )
    budget.record_call("one", total_tokens=MAX_SAFE_INTEGER, quality="reported")
    budget.record_call("two", total_tokens=1, quality="reported")
    assert budget.used_tokens == MAX_SAFE_INTEGER + 1
    assert budget.check() == "unverifiable"
    snapshot = budget.public_snapshot()
    assert snapshot["known_used_tokens"] is None
    assert snapshot["remaining_tokens"] is None
    assert snapshot["coverage"] == "unavailable"


def test_persisted_projection_incomplete_calls_and_degraded_are_unknown():
    from runtime_service.observability.usage_query import project_token_budget

    for field in ("incomplete_call_count", "missing_usage_call_count", "degraded"):
        summary = dict(
            token_budget_policy=TokenBudgetPolicy(100, 80).as_dict(),
            total_tokens=20,
            incomplete_call_count=0,
            missing_usage_call_count=0,
            degraded=False,
        )
        summary[field] = 1
        assert project_token_budget(summary)["remaining_tokens"] is None
    summary["total_tokens"] = MAX_SAFE_INTEGER + 1
    assert project_token_budget(summary)["known_used_tokens"] is None
