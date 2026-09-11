import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from platform_api.core.context.models import ActorContext
from platform_api.core.db import (
    build_engine,
    build_session_factory,
    create_core_tables,
    session_scope,
)
from platform_api.core.errors import ForbiddenError
from platform_api.modules.agents.application.contracts import (
    ListAssistantsQuery,
    UpdateAssistantCommand,
)
from platform_api.modules.agents.application.service import AssistantsService
from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
from platform_api.modules.runtime_catalog.infra.sqlalchemy.models import (
    RuntimeCatalogGraphRecord,
)
from platform_api.modules.runtime_policies.infra.sqlalchemy.models import (
    ProjectGraphPolicyRecord,
)
from sqlalchemy import select


class GraphAlignmentTest(unittest.TestCase):
    def test_authorized_graphs_materialize_once_preserve_configuration_and_follow_revocation(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            engine = build_engine(f"sqlite:///{Path(directory) / 'test.db'}")
            self.addCleanup(engine.dispose)
            create_core_tables(engine)
            factory = build_session_factory(engine)
            with session_scope(factory) as session:
                repo = SqlAlchemyProjectsRepository(session)
                tenant = repo.get_or_create_default_tenant()
                project = repo.create_project(
                    tenant_id=tenant.id, name="Aligned", description=""
                )
                project_id = project.id
                graph = RuntimeCatalogGraphRecord(
                    runtime_id="default",
                    graph_key="demo",
                    display_name="Demo",
                    sync_status="ready",
                )
                session.add(graph)
                session.flush()
                graph_id = graph.id
            actor = ActorContext(
                user_id=str(uuid4()),
                project_roles={str(project_id): ("project_admin",)},
            )
            service = AssistantsService(
                session_factory=factory, schema_provider=SimpleNamespace()
            )

            def read():
                return service.list_assistants(
                    actor=actor, project_id=str(project_id), query=ListAssistantsQuery()
                )

            with ThreadPoolExecutor(max_workers=4) as workers:
                initial = list(workers.map(lambda _: read(), range(4)))
            first = initial[0]
            self.assertEqual({page.items[0].id for page in initial}, {first.items[0].id})
            self.assertEqual(first.total, 1)
            item = first.items[0]
            self.assertEqual(item.graph_id, "demo")
            service.update_assistant(
                actor=actor,
                assistant_id=item.id,
                command=UpdateAssistantCommand(
                    name="Custom", context={"temperature": 0.3}
                ),
            )
            self.assertEqual(read().items[0].id, item.id)
            self.assertEqual(read().items[0].context, {"temperature": 0.3})
            with session_scope(factory) as session:
                session.add(
                    ProjectGraphPolicyRecord(
                        project_id=project_id,
                        graph_catalog_id=graph_id,
                        is_enabled=False,
                    )
                )
            self.assertEqual(read().total, 0)
            self.assertEqual(
                service.get_assistant(actor=actor, assistant_id=item.id).name, "Custom"
            )
            with session_scope(factory) as session:
                policy = session.scalar(select(ProjectGraphPolicyRecord))
                policy.is_enabled = True
            self.assertEqual(read().items[0].id, item.id)
            with self.assertRaises(ForbiddenError):
                service.list_assistants(
                    actor=ActorContext(user_id=str(uuid4())),
                    project_id=str(project_id),
                    query=ListAssistantsQuery(),
                )
            with session_scope(factory) as session:
                self.assertEqual(len(session.scalars(select(AgentRecord)).all()), 1)
                self.assertEqual(session.get(AgentRecord, UUID(item.id)).name, "Custom")
