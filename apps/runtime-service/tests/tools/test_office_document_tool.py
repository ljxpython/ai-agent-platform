import asyncio
import hashlib
import json
from unittest.mock import AsyncMock

import pytest
from deepagents.backends.protocol import ExecuteResponse
from langchain_core.tools import StructuredTool
from workspace.test_office_documents import docx_bytes

from runtime_service.tools.documents import build_document_tools
from runtime_service.workspace.document_reader import DOCX_MIME, read_office
from runtime_service.workspace.documents import DocumentWorkspace


def stored(tmp_path):
    (tmp_path / "work").mkdir()
    raw = docx_bytes("Office body")
    ref = DocumentWorkspace(tmp_path).put(
        raw, hashlib.sha256(raw).hexdigest(), DOCX_MIME
    )
    return raw, ref


def test_office_uses_one_official_tool_and_fixed_async_executor(monkeypatch, tmp_path):
    raw, ref = stored(tmp_path)
    result = read_office(raw, DOCX_MIME, {"file_path": ref["path"]})
    execute = AsyncMock(
        return_value=ExecuteResponse(output=json.dumps(result), exit_code=0)
    )
    monkeypatch.setattr(
        "runtime_service.workspace.execution.execute_in_workspace", execute
    )
    tool = build_document_tools(tmp_path, execution_image="reader:fixture")[0]
    assert isinstance(tool, StructuredTool) and tool.name == "parse_document"
    assert tool.func is not None and tool.coroutine is not None
    assert set(tool.args) == {
        "file_path",
        "query",
        "page_start",
        "page_end",
        "read_options",
    }
    assert "tool.operation_failed" in tool.invoke({"file_path": ref["path"]})
    execute.assert_not_called()
    message = asyncio.run(
        tool.ainvoke(
            {
                "type": "tool_call",
                "id": "office-1",
                "name": tool.name,
                "args": {"file_path": ref["path"]},
            }
        )
    )
    assert message.tool_call_id == "office-1" and message.status == "success"
    body = json.loads(message.content)
    assert body["file"] == {**ref, "file_name": ref["path"].rsplit("/", 1)[-1]}
    assert body["text"] == "Office body"
    assert execute.call_args.kwargs == {
        "image": "reader:fixture",
        "timeout": 30,
        "protected": True,
    }
    assert (
        "python -m runtime_service.workspace.document_reader"
        in execute.call_args.args[1]
    )


@pytest.mark.parametrize(
    "response",
    [
        ExecuteResponse(output="broken", exit_code=0),
        ExecuteResponse(output="{}", exit_code=0),
        ExecuteResponse(output='{"error":"private parser stack"}', exit_code=0),
        ExecuteResponse(output="{}", exit_code=137),
        ExecuteResponse(output="{}", exit_code=0, truncated=True),
    ],
)
def test_bad_reader_results_are_safe_tool_errors(monkeypatch, tmp_path, response):
    _, ref = stored(tmp_path)
    monkeypatch.setattr(
        "runtime_service.workspace.execution.execute_in_workspace",
        AsyncMock(return_value=response),
    )
    tool = build_document_tools(tmp_path, execution_image="reader:fixture")[0]
    message = asyncio.run(
        tool.ainvoke(
            {
                "type": "tool_call",
                "id": "bad",
                "name": tool.name,
                "args": {"file_path": ref["path"]},
            }
        )
    )
    body = json.loads(message.content)
    assert body["code"] == "tool.operation_failed" and message.status == "error"
    assert "private" not in message.content


def test_cancel_and_runtime_policy_propagate(monkeypatch, tmp_path):
    from runtime_service.runtime.errors import RuntimeWorkspaceError

    _, ref = stored(tmp_path)
    tool = build_document_tools(tmp_path, execution_image="reader:fixture")[0]
    for failure in (
        asyncio.CancelledError(),
        RuntimeWorkspaceError("runtime.workspace.execution_unavailable"),
        RuntimeWorkspaceError("runtime.workspace.execution_outcome_unknown"),
    ):
        monkeypatch.setattr(
            "runtime_service.workspace.execution.execute_in_workspace",
            AsyncMock(side_effect=failure),
        )
        with pytest.raises(type(failure)):
            asyncio.run(tool.ainvoke({"file_path": ref["path"]}))


def test_legacy_sync_and_async_keep_the_contract(tmp_path):
    raw = b"legacy content"
    ref = DocumentWorkspace(tmp_path).put(
        raw, hashlib.sha256(raw).hexdigest(), "text/plain"
    )
    tool = build_document_tools(tmp_path)[0]
    request = {"file_path": ref["path"]}
    assert tool.invoke(request) == asyncio.run(tool.ainvoke(request))
    assert "tool.invalid_input" in tool.invoke(
        {**request, "read_options": {"char_offset": 1}}
    )


def test_no_image_and_missing_source_do_not_start_a_parser(monkeypatch, tmp_path):
    _, ref = stored(tmp_path)
    execute = AsyncMock()
    monkeypatch.setattr(
        "runtime_service.workspace.execution.execute_in_workspace", execute
    )
    tool = build_document_tools(tmp_path)[0]
    assert "tool.operation_failed" in asyncio.run(
        tool.ainvoke({"file_path": ref["path"]})
    )
    assert "tool.invalid_input" in asyncio.run(
        tool.ainvoke({"file_path": "/workspace/uploads/" + "b" * 64 + ".docx"})
    )
    execute.assert_not_called()


@pytest.mark.parametrize(
    "change",
    [
        {"version": True},
        {"text": "x" * 12001},
        {"text": "different content"},
        {"read_range": [1, 2]},
        {"matched_sections": [2]},
        {"chunks": [{"section": 1, "char_offset": -1, "text": "Office body"}]},
        {"warnings": ["x" * 101]},
        {"truncated": True, "next_read": None},
        {
            "truncated": True,
            "next_read": {"file_path": "/workspace/uploads/other.docx"},
        },
        {
            "truncated": True,
            "next_read": {"read_options": {"section_start": 2}},
        },
    ],
    ids=[
        "version",
        "text-limit",
        "text-shape",
        "range",
        "match",
        "offset",
        "warning-limit",
        "missing-next",
        "foreign-next",
        "next-range",
    ],
)
def test_reader_output_bounds_are_enforced(monkeypatch, tmp_path, change):
    raw, ref = stored(tmp_path)
    result = read_office(raw, DOCX_MIME, {"file_path": ref["path"]})
    if change.get("next_read") is not None and "file_path" not in change["next_read"]:
        change = {
            **change,
            "next_read": {"file_path": ref["path"], **change["next_read"]},
        }
    result.update(change)
    monkeypatch.setattr(
        "runtime_service.workspace.execution.execute_in_workspace",
        AsyncMock(return_value=ExecuteResponse(output=json.dumps(result), exit_code=0)),
    )
    message = asyncio.run(
        build_document_tools(tmp_path, execution_image="reader:fixture")[0].ainvoke(
            {
                "type": "tool_call",
                "id": "bad-shape",
                "name": "parse_document",
                "args": {"file_path": ref["path"]},
            }
        )
    )
    assert message.status == "error" and "tool.operation_failed" in message.content
