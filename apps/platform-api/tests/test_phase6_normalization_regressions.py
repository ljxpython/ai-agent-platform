from __future__ import annotations

import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock

from platform_api.modules.runtime_gateway.application.service import RuntimeGatewayService


class RuntimeGatewayNormalizationRegressionTest(unittest.IsolatedAsyncioTestCase):
    def test_cold_import_identity_and_projects_sqlalchemy_modules(self) -> None:
        models_module = importlib.import_module("platform_api.modules.identity.models")
        repository_module = importlib.import_module(
            "platform_api.modules.projects.repository"
        )
        service_module = importlib.import_module("platform_api.modules.runtime_gateway.application.service")

        self.assertIsNotNone(models_module)
        self.assertTrue(hasattr(repository_module, "SqlAlchemyProjectsRepository"))
        self.assertTrue(hasattr(service_module, "RuntimeGatewayService"))

    async def test_create_thread_promotes_graph_id_from_legacy_graph_metadata(self) -> None:
        upstream = SimpleNamespace(create_thread=AsyncMock(return_value={"ok": True}))
        service = RuntimeGatewayService(
            session_factory=None,
            upstream=upstream,
        )
        service._prepare_project_scope = Mock()  # type: ignore[method-assign]

        payload = await service.create_thread(
            actor=SimpleNamespace(),
            project_id="project-1",
            payload={
                "metadata": {
                    "target_type": "graph",
                    "assistant_id": "test_case_agent",
                }
            },
        )

        self.assertEqual(payload, {"ok": True})
        upstream.create_thread.assert_awaited_once_with(
            {
                "metadata": {
                    "target_type": "graph",
                    "assistant_id": "test_case_agent",
                    "project_id": "project-1",
                },
                "graph_id": "test_case_agent",
            }
        )





if __name__ == "__main__":
    unittest.main()
