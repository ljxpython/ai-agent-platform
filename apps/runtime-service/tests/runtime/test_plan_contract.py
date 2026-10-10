import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langchain_core.tools import ToolException
from pydantic import ValidationError

from runtime_service.observability.diagnostics import safe_fields
from runtime_service.runtime import (
    RuntimeResolutionError,
    parse_runtime_context,
    runtime_context_hash,
)
from runtime_service.runtime.planning import (
    PlanReply,
    apply_plan_reply,
    new_plan,
    plan_content_hash,
    read_plan,
    validate_plan_text,
)
from runtime_service.services.dearflow_agent.middleware import memory
from runtime_service.services.dearflow_agent.tools import search
from runtime_service.tools.plan_mode import save_plan


def draft():
    plan = new_plan("execution")
    plan = plan.model_copy(
        update={"revision": 1, "title": "Plan", "markdown": "Research first."}
    )
    plan.content_hash = plan_content_hash(plan)
    return plan


@pytest.mark.parametrize("value", [None, "true", 0, 1, [], {}])
def test_plan_context_requires_boolean(value):
    with pytest.raises(RuntimeResolutionError):
        parse_runtime_context({"plan_mode": value})


def test_signed_context_and_snapshot_integrity():
    assert runtime_context_hash({}) != runtime_context_hash({"plan_mode": True})
    assert runtime_context_hash({"plan_execution_id": "a"}) != runtime_context_hash(
        {"plan_execution_id": "b"}
    )
    plan = draft()
    assert read_plan({"runtime_plan": plan.model_dump()}) == plan
    raw = plan.model_dump()
    raw["markdown"] = "forged"
    with pytest.raises(RuntimeResolutionError):
        read_plan({"runtime_plan": raw})
    with pytest.raises(RuntimeResolutionError):
        read_plan({"runtime_plan": {**plan.model_dump(), "active": False}})


@pytest.mark.parametrize(
    "title,markdown",
    [
        ("", "draft"),
        ("x" * 129, "draft"),
        ("Plan", ""),
        ("Plan", "x" * 65537),
        ("Plan", "\ud800"),
    ],
)
def test_invalid_plan_content(title, markdown):
    with pytest.raises(RuntimeResolutionError):
        validate_plan_text(title, markdown)


def test_reply_revision_identity_and_strict_version():
    plan = draft()
    answer = {
        "version": 1,
        "type": "agent_plan_response",
        "plan_id": plan.plan_id,
        "revision": plan.revision,
        "content_hash": plan.content_hash,
        "decision": "approve",
    }
    approved = apply_plan_reply(plan, answer, "human")
    assert not approved.active and approved.approved_by == {"user_id": "human"}
    for update in (
        {"revision": 2},
        {"version": True},
        {"active": False},
        {"decision": "request_changes"},
    ):
        with pytest.raises((RuntimeResolutionError, ValidationError)):
            apply_plan_reply(plan, {**answer, **update}, "human")
    with pytest.raises(ValidationError):
        PlanReply.model_validate({**answer, "revision": True})


def test_active_plan_skips_automatic_memory(monkeypatch):
    allowed = AsyncMock()
    monkeypatch.setattr(memory, "memory_allowed", allowed)
    middleware = memory.MemoryContextMiddleware(None)
    asyncio.run(
        middleware.aafter_agent(
            {"runtime_plan": new_plan("execution").model_dump()},
            SimpleNamespace(context={}),
        )
    )
    allowed.assert_not_awaited()


@pytest.mark.parametrize("link", ["directory", "file"])
def test_research_cache_rejects_symlink_escape(tmp_path, link):
    import hashlib

    root, outside = tmp_path / "workspace", tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    target = outside / "canary.txt"
    target.write_text("unchanged")
    if link == "directory":
        (root / "sources").symlink_to(outside, target_is_directory=True)
    else:
        (root / "sources").mkdir()
        digest = hashlib.sha256(b"evidence").hexdigest()
        (root / "sources" / (digest + ".txt")).symlink_to(target)
    runtime = SimpleNamespace(
        tool_call_id="call",
        execution_info=SimpleNamespace(
            thread_id="thread", run_id="run", checkpoint_ns=""
        ),
    )
    with pytest.raises(ToolException):
        search._evidence(
            SimpleNamespace(root=root),
            runtime,
            [{"source_url": "https://example.com", "content": "evidence"}],
        )
    assert target.read_text() == "unchanged"
    assert list(outside.iterdir()) == [target]
    assert not list(root.rglob(".source-*"))


def test_save_normalizes_text_and_does_not_add_revisions_for_identical_content():
    runtime = SimpleNamespace(
        state={"runtime_plan": new_plan("execution").model_dump()},
        context={"plan_execution_id": "execution"},
        server_info=None,
        tool_call_id="save",
    )
    first = save_plan.func(" Plan ", "Read\r\nthen validate.", runtime)
    runtime.state = first.update
    second = save_plan.func("Plan", "Read\nthen validate.", runtime)
    assert second.update["runtime_plan"] == first.update["runtime_plan"]
    third = save_plan.func("Plan", "Read\nthen validate and roll back.", runtime)
    assert third.update["runtime_plan"]["revision"] == 2
    assert (
        third.update["runtime_plan"]["content_hash"]
        != first.update["runtime_plan"]["content_hash"]
    )


def test_plan_audit_fields_exclude_markdown_and_execution_identity():
    result = safe_fields(
        {
            "plan_id": "plan",
            "revision": 1,
            "content_hash": "sha256:" + "a" * 64,
            "actor_id": "human",
            "decision": "approve",
            "markdown": "PRIVATE_CANARY",
            "plan_execution_id": "PRIVATE_CANARY",
        }
    )
    assert set(result) == {
        "plan_id",
        "revision",
        "content_hash",
        "actor_id",
        "decision",
    }
