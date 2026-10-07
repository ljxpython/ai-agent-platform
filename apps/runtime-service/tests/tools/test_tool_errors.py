"""Safe native and official middleware errors share a selective, bounded contract."""

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import ToolErrorMiddleware
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import ToolException, tool
from langgraph.errors import GraphBubbleUp
from support import BindableFakeMessagesChatModel

from runtime_service.runtime.errors import (
    RuntimeAuthError,
    RuntimeResolutionError,
    RuntimeWorkspaceError,
)
from runtime_service.services.dearflow_agent.tools import media
from runtime_service.tools.errors import (
    handle_expected_tool_error,
    is_transport_error,
    on_tool_error,
    tool_error_content,
)
from runtime_service.tools.images import (
    ImageWorkspace,
    ImageWorkspaceError,
    build_image_tools,
)
from runtime_service.workspace.documents import DocumentError


@pytest.mark.parametrize(
    "name,error,code,outcome",
    [
        (
            "search_web",
            ToolException("invalid_research_query"),
            "tool.invalid_input",
            "not_started",
        ),
        (
            "search_web",
            ToolException("research_provider_failed"),
            "tool.upstream_unavailable",
            "failed",
        ),
        (
            "github_query",
            ToolException("invalid_github_path"),
            "tool.invalid_input",
            "not_started",
        ),
        (
            "arxiv_search",
            ToolException("invalid_arxiv_date_range"),
            "tool.invalid_input",
            "not_started",
        ),
        (
            "parse_document",
            DocumentError("invalid_page_range"),
            "tool.invalid_input",
            "not_started",
        ),
        (
            "edit_image",
            ImageWorkspaceError("image_path_invalid", "PATH_TOKEN_CANARY"),
            "tool.invalid_input",
            "not_started",
        ),
        (
            "generate_image",
            ToolException("image_submission_unknown"),
            "tool.outcome_unknown",
            "unknown",
        ),
        (
            "generate_image",
            ToolException("external_task_idempotency_conflict"),
            "tool.outcome_unknown",
            "unknown",
        ),
        (
            "generate_image",
            ToolException("external_task_capacity"),
            "tool.operation_failed",
            "not_started",
        ),
    ],
)
def test_approved_content_is_bounded_and_uses_only_trusted_fields(
    name, error, code, outcome
):
    error.__cause__ = ValueError(
        "SECRET_CANARY /private/path token=secret https://provider.invalid"
    )
    content = tool_error_content(error, name)
    assert len(content.encode()) <= 2048
    payload = json.loads(content)
    assert payload["status"] == "error" and payload["name"] == name
    assert payload["code"] == code and payload["outcome"] == outcome
    assert payload["error_type"] == type(error).__name__
    assert "CANARY" not in content and "provider.invalid" not in content
    request = SimpleNamespace(tool_call={"name": name, "id": "call"})
    assert (
        on_tool_error(error, request)
        == handle_expected_tool_error(error, tool_name=name)
        == content
    )


@pytest.mark.parametrize(
    "error",
    [
        RuntimeAuthError("runtime.auth.denied"),
        RuntimeResolutionError("runtime.tool.not_allowed"),
        RuntimeWorkspaceError("runtime.workspace.unavailable"),
        GraphBubbleUp(),
        asyncio.CancelledError(),
        RuntimeError("defect"),
        ValueError("unknown"),
        ToolException("unknown"),
        DocumentError("memory_scope_denied", 403),
        DocumentError("file_hash_mismatch", 409),
        DocumentError("memory_maintenance_required"),
        ImageWorkspaceError("image_workspace_unavailable", "CANARY"),
        ExceptionGroup("mixed", [ConnectionError(), RuntimeAuthError("denied")]),
    ],
)
def test_security_control_flow_and_unknown_errors_are_not_recoverable(error):
    assert tool_error_content(error, "search_web") is None
    if type(error) is not ValueError:
        assert tool_error_content(error, "read_reference") is None
    with pytest.raises(type(error)):
        handle_expected_tool_error(error, tool_name="search_web")


def test_tool_name_and_message_size_are_not_derived_from_exception():
    assert (
        tool_error_content(ToolException("invalid_research_query"), "execute") is None
    )
    assert (
        tool_error_content(ToolException("invalid_research_query"), "n" * 2048) is None
    )
    oversized_type = type("n" * 2048, (ToolException,), {})
    assert (
        tool_error_content(oversized_type("invalid_research_query"), "search_web")
        is None
    )


