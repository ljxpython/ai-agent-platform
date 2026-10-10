"""Disposable server roles and graph factory; never registered by production config."""

import asyncio
import json
import os
import sys
from pathlib import Path

if sys.argv[1:2] != ["platform"]:
    from runtime_service.auth.platform import auth  # noqa: F401 - fixture config symbol


def record(event, **fields):
    with Path(os.environ["TOOL_ERROR_TEST_FACTS"]).open("a") as stream:
        stream.write(json.dumps({"event": event, "pid": os.getpid(), **fields}) + "\n")


async def provider(*args):
    payload = args[1] if len(args) > 1 and isinstance(args[1], dict) else {}
    query = payload.get("query")
    record("provider", query=query)
    if query == "fatal":
        raise RuntimeError(
            "EXCEPTION_CANARY token=synthetic /private/fixture https://provider.invalid"
        )
    if query == "slow":
        await asyncio.sleep(60)
    return {"results": []}


async def graph(config, *, showcase=False):
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from pydantic import Field
    from support import BindableFakeMessagesChatModel

    from runtime_service.services.dearflow_agent import agent as dear_agent
    from runtime_service.services.dearflow_agent.tools import search
    from runtime_service.services.demo.showcase_demo import agent as showcase_agent

    agent = showcase_agent if showcase else dear_agent
    if os.getenv("WORKSPACE_TEST_PROBE_FAILURE_FILE"):
        from runtime_service.observability import diagnostics, langfuse
        from runtime_service.workspace import execution

        if not getattr(execution, "_workspace_fixture_installed", False):
            original_control = execution._docker_control

            async def control(*args, **kwargs):
                if (
                    args[0] == "info"
                    and Path(os.environ["WORKSPACE_TEST_PROBE_FAILURE_FILE"]).exists()
                ):
                    return False
                return await original_control(*args, **kwargs)

            execution._docker_control = control
            original_export = langfuse.record_diagnostic_event

            def export(event, fields):
                if event in {
                    "runtime.workspace.execution_completed",
                    "runtime.graph.completed",
                }:
                    record("diagnostic", name=event, **diagnostics.safe_fields(fields))
                original_export(event, fields)

            langfuse.record_diagnostic_event = export
            execution._workspace_fixture_installed = True

    class ScenarioModel(BindableFakeMessagesChatModel):
        seen: list = Field(default_factory=list)

        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            self.seen.append(messages)
            errors = [
                m
                for m in messages
                if isinstance(m, ToolMessage) and m.status == "error"
            ]
            record("model", errors=[m.tool_call_id for m in errors])
            prompt = next(
                m.content for m in reversed(messages) if isinstance(m, HumanMessage)
            )
            if isinstance(messages[-1], ToolMessage):
                response = AIMessage(content="recovered")
            elif prompt == "workspace-child":
                response = self.call(
                    "task",
                    {
                        "subagent_type": "general-purpose",
                        "description": "workspace-unknown",
                    },
                )
            elif prompt.startswith("workspace-") or "workspace-unknown" in prompt:
                command = "printf once >> counter.txt; exit 125"
                if prompt == "workspace-success":
                    command = "printf once >> counter.txt; exit 7"
                if prompt == "workspace-cancel":
                    command = "printf once >> counter.txt; sleep 30; touch leaked.txt"
                record("workspace_tool_request", prompt=prompt)
                response = self.call("execute", {"command": command})
            elif prompt == "child":
                response = self.call(
                    "task",
                    {"subagent_type": "general-purpose", "description": "child-search"},
                )
            elif "child-search" in prompt or prompt == "main":
                response = self.call("search_web", {"query": ""})
            elif prompt == "approval":
                response = self.call(
                    "write_file",
                    {"file_path": "/workspace/work/approved.txt", "content": "once"},
                )
            elif prompt == "clarification":
                response = self.call(
                    "request_information",
                    {
                        "question": "Title?",
                        "fields": [{"name": "title", "label": "Title", "type": "text"}],
                    },
                )
            else:
                response = self.call("search_web", {"query": prompt})
            self.responses = [response]
            self.i = 0
            return super()._generate(
                messages, stop=stop, run_manager=run_manager, **kwargs
            )

        @staticmethod
        def call(name, args):
            return AIMessage(
                content="",
                tool_calls=[{"name": name, "args": args, "id": "fixture-" + name}],
            )

    agent.build_model = lambda *args, **kwargs: ScenarioModel(
        responses=[AIMessage(content="initial")]
    )
    search.tavily = provider
    try:
        return await agent.get_agent(config)
    except Exception as exc:
        record("factory_error", error_type=type(exc).__name__, message=str(exc))
        raise


