import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import inspect

from platform_api.core.context.models import ActorContext
from platform_api.core.db import (
    build_engine,
    build_session_factory,
    create_core_tables,
    session_scope,
)
from platform_api.core.errors import ConflictError, ForbiddenError
from platform_api.modules.agents.application.contracts import (
    CreateAssistantCommand,
    UpdateAssistantCommand,
)
from platform_api.modules.agents.application.service import AssistantsService
from platform_api.modules.agents.domain import AssistantStatus
from platform_api.modules.agents.infra.sqlalchemy.repository import (
    SqlAlchemyAssistantsRepository,
)
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
from platform_api.modules.runtime_gateway.application.service import (
    RuntimeGatewayService,
)


class AgentSingleTableTest(unittest.IsolatedAsyncioTestCase):
    async def test_configuration_lifecycle_and_project_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = build_engine(f"sqlite:///{Path(directory) / 'agents.db'}")
            self.addCleanup(engine.dispose)
            factory = build_session_factory(engine)
            create_core_tables(engine)
            self.assertNotIn("agent_profiles", inspect(engine).get_table_names())
            with session_scope(factory) as session:
                projects = SqlAlchemyProjectsRepository(session)
                tenant = projects.get_or_create_default_tenant()
                project_id = str(
                    projects.create_project(
                        tenant_id=tenant.id, name="Agents", description=""
                    ).id
                )
            actor = ActorContext(
                user_id=str(uuid4()), project_roles={project_id: ("project_admin",)}
            )
            service = AssistantsService(
                session_factory=factory,
                schema_provider=SimpleNamespace(build_schema=AsyncMock(return_value={})),
            )
            created = await service.create_assistant(
                actor=actor,
                project_id=project_id,
                command=CreateAssistantCommand(
                    name="Demo", graph_id="demo", context={"temperature": 0.2}
                ),
            )
            updated = service.update_assistant(
                actor=actor,
                assistant_id=created.id,
                command=UpdateAssistantCommand(
                    status=AssistantStatus.DISABLED, context={"temperature": 0.5}
                ),
            )
            fetched = service.get_assistant(actor=actor, assistant_id=created.id)
            gateway = RuntimeGatewayService(session_factory=factory, upstream=None)
            with self.assertRaises(ForbiddenError):
                gateway._assert_runtime_target_allowed(
                    project_id=project_id,
                    assistant_id="demo",
                    thread={"metadata": {"project_id": project_id, "graph_id": "demo"}},
                )
            with self.assertRaises(ConflictError):
                await service.create_assistant(
                    actor=actor,
                    project_id=project_id,
                    command=CreateAssistantCommand(name="Another", graph_id="demo"),
                )
            with self.assertRaises(ForbiddenError):
                service.get_assistant(
                    actor=ActorContext(user_id=str(uuid4())),
                    assistant_id=created.id,
                )
            self.assertEqual(fetched.status, updated.status)
            self.assertEqual(fetched.context, updated.context)
            self.assertEqual(fetched.created_by, actor.user_id)
            with session_scope(factory) as session:
                repo = SqlAlchemyAssistantsRepository(session)
                self.assertIsNone(
                    repo.get_by_project_and_graph_id(
                        project_id=uuid4(), graph_id="demo"
                    )
                )
                records, total = repo.list_project_assistants(
                    project_id=UUID(project_id),
                    limit=10,
                    offset=0,
                    query="Demo",
                    graph_id="demo",
                )
                self.assertEqual(total, 1)
                self.assertEqual(records[0].status, updated.status.value)
            service.delete_assistant(
                actor=actor,
                assistant_id=created.id,
            )
            with session_scope(factory) as session:
                self.assertIsNone(
                    SqlAlchemyAssistantsRepository(session).get_assistant_by_id(
                        UUID(created.id)
                    )
                )
