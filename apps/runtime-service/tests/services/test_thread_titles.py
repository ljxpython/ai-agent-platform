from __future__ import annotations

import asyncio
import hashlib
from dataclasses import replace
from threading import Event
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import AIMessage

from runtime_service.runtime import (
    RuntimeAuthError,
    RuntimeResolutionError,
    verified_delegation_from_user,
)
from runtime_service.runtime.resolver import runtime_context_hash
from runtime_service.services import thread_titles as titles
from runtime_service.workspace.documents import DocumentWorkspace
from runtime_service.workspace.scoped import resolve_thread_workspace


def facts(context=None):
    return verified_delegation_from_user(
        {
            "runtime_principal": {
                "user_id": "user",
                "tenant_id": "tenant",
                "project_id": "project",
                "role": "project_member",
                "permissions": [],
            },
            "runtime_policy": {
                "version": "v1",
                "allowed_model_ids": ["model"],
                "tool_overrides": {},
                "tool_policy_version": "v1",
            },
            "runtime_scope": {
                "tenant_id": "tenant",
                "project_id": "project",
                "thread_id": "thread",
                "assistant_id": "reference_agent",
                "operation": "title-generate",
            },
            "runtime_context_hash": runtime_context_hash(
                context or {"model_id": "model"}
            ),
        }
    )


def payload(**updates):
    return {
        "assistant_id": "reference_agent",
        "messages": [{"role": "user", "content": "规划权限设计"}],
        "context": {"model_id": "model"},
        "config": {"configurable": {"runtime_model_ref": "opaque"}},
        **updates,
    }


@pytest.mark.anyio
async def test_managed_one_shot_has_no_tools_retries_stream_or_parent_callbacks(
    monkeypatch,
):
    connection = AsyncMock(return_value={"model": "managed"})
    model = SimpleNamespace(
        ainvoke=AsyncMock(return_value=AIMessage(content="权限设计"))
    )
    build = Mock(return_value=model)
    monkeypatch.setattr(titles, "fetch_model_connection", connection)
    monkeypatch.setattr(titles, "build_model", build)
    result = await titles.generate_thread_title(
        facts=facts(), thread_id="thread", payload=payload()
    )
    assert result == {"title": "权限设计", "outcome": "applied", "reason": None}
    assert (
        build.call_args.kwargs["max_retries"] == 0 and model.disable_streaming is True
    )
    assert model.ainvoke.await_count == 1
    assert model.ainvoke.await_args.kwargs["config"] == {
        "callbacks": [],
        "tags": ["nostream"],
    }
    connection.assert_awaited_once_with(
        "opaque", model_id="model", project_id="project"
    )


@pytest.mark.anyio
async def test_deadline_covers_connection_and_cancellation_propagates(monkeypatch):
    async def slow(*args, **kwargs):
        await asyncio.sleep(10)

    monkeypatch.setattr(titles, "fetch_model_connection", slow)
    result = await titles.generate_thread_title(
        facts=facts(), thread_id="thread", payload=payload(timeout_seconds=0.01)
    )
    assert result["reason"] == "timeout"
    task = asyncio.create_task(
        titles.generate_thread_title(
            facts=facts(), thread_id="thread", payload=payload()
        )
    )
    await asyncio.sleep(0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.anyio
async def test_deadline_covers_blocking_model_construction(monkeypatch):
    release = Event()
    model = SimpleNamespace(ainvoke=AsyncMock(return_value=AIMessage(content="标题")))

    def build(*args, **kwargs):
        release.wait(1)
        return model

    monkeypatch.setattr(
        titles, "fetch_model_connection", AsyncMock(return_value={"model": "managed"})
    )
    monkeypatch.setattr(titles, "build_model", build)
    try:
        result = await titles.generate_thread_title(
            facts=facts(), thread_id="thread", payload=payload(timeout_seconds=0.02)
        )
        assert result["reason"] == "timeout"
        model.ainvoke.assert_not_awaited()
    finally:
        release.set()


@pytest.mark.anyio
async def test_policy_and_reference_errors_fail_closed_and_provider_degrades(
    monkeypatch,
):
    model = SimpleNamespace(
        ainvoke=AsyncMock(side_effect=ConnectionError("private error"))
    )
    assert (
        await titles.generate_thread_title(
            facts=facts(), thread_id="thread", payload=payload(), model=model
        )
    )["reason"] == "provider_failure"
    with pytest.raises(RuntimeAuthError):
        await titles.generate_thread_title(
            facts=replace(facts(), context_hash=runtime_context_hash(None)),
            thread_id="thread",
            payload=payload(),
            model=model,
        )
    denied = AsyncMock(
        side_effect=RuntimeResolutionError("runtime.model.reference_denied")
    )
    monkeypatch.setattr(titles, "fetch_model_connection", denied)
    with pytest.raises(RuntimeResolutionError):
        await titles.generate_thread_title(
            facts=facts(), thread_id="thread", payload=payload()
        )


@pytest.mark.anyio
async def test_empty_body_never_uses_reasoning_and_missing_model_degrades():
    model = SimpleNamespace(
        ainvoke=AsyncMock(
            return_value=AIMessage(
                content="", additional_kwargs={"reasoning_content": "private"}
            )
        )
    )
    assert (
        await titles.generate_thread_title(
            facts=facts(), thread_id="thread", payload=payload(), model=model
        )
    )["reason"] == "empty_output"
    assert (
        await titles.generate_thread_title(
            facts=facts({"temperature": 0.1}),
            thread_id="thread",
            payload=payload(context={"temperature": 0.1}),
            model=model,
        )
    )["reason"] == "model_unavailable"


@pytest.mark.anyio
async def test_attachment_only_uses_verified_thread_files_and_never_calls_model(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path))
    scoped_facts = replace(
        facts(), scope=replace(facts().scope, assistant_id="dearflow_agent")
    )
    root = resolve_thread_workspace("tenant", "project", "thread", "dearflow_agent")
    data = b"scoped attachment"
    ref = DocumentWorkspace(root).put(
        data, hashlib.sha256(data).hexdigest(), "text/plain", "权限设计.txt"
    )
    model = SimpleNamespace(ainvoke=AsyncMock())
    body = payload(assistant_id="dearflow_agent", messages=[], files=[ref])
    result = await titles.generate_thread_title(
        facts=scoped_facts, thread_id="thread", payload=body, model=model
    )
    assert result["outcome"] == "applied" and result["title"] == "权限设计txt"
    body["files"] = [ref, ref]
    assert (
        await titles.generate_thread_title(
            facts=scoped_facts, thread_id="thread", payload=body, model=model
        )
    )["title"] == "2个附件"
    body["files"] = [{**ref, "size_bytes": ref["size_bytes"] + 1}]
    assert (
        await titles.generate_thread_title(
            facts=scoped_facts, thread_id="thread", payload=body, model=model
        )
    )["reason"] == "materials_missing"
    body["files"] = [ref]
    other = replace(scoped_facts, scope=replace(scoped_facts.scope, thread_id="other"))
    assert (
        await titles.generate_thread_title(
            facts=other, thread_id="other", payload=body, model=model
        )
    )["reason"] == "materials_missing"
    model.ainvoke.assert_not_awaited()
