"""Platform DB ACL and gateway checks; no Runtime ACL implementation is involved."""

import tempfile
import os
import time
import unittest
import json
import statistics
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import urlparse

from sqlalchemy import create_engine, select, text
from uuid import uuid4

from platform_api.core.context.models import ActorContext
from platform_api.core.db import (
    build_engine,
    build_session_factory,
    create_core_tables,
    session_scope,
)
from platform_api.core.errors import ForbiddenError
from platform_api.modules.audit.models import AuditLogRecord
from platform_api.modules.iam.domain import ProjectRole
from platform_api.modules.identity.repository import SqlAlchemyIdentityRepository
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
from platform_api.modules.runtime_gateway.application import thread_access as acl
from platform_api.modules.runtime_gateway.application.service import (
    RuntimeGatewayService,
)
from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
    ThreadAccessRecord,
)


class ThreadAclTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = build_engine(f"sqlite:///{Path(self.temp.name) / 'acl.db'}")
        self.factory = build_session_factory(self.engine)
        create_core_tables(self.engine)
        with session_scope(self.factory) as session:
            projects = SqlAlchemyProjectsRepository(session)
            tenant = projects.get_or_create_default_tenant()
            project = projects.create_project(
                tenant_id=tenant.id, name="ACL", description=""
            )
            self.project = str(project.id)
            users = SqlAlchemyIdentityRepository(session)
            self.actors = {}
            for name, role in (
                ("owner", ProjectRole.EXECUTOR),
                ("peer", ProjectRole.EXECUTOR),
                ("admin", ProjectRole.ADMIN),
            ):
                user = users.create_user(
                    username=name,
                    password_hash="unused",
                    external_subject=name,
                    email=None,
                    platform_roles=(),
                    is_super_admin=False,
                )
                projects.upsert_project_member(
                    project_id=project.id, user_id=user.id, role=role
                )
                self.actors[name] = ActorContext(
                    user_id=str(user.id), project_roles={self.project: (role.value,)}
                )
        self.owner, self.peer, self.admin = (
            self.actors[key] for key in ("owner", "peer", "admin")
        )
        self.superadmin = ActorContext(
            user_id="platform-admin", platform_roles=("platform_super_admin",)
        )
        acl.register(
            self.factory, thread_id="private", project_id=self.project, actor=self.owner
        )
        self.upstream = SimpleNamespace(
            get_thread=AsyncMock(
                return_value={
                    "thread_id": "private",
                    "metadata": {
                        "project_id": self.project,
                        "graph_id": "showcase_demo",
                    },
                }
            ),
            update_thread=AsyncMock(),
            delete_thread=AsyncMock(),
            create_thread=AsyncMock(
                side_effect=lambda payload: {
                    "thread_id": payload["thread_id"],
                    "metadata": payload["metadata"],
                }
            ),
            search_threads=AsyncMock(return_value=[]),
        )
        self.service = RuntimeGatewayService(
            session_factory=self.factory, upstream=self.upstream
        )

    def tearDown(self):
        self.engine.dispose()
        self.temp.cleanup()

    async def test_private_read_and_full_access_require_owner(self):
        for actor in (self.peer, self.admin, self.superadmin):
            with self.subTest(actor=actor.user_id), self.assertRaises(ForbiddenError):
                await self.service.get_thread(
                    actor=actor, project_id=self.project, thread_id="private"
                )
        self.upstream.get_thread.assert_not_awaited()
        thread = await self.service.get_thread(
            actor=self.owner, project_id=self.project, thread_id="private"
        )
        self.assertIn("full_access", thread["metadata"]["allowed_actions"])
        for actor in (self.admin, self.superadmin):
            await self.service.delete_thread(
                actor=actor, project_id=self.project, thread_id="private"
            )

    async def test_share_revoke_and_independent_actions(self):
        await self.service.share_thread(
            actor=self.owner,
            project_id=self.project,
            thread_id="private",
            user_id=self.peer.user_id,
            actions=["read", "comment"],
        )
        result = await self.service.get_thread(
            actor=self.peer, project_id=self.project, thread_id="private"
        )
        self.assertEqual(
            set(result["metadata"]["allowed_actions"]), {"read", "comment"}
        )
        with self.assertRaises(ForbiddenError):
            await self.service.update_thread(
                actor=self.peer,
                project_id=self.project,
                thread_id="private",
                metadata_updates={"title": "denied"},
            )
        await self.service.share_thread(
            actor=self.owner,
            project_id=self.project,
            thread_id="private",
            user_id=self.peer.user_id,
            actions=[],
        )
        self.upstream.get_thread.reset_mock()
        with self.assertRaises(ForbiddenError):
            await self.service.get_thread(
                actor=self.peer, project_id=self.project, thread_id="private"
            )
        self.upstream.get_thread.assert_not_awaited()

    async def test_takeover_is_read_only_expiring_and_audited(self):
        await self.service.takeover_thread(
            actor=self.superadmin,
            project_id=self.project,
            thread_id="private",
            category="user_support",
            reason="User requested support for this specific conversation",
            reference="CASE-123",
            duration_minutes=15,
        )
        result = await self.service.get_thread(
            actor=self.superadmin, project_id=self.project, thread_id="private"
        )
        self.assertEqual(
            set(result["metadata"]["allowed_actions"]), {"read", "approve", "delete"}
        )
        with session_scope(self.factory) as session:
            actions = set(session.scalars(select(AuditLogRecord.action)))
            self.assertEqual(
                actions, {"thread.takeover.granted", "thread.takeover.accessed"}
            )
            row = session.get(ThreadAccessRecord, "private")
            row.takeovers = {self.superadmin.user_id: {"expires_at": time.time() - 1}}
        with self.assertRaises(ForbiddenError):
            await self.service.get_thread(
                actor=self.superadmin, project_id=self.project, thread_id="private"
            )

    async def test_new_thread_ignores_supplied_identity_and_acl(self):
        result = await self.service.create_thread(
            actor=self.owner,
            project_id=self.project,
            payload={
                "thread_id": "private",
                "metadata": {
                    "owner_user_id": self.peer.user_id,
                    "visibility": "project",
                    "sandbox_id": "another-sandbox",
                    "access_policy": "full_access",
                },
            },
        )
        self.assertNotEqual(result["thread_id"], "private")
        with session_scope(self.factory) as session:
            self.assertEqual(
                session.get(
                    ThreadAccessRecord, result["thread_id"]
                ).provisioning_status,
                "ready",
            )
        self.assertEqual(result["metadata"]["owner_user_id"], self.owner.user_id)
        sent = self.upstream.create_thread.call_args.args[0]
        self.assertFalse(set(sent["metadata"]) & acl.ACL_KEYS)
        self.assertNotIn("sandbox_id", sent["metadata"])
        await self.service.update_thread(
            actor=self.owner,
            project_id=self.project,
            thread_id="private",
            metadata_updates={"title": "new"},
        )
        self.upstream.update_thread.assert_awaited_once_with(
            "private", {"metadata": {"title": "new"}}
        )

    async def test_service_account_only_sees_project_shared_threads(self):
        service_actor = ActorContext(
            subject="service",
            principal_type="service_account",
            project_roles={self.project: ("project_executor",)},
        )
        self.assertFalse(
            acl.allowed(
                service_actor, self.project, acl.get(self.factory, "private"), "read"
            )
        )
        acl.share(
            self.factory,
            actor=self.owner,
            project_id=self.project,
            thread_id="private",
            user_id=None,
            actions=["read", "comment"],
        )
        metadata = acl.get(self.factory, "private")
        self.assertTrue(acl.allowed(service_actor, self.project, metadata, "comment"))
        self.assertFalse(acl.allowed(service_actor, self.project, metadata, "terminal"))
        revoked = ActorContext(user_id=self.owner.user_id)
        self.assertFalse(acl.allowed(revoked, self.project, metadata, "read"))

    async def test_takeover_project_shared_thread_ends_without_business_membership(
        self,
    ):
        acl.share(
            self.factory,
            actor=self.owner,
            project_id=self.project,
            thread_id="private",
            user_id=None,
            actions=["read"],
        )
        with self.assertRaises(ForbiddenError):
            await self.service.get_thread(
                actor=self.superadmin, project_id=self.project, thread_id="private"
            )
        await self.service.takeover_thread(
            actor=self.superadmin,
            project_id=self.project,
            thread_id="private",
            category="user_support",
            reason="User requested support for this conversation",
            reference="CASE-124",
            duration_minutes=15,
        )
        result = await self.service.get_thread(
            actor=self.superadmin, project_id=self.project, thread_id="private"
        )
        self.assertEqual(
            set(result["metadata"]["allowed_actions"]), {"read", "approve", "delete"}
        )
        self.assertNotIn("takeovers", result["metadata"])
        await self.service.end_thread_takeover(
            actor=self.superadmin, project_id=self.project, thread_id="private"
        )
        with self.assertRaises(ForbiddenError):
            await self.service.get_thread(
                actor=self.superadmin, project_id=self.project, thread_id="private"
            )
        with session_scope(self.factory) as session:
            self.assertIn(
                "thread.takeover.ended",
                set(session.scalars(select(AuditLogRecord.action))),
            )

    async def test_takeover_cannot_cross_project_or_be_ended_by_another_admin(self):
        kwargs = dict(
            actor=self.superadmin,
            thread_id="private",
            category="user_support",
            reason="User requested support for this conversation",
            reference="CASE-125",
            duration_minutes=15,
        )
        with self.assertRaises(ForbiddenError):
            acl.takeover(self.factory, project_id="different-project", **kwargs)
        acl.takeover(self.factory, project_id=self.project, **kwargs)
        with self.assertRaises(ForbiddenError):
            acl.end_takeover(
                self.factory,
                actor=self.superadmin,
                project_id="different-project",
                thread_id="private",
            )
        acl.end_takeover(
            self.factory, actor=self.admin, project_id=self.project, thread_id="private"
        )
        self.assertTrue(
            acl.allowed(
                self.superadmin, self.project, acl.get(self.factory, "private"), "read"
            )
        )

    async def test_registration_failure_never_creates_upstream_thread(self):
        with patch.object(
            acl, "register", side_effect=RuntimeError("database unavailable")
        ):
            with self.assertRaisesRegex(RuntimeError, "database unavailable"):
                await self.service.create_thread(
                    actor=self.owner, project_id=self.project, payload={}
                )
        self.upstream.create_thread.assert_not_awaited()
        self.upstream.delete_thread.assert_not_awaited()

    async def test_explicit_create_rejection_removes_reservation(self):
        from platform_api.core.errors import UpstreamServiceError

        self.upstream.create_thread.side_effect = UpstreamServiceError(
            upstream="langgraph", status_code=403, code="denied", message="Denied"
        )
        with self.assertRaises(UpstreamServiceError):
            await self.service.create_thread(
                actor=self.owner, project_id=self.project, payload={}
            )
        created_id = self.upstream.create_thread.call_args.args[0]["thread_id"]
        self.assertEqual(acl.get(self.factory, created_id), {})
        self.upstream.delete_thread.assert_not_awaited()

    async def test_unknown_create_result_keeps_reservation(self):
        from platform_api.core.errors import UpstreamServiceError

        self.upstream.create_thread.side_effect = UpstreamServiceError(
            upstream="langgraph", status_code=504, code="timeout", message="Timed out"
        )
        with self.assertRaises(UpstreamServiceError):
            await self.service.create_thread(
                actor=self.owner, project_id=self.project, payload={}
            )
        created_id = self.upstream.create_thread.call_args.args[0]["thread_id"]
        self.assertEqual(
            acl.get(self.factory, created_id)["owner_user_id"], self.owner.user_id
        )
        with session_scope(self.factory) as session:
            self.assertEqual(
                session.get(ThreadAccessRecord, created_id).provisioning_status,
                "pending",
            )
        self.upstream.delete_thread.assert_not_awaited()

    async def test_unknown_create_result_is_reconciled_when_thread_exists(self):
        from platform_api.core.errors import UpstreamServiceError

        self.upstream.create_thread.side_effect = UpstreamServiceError(
            upstream="langgraph", status_code=504, code="timeout", message="Timed out"
        )
        self.upstream.get_thread.side_effect = lambda thread_id: {
            "thread_id": thread_id,
            "metadata": {"project_id": self.project},
        }
        self.upstream.with_forwarded_headers = Mock(return_value=self.upstream)
        self.service._delegation_headers_factory = Mock(
            return_value={"authorization": "Bearer scoped"}
        )
        result = await self.service.create_thread(
            actor=self.owner, project_id=self.project, payload={}
        )
        thread_id = self.upstream.create_thread.call_args.args[0]["thread_id"]
        self.assertEqual(result["thread_id"], thread_id)
        self.assertEqual(
            acl.get(self.factory, thread_id)["owner_user_id"], self.owner.user_id
        )
        with session_scope(self.factory) as session:
            self.assertEqual(
                session.get(ThreadAccessRecord, thread_id).provisioning_status, "ready"
            )
        self.assertEqual(
            self.service._delegation_headers_factory.call_args.kwargs["operation"],
            "thread-reconcile",
        )

    async def test_reconcile_does_not_provision_thread_from_another_project(self):
        from platform_api.core.errors import UpstreamServiceError

        self.upstream.create_thread.side_effect = UpstreamServiceError(
            upstream="langgraph", status_code=504, code="timeout", message="Timed out"
        )
        self.upstream.get_thread.side_effect = lambda thread_id: {
            "thread_id": thread_id,
            "metadata": {"project_id": "another-project"},
        }
        self.upstream.with_forwarded_headers = Mock(return_value=self.upstream)
        self.service._delegation_headers_factory = Mock(
            return_value={"authorization": "Bearer scoped"}
        )
        with self.assertRaises(ForbiddenError):
            await self.service.create_thread(
                actor=self.owner, project_id=self.project, payload={}
            )
        thread_id = self.upstream.create_thread.call_args.args[0]["thread_id"]
        with session_scope(self.factory) as session:
            self.assertEqual(
                session.get(ThreadAccessRecord, thread_id).provisioning_status,
                "pending",
            )

    async def test_unknown_create_result_keeps_reservation_after_reconcile_404(self):
        from platform_api.core.errors import UpstreamServiceError

        self.upstream.create_thread.side_effect = UpstreamServiceError(
            upstream="langgraph", status_code=504, code="timeout", message="Timed out"
        )
        self.upstream.get_thread.side_effect = UpstreamServiceError(
            upstream="langgraph", status_code=404, code="not_found", message="Not found"
        )
        self.upstream.with_forwarded_headers = Mock(return_value=self.upstream)
        self.service._delegation_headers_factory = Mock(
            return_value={"authorization": "Bearer scoped"}
        )
        with self.assertRaises(UpstreamServiceError) as caught:
            await self.service.create_thread(
                actor=self.owner, project_id=self.project, payload={}
            )
        thread_id = self.upstream.create_thread.call_args.args[0]["thread_id"]
        self.assertEqual(
            caught.exception.extra,
            {
                "upstream": "langgraph",
                "thread_id": thread_id,
                "reconcile_path": f"/api/langgraph/threads/{thread_id}/reconcile",
            },
        )
        self.assertEqual(
            acl.get(self.factory, thread_id)["owner_user_id"], self.owner.user_id
        )
        with session_scope(self.factory) as session:
            self.assertEqual(
                session.get(ThreadAccessRecord, thread_id).provisioning_status,
                "pending",
            )

    async def test_pending_owner_can_reconcile_after_late_create(self):
        thread_id = str(uuid4())
        acl.register(
            self.factory,
            thread_id=thread_id,
            project_id=self.project,
            actor=self.owner,
        )
        self.upstream.get_thread.return_value = {
            "thread_id": thread_id,
            "metadata": {"project_id": self.project},
        }
        self.upstream.with_forwarded_headers = Mock(return_value=self.upstream)
        self.service._delegation_headers_factory = Mock(
            return_value={"authorization": "Bearer scoped"}
        )
        result = await self.service.reconcile_pending_thread(
            actor=self.owner, project_id=self.project, thread_id=thread_id
        )
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["thread"]["thread_id"], thread_id)
        self.assertEqual(
            self.service._delegation_headers_factory.call_args.kwargs["operation"],
            "thread-reconcile",
        )
        with session_scope(self.factory) as session:
            self.assertEqual(
                session.get(ThreadAccessRecord, thread_id).provisioning_status, "ready"
            )

    async def test_pending_reconcile_404_stays_pending_and_peer_is_denied(self):
        from platform_api.core.errors import UpstreamServiceError

        thread_id = str(uuid4())
        acl.register(
            self.factory,
            thread_id=thread_id,
            project_id=self.project,
            actor=self.owner,
        )
        self.upstream.get_thread.side_effect = UpstreamServiceError(
            upstream="langgraph", status_code=404, code="not_found", message="Not found"
        )
        self.upstream.with_forwarded_headers = Mock(return_value=self.upstream)
        self.service._delegation_headers_factory = Mock(
            return_value={"authorization": "Bearer scoped"}
        )
        with self.assertRaises(ForbiddenError):
            await self.service.reconcile_pending_thread(
                actor=self.peer, project_id=self.project, thread_id=thread_id
            )
        result = await self.service.reconcile_pending_thread(
            actor=self.owner, project_id=self.project, thread_id=thread_id
        )
        self.assertEqual(result, {"thread_id": thread_id, "status": "pending"})
        with session_scope(self.factory) as session:
            self.assertEqual(
                session.get(ThreadAccessRecord, thread_id).provisioning_status,
                "pending",
            )

    async def test_reconcile_404_does_not_remove_acl_after_provisioning_race(self):
        from platform_api.core.errors import UpstreamServiceError

        self.upstream.create_thread.side_effect = UpstreamServiceError(
            upstream="langgraph", status_code=504, code="timeout", message="Timed out"
        )

        async def late_404(thread_id):
            acl.mark_provisioned(self.factory, thread_id)
            raise UpstreamServiceError(
                upstream="langgraph",
                status_code=404,
                code="not_found",
                message="Not found",
            )

        self.upstream.get_thread.side_effect = late_404
        self.upstream.with_forwarded_headers = Mock(return_value=self.upstream)
        self.service._delegation_headers_factory = Mock(
            return_value={"authorization": "Bearer scoped"}
        )
        with self.assertRaises(UpstreamServiceError):
            await self.service.create_thread(
                actor=self.owner, project_id=self.project, payload={}
            )
        thread_id = self.upstream.create_thread.call_args.args[0]["thread_id"]
        self.assertEqual(
            acl.get(self.factory, thread_id)["owner_user_id"], self.owner.user_id
        )
        with session_scope(self.factory) as session:
            self.assertEqual(
                session.get(ThreadAccessRecord, thread_id).provisioning_status, "ready"
            )

    async def test_unknown_create_result_keeps_reservation_when_reconcile_fails(self):
        from platform_api.core.errors import UpstreamServiceError

        original = UpstreamServiceError(
            upstream="langgraph", status_code=504, code="timeout", message="Timed out"
        )
        self.upstream.create_thread.side_effect = original
        self.upstream.get_thread.side_effect = UpstreamServiceError(
            upstream="langgraph",
            status_code=503,
            code="unavailable",
            message="Unavailable",
        )
        self.upstream.with_forwarded_headers = Mock(return_value=self.upstream)
        self.service._delegation_headers_factory = Mock(
            return_value={"authorization": "Bearer scoped"}
        )
        with self.assertRaises(UpstreamServiceError) as raised:
            await self.service.create_thread(
                actor=self.owner, project_id=self.project, payload={}
            )
        thread_id = self.upstream.create_thread.call_args.args[0]["thread_id"]
        self.assertIs(raised.exception, original)
        self.assertEqual(
            acl.get(self.factory, thread_id)["owner_user_id"], self.owner.user_id
        )
        with session_scope(self.factory) as session:
            self.assertEqual(
                session.get(ThreadAccessRecord, thread_id).provisioning_status,
                "pending",
            )

    async def test_manager_approval_does_not_grant_private_read_or_leak_run_input(self):
        self.upstream.create_thread_run = AsyncMock(
            return_value={"run_id": "source-run"}
        )
        self.upstream.get_thread_run = AsyncMock(
            return_value={"run_id": "source-run", "status": "interrupted"}
        )
        self.upstream.get_thread_state = AsyncMock(
            return_value={
                "metadata": {"run_id": "source-run"},
                "tasks": [{"interrupts": [{"id": "approval"}]}],
            }
        )
        # Model/Agent fixtures are external to this ACL contract; IAM, ACL and the durable request ledger are real.
        self.service._project_default_model_id = Mock(return_value=None)
        self.service._assert_runtime_target_allowed = Mock()
        self.service._assert_runtime_options_allowed = Mock()
        await self.service.create_thread_run(
            actor=self.owner,
            project_id=self.project,
            thread_id="private",
            payload={
                "assistant_id": "showcase_demo",
                "input": {"message": "private content"},
            },
        )
        command = {
            "command": {"resume": {"approval": {"decisions": [{"type": "reject"}]}}}
        }
        with self.assertRaises(ForbiddenError):
            await self.service.create_thread_run(
                actor=self.peer,
                project_id=self.project,
                thread_id="private",
                payload=command,
            )
        self.upstream.create_thread_run.return_value = {
            "run_id": "resumed-run",
            "input": "private content",
            "config": {"secret": "hidden"},
        }
        result = await self.service.create_thread_run(
            actor=self.superadmin,
            project_id=self.project,
            thread_id="private",
            payload=command,
        )
        self.assertEqual(result, {"thread_id": "private", "run_id": "resumed-run"})
        with self.assertRaises(ForbiddenError):
            await self.service.get_thread(
                actor=self.superadmin, project_id=self.project, thread_id="private"
            )

    async def test_operator_catalog_refresh_does_not_grant_project_execution(self):
        import jwt
        from platform_api.config import Settings
        from platform_api.modules.runtime_catalog.application.service import (
            RuntimeCatalogService,
        )

        operator = ActorContext(
            user_id="operator", platform_roles=("platform_operator",)
        )
        settings = Settings(
            runtime_delegation_secret="catalog-test-delegation-secret-at-least-32-bytes"
        )
        upstream = SimpleNamespace(
            require_json=AsyncMock(return_value={"tools": []}),
            list_deployed_graphs=AsyncMock(return_value=[]),
        )
        service = RuntimeCatalogService(
            session_factory=self.factory,
            upstream=upstream,
            runtime_base_url="http://runtime.test",
            settings=settings,
        )
        with patch(
            "platform_api.modules.runtime_catalog.application.service.RuntimePolicyOverlayService"
        ) as overlay:
            overlay.return_value.build_delegation_policy.return_value = {
                "version": "test",
                "allowed_model_ids": ["test:model"],
            }
            await service.refresh_tools(actor=operator, project_id=self.project)
            await service.refresh_graphs(actor=operator, project_id=self.project)
            with self.assertRaises(ForbiddenError):
                service._runtime_headers(actor=operator, project_id=self.project)
            with self.assertRaises(ForbiddenError):
                await service.refresh_tools(actor=self.owner, project_id=self.project)
        header = upstream.list_deployed_graphs.call_args.kwargs["forwarded_headers"][
            "authorization"
        ]
        claims = jwt.decode(
            header.removeprefix("Bearer "),
            settings.runtime_delegation_secret,
            algorithms=["HS256"],
            audience=settings.runtime_delegation_audience,
            issuer=settings.runtime_delegation_issuer,
        )
        self.assertEqual(claims["role"], "platform_operator")
        self.assertEqual(claims["scope"]["operation"], "read")
        self.assertEqual(claims["permissions"], [])
        self.assertFalse(operator.project_role_set(self.project))
        with self.assertRaises(ForbiddenError):
            await self.service.create_thread(
                actor=operator, project_id=self.project, payload={}
            )
        self.upstream.create_thread.assert_not_awaited()

    @unittest.skipUnless(
        os.getenv("RUN_GOVERNANCE_BENCHMARK") == "1",
        "explicit ACL performance baseline gate",
    )
    async def test_acl_filter_ten_thousand_records_baseline(self):
        # Only the isolated fixture database is populated; Runtime is not called.
        with session_scope(self.factory) as session:
            session.add_all(
                ThreadAccessRecord(
                    thread_id=f"bench-{index}",
                    project_id=self.project,
                    owner_user_id=self.owner.user_id,
                    visibility="private",
                    shared_actions={self.peer.user_id: ["read"]}
                    if index % 10 == 0
                    else {},
                    project_actions=[],
                    takeovers={},
                )
                for index in range(10_000)
            )
        durations = []
        for _ in range(10):
            start = time.perf_counter()
            rows = acl.visible_records(
                self.factory, actor=self.peer, project_id=self.project
            )
            durations.append((time.perf_counter() - start) * 1000)
            self.assertEqual(len(rows), 1000)
        print(
            json.dumps(
                {
                    "benchmark": "acl-local-filter",
                    "database": "temporary-sqlite",
                    "records": 10_001,
                    "visible": 1000,
                    "samples": len(durations),
                    "median_ms": round(statistics.median(durations), 2),
                    "max_ms": round(max(durations), 2),
                    "excludes": "Runtime HTTP batches and network latency",
                }
            )
        )

    @unittest.skipUnless(
        os.getenv("RUN_LOCAL_GOVERNANCE_CONTRACT") == "1",
        "explicit local PostgreSQL contract gate",
    )
    async def test_postgres_visible_candidates_keep_shares_and_takeover_expiry(self):
        from platform_api.config import Settings
        from sqlalchemy.engine import make_url

        url = make_url(Settings().database_url)
        self.assertIn(url.host, {"localhost", "127.0.0.1", "::1"})
        engine = create_engine(url)
        schema = "governance_acl_" + uuid4().hex
        try:
            with engine.connect() as connection:
                transaction = connection.begin()
                try:
                    connection.execute(text(f'CREATE SCHEMA "{schema}"'))
                    connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                    ThreadAccessRecord.__table__.create(connection)
                    factory = build_session_factory(connection)
                    for name, shares, takeovers in (
                        ("private", {}, {}),
                        ("shared", {self.peer.user_id: ["read"]}, {}),
                        (
                            "takeover",
                            {},
                            {self.superadmin.user_id: {"expires_at": time.time() + 60}},
                        ),
                        (
                            "expired",
                            {},
                            {self.superadmin.user_id: {"expires_at": time.time() - 1}},
                        ),
                    ):
                        connection.execute(
                            ThreadAccessRecord.__table__.insert().values(
                                thread_id=name,
                                project_id=self.project,
                                owner_user_id=self.owner.user_id,
                                visibility="private",
                                shared_actions=shares,
                                project_actions=[],
                                takeovers=takeovers,
                            )
                        )
                    self.assertEqual(
                        set(
                            acl.visible_records(
                                factory, actor=self.peer, project_id=self.project
                            )
                        ),
                        {"shared"},
                    )
                    self.assertEqual(
                        set(
                            acl.visible_records(
                                factory, actor=self.superadmin, project_id=self.project
                            )
                        ),
                        {"takeover"},
                    )
                    self.assertEqual(
                        len(
                            acl.visible_records(
                                factory, actor=self.owner, project_id=self.project
                            )
                        ),
                        4,
                    )
                finally:
                    transaction.rollback()
        finally:
            engine.dispose()

    @unittest.skipUnless(
        os.getenv("RUN_LOCAL_GOVERNANCE_CONTRACT") == "1",
        "explicit local Runtime contract gate",
    )
    async def test_real_runtime_private_share_revoke_list_and_count(self):
        from platform_api.adapters.langgraph.runtime_gateway_upstream import (
            LangGraphRuntimeGatewayUpstream,
        )
        from platform_api.config import Settings
        from platform_api.core.security import (
            create_runtime_delegation_token,
            empty_runtime_context_hash,
        )

        settings = Settings()
        self.assertIn(
            urlparse(settings.langgraph_upstream_url).hostname,
            {"localhost", "127.0.0.1", "::1"},
        )
        # This synthetic unit-test record is not a real upstream UUID.
        acl.remove(
            self.factory, actor=self.admin, project_id=self.project, thread_id="private"
        )
        token = create_runtime_delegation_token(
            subject=self.owner.user_id,
            tenant_id="__default",
            project_id=self.project,
            role="project_executor",
            permissions=[],
            policy_version="contract",
            allowed_model_ids=["contract:model"],
            tool_overrides={},
            tool_policy_version="unscoped-read-v2",
            scope={
                "tenant_id": "__default",
                "project_id": self.project,
                "operation": "read",
            },
            context_hash=empty_runtime_context_hash(),
            settings=settings,
        )
        upstream = LangGraphRuntimeGatewayUpstream(
            base_url=settings.langgraph_upstream_url,
            timeout_seconds=10,
            forwarded_headers={"authorization": f"Bearer {token}"},
        )
        service = RuntimeGatewayService(session_factory=self.factory, upstream=upstream)
        created = []
        try:
            for actor in (self.owner, self.peer):
                result = await service.create_thread(
                    actor=actor,
                    project_id=self.project,
                    payload={"metadata": {"harness": "platform-thread-acl-contract"}},
                )
                created.append(result["thread_id"])

            async def visible(actor, expected):
                rows = await service.search_threads(
                    actor=actor, project_id=self.project, payload={}
                )
                self.assertEqual({row["thread_id"] for row in rows}, set(expected))
                self.assertEqual(
                    await service.count_threads(
                        actor=actor, project_id=self.project, payload={}
                    ),
                    {"count": len(expected)},
                )

            await visible(self.owner, created[:1])
            await visible(self.peer, created[1:])
            with self.assertRaises(ForbiddenError):
                await service.get_thread(
                    actor=self.peer, project_id=self.project, thread_id=created[0]
                )
            await service.share_thread(
                actor=self.owner,
                project_id=self.project,
                thread_id=created[0],
                user_id=self.peer.user_id,
                actions=["read"],
            )
            await visible(self.peer, created)
            shared = await service.get_thread(
                actor=self.peer, project_id=self.project, thread_id=created[0]
            )
            self.assertEqual(shared["metadata"]["allowed_actions"], ["read"])
            await service.share_thread(
                actor=self.owner,
                project_id=self.project,
                thread_id=created[0],
                user_id=self.peer.user_id,
                actions=[],
            )
            await visible(self.peer, created[1:])
            with self.assertRaises(ForbiddenError):
                await service.get_thread(
                    actor=self.peer, project_id=self.project, thread_id=created[0]
                )
            if os.getenv("RUN_GOVERNANCE_BENCHMARK") == "1":
                # Exercise three real HTTP batches, including the final partial batch.
                for _ in range(200):
                    result = await service.create_thread(
                        actor=self.owner,
                        project_id=self.project,
                        payload={
                            "metadata": {"harness": "platform-thread-acl-contract"}
                        },
                    )
                    created.append(result["thread_id"])
                durations = []
                for _ in range(5):
                    start = time.perf_counter()
                    rows = await service.search_threads(
                        actor=self.owner,
                        project_id=self.project,
                        payload={"limit": 100, "offset": 200},
                    )
                    count = await service.count_threads(
                        actor=self.owner, project_id=self.project, payload={}
                    )
                    durations.append((time.perf_counter() - start) * 1000)
                    self.assertEqual(len(rows), 1)
                    self.assertNotEqual(rows[0]["thread_id"], created[1])
                    self.assertEqual(count, {"count": 201})
                print(
                    json.dumps(
                        {
                            "benchmark": "acl-runtime-list-and-count",
                            "visible": 201,
                            "samples": len(durations),
                            "http_batches_per_sample": 6,
                            "median_ms": round(statistics.median(durations), 2),
                            "max_ms": round(max(durations), 2),
                            "budget_ms": 5000,
                        }
                    )
                )
                self.assertLess(
                    max(durations),
                    5000,
                    "Local list + count exceeds the 5-second acceptance budget",
                )
        finally:
            cleanup_errors = []
            for thread_id in created:
                try:
                    await service.delete_thread(
                        actor=self.admin, project_id=self.project, thread_id=thread_id
                    )
                except Exception as exc:
                    cleanup_errors.append(
                        RuntimeError(
                            f"Cleanup failed for project={self.project}, thread={thread_id}: {exc}"
                        )
                    )
            if cleanup_errors:
                raise ExceptionGroup("Test Thread cleanup failed", cleanup_errors)


if __name__ == "__main__":
    unittest.main()
