from __future__ import annotations

import importlib
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock
from platform_api.core.context.models import ActorContext
from tests.thread_acl_fixture import thread_acl_factory

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
        actor = ActorContext(user_id="owner", project_roles={"project-1": ("project_executor",)})
        upstream = SimpleNamespace(create_thread=AsyncMock(side_effect=lambda payload: {"thread_id": payload["thread_id"], "metadata": payload["metadata"]}))
        service = RuntimeGatewayService(
            session_factory=thread_acl_factory(self, actor=actor, project_id="project-1"),
            upstream=upstream,
        )
        service._prepare_project_scope = Mock()  # type: ignore[method-assign]

        payload = await service.create_thread(
            actor=actor,
            project_id="project-1",
            payload={
                "metadata": {
                    "target_type": "graph",
                    "assistant_id": "test_case_agent",
                }
            },
        )

        self.assertEqual(payload["metadata"]["owner_user_id"], "owner")
        upstream.create_thread.assert_awaited_once_with(
            {
                "metadata": {
                    "target_type": "graph",
                    "assistant_id": "test_case_agent",
                    "project_id": "project-1",
                },
                "graph_id": "test_case_agent",
                "thread_id": payload["thread_id"],
                "if_exists": "raise",
            }
        )





if __name__ == "__main__":
    unittest.main()
