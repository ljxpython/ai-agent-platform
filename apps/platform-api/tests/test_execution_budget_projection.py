from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from platform_api.adapters.langgraph.sdk_client import (
    project_budget_notice,
    project_execution_error,
    redact_runtime_private_fields,
)
from platform_api.core.runtime_contract import (
    PRIVATE_RUNTIME_STATE_KEYS,
    reject_private_runtime_state,
)
from platform_api.modules.runtime_gateway.application.service import (
    _DEFAULT_STREAM_MODES,
    RuntimeGatewayService,
    _normalize_payload,
)
from platform_api.modules.runtime_gateway.presentation.http import _redact_sse_frame


def notice(**changes):
    return {
        "version": 1,
        "type": "runtime_budget_notice",
        "notice_id": "budget:run-1:test:run:model",
        "run_id": "run-1",
        "scope": "primary",
        "budget_scope": "run",
        "code": "model_call_limit_reached",
        "limit": 50,
        "used": 50,
        "remaining": 0,
        "unit": "model_calls",
        **changes,
    }


class ExecutionBudgetProjectionTest(unittest.TestCase):
    def test_exact_errors_and_unknown_provider_timeout(self):
        for kind, code in (
            ("GraphRecursionError", "runtime_graph_step_limit_reached"),
            ("ModelCallLimitExceededError", "runtime_model_call_limit_reached"),
            ("ToolCallLimitExceededError", "runtime_tool_call_limit_reached"),
            ("RunTimedOut", "runtime_run_timeout"),
            ("TimeoutError", "runtime_execution_failed"),
            ("UnknownCanary", "runtime_execution_failed"),
            ("TokenBudgetExceededError", "runtime_token_budget_exhausted"),
            ("TokenBudgetUnverifiableError", "runtime_token_budget_unverifiable"),
        ):
            for field in ("type", "error"):
                with self.subTest(kind=kind, field=field):
                    result = project_execution_error(
                        {
                            field: kind,
                            "message": "SECRET_CANARY",
                            "body": "SECRET_CANARY",
                        }
                    )
                    self.assertEqual(result["code"], code)
                    self.assertNotIn("CANARY", json.dumps(result))
        self.assertEqual(
            project_execution_error("ModelCallLimitExceededError CANARY"),
            "Runtime execution failed",
        )

    def test_error_slots_in_native_protocol_and_v3_frames(self):
        detail = {
            "type": "ModelCallLimitExceededError",
            "message": "SECRET_CANARY",
            "stack": "SECRET_CANARY",
        }
        for method, data in (
            (
                "tasks",
                {"id": "task-1", "error": detail, "result": {"normal": "preserved"}},
            ),
            ("lifecycle", {"status": "error", "error": detail}),
            ("error", detail),
            ("debug", {"type": "task_result", "payload": {"error": detail}}),
            ("checkpoints", {"values": {"messages": []}, "tasks": [{"error": detail}]}),
        ):
            for protocol in (False, True):
                if method == "error" and protocol:
                    continue
                with self.subTest(method=method, protocol=protocol):
                    payload = (
                        {
                            "method": method,
                            "params": {
                                "run_id": "run-1",
                                "namespace": ["tools:child"],
                                "seq": 7,
                                "data": data,
                            },
                        }
                        if protocol
                        else data
                    )
                    frame = (
                        "event: " + method + "\nid: 7\ndata: " + json.dumps(payload)
                    ).encode()
                    result = _redact_sse_frame(frame, protocol=protocol)
                    self.assertNotIn(b"CANARY", result)
                    self.assertIn(b"runtime_model_call_limit_reached", result)
                    self.assertIn(b"id: 7", result)
                    if protocol:
                        self.assertIn(b'"seq":7', result)

    def test_notice_and_end_marker_whitelist_preserve_messages(self):
        unsafe = notice(
            prompt="SECRET_CANARY", token="SECRET_CANARY", host="/private/path"
        )
        cleaned = redact_runtime_private_fields(
            {
                "custom": unsafe,
                "messages": [
                    {
                        "type": "ai",
                        "content": "normal output",
                        "additional_kwargs": {"runtime_budget_notice": unsafe},
                    }
                ],
            }
        )
        self.assertEqual(cleaned["custom"], notice())
        self.assertEqual(
            cleaned["messages"][0]["additional_kwargs"]["runtime_budget_notice"],
            notice(),
        )
        self.assertEqual(cleaned["messages"][0]["content"], "normal output")
        self.assertNotIn("SECRET_CANARY", json.dumps(cleaned))
        self.assertEqual(
            redact_runtime_private_fields({"type": "unrelated_custom", "data": 7}),
            {"type": "unrelated_custom", "data": 7},
        )

    def test_invalid_notice_is_ignored(self):
        for changes in (
            {"version": True},
            {"version": 2},
            {"code": []},
            {"code": "unknown"},
            {"scope": []},
            {"remaining": True},
            {"used": -1},
            {"limit": float("nan")},
            {"limit": float("inf")},
            {"limit": 10**400},
            {"unit": "seconds"},
            {"budget_scope": "graph"},
            {"used": 1.5},
            {"run_id": "x" * 129},
            {"notice_id": "x" * 257},
            {"run_id": "secret\npath"},
        ):
            with self.subTest(changes=changes):
                self.assertIsNone(project_budget_notice(notice(**changes)))
        self.assertIsNotNone(
            project_budget_notice(notice(limit=None, used=None, remaining=None))
        )

    def test_all_network_input_shapes_reject_budget_injection(self):
        for key in PRIVATE_RUNTIME_STATE_KEYS:
            for payload in (
                {"input": {key: 0}},
                {"values": {key: 0}},
                {"command": {"update": {key: 0}}},
                {"command": {"resume": {"interrupt": {key: 0}}}},
                {"input": {"messages": [{"additional_kwargs": {key: {}}}]}},
            ):
                with self.subTest(key=key, payload=payload):
                    with self.assertRaises(ValueError):
                        reject_private_runtime_state(payload)
                    with self.assertRaises(Exception) as error:
                        _normalize_payload(payload)
                    self.assertEqual(error.exception.code, "runtime_private_state")
        with self.assertRaises(ValueError):
            reject_private_runtime_state(
                {"input": {"messages": [{"type": "runtime_budget_notice"}]}}
            )

    def test_private_counters_and_clocks_not_public_and_defaults_have_custom(self):
        private = {
            key: "SECRET_CANARY"
            for key in PRIVATE_RUNTIME_STATE_KEYS
            if key not in ("runtime_budget_notice", "conversation_offloading")
        }
        self.assertEqual(
            redact_runtime_private_fields({**private, "normal": 1}), {"normal": 1}
        )
        self.assertIn("custom", _DEFAULT_STREAM_MODES)

    def test_token_notice_cross_fields_and_exact_machine_codes(self):
        for code, used, remaining in (
            ("token_budget_approaching", 80, 20),
            ("token_budget_exhausted", 105, 0),
            ("token_budget_unverifiable", None, None),
        ):
            value = notice(
                code=code,
                unit="tokens_total",
                limit=100,
                used=used,
                remaining=remaining,
            )
            self.assertEqual(project_budget_notice(value), value)
            for change in (
                {"scope": "subagent"},
                {"limit": 0},
                {"remaining": 10},
                {"unit": "model_calls"},
            ):
                self.assertIsNone(project_budget_notice({**value, **change}))
        for value in (
            "runtime.token_budget.exhausted",
            {"code": "runtime_token_budget_exhausted", "message": "SECRET_CANARY"},
        ):
            result = project_execution_error(value)
            self.assertEqual(result["code"], "runtime_token_budget_exhausted")
            self.assertNotIn("CANARY", json.dumps(result))
        for value in (
            "TokenBudgetExceededError SECRET_CANARY",
            {"type": "prefix TokenBudgetExceededError", "message": "SECRET_CANARY"},
        ):
            result = project_execution_error(value)
            self.assertNotIn("runtime_token_budget_exhausted", str(result))

    def test_token_error_survives_recursive_v3_projection(self):
        for kind, code in (
            ("TokenBudgetExceededError", "runtime_token_budget_exhausted"),
            ("TokenBudgetUnverifiableError", "runtime_token_budget_unverifiable"),
        ):
            detail = {"type": kind, "message": "SECRET_CANARY"}
            for method, data in (
                ("lifecycle", {"event": "failed", "status": "error", "error": detail}),
                (
                    "tasks",
                    {
                        "id": "t",
                        "name": "tools",
                        "result": {},
                        "interrupts": [],
                        "error": detail,
                    },
                ),
                (
                    "debug",
                    {
                        "type": "task_result",
                        "payload": {
                            "id": "t",
                            "name": "tools",
                            "result": {},
                            "interrupts": [],
                            "error": detail,
                        },
                    },
                ),
                ("checkpoints", {"values": {}, "tasks": [{"error": detail}]}),
                ("tools", {"event": "on_tool_end", "error": detail}),
            ):
                for protocol in (False, True):
                    frame = (
                        {
                            "method": method,
                            "params": {"namespace": [], "data": data},
                            "seq": 1,
                        }
                        if protocol
                        else data
                    )
                    encoded = (
                        "event: " + method + "\ndata: " + json.dumps(frame)
                    ).encode()
                    result = _redact_sse_frame(encoded, protocol=protocol)
                    self.assertIn(code.encode(), result, result)
                    self.assertNotIn(b"SECRET_CANARY", result)
            self.assertNotIn("CANARY", str(result))


class BudgetWriteBoundaryTest(unittest.IsolatedAsyncioTestCase):
    async def test_resume_injection_is_rejected_before_interrupt_lookup(self):
        upstream = SimpleNamespace(get_thread_state=AsyncMock())
        service = RuntimeGatewayService(upstream=upstream, session_factory=None)
        service._load_thread = AsyncMock(return_value={})
        for method, payload in (
            (
                service.create_thread_run,
                {
                    "assistant_id": "reference_agent",
                    "command": {"resume": {"invalid-id": {"runtime_wrapup_start": 0}}},
                },
            ),
            (
                service.send_thread_command,
                {
                    "method": "input.respond",
                    "params": {
                        "resume": {"invalid-id": {"thread_model_call_count": 0}}
                    },
                },
            ),
        ):
            with self.assertRaises(Exception) as error:
                await method(
                    actor=None,
                    project_id="project",
                    thread_id="thread",
                    payload=payload,
                )
            self.assertEqual(error.exception.code, "runtime_private_state")
        upstream.get_thread_state.assert_not_awaited()
