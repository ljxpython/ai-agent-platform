from __future__ import annotations

import json
import unittest

from platform_api.adapters.langgraph.sdk_client import redact_runtime_private_fields
from platform_api.core.runtime_contract import (
    normalize_protocol_v2_command,
    normalize_runtime_contract,
    normalize_runtime_payload,
)
from platform_api.modules.runtime_gateway.application.service import (
    _normalize_protocol_lifecycle_frame,
)
from platform_api.modules.runtime_gateway.presentation.http import _redact_sse_frame

KEY = "__graphharbor_run_budget"


class RunBudgetContractTests(unittest.TestCase):
    def test_client_cannot_supply_budget_through_any_run_or_resume_envelope(self):
        for payload in (
            {KEY: {}},
            {"input": {KEY: {}}},
            {"config": {"configurable": {KEY: {}}}},
            {"metadata": {KEY: {}}},
            {"context": {KEY: {}}},
            {"command": {"resume": {KEY: {}}}},
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):
                    normalize_runtime_payload(payload=payload, project_id="project")
        for method in ("run.start", "input.respond"):
            with self.subTest(method=method):
                with self.assertRaises(ValueError):
                    normalize_protocol_v2_command(
                        payload={
                            "id": 1,
                            "method": method,
                            "params": {"input": {KEY: {}}},
                        }
                    )
        for part in ("config", "context", "metadata"):
            values = dict(config={}, context={}, metadata={}, project_id="project")
            values[part] = {"nested": {KEY: {}}}
            with self.subTest(part=part):
                with self.assertRaises(ValueError):
                    normalize_runtime_contract(**values)

    def test_query_history_and_sse_share_recursive_private_redaction(self):
        value = {
            "status": "timeout",
            "reason": "timeout",
            "kwargs": {KEY: {"deadline_monotonic": 999}, "input": {"messages": []}},
            "history": [{"metadata": {KEY: {}}}],
        }
        clean = redact_runtime_private_fields(value)
        self.assertNotIn(KEY, str(clean))
        self.assertEqual(clean["status"], "timeout")
        for protocol in (True, False):
            payload = (
                {"method": "lifecycle", "params": {"run_id": "run", "data": value}}
                if protocol
                else value
            )
            frame = ("data: " + json.dumps(payload) + "\n\n").encode()
            self.assertNotIn(KEY.encode(), _redact_sse_frame(frame, protocol=protocol))

    def test_sdk_completed_label_preserves_server_timeout(self):
        payload = {
            "method": "lifecycle",
            "params": {
                "run_id": "run",
                "data": {
                    "event": "completed",
                    "status": "timeout",
                    "reason": "timeout",
                },
            },
        }
        frame, terminal = _normalize_protocol_lifecycle_frame(
            ("data: " + json.dumps(payload) + "\n\n").encode()
        )
        self.assertEqual(terminal, {"run_id": "run", "status": "timeout"})
        self.assertIn(b'"timeout"', frame)

    def test_stop_confirmation_is_preserved_by_stream_projection_and_redaction(self):
        for stopped in (False, True):
            with self.subTest(stopped=stopped):
                payload = {
                    "method": "lifecycle",
                    "params": {
                        "run_id": "run",
                        "data": {
                            "status": "interrupted",
                            "reason": "cancel_requested",
                            "execution_stopped": stopped,
                            "lease_fenced": not stopped,
                            KEY: {"deadline_monotonic": 999},
                        },
                    },
                }
                frame = ("data: " + json.dumps(payload) + "\n\n").encode()
                clean = _redact_sse_frame(frame, protocol=True)
                projected, _ = _normalize_protocol_lifecycle_frame(clean)
                data = json.loads(projected.decode().removeprefix("data: "))["params"][
                    "data"
                ]
                self.assertIs(data["execution_stopped"], stopped)
                self.assertIs(data["lease_fenced"], not stopped)
                self.assertNotIn(KEY.encode(), projected)
