from __future__ import annotations

import json
import os
import subprocess
import time
import unittest
from pathlib import Path
from uuid import uuid4

import jwt

from platform_api.config import Settings
from platform_api.core.security import create_runtime_delegation_token
from platform_api.modules.runtime_gateway.application.service import (
    _runtime_context_snapshot,
)

ROOT = Path(__file__).resolve().parents[3]
RUNTIME_PYTHON = Path(
    os.getenv(
        "RUNTIME_CONTRACT_PYTHON", str(ROOT / "apps/runtime-service/.venv/bin/python")
    )
)
VERIFIER = Path(__file__).parent / "fixtures/runtime_delegation_verifier.py"
OPERATIONS = (
    "read",
    "thread-create",
    "thread-reconcile",
    "run-create",
    "thread-edit",
    "thread-delete",
    "run-cancel",
    "run-delete",
    "message-enqueue",
    "message-read",
    "image-upload",
    "image-read",
    "workspace-file-upload",
    "workspace-file-read",
    "workspace-fork",
    "terminal-read",
    "terminal-write",
    "dear-skills-read",
    "dear-skills-write",
    "dear-memory-read",
    "dear-memory-write",
    "dear-governance-read",
    "dear-governance-write",
    "suggestions-generate",
    "diagnostics-read",
    "usage-read",
    "thread-stop",
    "thread-stop-read",
    "run-cancellation-read",
)


