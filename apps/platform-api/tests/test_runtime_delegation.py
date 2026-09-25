from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import jwt
from fastapi import FastAPI, Request

from platform_api.config import Settings
from platform_api.core.context.models import (
    ActorContext,
    PlatformRequestContext,
    ProjectContext,
    RequestContext,
    TenantContext,
)
from platform_api.core.runtime_contract import (
    normalize_protocol_v2_command,
    normalize_protocol_v2_event_request,
    normalize_runtime_payload,
)
from platform_api.core.security import (
    create_runtime_delegation_token,
    empty_runtime_context_hash,
)
from platform_api.modules.runtime_gateway.presentation.http import (
    get_runtime_gateway_service,
)


class MessagePayloadBoundaryTest(unittest.IsolatedAsyncioTestCase):
    async def test_sender_source_policy_and_approval_cannot_enter_as_message_fields(
        self,
    ):
        from unittest.mock import AsyncMock
        from platform_api.core.errors import BadRequestError
        from platform_api.modules.runtime_gateway.presentation.http import (
            enqueue_thread_message,
        )

        request = Request({"type": "http", "headers": [(b"x-project-id", b"project")]})
        request.state.platform_context = SimpleNamespace(
            project=ProjectContext(project_id="project")
        )
        service = SimpleNamespace(enqueue_thread_message=AsyncMock())
        for field in (
            "sender",
            "sender_id",
            "source",
            "config",
            "context",
            "resume",
            "authorization_ref",
        ):
            with self.subTest(field=field), self.assertRaises(BadRequestError):
                await enqueue_thread_message(
                    request,
                    "thread",
                    {"content": "text", field: "forged"},
                    ActorContext(),
                    service,
                )
        service.enqueue_thread_message.assert_not_called()