async def showcase_graph(config):
    return await graph(config, showcase=True)


def platform_app(spec):
    import base64
    import hashlib
    from contextlib import asynccontextmanager
    from uuid import UUID

    from platform_api.core.db import session_scope
    from platform_api.core.security import create_access_token, hash_password
    from platform_api.main import create_app
    from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
    from platform_api.modules.identity.repository import SqlAlchemyIdentityRepository
    from platform_api.modules.projects.models import (
        ProjectMemberRecord,
        ProjectRecord,
        TenantRecord,
    )
    from platform_api.modules.runtime_catalog.application.credentials import (
        encrypt_api_key,
    )
    from platform_api.modules.runtime_catalog.infra.sqlalchemy.models import (
        RuntimeCatalogModelRecord,
    )

    app = create_app()
    model_values = {
        "base_url": spec.get("provider_url", "https://unused.invalid"),
        "name": "fixture",
        "api_key": "synthetic",
    }
    if spec.get("real_model"):
        from dotenv import dotenv_values

        source = dotenv_values(
            os.getenv(
                "BACKGROUND_REAL_MODEL_ENV_FILE", str(Path.home() / ".my_best/.env")
            )
        )
        required = ("GPT_PROXY_URL", "GPT_PROXY_DEFAULT_MODEL", "GPT_PROXY_API_KEY")
        if any(not source.get(name) for name in required):
            raise ValueError("Missing managed real-model test configuration")
        model_values = dict(
            zip(
                ("base_url", "name", "api_key"),
                (source[name] for name in required),
                strict=True,
            )
        )
    settings = app.state.settings
    settings.platform_db_enabled = settings.platform_db_auto_create = True
    settings.database_url = "sqlite:///" + spec["database"]
    settings.bootstrap_admin_enabled = False
    settings.auth_required = True
    settings.runtime_delegation_secret = settings.runtime_model_config_secret = spec[
        "secret"
    ]
    settings.model_config_master_key = base64.urlsafe_b64encode(
        hashlib.sha256(spec["secret"].encode()).digest()
    ).decode()
    settings.langgraph_upstream_url = spec["runtime_url"]
    settings.langgraph_upstream_timeout_seconds = 180
    original = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with original(application):
            with session_scope(app.state.db_session_factory) as session:
                tenant, project, model = (
                    UUID(spec[k]) for k in ("tenant", "project", "model")
                )
                repo = SqlAlchemyIdentityRepository(session)
                from platform_api.modules.identity.models import UserRecord
                from sqlalchemy import select

                user = session.scalar(
                    select(UserRecord).where(UserRecord.username == "tool-error-test")
                )
                if user is None:
                    user = repo.create_user(
                        username="tool-error-test",
                        password_hash=hash_password("synthetic-test-password"),
                        external_subject="tool-error-test",
                        email=None,
                        is_super_admin=False,
                        platform_roles=(),
                        must_change_password=False,
                    )
                    session.add(TenantRecord(id=tenant, name="fixture", slug="fixture"))
                    session.flush()
                    session.add(
                        ProjectRecord(id=project, tenant_id=tenant, name="fixture")
                    )
                    session.flush()
                    session.add(
                        ProjectMemberRecord(
                            project_id=project, user_id=user.id, role="editor"
                        )
                    )
                    session.add(
                        AgentRecord(
                            project_id=project,
                            name="fixture",
                            graph_id="dearflow_agent",
                            created_by=user.id,
                            updated_by=user.id,
                        )
                    )
                    session.add(
                        AgentRecord(
                            project_id=project,
                            name="workspace-fixture",
                            graph_id="showcase_demo",
                            created_by=user.id,
                            updated_by=user.id,
                        )
                    )
                    session.add(
                        RuntimeCatalogModelRecord(
                            id=model,
                            display_name="fixture",
                            provider="openai",
                            base_url=model_values["base_url"],
                            protocol="openai",
                            model_name=model_values["name"],
                            api_key_ciphertext=encrypt_api_key(
                                model_values["api_key"],
                                master_key=settings.model_config_master_key,
                            ),
                            enabled=True,
                        )
                    )
                    session.flush()
                token = create_access_token(
                    user_id=str(user.id), username=user.username, settings=settings
                )
                peer = session.scalar(
                    select(UserRecord).where(UserRecord.username == "workspace-peer")
                )
                if peer is None:
                    peer = repo.create_user(
                        username="workspace-peer",
                        password_hash="unused",
                        external_subject="workspace-peer",
                        email=None,
                        is_super_admin=False,
                        platform_roles=(),
                        must_change_password=False,
                    )
                    session.add(
                        ProjectMemberRecord(
                            project_id=project, user_id=peer.id, role="executor"
                        )
                    )
                    other = UUID(spec["other_project"])
                    session.add(ProjectRecord(id=other, tenant_id=tenant, name="other"))
                    session.flush()
                    session.add(
                        ProjectMemberRecord(
                            project_id=other, user_id=user.id, role="editor"
                        )
                    )
                peer_token = create_access_token(
                    user_id=str(peer.id), username=peer.username, settings=settings
                )
            Path(spec["ready"]).write_text(
                json.dumps(
                    {
                        "token": token,
                        "peer_token": peer_token,
                        "peer_id": str(peer.id),
                        "pid": os.getpid(),
                    }
                )
            )
            yield

    app.router.lifespan_context = lifespan
    return app


