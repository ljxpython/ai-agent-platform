from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest
from support import with_run_budget

from runtime_service.runtime.errors import RuntimeResolutionError
from runtime_service.runtime.run_budget import (
    RUN_BUDGET_KEY,
    read_run_budget,
    resolve_wrapup_reserve_seconds,
)


def test_budget_is_immutable_and_separate_for_each_run():
    first = read_run_budget(with_run_budget({"configurable": {"thread_id": "a"}}))
    second = read_run_budget(with_run_budget({"configurable": {"thread_id": "b"}}))
    assert first.run_id != second.run_id
    assert first.soft_deadline_monotonic == first.deadline_monotonic - 120
    with pytest.raises(FrozenInstanceError):
        first.timeout_seconds = 10


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", True),
        ("version", 2),
        ("timeout_seconds", False),
        ("timeout_seconds", -1),
        ("timeout_seconds", float("nan")),
        ("deadline_monotonic", float("inf")),
        ("deadline_monotonic", "123"),
        ("run_id", "other"),
        ("thread_id", "other"),
        ("deadline_at", "2026-10-06T00:00:00"),
        ("started_at", "bad"),
    ],
)
def test_invalid_worker_snapshot_is_rejected(field, value):
    config = with_run_budget({"configurable": {"thread_id": "thread"}})
    config["configurable"][RUN_BUDGET_KEY][field] = value
    with pytest.raises(RuntimeResolutionError):
        read_run_budget(config)


def test_missing_budget_is_allowed_only_for_probe_or_explicit_local_test():
    assert read_run_budget({}, required=False) is None
    with pytest.raises(RuntimeResolutionError):
        read_run_budget({})


@pytest.mark.parametrize(
    "raw", ["-1", "True", "NaN", "Infinity", "120.5", "300", "301"]
)
def test_invalid_reserve(raw):
    with pytest.raises(ValueError):
        resolve_wrapup_reserve_seconds(300, raw)


def test_reserve_defaults_and_can_be_disabled(monkeypatch):
    assert resolve_wrapup_reserve_seconds(300, "") == 120
    assert resolve_wrapup_reserve_seconds(1, "0") == 0
    monkeypatch.setenv("AGENT_RUN_WRAPUP_RESERVE_SECONDS", "0")
    assert (
        read_run_budget(
            with_run_budget({"configurable": {"thread_id": "a"}})
        ).wrapup_reserve_seconds
        == 0
    )
