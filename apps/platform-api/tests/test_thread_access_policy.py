import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from platform_api.modules.runtime_gateway.application.service import RuntimeGatewayService


class ThreadAccessPolicyTest(unittest.IsolatedAsyncioTestCase):
    async def test_gateway_overrides_client_policy_from_thread_metadata(self) -> None:
        service = RuntimeGatewayService(session_factory=None, upstream=SimpleNamespace())
        payload = service._inject_thread_access_policy(
            thread={"metadata": {"access_policy": "workspace_write"}},
            payload={"context": {"access_policy": "review"}},
        )
        self.assertEqual(payload["context"]["access_policy"], "workspace_write")
        self.assertEqual(payload["config"]["configurable"]["platform_runtime"]["access_policy"], "workspace_write")

    async def test_policy_update_preserves_thread_metadata(self) -> None:
        upstream = SimpleNamespace(update_thread=AsyncMock())
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(return_value={"metadata": {"project_id": "p", "graph_id": "showcase_demo"}})  # type: ignore[method-assign]
        result = await service.update_thread_access_policy(
            actor=SimpleNamespace(), project_id="p", thread_id="t", policy="workspace_write"
        )
        self.assertEqual(result, {"thread_id": "t", "access_policy": "workspace_write"})
        upstream.update_thread.assert_awaited_once_with(
            "t", {"metadata": {"project_id": "p", "graph_id": "showcase_demo", "access_policy": "workspace_write"}}
        )

    async def test_policy_update_supports_full_access(self) -> None:
        upstream = SimpleNamespace(update_thread=AsyncMock())
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._load_thread = AsyncMock(return_value={"metadata": {"project_id": "p", "graph_id": "showcase_demo"}})  # type: ignore[method-assign]
        result = await service.update_thread_access_policy(
            actor=SimpleNamespace(), project_id="p", thread_id="t", policy="full_access"
        )
        self.assertEqual(result, {"thread_id": "t", "access_policy": "full_access"})
        upstream.update_thread.assert_awaited_once_with(
            "t", {"metadata": {"project_id": "p", "graph_id": "showcase_demo", "access_policy": "full_access"}}
        )

    async def test_create_thread_preserves_explicit_access_policy(self) -> None:
        upstream = SimpleNamespace(create_thread=AsyncMock(return_value={"thread_id": "new_t"}))
        service = RuntimeGatewayService(session_factory=None, upstream=upstream)
        service._prepare_project_scope = lambda *args, **kwargs: None  # type: ignore[assignment]
        await service.create_thread(
            actor=SimpleNamespace(),
            project_id="p",
            payload={"graph_id": "showcase_demo", "metadata": {"access_policy": "full_access"}},
        )
        upstream.create_thread.assert_awaited_once_with({
            "graph_id": "showcase_demo",
            "metadata": {"project_id": "p", "access_policy": "full_access"},
        })