class RuntimeDelegationContractTest(unittest.TestCase):
    def setUp(self) -> None:
        if not RUNTIME_PYTHON.is_file():
            self.skipTest("Runtime test environment is required")
        self.settings = Settings(
            runtime_delegation_secret="runtime-delegation-secret-at-least-48-bytes-for-tests",
            runtime_delegation_ttl_seconds=300,
        )

    def _token(self, *, operation="read", scope=None, **overrides) -> str:
        values = {
            "subject": "user-1",
            "tenant_id": "tenant-1",
            "project_id": "project-1",
            "role": "project_editor",
            "permissions": [],
            "policy_version": "policy-1",
            "allowed_model_ids": ["model-1"],
            "tool_overrides": {},
            "tool_policy_version": "tools-1",
            "settings": self.settings,
            "scope": scope
            or {
                "tenant_id": "tenant-1",
                "project_id": "project-1",
                "assistant_id": "agent-1",
                "thread_id": "thread-1",
                "operation": operation,
            },
        }
        return create_runtime_delegation_token(**(values | overrides))

    def _resign(self, token: str, changes: dict, *, kid=None, algorithm="HS256") -> str:
        claims = jwt.decode(
            token,
            self.settings.runtime_delegation_secret,
            algorithms=["HS256"],
            issuer=self.settings.runtime_delegation_issuer,
            audience=self.settings.runtime_delegation_audience,
        )
        for name, value in changes.items():
            if value is None:
                claims.pop(name, None)
            else:
                claims[name] = value
        headers = {"typ": "JWT"}
        if kid is not None:
            headers["kid"] = kid
        return jwt.encode(
            claims,
            self.settings.runtime_delegation_secret,
            algorithm=algorithm,
            headers=headers,
        )

    def _verify(self, cases: list[dict]) -> list[dict]:
        environment = {
            "PYTHONPATH": str(ROOT / "apps/runtime-service/src"),
            "PATH": os.environ.get("PATH", ""),
            "LANGFUSE_ENABLED": "false",
            "OTEL_SDK_DISABLED": "true",
        }
        completed = subprocess.run(
            [str(RUNTIME_PYTHON), str(VERIFIER)],
            check=False,
            input=json.dumps(
                {
                    "cases": cases,
                    "secret": self.settings.runtime_delegation_secret,
                    "issuer": self.settings.runtime_delegation_issuer,
                    "audience": self.settings.runtime_delegation_audience,
                }
            ),
            text=True,
            capture_output=True,
            timeout=180,
            cwd=ROOT,
            env=environment,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr[-2000:])
        return json.loads(completed.stdout)

    def test_all_platform_operations_pass_current_runtime_verifier(self) -> None:
        self.assertIn("diagnostics-read", OPERATIONS)
        self.assertEqual(len(OPERATIONS), len(set(OPERATIONS)))
        tokens = [
            self._token(
                operation=operation,
                request_id="request-1",
                platform_trace_id="request-1",
            )
            for operation in OPERATIONS
        ]
        results = self._verify([{"token": token} for token in tokens])
        self.assertEqual(len(results), len(OPERATIONS))
        for operation, result in zip(OPERATIONS, results, strict=True):
            with self.subTest(operation=operation):
                self.assertEqual(
                    result,
                    {
                        "accepted": True,
                        "operation": operation,
                        "request_id": "request-1",
                        "platform_trace_id": "request-1",
                    },
                )

    def test_signed_claim_rejections_and_optional_claims(self) -> None:
        token = self._token(request_id="request-1", platform_trace_id="trace-1")
        now = int(time.time())
        bad = [
            {"delegation_version": True},
            {"delegation_version": 3},
            {"unexpected_claim": "value"},
            {"type": "access"},
            {"iss": "wrong"},
            {"aud": "wrong"},
            {"exp": now - 1},
            {"nbf": now + 300},
            {"iat": now + 300},
            {"context_hash": "sha256:INVALID"},
            {"policy_tenant_id": "other"},
            {"policy_project_id": "other"},
            {
                "scope": {
                    "tenant_id": "tenant-1",
                    "project_id": "project-1",
                    "operation": "read",
                    "unknown": "x",
                }
            },
        ]
        cases = [{"token": self._resign(token, change)} for change in bad]
        cases += [
            {"token": self._resign(token, {"jti": None, "nbf": None})},
            {
                "token": self._resign(
                    token,
                    {"policy_tenant_id": "tenant-1", "policy_project_id": "project-1"},
                )
            },
            {"token": self._resign(token, {}, kid="different")},
            {"token": self._resign(token, {})},
            {"token": self._resign(token, {}, algorithm="HS384")},
            {
                "token": jwt.encode(
                    {"type": "runtime_delegation"},
                    "wrong-secret-at-least-32-bytes-long",
                    algorithm="HS256",
                )
            },
            {"token": token, "mode": "http"},
            {"token": self._resign(token, {"aud": "wrong"}), "mode": "http"},
        ]
        results = self._verify(cases)
        self.assertTrue(all(not item["accepted"] for item in results[: len(bad)]))
        self.assertTrue(
            all(item["accepted"] for item in results[len(bad) : len(bad) + 4])
        )
        self.assertEqual(results[-4]["accepted"], False)
        self.assertEqual(results[-3]["accepted"], False)
        self.assertEqual(results[-2], {"accepted": True, "identity": "user-1"})
        self.assertEqual(results[-1], {"accepted": False, "status": 401})

    def test_context_hash_and_scope_are_checked_by_runtime(self) -> None:
        empty = self._token()
        context = {
            "model_id": "model-1",
            "temperature": 0.5,
            "execution_mode": "flash",
            "access_policy": "review",
        }
        context_hash, snapshot = _runtime_context_snapshot(
            {"params": {"context": context}}
        )
        bound = self._token(context_hash=context_hash)
        sentinel = self._token(allowed_model_ids=["platform:no-enabled-model"])
        maximum_text = self._token(
            subject="x" * 128,
            policy_version="v" * 100_000,
            tool_policy_version="t" * 100_000,
        )
        cases = [
            {"token": empty, "context": None},
            {"token": empty, "context": {"model_id": "model-1"}},
            {"token": empty, "expected_scope": {"thread_id": "other"}},
            {"token": empty, "expected_scope": {"thread_id": "thread-1"}},
            {"token": bound, "context": snapshot},
            {"token": bound, "context": {**snapshot, "access_policy": "full_access"}},
            {"token": sentinel},
            {"token": maximum_text},
        ]
        results = self._verify(cases)
        self.assertEqual(
            [r["accepted"] for r in results],
            [True, False, False, True, True, False, True, True],
        )
        self.assertEqual(results[1]["code"], "runtime.auth.context_hash_mismatch")

    def test_native_resource_authorization_and_custom_isolation(self) -> None:
        native = {
            "read": ("threads", "read", {"thread_id": "thread-1"}, "read"),
            "thread-create": ("threads", "create", {"thread_id": "thread-1"}, "create"),
            "thread-reconcile": (
                "threads",
                "read",
                {"thread_id": "thread-1"},
                "reconcile",
            ),
            "run-create": (
                "threads",
                "create_run",
                {"thread_id": "thread-1", "assistant_id": "agent-1"},
                "comment",
            ),
            "thread-edit": ("threads", "update", {"thread_id": "thread-1"}, "edit"),
            "thread-delete": ("threads", "delete", {"thread_id": "thread-1"}, "delete"),
            "run-cancel": (
                "threads",
                "update",
                {"thread_id": "thread-1", "run_id": "run-1"},
                "edit",
            ),
            "run-delete": (
                "threads",
                "delete",
                {"thread_id": "thread-1", "run_id": "run-1"},
                "delete",
            ),
        }
        self.assertEqual(len(native), 8)
        cases = []
        for operation, (resource, action, value, _) in native.items():
            cases.append(
                {
                    "token": self._token(operation=operation),
                    "mode": "native",
                    "resource": resource,
                    "action": action,
                    "value": value,
                }
            )
        for operation in set(OPERATIONS) - set(native):
            cases.append(
                {
                    "token": self._token(operation=operation),
                    "mode": "native",
                    "resource": "threads",
                    "action": "read",
                    "value": {"thread_id": "thread-1"},
                }
            )
        cases += [
            {
                "token": self._token(operation="run-create"),
                "mode": "native",
                "resource": "threads",
                "action": "create_run",
                "value": {"thread_id": "other", "assistant_id": "agent-1"},
            },
            {
                "token": self._token(operation="run-create"),
                "mode": "native",
                "resource": "threads",
                "action": "create_run",
                "value": {"thread_id": "thread-1", "assistant_id": "other"},
            },
            {
                "token": self._token(operation="run-cancel"),
                "mode": "native",
                "resource": "threads",
                "action": "update",
                "value": {"thread_id": "thread-1"},
            },
            {
                "token": self._token(operation="thread-edit"),
                "mode": "native",
                "resource": "threads",
                "action": "update",
                "value": {"thread_id": "thread-1", "run_id": "run-1"},
            },
            {
                "token": self._token(operation="read"),
                "mode": "native",
                "resource": "threads",
                "action": "read",
                "value": {"thread_id": "thread-1"},
                "acl": "deny",
            },
            {
                "token": self._token(operation="read"),
                "mode": "native",
                "resource": "threads",
                "action": "read",
                "value": {"thread_id": "thread-1"},
                "acl": "unavailable",
            },
            {
                "token": self._token(operation="run-create"),
                "mode": "native",
                "resource": "threads",
                "action": "create_run",
                "value": {
                    "thread_id": "thread-1",
                    "assistant_id": "agent-1",
                    "command": {"resume": "approved"},
                },
            },
        ]
        account_id, credential_id = uuid4(), uuid4()
        cases.append(
            {
                "token": self._token(
                    subject=f"service-account:{account_id}",
                    credential_id=str(credential_id),
                ),
                "mode": "native",
                "resource": "threads",
                "action": "read",
                "value": {"thread_id": "thread-1"},
            }
        )
        for operation, (resource, action, value, _) in native.items():
            cases.append(
                {
                    "token": self._token(operation=operation),
                    "mode": "native",
                    "resource": resource,
                    "action": "unsupported",
                    "value": value,
                }
            )
            cases.append(
                {
                    "token": self._token(operation=operation),
                    "mode": "native",
                    "resource": resource,
                    "action": action,
                    "value": {**value, "thread_id": "other"},
                }
            )
        cases.append(
            {
                "token": self._token(operation="read"),
                "mode": "native",
                "resource": "assistants",
                "action": "read",
                "value": {"assistant_id": "other"},
            }
        )
        results = self._verify(cases)
        for (operation, (_, _, _, expected_action)), result in zip(
            native.items(), results, strict=False
        ):
            with self.subTest(operation=operation):
                self.assertEqual(result["acl_action"], expected_action)
                self.assertEqual(result["acl_calls"], 1)
        custom_count = len(OPERATIONS) - len(native)
        custom_start = len(native)
        invalid_start = custom_start + custom_count
        self.assertTrue(
            all(
                r == {"accepted": False, "status": 403}
                for r in results[custom_start:invalid_start]
            )
        )
        self.assertTrue(
            all(
                r == {"accepted": False, "status": 403}
                for r in results[invalid_start : invalid_start + 4]
            )
        )
        self.assertEqual(results[invalid_start + 4], {"accepted": False, "status": 403})
        self.assertEqual(results[invalid_start + 5], {"accepted": False, "status": 503})
        self.assertEqual(results[invalid_start + 6]["acl_action"], "approve")
        self.assertEqual(
            results[invalid_start + 7]["credential_id"], str(credential_id)
        )
        self.assertTrue(
            all(
                r == {"accepted": False, "status": 403}
                for r in results[invalid_start + 8 :]
            )
        )

    def test_custom_endpoint_operation_boundaries(self) -> None:
        custom = [
            operation
            for operation in OPERATIONS
            if operation
            not in {
                "read",
                "thread-create",
                "thread-reconcile",
                "run-create",
                "thread-edit",
                "thread-delete",
                "run-cancel",
                "run-delete",
                "run-cancellation-read",
            }
        ]
        self.assertIn("diagnostics-read", custom)
        self.assertEqual(len(custom), len(set(custom)))
        cases = []
        for operation in custom:
            assistant = (
                "dearflow_agent"
                if operation.startswith("dear-")
                else "reference_agent"
                if operation.startswith("message-")
                else "showcase_demo"
            )
            scope = {
                "tenant_id": "tenant-1",
                "project_id": "project-1",
                "assistant_id": assistant,
                "operation": operation,
            }
            thread_id = (
                str(uuid4())
                if operation in {"diagnostics-read", "usage-read"}
                else "thread-1"
            )
            if operation not in {
                "dear-skills-read",
                "dear-skills-write",
                "dear-memory-read",
                "dear-memory-write",
            }:
                scope["thread_id"] = thread_id
            cases.append(
                {
                    "token": self._token(scope=scope),
                    "mode": "custom",
                    "endpoint": operation,
                    "thread_id": thread_id,
                    **(
                        {
                            "run_read_token": self._token(
                                scope={
                                    "tenant_id": "tenant-1",
                                    "project_id": "project-1",
                                    "operation": "read",
                                }
                            )
                        }
                        if operation.startswith("message-")
                        else {}
                    ),
                }
            )
            cases.append(
                {
                    "token": self._token(scope={**scope, "operation": "read"}),
                    "mode": "custom",
                    "endpoint": operation,
                    "thread_id": thread_id,
                }
            )
            cases.append(
                {
                    "token": self._token(scope={**scope, "thread_id": "other"}),
                    "mode": "custom",
                    "endpoint": operation,
                    "thread_id": thread_id,
                }
            )
        results = self._verify(cases)
        for index, operation in enumerate(custom):
            accepted, denied, wrong_target = results[index * 3 : index * 3 + 3]
            with self.subTest(operation=operation):
                self.assertTrue(accepted["accepted"], accepted)
                self.assertEqual(denied, {"accepted": False, "status": 403})
                self.assertEqual(wrong_target, {"accepted": False, "status": 403})
                if operation.startswith("message-"):
                    self.assertEqual(accepted["boundary"], "storage_unavailable")


if __name__ == "__main__":
    unittest.main()
