from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from platform_api.core.context.models import ActorContext
from platform_api.core.db import build_engine, build_session_factory, create_core_tables, session_scope
from platform_api.modules.agents.domain import AssistantItem
from platform_api.modules.operations.application import CreateOperationCommand, OperationsService
from platform_api.modules.operations.application.artifacts import LocalOperationArtifactStore
from platform_api.modules.operations.application.execution import (
    DatabasePollingOperationDispatcher,
    OperationExecutorRegistry,
)
from platform_api.modules.operations.application.executors import (
    AssistantResyncExecutor,
)
from platform_api.modules.operations.application.worker import OperationWorker
from platform_api.modules.operations.domain import OperationStatus
from platform_api.modules.projects.infra.sqlalchemy.repository import SqlAlchemyProjectsRepository


class _FakeAssistantsService:
    async def resync_assistant(self, *, actor: ActorContext, assistant_id: str) -> AssistantItem:
        return AssistantItem(
            id=assistant_id,
            project_id=str(next(iter(actor.project_roles.keys()), "")),
            name="Research Demo",
            description="resynced by worker",
            graph_id="research_demo",
            runtime_base_url="http://127.0.0.1:8123",
            metadata={"source": "worker-test"},
        )


class OperationsArtifactFlowTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        database_path = Path(self._tmpdir.name) / "platform-api-test.db"
        self._engine = build_engine(f"sqlite:///{database_path}")
        self._session_factory = build_session_factory(self._engine)
        create_core_tables(self._engine)

        self.project_id = self._create_project()
        self.actor = ActorContext(
            user_id=str(uuid4()),
            platform_roles=("platform_super_admin",),
            project_roles={self.project_id: ("project_admin",)},
        )
        self.artifact_store = LocalOperationArtifactStore(str(Path(self._tmpdir.name) / "artifacts"))
        self.fake_assistants = _FakeAssistantsService()
        self.service = OperationsService(
            session_factory=self._session_factory,
            dispatcher=DatabasePollingOperationDispatcher(),
            artifact_store=self.artifact_store,
        )
        self.worker = OperationWorker(
            session_factory=self._session_factory,
            executor_registry=OperationExecutorRegistry(
                (
                    AssistantResyncExecutor(service=self.fake_assistants),  # type: ignore[arg-type]
                )
            ),
            poll_interval_seconds=0.01,
            idle_sleep_seconds=0.01,
        )

    def tearDown(self) -> None:
        self._engine.dispose()
        self._tmpdir.cleanup()

    def _create_project(self) -> str:
        with session_scope(self._session_factory) as session:
            repository = SqlAlchemyProjectsRepository(session)
            tenant = repository.get_or_create_default_tenant()
            project = repository.create_project(
                tenant_id=tenant.id,
                name="Operations Smoke Project",
                description="phase-3 operation flow test",
            )
            return str(project.id)

    async def test_assistant_resync_operation_flow(self) -> None:
        submitted = await self.service.submit_operation(
            actor=self.actor,
            command=CreateOperationCommand(
                kind="assistant.resync",
                project_id=self.project_id,
                input_payload={"assistant_id": "assistant-123"},
            ),
        )

        processed = await self.worker.run_once()
        final = await self.service.get_operation(actor=self.actor, operation_id=submitted.id)

        self.assertTrue(processed)
        self.assertEqual(final.status, OperationStatus.SUCCEEDED)
        self.assertEqual(final.result_payload["id"], "assistant-123")
        self.assertEqual(final.result_payload["name"], "Research Demo")

if __name__ == "__main__":
    unittest.main()
