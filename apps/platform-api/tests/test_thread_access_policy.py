import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from platform_api.core.context.models import ActorContext
from platform_api.core.errors import ForbiddenError
from platform_api.modules.runtime_gateway.application import thread_access
from platform_api.modules.runtime_gateway.application.service import (
    RuntimeGatewayService,
)
from tests.thread_acl_fixture import thread_acl_factory


class ThreadAccessPolicyTest(unittest.IsolatedAsyncioTestCase):
    async def test_long_lived_gateway_refreshes_each_material_read(self):
        thread_id, run_id = str(uuid4()), str(uuid4())
        actor = ActorContext(
            user_id="owner", project_roles={"p": ("project_executor",)}
        )
        factory = thread_acl_factory(
            self, actor=actor, project_id="p", thread_id=thread_id
        )
        thread = {"thread_id": thread_id, "metadata": {"project_id": "p"}}
        run = {"thread_id": thread_id, "run_id": run_id}
        scoped = SimpleNamespace(
            get_thread=AsyncMock(return_value=thread),
            list_thread_runs=AsyncMock(return_value=[run]),
            get_thread_run=AsyncMock(return_value=run),
            get_execution_evidence=AsyncMock(return_value={"manifest": {}}),
        )
        stale = SimpleNamespace(
            get_thread=AsyncMock(side_effect=RuntimeError("expired request token")),
            list_thread_runs=AsyncMock(
                side_effect=RuntimeError("expired request token")
            ),
            get_thread_run=AsyncMock(side_effect=RuntimeError("expired request token")),
            with_forwarded_headers=Mock(return_value=scoped),
        )
        mint = Mock(side_effect=lambda **kw: {"authorization": str(uuid4())})
        service = RuntimeGatewayService(
            session_factory=factory, upstream=stale, delegation_headers_factory=mint
        )
        service._prepare_project_scope = lambda **kwargs: None
        await service.get_thread(actor=actor, project_id="p", thread_id=thread_id)
        self.assertEqual(
            await service.list_thread_runs(
                actor=actor, project_id="p", thread_id=thread_id, params={}
            ),
            [run],
        )
        self.assertEqual(
            await service.get_thread_execution_evidence(
                actor=actor, project_id="p", thread_id=thread_id, run_id=run_id
            ),
            {"manifest": {}},
        )
        stale.get_thread.assert_not_awaited()
        stale.list_thread_runs.assert_not_awaited()
        stale.get_thread_run.assert_not_awaited()
        self.assertEqual(len(mint.call_args_list), 6)
        for call in mint.call_args_list:
            self.assertEqual(call.kwargs["thread_id"], thread_id)
            self.assertEqual(call.kwargs["project_id"], "p")
            self.assertIn(call.kwargs["operation"], {"read", "diagnostics-read"})
        self.assertEqual(
            len(
                {
                    call.args[0]["authorization"]
                    for call in stale.with_forwarded_headers.call_args_list
                }
            ),
            6,
        )
        mint.reset_mock()
        with self.assertRaises(ForbiddenError):
            await service.get_thread(
                actor=ActorContext(
                    user_id="other", project_roles={"p": ("project_executor",)}
                ),
                project_id="p",
                thread_id=thread_id,
            )
        mint.assert_not_called()

    def setUp(self):
        self.actor = ActorContext(
            user_id="owner", project_roles={"p": ("project_executor",)}
        )
        self.factory = thread_acl_factory(
            self, actor=self.actor, project_id="p", thread_id="t"
        )
        self.metadata = thread_access.get(self.factory, "t")

    async def test_gateway_overrides_client_policy_from_thread_metadata(self) -> None:
        service = RuntimeGatewayService(
            session_factory=None, upstream=SimpleNamespace()
        )
        payload = service._inject_thread_access_policy(
            thread={"metadata": {"access_policy": "workspace_write"}},
            payload={"context": {"access_policy": "review"}},
        )
        self.assertEqual(payload["context"]["access_policy"], "workspace_write")
        self.assertEqual(
            payload["config"]["configurable"]["platform_runtime"]["access_policy"],
            "workspace_write",
        )

    async def test_policy_update_preserves_thread_metadata(self) -> None:
        upstream = SimpleNamespace(update_thread=AsyncMock())
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(return_value={"metadata": self.metadata})
        result = await service.update_thread_access_policy(
            actor=self.actor, project_id="p", thread_id="t", policy="workspace_write"
        )
        self.assertEqual(result, {"thread_id": "t", "access_policy": "workspace_write"})
        upstream.update_thread.assert_awaited_once_with(
            "t", {"metadata": {"access_policy": "workspace_write"}}
        )

    async def test_policy_update_supports_full_access(self) -> None:
        upstream = SimpleNamespace(update_thread=AsyncMock())
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(return_value={"metadata": self.metadata})
        result = await service.update_thread_access_policy(
            actor=self.actor, project_id="p", thread_id="t", policy="full_access"
        )
        self.assertEqual(result, {"thread_id": "t", "access_policy": "full_access"})
        upstream.update_thread.assert_awaited_once_with(
            "t", {"metadata": {"access_policy": "full_access"}}
        )

    async def test_create_thread_preserves_explicit_access_policy(self) -> None:
        upstream = SimpleNamespace(
            create_thread=AsyncMock(
                side_effect=lambda payload: {
                    "thread_id": payload["thread_id"],
                    "metadata": payload["metadata"],
                }
            )
        )
        service = RuntimeGatewayService(session_factory=self.factory, upstream=upstream)
        service._prepare_project_scope = lambda *args, **kwargs: None  # type: ignore[assignment]
        await service.create_thread(
            actor=self.actor,
            project_id="p",
            payload={
                "graph_id": "showcase_demo",
                "metadata": {"access_policy": "full_access"},
            },
        )
        sent = upstream.create_thread.call_args.args[0]
        self.assertEqual(
            sent["metadata"],
            {
                "project_id": "p",
                "tenant_id": "__default",
                "access_policy": "full_access",
            },
        )
        self.assertEqual(sent["retention"], {"mode": "idle", "ttl_minutes": 43200})
        self.assertEqual(
            thread_access.get(self.factory, sent["thread_id"])["owner_user_id"],
            self.actor.user_id,
        )

    async def test_executor_cannot_change_another_owners_policy_or_open_terminal(
        self,
    ) -> None:
        upstream = SimpleNamespace(
            create_thread=AsyncMock(), terminal_request=AsyncMock()
        )
        service = RuntimeGatewayService(session_factory=self.factory, upstream=upstream)
        service._prepare_project_scope = lambda **kwargs: None
        actor = ActorContext(
            user_id="executor", project_roles={"p": ("project_executor",)}
        )
        with self.assertRaises(ForbiddenError):
            await service.update_thread_access_policy(
                actor=actor, project_id="p", thread_id="t", policy="full_access"
            )
        with self.assertRaises(ForbiddenError):
            await service.thread_terminal(
                actor=actor, project_id="p", thread_id="t", action="create"
            )
        upstream.create_thread.assert_not_awaited()
        upstream.terminal_request.assert_not_awaited()
