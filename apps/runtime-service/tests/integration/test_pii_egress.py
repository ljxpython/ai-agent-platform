"""Capture actual provider serialization at a local HTTP endpoint."""

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_deepseek import ChatDeepSeek
from langchain_openai import ChatOpenAI

from runtime_service.middlewares.pii_redaction import PiiRedactionMiddleware
from runtime_service.runtime.pii import PiiRedactionConfig

EMAIL = "alice@example.test"
KEY = "sk-" + "A" * 24
PHONE = "13800138000"


@pytest.mark.parametrize(
    "protocol,invalid",
    [
        ("openai", False),
        ("deepseek", False),
        ("anthropic", False),
        ("openai", True),
        ("deepseek", True),
    ],
)
def test_final_provider_payload_and_headers(protocol, invalid):
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            received.append((body, dict(self.headers)))
            if self.path.endswith("/messages"):
                response = {
                    "id": "message-fixture",
                    "type": "message",
                    "role": "assistant",
                    "model": "fixture",
                    "content": [{"type": "text", "text": "ok"}],
                    "stop_reason": "end_turn",
                    "stop_sequence": None,
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                }
            else:
                response = {
                    "id": "fixture",
                    "object": "chat.completion",
                    "model": "fixture",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "ok"},
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 1,
                        "completion_tokens": 1,
                        "total_tokens": 2,
                    },
                }
            data = json.dumps(response).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    @tool
    def contact(query: str) -> str:
        """Contact alice@example.test."""
        return query

    options = {
        "model": "fixture",
        "api_key": KEY,
        "base_url": f"http://127.0.0.1:{server.server_port}/v1",
        "max_retries": 0,
        "timeout": 10,
    }
    model = {
        "openai": ChatOpenAI,
        "deepseek": ChatDeepSeek,
        "anthropic": ChatAnthropic,
    }[protocol](**options)
    args = {"query": EMAIL + " " + PHONE}
    call = {"name": "contact", "args": args, "id": "call-1", "type": "tool_call"}
    raw = {
        "id": "call-1",
        "type": "function",
        "function": {"name": "contact", "arguments": json.dumps(args)},
    }
    if invalid:
        call["args"] = json.dumps(args) + " malformed"
    messages = [
        HumanMessage(EMAIL),
        AIMessage(
            content="",
            tool_calls=[] if invalid else [call],
            invalid_tool_calls=[call] if invalid else [],
            additional_kwargs={"reasoning_content": EMAIL}
            if invalid
            else {"tool_calls": [raw], "reasoning_content": EMAIL},
        ),
        ToolMessage(content=EMAIL + " " + KEY, tool_call_id="call-1"),
        HumanMessage(PHONE),
    ]
    request = ModelRequest(
        model=model,
        messages=messages,
        system_message=SystemMessage(EMAIL),
        tools=[contact],
        state={"messages": messages},
    )
    policy = PiiRedactionConfig(
        True,
        "synthetic-redaction-secret-32-bytes",
        scope=("tenant", "project", "thread"),
    )

    async def handler(candidate):
        response = await candidate.model.bind_tools(candidate.tools).ainvoke(
            [candidate.system_message, *candidate.messages]
        )
        return ModelResponse(result=[response])

    try:
        asyncio.run(PiiRedactionMiddleware(policy).awrap_model_call(request, handler))
        assert len(received) == 1
        body, headers = received[0]
        serialized = json.dumps(body)
        for value in (EMAIL, KEY, PHONE):
            assert value not in serialized
        assert (
            "[EMAIL_" in serialized
            and "[PHONE_" in serialized
            and "[API_KEY_" in serialized
        )
        assert (
            "call-1" in serialized and "contact" in serialized and "query" in serialized
        )
        assert KEY in str(headers)
        assert (
            messages[0].content == EMAIL
            and contact.description == "Contact alice@example.test."
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
