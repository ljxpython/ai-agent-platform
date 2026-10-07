from __future__ import annotations

import base64
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import test_byok_model_lifecycle as byok
from pydantic import ValidationError

from platform_api.adapters.langgraph.sdk_client import redact_runtime_private_fields
from platform_api.core.errors import BadRequestError, ForbiddenError, NotFoundError
from platform_api.modules.agents.application.contracts import (
    CreateAssistantCommand,
    UpdateAssistantCommand,
)
from platform_api.modules.agents.application.service import AssistantsService
from platform_api.modules.agents.domain.models import (
    MODEL_RESILIENCE_KEY,
    ModelResilienceSettings,
)
from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
from platform_api.modules.runtime_catalog.application.model_connection import (
    ModelReferenceError,
    create_model_reference,
    parse_model_reference,
)
from platform_api.modules.runtime_catalog.domain.models import (
    RuntimeModelCreate,
    RuntimeModelUpdate,
)
from platform_api.modules.runtime_gateway.application import thread_access
from platform_api.modules.runtime_gateway.application.service import (
    RuntimeGatewayService,
)
from platform_api.modules.runtime_policies.application.contracts import (
    UpsertRuntimeModelPolicyCommand,
)
from platform_api.modules.runtime_policies.application.service import (
    RuntimePolicyOverlayService,
)
from platform_api.modules.scheduled_tasks.service import authorize_execution, sign_task


class AgentModelResilienceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        byok.ByokModelLifecycleTest.setUp(self)
        self.primary = self.make_model("primary", self.project_1, self.actor_admin_1)
        self.backup = self.make_model("backup", self.project_1, self.actor_admin_1)
        self.foreign = self.make_model("foreign", self.project_2, self.actor_admin_2)
        self.policy = ModelResilienceSettings.disabled().model_copy(
            update={"enabled": True, "fallback_model_id": self.backup.id}
        )
        self.agents = AssistantsService(
            session_factory=self.factory,
            schema_provider=SimpleNamespace(
                build_schema=AsyncMock(
                    return_value={
                        "schema_version": "remote-v1",
                        "sections": [{"key": "context"}],
                    }
                )
            ),
        )
        self.policies = RuntimePolicyOverlayService(
            session_factory=self.factory, runtime_base_url="http://runtime"
        )
        self.thread_id = str(uuid4())
        thread_access.register(
            self.factory,
            actor=self.actor_admin_1,
            project_id=str(self.project_1),
            thread_id=self.thread_id,
        )
        self.upstream = SimpleNamespace(
            create_thread_run=AsyncMock(return_value={"run_id": str(uuid4())}),
            get_thread_run=AsyncMock(return_value={"status": "success"}),
        )
        self.gateway = RuntimeGatewayService(
            session_factory=self.factory,
            upstream=self.upstream,
            runtime_model_config_secret=self.settings.runtime_model_config_secret,
        )
        self.gateway._load_thread = AsyncMock(
            return_value={"thread_id": self.thread_id}
        )

    def make_model(self, name, project, actor):
        return self.service.create_model(
            actor=actor,
            project_id=str(project),
            payload=RuntimeModelCreate(
                provider="openai",
                display_name=name,
                base_url="https://provider.invalid/v1",
                protocol="openai",
                model=name,
                api_key="private-key-" + name,
                scope_type="project",
                project_id=str(project),
            ),
        )

    async def create(self, settings=None, graph="reference_agent"):
        return await self.agents.create_assistant(
            actor=self.actor_admin_1,
            project_id=str(self.project_1),
            command=CreateAssistantCommand(
                name=graph,
                graph_id=graph,
                context={"model_id": self.primary.id},
                model_resilience=settings,
            ),
        )

    def update(self, item, **values):
        return self.agents.update_assistant(
            actor=self.actor_admin_1,
            assistant_id=item.id,
            command=UpdateAssistantCommand(**values),
        )

    async def test_management_json_roundtrip_schema_and_strict_boundaries(self):
        item = await self.create(self.policy)
        self.assertEqual(item.model_resilience, self.policy)
        self.assertNotIn(MODEL_RESILIENCE_KEY, item.context)
        updated = self.update(item, context={"temperature": 0.4})
        self.assertEqual(updated.model_resilience, self.policy)
        self.assertEqual(updated.context, {"temperature": 0.4})
        self.assertEqual(
            self.update(item, name="renamed").model_resilience, self.policy
        )
        self.assertFalse(
            self.update(item, model_resilience=None).model_resilience.enabled
        )
        with self.factory() as session:
            self.assertNotIn(
                MODEL_RESILIENCE_KEY, session.get(AgentRecord, UUID(item.id)).context
            )
        for graph, supported in (("reference_agent", True), ("other_graph", False)):
            schema = await self.agents.get_parameter_schema(
                actor=self.actor_admin_1, graph_id=graph, project_id=str(self.project_1)
            )
            self.assertEqual(schema["sections"][0]["key"], "context")
            self.assertEqual(schema["sections"][-1]["supported"], supported)
        for invalid in (
            {"enabled": 1},
            {"max_attempts": True},
            {"max_attempts": 2.5},
            {"attempt_timeout_seconds": True},
            {"total_timeout_seconds": float("nan")},
            {"total_timeout_seconds": float("inf")},
            {"total_timeout_seconds": 1},
            {"unknown": 1},
            {"fallback_model_id": "not-a-catalog-id"},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                UpdateAssistantCommand(
                    model_resilience={**self.policy.model_dump(), **invalid}
                )
        with self.assertRaises(ValidationError):
            UpdateAssistantCommand(model_resilience={"enabled": True})
        with self.assertRaises(BadRequestError):
            self.update(item, context={MODEL_RESILIENCE_KEY: self.policy.model_dump()})

    async def test_candidates_share_catalog_delegation_and_save_authorization(self):
        item = await self.create()
        for candidate in (self.foreign.id, str(uuid4())):
            with self.subTest(candidate=candidate), self.assertRaises(ForbiddenError):
                self.update(
                    item,
                    model_resilience=self.policy.model_copy(
                        update={"fallback_model_id": candidate}
                    ),
                )
        with self.assertRaises(BadRequestError):
            self.update(
                item,
                model_resilience=self.policy.model_copy(
                    update={"fallback_model_id": self.primary.id}
                ),
            )
        with self.assertRaises(BadRequestError):
            await self.create(self.policy, graph="other_graph")
        allowed = self.policies.build_delegation_policy(project_id=str(self.project_1))[
            "allowed_model_ids"
        ]
        self.assertIn(self.primary.id, allowed)
        self.assertIn(self.backup.id, allowed)
        self.assertNotIn(self.foreign.id, allowed)
        listing = self.policies.list_model_policies(
            actor=self.actor_admin_1, project_id=str(self.project_1)
        )
        self.assertNotIn(self.foreign.id, [p.model_id for p in listing.items])
        with self.assertRaises(NotFoundError):
            self.policies.upsert_model_policy(
                actor=self.actor_admin_1,
                project_id=str(self.project_1),
                catalog_id=self.foreign.id,
                command=UpsertRuntimeModelPolicyCommand(is_enabled=True),
            )
        self.policies.upsert_model_policy(
            actor=self.actor_admin_1,
            project_id=str(self.project_1),
            catalog_id=self.backup.id,
            command=UpsertRuntimeModelPolicyCommand(is_enabled=False),
        )
        with self.assertRaises(ForbiddenError):
            self.update(item, model_resilience=self.policy)

    async def test_signed_bundle_redeems_both_and_revocation_fails_closed(self):
        await self.create(self.policy)
        payload = self.gateway._attach_runtime_model_reference(
            project_id=str(self.project_1),
            actor=self.actor_admin_1,
            thread_id=self.thread_id,
            payload={
                "assistant_id": "reference_agent",
                "context": {"model_id": self.primary.id},
            },
        )
        reference = payload["config"]["configurable"]["runtime_model_ref"]
        values = parse_model_reference(
            reference, secret=self.settings.runtime_model_config_secret
        )
        self.assertEqual(values["model_resilience"], self.policy.model_dump())
        with self.assertRaises(ModelReferenceError):
            parse_model_reference(
                reference + "x", secret=self.settings.runtime_model_config_secret
            )
        bundle = self.service.resolve_model_connection(
            reference=reference, project_id=str(self.project_1)
        )
        self.assertEqual(bundle["api_key"], "private-key-primary")
        self.assertEqual(bundle["fallback_connection"]["api_key"], "private-key-backup")
        self.assertNotIn("private-key", repr(values))
        foreign_ref = create_model_reference(
            project_id=str(self.project_1),
            model_id=self.primary.id,
            secret=self.settings.runtime_model_config_secret,
            actor=values["actor"],
            agent_key="reference_agent",
            thread_id=self.thread_id,
            model_resilience=self.policy.model_copy(
                update={"fallback_model_id": self.foreign.id}
            ),
        )
        with self.assertRaises(ForbiddenError):
            self.service.resolve_model_connection(
                reference=foreign_ref, project_id=str(self.project_1)
            )
        self.service.update_model(
            actor=self.actor_admin_1,
            project_id=str(self.project_1),
            model_id=self.backup.id,
            payload=RuntimeModelUpdate(enabled=False),
        )
        with self.assertRaises(ForbiddenError):
            self.service.resolve_model_connection(
                reference=reference, project_id=str(self.project_1)
            )

    async def test_submission_reuses_frozen_policy_after_unknown_result(self):
        item = await self.create(self.policy)
        payload = {
            "assistant_id": "reference_agent",
            "context": {"model_id": self.primary.id},
            "input": {"messages": [{"role": "user", "content": "hello"}]},
        }
        command = {"method": "run.start", "params": payload}

        async def submit(key="same-key"):
            return await self.gateway.launch_runtime_run(
                actor=self.actor_admin_1,
                project_id=str(self.project_1),
                thread_id=self.thread_id,
                command=command,
                upstream_payload=payload,
                idempotency_key=key,
            )

        self.upstream.create_thread_run.side_effect = TimeoutError("lost response")
        with self.assertRaises(TimeoutError):
            await submit()
        self.update(item, model_resilience=None)
        self.upstream.create_thread_run.side_effect = None
        record, _ = await submit()
        sent = self.upstream.create_thread_run.call_args.args[1]
        self.assertNotIn(MODEL_RESILIENCE_KEY, sent["config"])
        self.assertEqual(
            record.config_snapshot[MODEL_RESILIENCE_KEY], self.policy.model_dump()
        )
        reference = sent["config"]["configurable"]["runtime_model_ref"]
        self.assertEqual(
            parse_model_reference(
                reference, secret=self.settings.runtime_model_config_secret
            )["model_resilience"],
            self.policy.model_dump(),
        )
        self.assertNotIn("runtime_model_ref", repr(redact_runtime_private_fields(sent)))
        fresh, _ = await submit("new-key")
        self.assertFalse(fresh.config_snapshot[MODEL_RESILIENCE_KEY]["enabled"])
        self.assertEqual(self.upstream.create_thread_run.await_count, 3)

    async def test_public_run_configuration_cannot_inject_policy(self):
        await self.create()
        for location in ("context", "config", "metadata", "input"):
            with self.subTest(location=location), self.assertRaises(BadRequestError):
                await self.gateway.launch_runtime_run(
                    actor=self.actor_admin_1,
                    project_id=str(self.project_1),
                    thread_id=self.thread_id,
                    command={},
                    upstream_payload={
                        "assistant_id": "reference_agent",
                        location: {MODEL_RESILIENCE_KEY: self.policy.model_dump()},
                    },
                    idempotency_key=location,
                )
        self.upstream.create_thread_run.assert_not_awaited()

    async def test_resume_keeps_parent_policy_after_agent_configuration_changes(self):
        item = await self.create(self.policy)
        payload = {
            "assistant_id": "reference_agent",
            "context": {"model_id": self.primary.id},
            "input": {"messages": [{"role": "user", "content": "hello"}]},
        }
        _, created = await self.gateway.launch_runtime_run(
            actor=self.actor_admin_1,
            project_id=str(self.project_1),
            thread_id=self.thread_id,
            command={"method": "run.start", "params": payload},
            upstream_payload=payload,
            idempotency_key="parent",
        )
        self.update(item, model_resilience=None)
        self.upstream.get_thread_state = AsyncMock(
            return_value={
                "metadata": {"run_id": created["run_id"]},
                "interrupts": [{"id": "approval"}],
            }
        )
        self.upstream.get_thread_run.return_value = {
            "run_id": created["run_id"],
            "status": "interrupted",
        }
        self.gateway._assert_runtime_target_allowed = lambda **kwargs: None
        await self.gateway.send_thread_command(
            actor=self.actor_admin_1,
            project_id=str(self.project_1),
            thread_id=self.thread_id,
            payload={
                "id": 1,
                "method": "input.respond",
                "params": {
                    "resume": {"approval": {"decisions": [{"type": "approve"}]}}
                },
            },
        )
        payload = self.upstream.create_thread_run.call_args.args[1]
        reference = payload["config"]["configurable"]["runtime_model_ref"]
        self.assertEqual(
            parse_model_reference(
                reference, secret=self.settings.runtime_model_config_secret
            )["model_resilience"],
            self.policy.model_dump(),
        )
        self.assertNotIn(MODEL_RESILIENCE_KEY, payload["config"])

    async def test_scheduled_callback_reads_current_policy_and_rejects_backup_revocation(
        self,
    ):
        item = await self.create(self.policy)
        values = {
            "v": 1,
            "tenant_id": "fixture-tenant",
            "project_id": str(self.project_1),
            "owner_id": str(self.user_admin_1),
            "credential_id": None,
            "agent_key": "reference_agent",
            "thread_mode": "reuse",
            "thread_id": self.thread_id,
        }
        payload = {
            **values,
            "task": sign_task(values, self.settings.runtime_delegation_secret),
            "task_id": str(uuid4()),
            "run_id": str(uuid4()),
            "context": {"model_id": self.primary.id},
        }
        self.gateway._assert_runtime_target_allowed = lambda **kwargs: None
        result = authorize_execution(
            self.factory, self.gateway, payload, self.settings.runtime_delegation_secret
        )
        self.assertTrue(result["allowed"])
        reference = result["configurable"]["runtime_model_ref"]
        self.assertEqual(
            parse_model_reference(
                reference, secret=self.settings.runtime_model_config_secret
            )["model_resilience"],
            self.policy.model_dump(),
        )
        self.service.update_model(
            actor=self.actor_admin_1,
            project_id=str(self.project_1),
            model_id=self.backup.id,
            payload=RuntimeModelUpdate(enabled=False),
        )
        denied = authorize_execution(
            self.factory,
            self.gateway,
            {**payload, "run_id": str(uuid4())},
            self.settings.runtime_delegation_secret,
        )
        self.assertFalse(denied["allowed"])
        self.assertEqual(denied["error_code"], "runtime_model_denied")
        self.update(item, model_resilience=None)
        current = authorize_execution(
            self.factory,
            self.gateway,
            {**payload, "run_id": str(uuid4())},
            self.settings.runtime_delegation_secret,
        )
        self.assertTrue(current["allowed"])
        self.assertNotIn(
            "model_resilience",
            parse_model_reference(
                current["configurable"]["runtime_model_ref"],
                secret=self.settings.runtime_model_config_secret,
            ),
        )

    async def test_signature_covers_backup_budget_and_project(self):
        reference = create_model_reference(
            project_id=str(self.project_1),
            model_id=self.primary.id,
            secret=self.settings.runtime_model_config_secret,
            model_resilience=self.policy,
        )
        version, payload, signature = reference.split(".")
        values = parse_model_reference(
            reference, secret=self.settings.runtime_model_config_secret
        )
        for mutation in (
            {"fallback_model_id": self.foreign.id},
            {"max_attempts": 5},
            {"total_timeout_seconds": 1200},
        ):
            altered = {
                **values,
                "model_resilience": {**values["model_resilience"], **mutation},
            }
            encoded = (
                base64.urlsafe_b64encode(json.dumps(altered).encode())
                .decode()
                .rstrip("=")
            )
            with (
                self.subTest(mutation=mutation),
                self.assertRaises(ModelReferenceError),
            ):
                parse_model_reference(
                    f"{version}.{encoded}.{signature}",
                    secret=self.settings.runtime_model_config_secret,
                )
        altered = {**values, "project_id": str(self.project_2)}
        encoded = (
            base64.urlsafe_b64encode(json.dumps(altered).encode()).decode().rstrip("=")
        )
        with self.assertRaises(ModelReferenceError):
            parse_model_reference(
                f"{version}.{encoded}.{signature}",
                secret=self.settings.runtime_model_config_secret,
            )

    async def test_context_override_deduplicates_the_backup_connection(self):
        await self.create(self.policy)
        payload = self.gateway._attach_runtime_model_reference(
            project_id=str(self.project_1),
            actor=self.actor_admin_1,
            thread_id=self.thread_id,
            payload={
                "assistant_id": "reference_agent",
                "context": {"model_id": self.backup.id},
            },
        )
        reference = payload["config"]["configurable"]["runtime_model_ref"]
        bundle = self.service.resolve_model_connection(
            reference=reference, project_id=str(self.project_1)
        )
        self.assertIsNone(bundle["fallback_connection"])
        self.assertTrue(bundle["model_resilience"]["enabled"])
        self.assertEqual(bundle["api_key"], "private-key-backup")