def test_image_missing_child_path_is_recoverable_but_trusted_root_is_fatal(tmp_path):
    async def run():
        tool = build_image_tools(ImageWorkspace(tmp_path))[2]
        result = await tool.ainvoke(
            {
                "type": "tool_call",
                "id": "missing-image",
                "name": tool.name,
                "args": {
                    "image_path": "/workspace/missing/image.png",
                    "question": "Inspect",
                },
            }
        )
        assert result.status == "error" and result.tool_call_id == "missing-image"
        assert json.loads(result.content)["code"] == "tool.invalid_input"
        missing_root = build_image_tools(ImageWorkspace(tmp_path / "absent-root"))[2]
        with pytest.raises(RuntimeWorkspaceError):
            await missing_root.ainvoke(
                {"image_path": "/workspace/uploads/image.png", "question": "Inspect"}
            )
        assert not (tmp_path / "absent-root").exists()

    asyncio.run(run())


@pytest.mark.parametrize("asynchronous", [False, True])
def test_official_middleware_pairs_sync_and_async_errors_and_keeps_success(
    asynchronous,
):
    @tool("search_web")
    def invalid(query: str) -> str:
        """Controlled expected failure without native handling."""
        if query == "ok":
            return "success"
        raise ToolException("invalid_research_query")

    model = BindableFakeMessagesChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "search_web", "args": {"query": ""}, "id": "error"}
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "search_web", "args": {"query": "ok"}, "id": "success"}
                ],
            ),
            AIMessage(content="continued"),
        ]
    )
    graph = create_agent(
        model, tools=[invalid], middleware=[ToolErrorMiddleware(on_error=on_tool_error)]
    )
    input_value = {"messages": [("user", "probe")]}
    result = (
        asyncio.run(graph.ainvoke(input_value))
        if asynchronous
        else graph.invoke(input_value)
    )
    messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert [(m.tool_call_id, m.status) for m in messages] == [
        ("error", "error"),
        ("success", "success"),
    ]
    assert messages[0].name == json.loads(messages[0].content)["name"] == "search_web"
    assert messages[1].content == "success" and messages[1].artifact is None
    assert result["messages"][-1].content == "continued"


def test_transport_exception_groups_require_every_leaf_to_be_known():
    known = ExceptionGroup(
        "transport",
        [httpx.ConnectError("CANARY"), ExceptionGroup("nested", [ConnectionError()])],
    )
    assert is_transport_error(known)
    assert not is_transport_error(
        ExceptionGroup("mixed", [known, ValueError("conversion")])
    )
    assert not is_transport_error(
        BaseExceptionGroup("cancel", [known, asyncio.CancelledError()])
    )


@pytest.mark.parametrize(
    "error",
    [
        RuntimeAuthError("denied"),
        RuntimeWorkspaceError("runtime.workspace.unavailable"),
        RuntimeError("defect"),
        asyncio.CancelledError(),
        ToolException("image_submission_unknown"),
    ],
)
def test_media_records_unknown_once_and_propagates_fatal_errors(
    monkeypatch, tmp_path, error
):
    row = {
        "id": "task",
        "status": "intent",
        "operation": "generate_image",
        "result": {},
        "error_code": None,
    }
    calls = []

    class Storage:
        def create(self, *args, **kwargs):
            return row, True

        def claim(self, identifier):
            calls.append("claim")
            return row

        def finish(self, claimed, **fields):
            row.update(fields)
            return True

        def get(self, *args):
            return row

    async def provider(**kwargs):
        calls.append("provider")
        raise error

    facts = SimpleNamespace(
        scope=SimpleNamespace(assistant_id="dearflow_agent", thread_id="thread"),
        principal=SimpleNamespace(
            tenant_id="tenant", project_id="project", user_id="user"
        ),
    )
    monkeypatch.setattr(media, "verified_delegation_from_user", lambda _: facts)
    monkeypatch.setattr(media, "ExternalTaskStorage", lambda _: Storage())
    monkeypatch.setattr(
        media,
        "build_image_tools",
        lambda _: [SimpleNamespace(name="generate_image", coroutine=provider)],
    )
    for key in ("DATABASE_URI", "IMAGE_25_KEY", "IMAGE_25_URL", "IMAGE_25_MODEL"):
        monkeypatch.setenv(key, "synthetic")
    runtime = SimpleNamespace(
        server_info=SimpleNamespace(user={}),
        execution_info=SimpleNamespace(thread_id="thread", run_id="run"),
        tool_call_id="call",
    )
    tool = media.build_media_tools(ImageWorkspace(tmp_path))[0]

    async def run():
        if isinstance(error, ToolException):
            result = await tool.coroutine(
                prompt="test", idempotency_key="once", runtime=runtime
            )
            assert result["status"] == "unknown" and result["task_id"] == "task"
        else:
            with pytest.raises(type(error)):
                await tool.coroutine(
                    prompt="test", idempotency_key="once", runtime=runtime
                )
        assert row["status"] == "unknown" and calls == ["claim", "provider"]
        result = await tool.coroutine(
            prompt="test", idempotency_key="once", runtime=runtime
        )
        assert result["status"] == "unknown" and calls == ["claim", "provider"]

    asyncio.run(run())