class RuntimeDelegationTokenTest(unittest.TestCase):
    def test_service_account_credential_is_bound_to_its_subject(self) -> None:
        from uuid import uuid4

        settings = Settings(
            runtime_delegation_secret="runtime-delegation-secret-at-least-32-bytes"
        )
        account_id, credential_id = uuid4(), uuid4()
        kwargs = dict(
            tenant_id="tenant-1",
            project_id="project-1",
            role="project_executor",
            permissions=[],
            policy_version="policy-1",
            allowed_model_ids=[],
            tool_overrides={},
            tool_policy_version="test-tools-v2",
            scope={
                "tenant_id": "tenant-1",
                "project_id": "project-1",
                "operation": "read",
            },
            settings=settings,
        )
        token = create_runtime_delegation_token(
            subject=f"service-account:{account_id}",
            credential_id=str(credential_id),
            **kwargs,
        )
        claims = jwt.decode(
            token,
            settings.runtime_delegation_secret,
            algorithms=["HS256"],
            issuer=settings.runtime_delegation_issuer,
            audience=settings.runtime_delegation_audience,
        )
        self.assertEqual(claims["credential_id"], str(credential_id))
        with self.assertRaisesRegex(ValueError, "requires a service account"):
            create_runtime_delegation_token(
                subject="user-1", credential_id=str(credential_id), **kwargs
            )

    def test_thread_create_scope_can_omit_assistant(self) -> None:
        settings = Settings(
            runtime_delegation_secret="runtime-delegation-secret-at-least-32-bytes"
        )
        token = create_runtime_delegation_token(
            subject="user-1",
            tenant_id="tenant-1",
            project_id="project-1",
            role="project_editor",
            permissions=[],
            policy_version="policy-1",
            allowed_model_ids=[],
            tool_overrides={},
            tool_policy_version="unscoped-thread-create",
            scope={
                "tenant_id": "tenant-1",
                "project_id": "project-1",
                "thread_id": "thread-1",
                "operation": "thread-create",
            },
            settings=settings,
        )
        claims = jwt.decode(
            token,
            settings.runtime_delegation_secret,
            algorithms=["HS256"],
            issuer=settings.runtime_delegation_issuer,
            audience=settings.runtime_delegation_audience,
        )
        self.assertNotIn("assistant_id", claims["scope"])

    def test_correlation_claims_are_bounded_and_optional(self) -> None:
        settings = Settings(
            runtime_delegation_secret="runtime-delegation-secret-at-least-32-bytes"
        )
        kwargs = dict(
            subject="user-1",
            tenant_id="tenant-1",
            project_id="project-1",
            role="project_editor",
            permissions=[],
            policy_version="policy-1",
            allowed_model_ids=[],
            tool_overrides={},
            tool_policy_version="tools-1",
            scope={
                "tenant_id": "tenant-1",
                "project_id": "project-1",
                "operation": "read",
            },
            settings=settings,
        )

        def claims(**correlation):
            return jwt.decode(
                create_runtime_delegation_token(**kwargs, **correlation),
                settings.runtime_delegation_secret,
                algorithms=["HS256"],
                issuer=settings.runtime_delegation_issuer,
                audience=settings.runtime_delegation_audience,
            )

        for name in ("request_id", "platform_trace_id"):
            self.assertNotIn(name, claims())
            self.assertEqual(claims(**{name: " trusted-id "})[name], "trusted-id")
            self.assertEqual(claims(**{name: "x" * 256})[name], "x" * 256)
            for value in ("", " ", "x" * 257, 1, [], {}):
                with (
                    self.subTest(name=name, value=value),
                    self.assertRaisesRegex(ValueError, name),
                ):
                    claims(**{name: value})

    def test_signs_runtime_service_claim_contract(self) -> None:
        settings = Settings(
            runtime_delegation_secret="runtime-delegation-secret-at-least-32-bytes",
            runtime_delegation_ttl_seconds=60,
        )

        token = create_runtime_delegation_token(
            subject="user-1",
            tenant_id="__default",
            project_id="project-1",
            role="project_editor",
            permissions=["project.runtime.write", "project.runtime.read"],
            policy_version="policy-1",
            allowed_model_ids=["model-1"],
            tool_overrides={},
            tool_policy_version="test-tools-v2",
            scope={
                "tenant_id": "__default",
                "project_id": "project-1",
                "operation": "read",
            },
            context_hash=empty_runtime_context_hash(),
            settings=settings,
        )

        claims = jwt.decode(
            token,
            settings.runtime_delegation_secret,
            algorithms=["HS256"],
            issuer=settings.runtime_delegation_issuer,
            audience=settings.runtime_delegation_audience,
            options={
                "require": [
                    "sub",
                    "tenant_id",
                    "project_id",
                    "role",
                    "permissions",
                    "iss",
                    "aud",
                    "iat",
                    "nbf",
                    "exp",
                    "jti",
                    "type",
                    "policy_version",
                    "allowed_model_ids",
                    "tool_overrides",
                    "tool_policy_version",
                    "delegation_version",
                    "scope",
                    "context_hash",
                ]
            },
        )
        self.assertEqual(claims["sub"], "user-1")
        self.assertEqual(claims["tenant_id"], "__default")
        self.assertEqual(claims["project_id"], "project-1")
        self.assertEqual(claims["role"], "project_editor")
        self.assertEqual(
            claims["permissions"],
            ["project.runtime.read", "project.runtime.write"],
        )
        self.assertEqual(claims["type"], "runtime_delegation")
        self.assertEqual(claims["policy_version"], "policy-1")
        self.assertEqual(claims["allowed_model_ids"], ["model-1"])
        self.assertEqual(claims["tool_overrides"], {})
        self.assertEqual(claims["delegation_version"], 2)
        self.assertEqual(
            claims["scope"],
            {"tenant_id": "__default", "project_id": "project-1", "operation": "read"},
        )
        self.assertTrue(claims["context_hash"].startswith("sha256:"))
        self.assertEqual(
            jwt.get_unverified_header(token)["kid"], "runtime-delegation-v1"
        )

    def test_rejects_unconfigured_secret(self) -> None:
        with self.assertRaisesRegex(ValueError, "at least 32 bytes"):
            create_runtime_delegation_token(
                subject="user-1",
                tenant_id="__default",
                project_id="project-1",
                role="project_editor",
                permissions=[],
                policy_version="policy-1",
                allowed_model_ids=["model-1"],
                tool_overrides={},
                tool_policy_version="test-tools-v2",
                scope={
                    "tenant_id": "__default",
                    "project_id": "project-1",
                    "operation": "read",
                },
                context_hash=empty_runtime_context_hash(),
                settings=Settings(runtime_delegation_secret=""),
            )

    def test_operation_scope_accepts_only_execution_and_message_operations(
        self,
    ) -> None:
        settings = Settings(
            runtime_delegation_secret="runtime-delegation-secret-at-least-32-bytes"
        )
        for operation in (
            "read",
            "run-create",
            "message-enqueue",
            "message-read",
            "dear-skills-read",
            "dear-skills-write",
        ):
            token = create_runtime_delegation_token(
                subject="user-1",
                tenant_id="__default",
                project_id="project-1",
                role="project_editor",
                permissions=["project.runtime.read"],
                policy_version="policy-1",
                allowed_model_ids=[],
                tool_overrides={},
                tool_policy_version="test-tools-v2",
                scope={
                    "tenant_id": "__default",
                    "project_id": "project-1",
                    "operation": operation,
                    "assistant_id": "reference_agent",
                },
                settings=settings,
            )
            claims = jwt.decode(
                token,
                settings.runtime_delegation_secret,
                algorithms=["HS256"],
                options={"verify_signature": False},
            )
            self.assertEqual(claims["scope"]["operation"], operation)
        with self.assertRaisesRegex(ValueError, "operation is unsupported"):
            create_runtime_delegation_token(
                subject="user-1",
                tenant_id="__default",
                project_id="project-1",
                role="project_editor",
                permissions=["project.runtime.read"],
                policy_version="policy-1",
                allowed_model_ids=[],
                tool_overrides={},
                tool_policy_version="test-tools-v2",
                scope={
                    "tenant_id": "__default",
                    "project_id": "project-1",
                    "operation": "admin",
                },
                settings=settings,
            )

    def test_gateway_replaces_client_identity_headers_with_delegation(self) -> None:
        project_id = "project-1"
        app = FastAPI()
        app.state.settings = Settings(
            runtime_delegation_secret="runtime-delegation-secret-at-least-32-bytes"
        )
        request = Request(
            {
                "type": "http",
                "method": "POST",
                "path": f"/api/langgraph/threads/{project_id}/commands",
                "query_string": b"",
                "headers": [
                    (b"authorization", b"Bearer browser-token"),
                    (b"x-project-id", b"forged-project"),
                ],
                "app": app,
                "client": ("127.0.0.1", 1),
                "server": ("testserver", 80),
                "scheme": "http",
            }
        )
        request.state.request_id = "request-1"
        request.state.platform_context = PlatformRequestContext(
            request=RequestContext(
                request_id="request-1",
                trace_id="request-1",
                method="POST",
                path=request.url.path,
                started_at=0.0,
            ),
            tenant=TenantContext(tenant_id="__default"),
            project=ProjectContext(project_id=project_id),
            actor=ActorContext(),
        )
        actor = ActorContext(
            user_id="user-1",
            subject="subject-1",
            project_roles={project_id: ("project_editor",)},
        )

        with (
            patch(
                "platform_api.modules.runtime_gateway.presentation.http.LangGraphRuntimeGatewayUpstream",
                return_value=SimpleNamespace(),
            ) as upstream_factory,
            patch(
                "platform_api.modules.runtime_gateway.presentation.http.RuntimePolicyOverlayService",
            ) as policy_factory,
        ):
            policy_factory.return_value.build_delegation_policy.return_value = {
                "version": "policy-1",
                "allowed_model_ids": ["model-1"],
                "tool_overrides": {},
                "tool_policy_version": "test-tools-v2",
                "runtime_permissions": ["runtime.tool.read"],
            }
            get_runtime_gateway_service(request, actor)

        forwarded = upstream_factory.call_args.kwargs["forwarded_headers"]
        self.assertEqual(set(forwarded), {"authorization", "x-request-id"})
        self.assertNotIn("browser-token", forwarded["authorization"])
        token = forwarded["authorization"].removeprefix("Bearer ")
        claims = jwt.decode(
            token,
            app.state.settings.runtime_delegation_secret,
            algorithms=["HS256"],
            audience="runtime-service",
            issuer="platform-api",
        )
        self.assertEqual(claims["sub"], "user-1")
        self.assertEqual(claims["project_id"], project_id)
        self.assertEqual(claims["policy_version"], "policy-1")
        self.assertEqual(
            claims["permissions"],
            [],
        )
        self.assertEqual(claims["request_id"], "request-1")
        self.assertNotIn("platform_trace_id", claims)


