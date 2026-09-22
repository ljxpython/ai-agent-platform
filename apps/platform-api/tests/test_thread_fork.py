import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from platform_api.core.context.models import ActorContext
from tests.thread_acl_fixture import thread_acl_factory

from platform_api.modules.runtime_gateway.application.service import RuntimeGatewayService


class ThreadForkTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.actor = ActorContext(user_id="owner", project_roles={"p": ("project_executor",)})
        self.factory = thread_acl_factory(self, actor=self.actor, project_id="p", thread_id="source")
        identity = patch("platform_api.modules.runtime_gateway.application.service.uuid4", return_value="target")
        identity.start()
        self.addCleanup(identity.stop)

    async def test_fork_copies_checkpoint_values_into_a_new_thread(self) -> None:
        upstream = SimpleNamespace(
            get_thread_state=AsyncMock(return_value={"values": {"messages": ["done"]}}),
            create_thread=AsyncMock(return_value={"thread_id": "target"}),
            update_thread_state=AsyncMock(),
            delete_thread=AsyncMock(),
        )
        service = RuntimeGatewayService(session_factory=self.factory, upstream=upstream)
        service._prepare_project_scope = Mock()
        service._load_thread = AsyncMock(return_value={"metadata": {"project_id": "p", "owner_user_id": "owner", "graph_id": "showcase_demo", "access_policy": "workspace_write", "agent_id": "agent-123"}})

        result = await service.fork_thread(
            actor=self.actor, project_id="p", thread_id="source",
            checkpoint_id="checkpoint", title="Branch",
        )

        self.assertEqual(result["thread_id"], "target")
        self.assertEqual(result["metadata"]["owner_user_id"], "owner")
        upstream.get_thread_state.assert_awaited_once_with("source", {"checkpoint_id": "checkpoint"})
        upstream.create_thread.assert_awaited_once_with({"metadata": {
            "project_id": "p", "graph_id": "showcase_demo", "access_policy": "workspace_write",
            "forked_from": {"thread_id": "source", "checkpoint_id": "checkpoint"},
            "agent_id": "agent-123",
            "title": "Branch",
        }, "graph_id": "showcase_demo", "thread_id": "target", "if_exists": "raise"})
        upstream.update_thread_state.assert_awaited_once_with("target", {"values": {"messages": ["done"]}})

    async def test_fork_removes_target_when_state_copy_fails(self) -> None:
        upstream = SimpleNamespace(
            get_thread_state=AsyncMock(return_value={"values": {"messages": ["done"]}}),
            create_thread=AsyncMock(return_value={"thread_id": "target"}),
            update_thread_state=AsyncMock(side_effect=RuntimeError("broken")),
            delete_thread=AsyncMock(),
        )
        service = RuntimeGatewayService(session_factory=self.factory, upstream=upstream)
        service._prepare_project_scope = Mock()
        service._load_thread = AsyncMock(return_value={"metadata": {"project_id": "p", "graph_id": "showcase_demo"}})  # type: ignore[method-assign]

        with self.assertRaisesRegex(RuntimeError, "broken"):
            await service.fork_thread(actor=self.actor, project_id="p", thread_id="source", checkpoint_id="checkpoint", title=None)
        upstream.delete_thread.assert_awaited_once_with("target")

    async def test_fork_invokes_workspace_fork_when_delegation_configured(self) -> None:
        fork_workspace_mock = AsyncMock(return_value={"forked": True})
        delegated_upstream = SimpleNamespace(fork_thread_workspace=fork_workspace_mock)
        upstream = SimpleNamespace(
            get_thread_state=AsyncMock(return_value={"values": {"messages": ["done"]}}),
            create_thread=AsyncMock(return_value={"thread_id": "target"}),
            update_thread_state=AsyncMock(),
            delete_thread=AsyncMock(),
            with_forwarded_headers=Mock(return_value=delegated_upstream),
        )
        factory_calls = []

        def fake_delegation_factory(**kwargs):
            factory_calls.append(kwargs)
            return {"Authorization": "Bearer fake-token"}

        service = RuntimeGatewayService(
            session_factory=self.factory,
            upstream=upstream,
            delegation_headers_factory=fake_delegation_factory,
        )
        service._prepare_project_scope = Mock()
        service._load_thread = AsyncMock(return_value={  # type: ignore[method-assign]
            "metadata": {"project_id": "p", "graph_id": "showcase_demo", "agent_id": "agent-1"}
        })

        result = await service.fork_thread(
            actor=self.actor, project_id="p", thread_id="source",
            checkpoint_id="checkpoint", title="Fork",
        )
        self.assertEqual(result["thread_id"], "target")
        self.assertEqual(len(factory_calls), 1)
        self.assertEqual(factory_calls[0]["operation"], "workspace-fork")
        self.assertEqual(factory_calls[0]["thread_id"], "target")
        upstream.with_forwarded_headers.assert_called_once_with({"Authorization": "Bearer fake-token"})
        fork_workspace_mock.assert_awaited_once_with(target_thread_id="target", source_thread_id="source")
