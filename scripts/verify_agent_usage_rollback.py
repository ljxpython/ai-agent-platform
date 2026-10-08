"""Run the pre-change apps against retained, migrated isolated usage databases.

Export HEAD with git archive first. Put its service src directories before this
repository in PYTHONPATH. No migrations or schema downgrades are executed here.
"""

import asyncio
import json
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import httpx
import psycopg
from cryptography.fernet import Fernet
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from langgraph_runtime_pg.production_worker import ProductionWorker
from langhost.server import create_app as runtime_app

from scripts.verify_agent_observability import interrupt_id, serve

SECRET = "usage-rollback-isolated-secret-at-least-32-bytes"


async def main():
    from platform_api.core.db import session_scope
    from platform_api.core.security import create_access_token
    from platform_api.main import create_app
    from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
    from platform_api.modules.iam.domain import ProjectRole
    from platform_api.modules.identity.repository import SqlAlchemyIdentityRepository
    from platform_api.modules.projects.repository import SqlAlchemyProjectsRepository
    from platform_api.modules.runtime_catalog.application.credentials import (
        encrypt_api_key,
    )
    from platform_api.modules.runtime_catalog.infra.sqlalchemy.models import (
        RuntimeCatalogModelRecord,
    )
    from runtime_service import webapp
    from runtime_service.observability import langfuse

    baseline = Path(os.environ["USAGE_BASELINE_ROOT"])
    assert Path(langfuse.__file__).is_relative_to(baseline)
    source = Path(os.environ["USAGE_EVIDENCE_PATH"])
    evidence = json.loads(source.read_text())
    admin = os.environ["USAGE_POSTGRES_ADMIN_DSN"].rsplit("/", 1)[0]
    runtime_dsn, platform_dsn = [admin + "/" + db for db in evidence["databases"]]
    with psycopg.connect(runtime_dsn) as conn:
        before = conn.execute("SELECT count(*) FROM runtime_usage_calls").fetchone()[0]
    os.environ.update(
        DATABASE_URI=runtime_dsn.replace("postgresql://", "postgresql+asyncpg://"),
        REDIS_URI=os.environ["USAGE_REDIS_URI"],
        GRAPHHARBOR_REDIS_PREFIX="graphharbor:usage:rollback:" + uuid4().hex,
        GRAPHHARBOR_ENV="production",
        RUNTIME_USAGE_ENABLED="false",
        LANGFUSE_ENABLED="false",
        OTEL_ENABLED="false",
        PLATFORM_RUNTIME_DELEGATION_SECRET=SECRET,
        PLATFORM_RUNTIME_DELEGATION_ISSUER="platform-api",
        PLATFORM_RUNTIME_DELEGATION_AUDIENCE="runtime-service",
        GRAPHHARBOR_RUNTIME_CONTEXT_SECRET=SECRET,
        GRAPHHARBOR_RUNTIME_CONTEXT_ISSUER="graphharbor",
        GRAPHHARBOR_RUNTIME_CONTEXT_AUDIENCE="graphharbor-worker",
    )
    provider = FastAPI()

    @provider.post("/v1/chat/completions")
    async def completion(request: Request):
        if (await request.json()).get("stream"):

            async def chunks():
                for part in (
                    {
                        "choices": [
                            {
                                "index": 0,
                                "delta": {
                                    "role": "assistant",
                                    "content": "rollback-ok",
                                },
                                "finish_reason": None,
                            }
                        ]
                    },
                    {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
                    {
                        "choices": [],
                        "usage": {
                            "prompt_tokens": 10,
                            "completion_tokens": 5,
                            "total_tokens": 15,
                        },
                    },
                ):
                    yield (
                        "data: "
                        + json.dumps(
                            {
                                "id": "rollback",
                                "object": "chat.completion.chunk",
                                "created": 1,
                                "model": "rollback-probe",
                                **part,
                            }
                        )
                        + "\n\n"
                    )
                yield "data: [DONE]\n\n"

            return StreamingResponse(chunks(), media_type="text/event-stream")
        return {
            "id": "rollback",
            "object": "chat.completion",
            "created": 1,
            "model": "rollback-probe",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "rollback-ok"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }

    async with serve(provider) as provider_url:
        native = runtime_app(
            {
                "graphs": {
                    name: str(
                        baseline
                        / "apps/runtime-service/src/runtime_service/services"
                        / relative
                    )
                    + ":get_agent"
                    for name, relative in {
                        "reference_agent": "reference_agent/agent.py",
                        "workflow_demo": "demo/workflow_demo/agent.py",
                    }.items()
                },
                "auth": {
                    "path": str(
                        baseline
                        / "apps/runtime-service/src/runtime_service/auth/platform.py"
                    )
                    + ":auth"
                },
                "http": {"disable_mcp": True},
            },
            base_dir=baseline,
            custom_app=webapp.app,
        )
        async with serve(native) as runtime_url:
            platform = create_app()
            settings = platform.state.settings
            settings.platform_db_enabled = True
            settings.platform_db_auto_create = False
            settings.bootstrap_admin_enabled = False
            settings.auth_required = True
            settings.database_url = platform_dsn.replace(
                "postgresql://", "postgresql+psycopg://"
            )
            settings.model_config_master_key = Fernet.generate_key().decode()
            settings.runtime_delegation_secret = (
                settings.runtime_model_config_secret
            ) = SECRET
            settings.langgraph_upstream_url = runtime_url
            async with serve(platform, separate_loop=True) as platform_url:
                os.environ.update(
                    PLATFORM_THREAD_AUTHORIZATION_URL=platform_url
                    + "/api/runtime/internal/thread-authorization",
                    PLATFORM_RUNTIME_MODEL_CONFIG_URL=platform_url
                    + "/api/runtime/internal/model-config",
                    PLATFORM_RUNTIME_MESSAGE_AUTH_URL=platform_url
                    + "/api/runtime/internal/message-authorization",
                    RUNTIME_SELF_URL=runtime_url,
                )
                model_id = uuid4()
                with session_scope(platform.state.db_session_factory) as session:
                    projects = SqlAlchemyProjectsRepository(session)
                    tenant = projects.get_or_create_default_tenant()
                    project = projects.create_project(
                        tenant_id=tenant.id, name="Usage rollback", description=""
                    )
                    user = SqlAlchemyIdentityRepository(session).create_user(
                        username="rollback-" + uuid4().hex,
                        external_subject=uuid4().hex,
                        password_hash="unused",
                        email=None,
                        is_super_admin=False,
                        platform_roles=(),
                        must_change_password=False,
                    )
                    projects.upsert_project_member(
                        project_id=project.id,
                        user_id=user.id,
                        role=ProjectRole.EXECUTOR,
                    )
                    session.add_all(
                        [
                            AgentRecord(
                                project_id=project.id,
                                name=name,
                                graph_id=name,
                                created_by=user.id,
                                updated_by=user.id,
                            )
                            for name in ("reference_agent", "workflow_demo")
                        ]
                    )
                    session.add(
                        RuntimeCatalogModelRecord(
                            id=model_id,
                            display_name="Rollback probe",
                            provider="openai",
                            protocol="openai",
                            model_name="rollback-probe",
                            base_url=provider_url + "/v1",
                            api_key_ciphertext=encrypt_api_key(
                                "isolated-key",
                                master_key=settings.model_config_master_key,
                            ),
                            enabled=True,
                        )
                    )
                    project_id, user_id = str(project.id), str(user.id)
                headers = {
                    "x-project-id": project_id,
                    "authorization": "Bearer "
                    + create_access_token(
                        user_id=user_id, username="rollback", settings=settings
                    ),
                }
                worker = ProductionWorker(
                    native.state.graph_registry, owner="usage-rollback"
                )
                async with httpx.AsyncClient(
                    base_url=platform_url, headers=headers, timeout=30, trust_env=False
                ) as client:

                    async def request(method, path, **kwargs):
                        response = await client.request(
                            method, "/api/langgraph" + path, **kwargs
                        )
                        assert response.status_code == 200, (
                            path,
                            response.status_code,
                            response.text[:200],
                        )
                        return response.json()

                    for graph in ("reference_agent", "workflow_demo"):
                        thread = (
                            await request("POST", "/threads", json={"graph_id": graph})
                        )["thread_id"]
                        run = (
                            await request(
                                "POST",
                                f"/threads/{thread}/runs",
                                json={
                                    "assistant_id": graph,
                                    "context": {"model_id": str(model_id)},
                                    "input": {
                                        "messages": [
                                            {"role": "user", "content": "rollback"}
                                        ],
                                        **(
                                            {"requires_confirmation": True}
                                            if graph == "workflow_demo"
                                            else {}
                                        ),
                                    },
                                },
                            )
                        )["run_id"]
                        assert await worker.run_once()
                        if graph == "workflow_demo":
                            state = await request("GET", f"/threads/{thread}/state")
                            active = interrupt_id(state)
                            assert active
                            run = (
                                await request(
                                    "POST",
                                    f"/threads/{thread}/runs",
                                    json={
                                        "assistant_id": graph,
                                        "command": {
                                            "resume": {
                                                active: {
                                                    "decisions": [{"type": "approve"}]
                                                }
                                            }
                                        },
                                    },
                                )
                            )["run_id"]
                            assert await worker.run_once()
                        assert (await request("GET", f"/threads/{thread}/runs/{run}"))[
                            "status"
                        ] == "success"
                        stream = await client.get(
                            f"/api/langgraph/threads/{thread}/runs/{run}/stream",
                            params={"last_event_id": "0"},
                        )
                        assert (
                            stream.status_code == 200
                            and "text/event-stream" in stream.headers["content-type"]
                        )
                        assert "rollback-ok" in stream.text
                        assert (
                            await client.get(
                                f"/api/langgraph/threads/{thread}/runs/{run}/usage"
                            )
                        ).status_code == 404
    with psycopg.connect(runtime_dsn) as conn:
        after = conn.execute("SELECT count(*) FROM runtime_usage_calls").fetchone()[0]
        assert before == after
    result = {
        "complete": True,
        "baseline_revision": (
            await asyncio.to_thread(
                subprocess.check_output,
                ["rtk", "proxy", "git", "rev-parse", "HEAD"],
                text=True,
            )
        ).strip(),
        "cases": {
            "migrated_db_old_apps_start": "passed",
            "normal_chat_sse": "passed",
            "hitl_resume_sse": "passed",
            "usage_routes_removed": "passed",
            "ledger_retained": "passed",
        },
        "ledger_calls_before": before,
        "ledger_calls_after": after,
        "databases": evidence["databases"],
        "migration_or_downgrade_executed": False,
    }
    source.with_name("rollback-evidence.json").write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