class ProtocolV2RuntimeNormalizationTest(unittest.TestCase):
    def test_client_cannot_supply_private_memory_source(self):
        for key in (
            "dear_memory_source",
            "runtime_message_claim",
            "dear_skill_snapshot",
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                normalize_runtime_payload(
                    payload={"input": {key: {"text": "forged"}}}, project_id="project"
                )
            with self.subTest(key=key), self.assertRaises(ValueError):
                normalize_protocol_v2_command(
                    payload={
                        "id": 1,
                        "method": "run.start",
                        "params": {
                            "assistant_id": "dearflow_agent",
                            "input": {key: {"text": "forged"}},
                        },
                    }
                )

    def test_rejects_client_tool_authorization_in_all_control_locations(self):
        for field in ("tools", "enable_tools", "tool_overrides", "tool_policy_version"):
            for location in (
                "context",
                "metadata",
                "config",
                "configurable",
                "platform_runtime",
                "config_metadata",
            ):
                with (
                    self.subTest(field=field, location=location),
                    self.assertRaises(ValueError),
                ):
                    value = {field: {}}
                    if location == "configurable":
                        params = {"config": {"configurable": value}}
                    elif location == "platform_runtime":
                        params = {
                            "config": {"configurable": {"platform_runtime": value}}
                        }
                    elif location == "config_metadata":
                        params = {"config": {"metadata": value}}
                    else:
                        params = {location: value}
                    normalize_protocol_v2_command(
                        payload={
                            "id": 1,
                            "method": "run.start",
                            "params": {"assistant_id": "reference_agent", **params},
                        }
                    )

    def test_moves_runtime_options_into_standard_config_namespace(self) -> None:
        normalized = normalize_protocol_v2_command(
            payload={
                "id": 7,
                "method": "run.start",
                "params": {
                    "assistant_id": "assistant-1",
                    "input": {"messages": []},
                    "config": {
                        "recursion_limit": 10,
                        "temperature": 0.2,
                        "configurable": {
                            "checkpoint_id": "checkpoint-1",
                        },
                    },
                },
            },
            default_model_id="project-default",
        )

        self.assertEqual(
            normalized["params"]["config"],
            {
                "recursion_limit": 10,
                "configurable": {
                    "checkpoint_id": "checkpoint-1",
                    "platform_runtime": {
                        "model_id": "project-default",
                        "temperature": 0.2,
                    },
                },
            },
        )
        self.assertNotIn("context", normalized["params"])

    def test_rejects_identity_in_platform_runtime(self) -> None:
        with self.assertRaisesRegex(ValueError, "trusted identity fields: project_id"):
            normalize_protocol_v2_command(
                payload={
                    "id": 8,
                    "method": "run.start",
                    "params": {
                        "assistant_id": "assistant-1",
                        "config": {
                            "configurable": {
                                "platform_runtime": {
                                    "project_id": "forged-project",
                                }
                            }
                        },
                    },
                }
            )

    def test_rejects_invalid_runtime_option_shape(self) -> None:
        with self.assertRaisesRegex(ValueError, "fields: tools"):
            normalize_protocol_v2_command(
                payload={
                    "id": 10,
                    "method": "run.start",
                    "params": {
                        "assistant_id": "assistant-1",
                        "config": {
                            "configurable": {"platform_runtime": {"tools": "utc_now"}}
                        },
                    },
                }
            )

    def test_rejects_legacy_context_fields_before_upstream(self) -> None:
        with self.assertRaisesRegex(
            ValueError, "Unsupported run.start context fields: system_prompt"
        ):
            normalize_protocol_v2_command(
                payload={
                    "id": 15,
                    "method": "run.start",
                    "params": {
                        "assistant_id": "assistant-1",
                        "context": {"system_prompt": "legacy"},
                    },
                }
            )

    def test_rejects_invalid_durable_run_parameters(self) -> None:
        base_params = {"assistant_id": "assistant-1", "input": {"messages": []}}

        with self.assertRaisesRegex(ValueError, "durability must be one of"):
            normalize_protocol_v2_command(
                payload={
                    "id": 11,
                    "method": "run.start",
                    "params": {**base_params, "durability": "eventual"},
                }
            )

        with self.assertRaisesRegex(ValueError, "durability must be one of"):
            normalize_protocol_v2_command(
                payload={
                    "id": 14,
                    "method": "run.start",
                    "params": {**base_params, "durability": {"mode": "sync"}},
                }
            )

        with self.assertRaisesRegex(ValueError, "stream_resumable must be a boolean"):
            normalize_protocol_v2_command(
                payload={
                    "id": 12,
                    "method": "run.start",
                    "params": {**base_params, "stream_resumable": "true"},
                }
            )

        with self.assertRaisesRegex(
            ValueError, "on_disconnect must be cancel or continue"
        ):
            normalize_protocol_v2_command(
                payload={
                    "id": 13,
                    "method": "run.start",
                    "params": {**base_params, "on_disconnect": "pause"},
                }
            )

        with self.assertRaisesRegex(
            ValueError, "on_disconnect must be cancel or continue"
        ):
            normalize_protocol_v2_command(
                payload={
                    "id": 15,
                    "method": "run.start",
                    "params": {**base_params, "on_disconnect": ["continue"]},
                }
            )

    def test_preserves_non_run_command_envelope(self) -> None:
        payload = {
            "id": 9,
            "method": "input.respond",
            "params": {"interrupt_id": "interrupt-1", "response": {"approve": True}},
        }
        self.assertEqual(normalize_protocol_v2_command(payload=payload), payload)

    def test_validates_event_replay_subscription(self) -> None:
        payload = {
            "channels": ["messages", "values", "tasks", "checkpoints"],
            "namespaces": [[], ["worker"]],
            "depth": 2,
            "since": 41,
        }
        self.assertEqual(normalize_protocol_v2_event_request(payload), payload)

        with self.assertRaisesRegex(ValueError, "since must be a non-negative integer"):
            normalize_protocol_v2_event_request({"channels": ["messages"], "since": -1})


if __name__ == "__main__":
    unittest.main()
