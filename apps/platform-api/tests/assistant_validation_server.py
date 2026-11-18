"""Loopback-only synthetic API fixture for the opt-in assistant live test.

Own SQLite database and documents; the configured local model catalog is read-only.
The parent receives credentials over a private pipe, never a log or fixture file.
"""

import json
import os
import secrets
import shutil
import socket
import sys
from pathlib import Path
from uuid import UUID, uuid4

import uvicorn
from fastapi import FastAPI, Request
from sqlalchemy import select, text

from platform_api.config import Settings
from platform_api.core.context.models import (
    ActorContext,
    PlatformRequestContext,
    ProjectContext,
    RequestContext,
    TenantContext,
)
from platform_api.core.db import build_engine, build_session_factory, create_core_tables
from platform_api.core.errors import ForbiddenError, register_exception_handlers
from platform_api.modules.identity.models import UserRecord
from platform_api.modules.platform_assistant import router as routes
from platform_api.modules.platform_assistant.evidence import require_history_access
from platform_api.modules.platform_assistant.service import require_target_project
from platform_api.modules.projects.models import ProjectMemberRecord
from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
from platform_api.modules.runtime_catalog.application.credentials import decrypt_api_key
from platform_api.modules.runtime_catalog.infra.sqlalchemy.models import (
    RuntimeCatalogModelRecord,
)
from platform_api.modules.runtime_gateway.application import thread_access