if __name__ == "__main__":
    import uvicorn

    role, path = sys.argv[1:]
    spec = json.loads(Path(path).read_text())
    if role == "platform":
        uvicorn.run(
            platform_app(spec),
            host="127.0.0.1",
            port=spec["platform_port"],
            log_level="error",
            access_log=False,
        )
    elif role == "runtime":
        from langhost.server import create_app

        if os.getenv("WORKSPACE_TEST_QUERY_FROM_FACTS") == "1":
            import httpx
            from langfuse.api.client import AsyncLangfuseAPI

            from runtime_service.observability import query
            from runtime_service.observability.diagnostics import trace_id_for

            def observations(request):
                # Real callbacks, synthetic metadata-only Langfuse transport.
                rows = []
                for index, line in enumerate(
                    Path(os.environ["TOOL_ERROR_TEST_FACTS"]).read_text().splitlines()
                ):
                    fact = json.loads(line)
                    if fact["event"] != "diagnostic":
                        continue
                    trace = trace_id_for(fact)
                    if trace != request.url.params.get("traceId"):
                        continue
                    rows.append(
                        {
                            "id": f"fixture-{index}",
                            "traceId": trace,
                            "name": fact["name"],
                            "startTime": "2026-10-07T00:00:00Z",
                            "endTime": "2026-10-07T00:00:00Z",
                            "projectId": "fixture-observability",
                            "parentObservationId": None,
                            "type": "EVENT",
                            "metadata": {
                                **{
                                    k: v
                                    for k, v in fact.items()
                                    if k not in {"event", "pid", "name"}
                                },
                                "schema_version": 1,
                                "event": fact["name"],
                                "command": "DIAGNOSTIC_CANARY",
                            },
                        }
                    )
                return httpx.Response(200, json={"data": rows[:100], "meta": {}})

            query._client = AsyncLangfuseAPI(
                base_url="http://fixture-observability.invalid",
                username="synthetic",
                password="synthetic",
                httpx_client=httpx.AsyncClient(
                    transport=httpx.MockTransport(observations)
                ),
            )

        from runtime_service.webapp import app as custom_app

        uvicorn.run(
            create_app(
                spec["config"], base_dir=Path(path).parent, custom_app=custom_app
            ),
            host="127.0.0.1",
            port=spec["runtime_port"],
            log_level="error",
            access_log=False,
        )
    elif role == "worker":
        from importlib import import_module

        from langgraph_runtime_pg.production_worker import ProductionWorker, run_worker

        original_run_forever = ProductionWorker.run_forever

        async def ready_worker(worker):
            Path(spec["worker_ready"]).write_text(str(os.getpid()))
            await original_run_forever(worker)

        ProductionWorker.run_forever = ready_worker

        # Cold Agent imports must finish before the Worker starts its Run lease.
        for module in (
            "runtime_service.services.dearflow_agent.agent",
            "runtime_service.services.demo.showcase_demo.agent",
        ):
            import_module(module)
        asyncio.run(run_worker(Path(path).parent / "langgraph.json"))
