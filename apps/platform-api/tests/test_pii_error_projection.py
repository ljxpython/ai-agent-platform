import asyncio
import json

import pytest

from platform_api.adapters.langgraph.sdk_client import (
    create_runtime_upstream_error,
    project_execution_error,
    redact_runtime_private_fields,
)
from platform_api.modules.runtime_gateway.presentation.http import (
    _redact_protocol_event_stream,
)

CODE = "runtime.privacy.redaction_failed"
MESSAGE = "隐私保护处理失败，本次模型请求未发送。"
ERROR = {"type": "RuntimePrivacyError", "message": CODE, "stack": "PRIVATE_CANARY"}


def test_exact_error_projection_http_and_history_are_idempotent():
    expected = {"code": CODE, "message": MESSAGE, "type": "RuntimePrivacyError"}
    assert project_execution_error(ERROR) == expected
    assert project_execution_error(expected) == expected
    assert project_execution_error(CODE) == CODE
    upstream = create_runtime_upstream_error(
        status_code=500,
        detail={"detail": {"code": CODE, "message": "PRIVATE_CANARY"}},
        fallback_code="upstream_failure",
    )
    assert (
        upstream.status_code == 502
        and upstream.code == CODE
        and upstream.message == MESSAGE
    )
    user = {"type": "human", "content": CODE, "metadata": {"error": ERROR}}
    value = {
        "thread_id": "thread",
        "error": ERROR,
        "tasks": [{"error": ERROR}],
        "values": {"messages": [user]},
    }
    safe = redact_runtime_private_fields(value)
    assert safe["error"] == safe["tasks"][0]["error"] == expected
    assert safe["values"]["messages"] == [user]
    assert redact_runtime_private_fields(safe) == safe


@pytest.mark.parametrize(
    "value",
    [
        "ValueError: " + CODE,
        CODE + ": scope",
        {"type": "ValueError", "message": CODE},
        {"type": "RuntimePrivacyError", "message": CODE + " PRIVATE_CANARY"},
        {"type": "RuntimePrivacyError", "message": CODE, "code": "unknown"},
        {"code": CODE, "message": "untrusted"},
    ],
)
def test_embedded_or_conflicting_codes_are_not_privacy_errors(value):
    assert project_execution_error(value) not in (
        CODE,
        {"code": CODE, "message": MESSAGE, "type": "RuntimePrivacyError"},
    )


@pytest.mark.parametrize(
    "protocol,typed", [(False, False), (False, True), (True, True)]
)
def test_all_native_failure_slots_and_fragmented_sse(protocol, typed):
    async def chunks(raw):
        yield raw[:17]
        yield raw[17:51]
        yield raw[51:]

    async def run():
        user = {"content": CODE, "error": "user text"}
        for method, data in (
            ("error", ERROR),
            ("lifecycle", {"status": "error", "error": ERROR}),
            ("tasks", {"id": "task", "error": ERROR, "result": user}),
            (
                "debug",
                {"type": "task_result", "payload": {"error": ERROR, "result": user}},
            ),
            (
                "checkpoints",
                {"tasks": [{"error": ERROR}], "values": {"messages": [user]}},
            ),
        ):
            if method == "error" and typed:
                continue
            payload = (
                {
                    "method": method,
                    "seq": 3,
                    "params": {"namespace": ["tools:child"], "data": data},
                }
                if typed
                else data
            )
            raw = (
                f"event: {method}|child\nid: cursor-3\ndata: {json.dumps(payload)}\n\n"
            ).encode()
            result = b"".join(
                [
                    item
                    async for item in _redact_protocol_event_stream(
                        chunks(raw), protocol=protocol
                    )
                ]
            )
            assert CODE.encode() in result and b"PRIVATE_CANARY" not in result
            assert b"id: cursor-3" in result
            if method in {"tasks", "debug", "checkpoints"}:
                assert b"user text" in result
            if typed:
                value = json.loads(result.decode().split("data: ")[1])
                assert value["seq"] == 3 and value["params"]["namespace"] == [
                    "tools:child"
                ]

    asyncio.run(run())


@pytest.mark.parametrize(
    "key",
    ["pii_redaction", "pii_config", "pii_token_secret", "pii_scope", "pii_detectors"],
)
def test_private_policy_injection_and_public_projection(key):
    from platform_api.core.runtime_contract import reject_private_runtime_state

    with pytest.raises(ValueError):
        reject_private_runtime_state(
            {"messages": [{"content": "normal", "metadata": {key: "synthetic"}}]}
        )
    projected = redact_runtime_private_fields(
        {
            "values": {
                key: "synthetic",
                "messages": [{"type": "human", "content": "normal"}],
            }
        }
    )
    assert (
        key not in str(projected)
        and projected["values"]["messages"][0]["content"] == "normal"
    )