def main():
    output = Path(sys.argv[1]).resolve()
    repo = Path(__file__).resolve().parents[3]
    if os.getenv("ASSISTANT_VALIDATION_NO_MODEL") == "1":
        model = {}
    elif os.getenv("ASSISTANT_VALIDATION_API_KEY"):
        model = {
            "model": os.environ["ASSISTANT_VALIDATION_MODEL"],
            "base_url": os.environ["ASSISTANT_VALIDATION_BASE_URL"],
            "api_key": os.environ["ASSISTANT_VALIDATION_API_KEY"],
        }
    else:
        settings = Settings(_env_file=repo / "apps/platform-api/.env")
        source_engine = build_engine(settings.database_url)
        with source_engine.connect() as connection:
            connection.execute(text("SET TRANSACTION READ ONLY"))
            selected = os.getenv("ASSISTANT_VALIDATION_MODEL_ID")
            row = (
                connection.execute(
                    select(RuntimeCatalogModelRecord)
                    .where(
                        RuntimeCatalogModelRecord.enabled.is_(True),
                        True
                        if selected
                        else RuntimeCatalogModelRecord.model_name
                        == "deepseek-v4.1-flash",
                        RuntimeCatalogModelRecord.id == UUID(selected)
                        if selected
                        else RuntimeCatalogModelRecord.provider == "maomaoai",
                    )
                    .limit(1)
                )
                .mappings()
                .one()
            )
            model = {
                "model": row["model_name"],
                "base_url": row["base_url"],
                "api_key": decrypt_api_key(
                    row["api_key_ciphertext"],
                    master_key=settings.model_config_master_key,
                ),
            }
        source_engine.dispose()
    docs = output / "guides"
    shutil.copytree(repo / "docs/assistant", docs)
    secret = secrets.token_hex(32)
    settings = Settings(
        _env_file=None,
        platform_assistant_enabled=True,
        runtime_delegation_secret=secret,
        assistant_document_root=str(docs),
    )
    engine = build_engine(f"sqlite:///{output / 'assistant.db'}")
    create_core_tables(engine)
    factory = build_session_factory(engine)
    user_id, assistant_thread, target_thread = (str(uuid4()) for _ in range(3))
    with factory.begin() as session:
        repository = SqlAlchemyProjectsRepository(session)
        tenant = repository.get_or_create_default_tenant()
        assistant_project = str(
            repository.create_project(
                tenant_id=tenant.id,
                name="Assistant validation",
                description="synthetic",
            ).id
        )
        target_project = str(
            repository.create_project(
                tenant_id=tenant.id, name="Target validation", description="synthetic"
            ).id
        )
        session.add(
            UserRecord(
                id=UUID(user_id),
                username="synthetic-validation",
                external_subject="test",
            )
        )
        for project in (assistant_project, target_project):
            session.add(
                ProjectMemberRecord(
                    project_id=UUID(project),
                    user_id=UUID(user_id),
                    role="project_admin",
                )
            )
    actor = ActorContext(
        user_id=user_id, project_roles={assistant_project: ("project_admin",)}
    )
    for thread, project in (
        (assistant_thread, assistant_project),
        (target_thread, target_project),
    ):
        thread_access.register(
            factory, thread_id=thread, project_id=project, actor=actor
        )
    run_statuses = {
        "rate_limit": "error",
        "recovered": "success",
        "unavailable": "error",
        "timeout": "error",
        "execution": "error",
        "interrupted": "interrupted",
        "running": "running",
        "pre_agent": "error",
        "request_fallback": "error",
    }
    cases = {name: str(uuid4()) for name in run_statuses}
    pre_agent_checkpoint = str(uuid4())
    trace = "11112222333344445555666677778888"
    log = output / "runtime.log"
    log.write_text(
        "\n".join(
            json.dumps(
                {
                    "ts": "2026-10-01T08:02:00+00:00",
                    "project_id": target_project,
                    "thread_id": target_thread,
                    "run_id": run,
                    "trace_id": trace if name != "request_fallback" else "",
                    "request_id": "b" * 32,
                    "event": "graph.failed" if name == "execution" else "model.failed",
                    "error_code": "graph_execution_failed"
                    if name == "execution"
                    else "provider_timeout"
                    if name == "timeout"
                    else "provider_rate_limited",
                    "password": "SYNTHETIC-DO-NOT-RETURN",
                }
            )
            for name, run in cases.items()
            if name not in {"unavailable", "interrupted", "running", "pre_agent"}
        )
    )
    settings.assistant_log_files = {"runtime-service": str(log)}

    class Gateway:
        def _assert_runtime_target_allowed(self, **kwargs):
            return None  # Fixture has one fixed graph; production catalog tests remain separate.

        async def get_thread(self, *, actor, project_id, thread_id):
            access = thread_access.get(factory, thread_id)
            if not thread_access.allowed(actor, project_id, access, "read"):
                raise ForbiddenError(code="thread_action_denied", message="denied")
            require_history_access(
                factory, settings, actor, project_id, thread_id, access
            )
            return {"metadata": {**access, "graph_id": "platform_assistant"}}

        async def get_thread_run(self, *, actor, project_id, thread_id, run_id):
            if thread_id == target_thread:
                require_target_project(factory, actor, thread_id)
                if run_id not in cases.values():
                    raise ForbiddenError(code="run_not_found", message="missing")
            return {
                "thread_id": thread_id,
                "run_id": run_id,
                "status": "running"
                if thread_id == assistant_thread
                else run_statuses[
                    next(name for name, run in cases.items() if run == run_id)
                ],
                "created_at": "2026-10-01T08:00:00+00:00",
                "updated_at": "2026-10-01T08:03:00+00:00",
                "kwargs": {
                    "context": {
                        "model_id": "synthetic-model",
                        "access_policy": "review",
                        "api_key": "SYNTHETIC-DO-NOT-RETURN",
                    }
                },
            }

        async def get_thread_history(self, *, actor, project_id, thread_id, payload):
            run_id = payload["metadata"]["run_id"]
            await self.get_thread_run(
                actor=actor, project_id=project_id, thread_id=thread_id, run_id=run_id
            )
            if run_id != cases["pre_agent"]:
                return []
            return [
                {
                    "metadata": {"run_id": run_id, "graph_id": "dearflow_agent"},
                    "checkpoint": {"checkpoint_id": pre_agent_checkpoint},
                    "tasks": [
                        {
                            "name": "ExecutionSkillsMiddleware.before_agent",
                            "error": "runtime.execution_failed",
                            "interrupts": [],
                        }
                    ],
                    "interrupts": [],
                    "values": {
                        "messages": [
                            {"type": "human", "content": "SYNTHETIC-DO-NOT-RETURN"}
                        ]
                    },
                }
            ]

        async def get_thread_run_diagnostics(
            self, *, actor, project_id, thread_id, run_id, request_id
        ):
            await self.get_thread_run(
                actor=actor, project_id=project_id, thread_id=thread_id, run_id=run_id
            )
            case = next(name for name, value in cases.items() if value == run_id)
            unavailable = case in {"unavailable", "pre_agent"}
            code = "provider_timeout" if case == "timeout" else "provider_rate_limited"
            return {
                "thread_id": thread_id,
                "run_id": run_id,
                "run_status": run_statuses[case],
                "availability": "disabled" if unavailable else "available",
                "unavailable_reason": "not_configured" if unavailable else None,
                "correlation": {
                    "platform_trace_id": None
                    if unavailable or case == "request_fallback"
                    else trace,
                    "execution_request_id": "b" * 32
                    if case == "request_fallback"
                    else None,
                },
                "model_errors": []
                if unavailable
                or case in {"execution", "interrupted", "running", "request_fallback"}
                else [
                    {
                        "observation_id": "model-1",
                        "scope": "primary",
                        "namespace": [],
                        "code": code,
                        "provider_status": 429
                        if code == "provider_rate_limited"
                        else None,
                    }
                ],
                "graph_executions": [
                    {
                        "observation_id": "graph-1",
                        "outcome": "failed"
                        if run_statuses[case] == "error"
                        else run_statuses[case],
                    }
                ],
                "retries": [{"unit": "model", "attempts": 2, "outcome": "success"}]
                if case == "recovered"
                else [],
                "truncated": False,
            }

    app = FastAPI()
    app.state.settings, app.state.db_session_factory = settings, factory
    gateway = Gateway()
    routes.get_runtime_gateway_service = lambda *args: gateway
    register_exception_handlers(app)
    app.include_router(routes.router)

    @app.middleware("http")
    async def context(request, call_next):
        request.state.platform_context = PlatformRequestContext(
            RequestContext(str(uuid4()), "test", request.method, request.url.path, 0),
            TenantContext(),
            ProjectContext(),
            ActorContext(),
        )
        return await call_next(request)

    @app.get("/validation/health")
    async def health():
        return {"ok": True}

    @app.post("/validation/update-guide")
    async def update_guide(request: Request):
        if request.headers.get("x-validation-key") != secret:
            raise ForbiddenError(code="denied", message="denied")
        guide = docs / "chat.md"
        guide.write_text(guide.read_text().replace("新会话", "新对话验证"))
        return {"updated": True}

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    print(
        json.dumps(
            {
                "port": sock.getsockname()[1],
                "secret": secret,
                "model": model,
                "actor_id": user_id,
                "project_id": assistant_project,
                "thread_id": assistant_thread,
                "target_thread_id": target_thread,
                "cases": cases,
            }
        ),
        flush=True,
    )
    uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False)).run(
        sockets=[sock]
    )


if __name__ == "__main__":
    main()
