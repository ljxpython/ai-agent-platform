import asyncio
import json
from copy import deepcopy
from unittest.mock import AsyncMock, Mock

import pytest
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.errors import GraphInterrupt
from support import BindableFakeMessagesChatModel

from runtime_service.middlewares.pii_redaction import PiiRedactionMiddleware
from runtime_service.runtime.errors import RuntimePrivacyError
from runtime_service.runtime.pii import (
    PiiRedactionConfig,
    redact_messages,
    redact_model_request,
)

EMAIL = "alice@example.test"
SECRET = "synthetic-redaction-secret-32-bytes"


@pytest.fixture
def policy():
    return PiiRedactionConfig(True, SECRET, scope=("tenant", "project", "thread"))


def test_full_request_copy_and_tool_execution_remain_factual(policy):
    @tool
    def original(query: str) -> str:
        """Contact alice@example.test."""
        return query

    model = BindableFakeMessagesChatModel(responses=[AIMessage(content="ok")])
    args = {"query": EMAIL, "api_key": "z" * 32, "nested": [EMAIL]}
    call = {"name": "original", "args": args, "id": "call-1", "type": "tool_call"}
    raw = {
        "id": "call-1",
        "type": "function",
        "function": {"name": "original", "arguments": json.dumps(args)},
    }
    messages = [
        HumanMessage(content="old " + EMAIL, id="h1"),
        AIMessage(
            content="answer " + EMAIL,
            tool_calls=[call],
            additional_kwargs={"tool_calls": [raw], "reasoning_content": EMAIL},
            id="a1",
        ),
        ToolMessage(
            content=EMAIL,
            tool_call_id="call-1",
            name="original",
            artifact={"raw": EMAIL},
            status="success",
            id="t1",
        ),
    ]
    state = {"messages": messages}
    request = ModelRequest(
        model=model,
        messages=messages,
        system_message=SystemMessage(content=EMAIL),
        tools=[original],
        state=state,
    )
    baseline = deepcopy(messages)
    safe = redact_model_request(request, policy)
    assert safe is not request and safe.state is state and safe.model is model
    assert (
        messages == baseline and original.description == "Contact alice@example.test."
    )
    assert original.invoke({"query": EMAIL}) == EMAIL
    assert safe.tools[0].invoke({"query": "facts"}) == "facts"
    assert EMAIL not in safe.system_message.content + safe.tools[0].description
    for item in safe.messages:
        assert EMAIL not in str(item.content)
    assert safe.messages[1].tool_calls[0]["args"]["nested"] != [EMAIL]
    safe_args = safe.messages[1].tool_calls[0]["args"]
    assert safe_args["api_key"].startswith("[API_KEY_")
    assert (
        json.loads(
            safe.messages[1].additional_kwargs["tool_calls"][0]["function"]["arguments"]
        )
        == safe_args
    )
    assert safe.messages[2].artifact == {"raw": EMAIL}
    assert (
        safe.messages[2].tool_call_id == "call-1"
        and safe.messages[2].status == "success"
    )


def test_adjacent_text_and_media_shape(policy):
    content = [
        {"type": "text", "text": "alice@", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "example.test"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,aGVsbG8="}},
        {"type": "file", "file": {"file_id": "file-1"}},
    ]
    original = HumanMessage(content=content, id="h")
    safe = redact_messages([original], policy)[0]
    assert "[EMAIL_" in safe.content[0]["text"]
    assert safe.content[1]["text"] == ""
    assert safe.content[2:] == content[2:] and original.content == content
    assert safe.id == original.id


def test_text_citations_and_plaintext_document_source_are_protected(policy):
    content = [
        {
            "type": "text",
            "text": "safe",
            "citations": [{"cited_text": EMAIL, "document_title": EMAIL}],
        },
        {
            "type": "document",
            "source": {"type": "text", "media_type": "text/plain", "data": EMAIL},
            "context": EMAIL,
        },
        {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": "aGVsbG8="},
        },
    ]
    original = HumanMessage(content=content)
    safe = redact_messages([original], policy)[0]
    assert EMAIL not in json.dumps(safe.content)
    assert safe.content[2] == content[2] and original.content == content


def test_sensitive_remote_media_url_is_blocked(policy):
    with pytest.raises(RuntimePrivacyError):
        redact_messages(
            [
                HumanMessage(
                    content=[
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "https://example.test/?email=" + EMAIL
                            },
                        }
                    ]
                )
            ],
            policy,
        )


@pytest.mark.parametrize(
    "content",
    [
        [{"type": "unknown", "text": EMAIL}],
        [{"type": "thinking", "thinking": EMAIL, "signature": "signed"}],
        [{"type": "redacted_thinking", "data": EMAIL}],
    ],
)
def test_unknown_and_signed_content_fail_before_provider(policy, content):
    request = ModelRequest(
        model=BindableFakeMessagesChatModel(responses=[AIMessage(content="ok")]),
        messages=[HumanMessage(content=content)],
    )
    middleware = PiiRedactionMiddleware(policy)
    handler = Mock()
    with pytest.raises(RuntimePrivacyError) as error:
        middleware.wrap_model_call(request, handler)
    assert str(error.value) == "runtime.privacy.redaction_failed"
    assert error.value.__context__ is None
    handler.assert_not_called()
    async_handler = AsyncMock()
    with pytest.raises(RuntimePrivacyError):
        asyncio.run(middleware.awrap_model_call(request, async_handler))
    async_handler.assert_not_called()


