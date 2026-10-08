"""Disposable server roles and graph factory; never registered by production config."""

import asyncio
import json
import os
import sys
from pathlib import Path

if len(sys.argv) < 2 or sys.argv[1] != "platform":
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


async def graph(config):
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from pydantic import Field
    from support import BindableFakeMessagesChatModel

    from runtime_service.services.dearflow_agent import agent
    from runtime_service.services.dearflow_agent.tools import search

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
    return await agent.get_agent(config)


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
                        RuntimeCatalogModelRecord(
                            id=model,
                            display_name="fixture",
                            provider="openai",
                            base_url="https://unused.invalid",
                            protocol="openai",
                            model_name="fixture",
                            api_key_ciphertext=encrypt_api_key(
                                "synthetic", master_key=settings.model_config_master_key
                            ),
                            enabled=True,
                        )
                    )
                    session.flush()
                token = create_access_token(
                    user_id=str(user.id), username=user.username, settings=settings
                )
            Path(spec["ready"]).write_text(
                json.dumps({"token": token, "pid": os.getpid()})
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

        uvicorn.run(
            create_app(spec["config"], base_dir=Path(path).parent),
            host="127.0.0.1",
            port=spec["runtime_port"],
            log_level="error",
            access_log=False,
        )
    elif role == "worker":
        from langgraph_runtime_pg.production_worker import run_worker

        asyncio.run(run_worker(Path(path).parent / "langgraph.json"))