def test_sync_async_disabled_and_control_flow(policy):
    request = ModelRequest(
        model=BindableFakeMessagesChatModel(responses=[AIMessage(content="ok")]),
        messages=[HumanMessage(content=EMAIL)],
    )
    middleware = PiiRedactionMiddleware(policy)
    received = []
    result = ModelResponse(result=[AIMessage(content="ok")])

    def handler(req):
        received.append(req.messages)
        return result

    async def async_handler(req):
        return handler(req)

    assert middleware.wrap_model_call(request, handler) is result
    assert asyncio.run(middleware.awrap_model_call(request, async_handler)) is result
    assert received[0] == received[1] and received[0] != request.messages
    for exception in (asyncio.CancelledError(), GraphInterrupt()):

        async def stop(req, exception=exception):
            raise exception

        with pytest.raises(type(exception)):
            asyncio.run(middleware.awrap_model_call(request, stop))
    assert redact_model_request(request, PiiRedactionConfig()) is request


def test_schema_descriptions_are_projected_without_changing_parameter_names(policy):
    model = BindableFakeMessagesChatModel(responses=[AIMessage(content="ok")])
    schema = {
        "type": "function",
        "function": {
            "name": "contact",
            "description": EMAIL,
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": EMAIL, "default": EMAIL}
                },
                "required": ["email"],
            },
        },
    }
    safe = redact_model_request(
        ModelRequest(model=model, messages=[], tools=[schema]), policy
    )
    assert schema["function"]["description"] == EMAIL
    projected = safe.tools[0]["function"]
    assert projected["name"] == "contact" and projected["parameters"]["required"] == [
        "email"
    ]
    assert EMAIL not in json.dumps(projected)


@pytest.mark.parametrize("field,value", [("enum", [EMAIL]), ("const", EMAIL)])
def test_sensitive_schema_constraints_fail_without_rewriting_contract(
    policy, field, value
):
    schema = {
        "name": "contact",
        "parameters": {
            "type": "object",
            "properties": {"email": {"type": "string", field: value}},
        },
    }
    request = ModelRequest(
        model=BindableFakeMessagesChatModel(responses=[]), messages=[], tools=[schema]
    )
    handler = Mock()
    with pytest.raises(RuntimePrivacyError):
        PiiRedactionMiddleware(policy).wrap_model_call(request, handler)
    handler.assert_not_called()


@pytest.mark.parametrize("field", ["properties", "$defs", "definitions"])
def test_sensitive_schema_identifiers_block_provider(policy, field):
    schema = {
        "name": "contact",
        "parameters": {"type": "object", field: {EMAIL: {"type": "string"}}},
    }
    request = ModelRequest(
        model=BindableFakeMessagesChatModel(responses=[]), messages=[], tools=[schema]
    )
    handler = Mock()
    with pytest.raises(RuntimePrivacyError):
        PiiRedactionMiddleware(policy).wrap_model_call(request, handler)
    handler.assert_not_called()
    assert EMAIL in schema["parameters"][field]


@pytest.mark.parametrize(
    "block",
    [
        {
            "type": "image_url",
            "image_url": {"url": "https://example.test/a", EMAIL: "metadata"},
        },
        {"type": "text", "text": "safe", EMAIL: "metadata"},
    ],
)
def test_sensitive_content_identifiers_block_provider(policy, block):
    content = [block]
    original = HumanMessage(content=content)
    with pytest.raises(RuntimePrivacyError):
        redact_messages([original], policy)
    assert original.content == content


def test_nested_signed_reasoning_and_structural_tool_keys_fail(policy):
    messages = [
        AIMessage(
            "",
            additional_kwargs={
                "reasoning_details": [{"text": EMAIL, "signature": "valid"}]
            },
        ),
        AIMessage(
            "", tool_calls=[{"name": "contact", "id": "c", "args": {EMAIL: "facts"}}]
        ),
    ]
    for message in messages:
        with pytest.raises(RuntimePrivacyError):
            redact_messages([message], policy)


@pytest.mark.parametrize("field", ["name", "id"])
def test_invalid_tool_call_sensitive_identifiers_block_provider(policy, field):
    call = {"name": "contact", "id": "call-1", "args": "malformed"}
    call[field] = EMAIL
    message = AIMessage("", invalid_tool_calls=[call])
    request = ModelRequest(
        model=BindableFakeMessagesChatModel(responses=[]), messages=[message]
    )
    handler = Mock()
    with pytest.raises(RuntimePrivacyError):
        PiiRedactionMiddleware(policy).wrap_model_call(request, handler)
    handler.assert_not_called()
    assert message.invalid_tool_calls[0][field] == EMAIL


def test_privacy_failure_is_not_a_provider_diagnostic(policy, monkeypatch):
    from runtime_service.middlewares import model_errors

    recorded = Mock()
    monkeypatch.setattr(model_errors, "log_diagnostic", recorded)
    monkeypatch.setattr(model_errors, "record_diagnostic_event", recorded)
    handler = AsyncMock(
        side_effect=RuntimePrivacyError("runtime.privacy.redaction_failed")
    )
    request = ModelRequest(
        model=BindableFakeMessagesChatModel(responses=[]), messages=[]
    )
    with pytest.raises(RuntimePrivacyError):
        asyncio.run(
            model_errors.ModelErrorMiddleware({}).awrap_model_call(request, handler)
        )
    recorded.assert_not_called()


def test_native_nested_document_text_is_scanned_as_continuous_blocks(policy):
    content = [
        {
            "type": "document",
            "source": {
                "type": "content",
                "content": [
                    {"type": "text", "text": "alice@"},
                    {"type": "text", "text": "example.test"},
                ],
            },
        }
    ]
    safe = redact_messages([HumanMessage(content=content)], policy)[0]
    assert "alice@" not in str(safe.content) and "[EMAIL_" in str(safe.content)
