"""Real Platform HTTP -> Runtime interceptor -> official MCP HTTP Adapter.

The provider is a protocol fixture; no RAG parsing, indexing, or model cost is claimed.
"""

import asyncio
import hashlib
import hmac
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

if __name__ != "__main__" or sys.argv[1] != "platform":
    from runtime_service.runtime import RuntimePrincipal
    from runtime_service.runtime.resource_bindings import thread_resource_metadata
    from runtime_service.tools.knowledge_jobs import JOB_TOOL, SUBMIT_TOOL
    from runtime_service.tools.knowledge_upload import canonical
    from runtime_service.tools.mcp import load_mcp_tools
    from runtime_service.workspace.attachment_receipts import AttachmentReceipts
    from runtime_service.workspace.documents import DocumentWorkspace
    from runtime_service.workspace.scoped import resolve_thread_workspace

SECRET = "synthetic-http-knowledge-secret-" * 2
TOKEN = "synthetic-http-provider-token-" * 2


def start_process(mode, data, sockets):
    path = Path(__file__).resolve()
    python = (
        path.parents[3] / "platform-api/.venv/bin/python"
        if mode == "platform"
        else Path(sys.executable)
    )
    env = {**os.environ, "KNOWLEDGE_HTTP_FIXTURE": json.dumps(data)}
    process = subprocess.Popen(
        [str(python), str(path), mode],
        env=env,
        pass_fds=tuple(s.fileno() for s in sockets),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for sock in sockets:
        sock.close()
    return process


def test_real_http_grants_upload_receipt_reads_revocation_and_rollback(
    monkeypatch, tmp_path
):
    from services.dearflow_agent.test_agent import config

    sockets = []
    for _ in range(2):
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        sockets.append(sock)
    ports = [sock.getsockname()[1] for sock in sockets]
    project, thread, run, user = [str(uuid4()) for _ in range(4)]
    data = dict(
        project=project,
        thread=thread,
        run=run,
        user=user,
        db=str(tmp_path / "platform.db"),
        platform_port=ports[0],
        provider_port=ports[1],
        platform_fd=sockets[0].fileno(),
        provider_fd=sockets[1].fileno(),
    )
    processes = []
    try:
        processes.append(start_process("platform", data, sockets[:1]))
        processes.append(start_process("provider", data, sockets[1:]))
        deadline = time.monotonic() + 45
        with httpx.Client(trust_env=False, timeout=1) as client:
            for url in (
                f"http://127.0.0.1:{ports[0]}/_system/health",
                f"http://127.0.0.1:{ports[1]}/fixture/health",
            ):
                while time.monotonic() < deadline:
                    assert all(p.poll() is None for p in processes), (
                        "fixture process exited"
                    )
                    try:
                        if client.get(url).status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.1)
                else:
                    pytest.fail("knowledge fixture startup timed out")
        monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
        monkeypatch.setenv("RUNTIME_KNOWLEDGE_UPLOAD_ENABLED", "1")
        monkeypatch.setenv("RUNTIME_KNOWLEDGE_KEY_ID", "knowledge-v1")
        monkeypatch.setenv("RUNTIME_KNOWLEDGE_SECRET", SECRET)
        monkeypatch.setenv(
            "PLATFORM_RUNTIME_DELEGATION_SECRET",
            "synthetic-http-delegation-secret-" * 2,
        )
        base = f"http://127.0.0.1:{ports[0]}"
        provider = f"http://127.0.0.1:{ports[1]}"
        monkeypatch.setenv(
            "PLATFORM_KNOWLEDGE_AUTHORIZATION_URL",
            base + "/api/runtime/internal/knowledge/authorize",
        )
        monkeypatch.setenv(
            "PLATFORM_THREAD_AUTHORIZATION_URL",
            base + "/api/runtime/internal/thread-authorization",
        )
        monkeypatch.setenv(
            "RUNTIME_MCP_CONNECTIONS_JSON",
            json.dumps(
                {
                    "fixture": {
                        "scope": {"tenant_id": "__default", "project_id": project},
                        "transport": "streamable_http",
                        "url": provider + "/mcp",
                        "headers": {"Authorization": "Bearer " + TOKEN},
                        "allowed_tools": [SUBMIT_TOOL, JOB_TOOL],
                    }
                }
            ),
        )
        cfg = config()
        cfg["configurable"]["thread_id"] = thread
        cfg["metadata"]["run_id"] = run
        identity = cfg["configurable"]["langgraph_auth_user"]
        identity["runtime_principal"].update(
            user_id=user, tenant_id="__default", project_id=project
        )
        identity["runtime_scope"].update(
            tenant_id="__default", project_id=project, thread_id=thread
        )
        principal = RuntimePrincipal(user, "__default", project, "developer", ())
        cfg["metadata"]["__graphharbor_thread_metadata"] = thread_resource_metadata(
            kind="mcp",
            provider="mcp_http",
            resource_id="fixture",
            principal=principal,
            thread_id=thread,
        )
        runtime = SimpleNamespace(
            config=cfg,
            context={},
            state={},
            tool_call_id="http-call",
            server_info=SimpleNamespace(user=identity),
            execution_info=SimpleNamespace(thread_id=thread, run_id=run),
        )
        raw = "平台知识上传HTTP完整契约验证。".encode()
        root = resolve_thread_workspace("__default", project, thread, "dearflow_agent")
        ref = DocumentWorkspace(root).put(
            raw, hashlib.sha256(raw).hexdigest(), "text/markdown", "知识契约.md"
        )
        AttachmentReceipts(root).record(ref)

        async def verify():
            tools = {
                t.name: t
                for t in await load_mcp_tools(
                    cfg, principal, (SUBMIT_TOOL, JOB_TOOL), ()
                )
            }
            started = time.monotonic()
            content, artifact = await tools[SUBMIT_TOOL].coroutine(
                runtime=runtime, file_ref=ref
            )
            receipt = artifact["structured_content"]
            assert receipt["status"] == "queued" and receipt["reused"] is False
            assert time.monotonic() - started < 10
            encoded = json.dumps([content, artifact])
            assert (
                SECRET not in encoded
                and TOKEN not in encoded
                and "PRIVATE" not in encoded
            )
            # Same tool invocation/recovery key, same durable task.
            _, repeated = await tools[SUBMIT_TOOL].coroutine(
                runtime=runtime, file_ref=ref
            )
            assert repeated["structured_content"]["job_id"] == receipt["job_id"]
            assert repeated["structured_content"]["reused"] is True
            _, status = await tools[JOB_TOOL].coroutine(
                runtime=runtime, job_id=receipt["job_id"]
            )
            assert "reused" not in status["structured_content"]
            async with httpx.AsyncClient(trust_env=False) as client:
                access = (await client.get(base + "/fixture/token")).json()[
                    "access_token"
                ]
                member_headers = {"Authorization": "Bearer " + access}
                response = await client.get(
                    base + f"/api/projects/{project}/knowledge/jobs",
                    headers=member_headers,
                )
                assert (
                    response.status_code == 200
                    and response.json()["items"][0]["job_id"] == receipt["job_id"]
                )
                assert "PRIVATE" not in response.text
                capability = await client.get(
                    base + f"/api/projects/{project}/knowledge/capabilities",
                    headers=member_headers,
                )
                assert (
                    capability.status_code == 200
                    and capability.json()["upload_enabled"] is True
                )
                await client.post(provider + "/fixture/publish")
                ready = await client.get(
                    base
                    + f"/api/projects/{project}/knowledge/jobs/{receipt['job_id']}",
                    headers=member_headers,
                )
                assert (
                    ready.status_code == 200
                    and ready.json()["status"] == "ready"
                    and ready.json()["searchable"] is True
                )
                documents = await client.get(
                    base + f"/api/projects/{project}/knowledge/documents",
                    headers=member_headers,
                )
                assert (
                    documents.status_code == 200
                    and documents.json()["items"][0]["document_id"]
                    == receipt["document_id"]
                )
                samples = {
                    "queued": {"content": content, "artifact": artifact},
                    "reused": repeated,
                    "job": status,
                    "capabilities": capability.json(),
                    "jobs": response.json(),
                    "ready": ready.json(),
                    "documents": documents.json(),
                }
                destination = os.environ.get("KNOWLEDGE_UPLOAD_FIXTURES")
                if destination:
                    directory = Path(destination)
                    directory.mkdir(parents=True, exist_ok=True)
                    for scenario, payload in samples.items():
                        encoded = json.dumps(
                            {
                                "origin": "controlled-http-provider-through-real-platform-and-official-adapter",
                                "scenario": scenario,
                                "payload": payload,
                            },
                            ensure_ascii=False,
                            indent=2,
                        )
                        assert (
                            SECRET not in encoded
                            and TOKEN not in encoded
                            and "PRIVATE" not in encoded
                        )
                        (directory / (scenario + ".json")).write_text(encoded)
                await client.post(base + "/fixture/revoke")
            runtime.tool_call_id = "after-revocation"
            with pytest.raises(Exception) as caught:
                await tools[SUBMIT_TOOL].coroutine(runtime=runtime, file_ref=ref)
            assert SECRET not in str(caught.value)
            # Roll back only the new write capability; read tool remains declared.
            monkeypatch.setenv("RUNTIME_KNOWLEDGE_UPLOAD_ENABLED", "0")
            remaining = await load_mcp_tools(
                cfg, principal, (SUBMIT_TOOL, JOB_TOOL), ()
            )
            assert [t.name for t in remaining] == [JOB_TOOL]

        asyncio.run(verify())
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=15)
        for sock in sockets:
            sock.close()


if __name__ == "__main__":
    import uvicorn
    from starlette.responses import JSONResponse

    data = json.loads(os.environ["KNOWLEDGE_HTTP_FIXTURE"])
    if sys.argv[1] == "platform":
        api = Path(__file__).resolve().parents[3] / "platform-api/src"
        sys.path.insert(0, str(api))
        from uuid import UUID

        from platform_api.config import KnowledgeConnection
        from platform_api.core.db import (
            build_engine,
            build_session_factory,
            create_core_tables,
        )
        from platform_api.core.security import create_access_token
        from platform_api.main import create_app
        from platform_api.modules.identity.models import UserRecord
        from platform_api.modules.projects.models import (
            ProjectMemberRecord,
            ProjectRecord,
            TenantRecord,
        )
        from platform_api.modules.runtime_gateway.infra.sqlalchemy.models import (
            RunRequestRecord,
            ThreadAccessRecord,
        )
        from sqlalchemy import select

        engine = build_engine("sqlite:///" + data["db"])
        create_core_tables(engine)
        factory = build_session_factory(engine)
        with factory.begin() as session:
            tenant = TenantRecord(name="fixture", slug="fixture")
            user = UserRecord(
                id=UUID(data["user"]),
                username="executor-fixture",
                external_subject="executor-fixture",
            )
            session.add_all([tenant, user])
            session.flush()
            session.add(
                ProjectRecord(
                    id=UUID(data["project"]), tenant_id=tenant.id, name="fixture"
                )
            )
            session.add(
                ProjectMemberRecord(
                    project_id=UUID(data["project"]), user_id=user.id, role="executor"
                )
            )
            session.add(
                ThreadAccessRecord(
                    thread_id=data["thread"],
                    project_id=data["project"],
                    owner_user_id=data["user"],
                )
            )
            session.add(
                RunRequestRecord(
                    project_id=data["project"],
                    thread_id=data["thread"],
                    run_id=data["run"],
                    agent_key="dearflow_agent",
                    requested_by=data["user"],
                    idempotency_key="fixture",
                    request_digest="0" * 64,
                    context_hash="fixture",
                    context_snapshot={},
                )
            )
        app = create_app()
        settings = app.state.settings
        settings.database_url = str(engine.url)
        settings.platform_db_enabled = True
        settings.platform_db_auto_create = False
        settings.bootstrap_admin_enabled = False
        settings.auth_required = False
        settings.runtime_delegation_secret = "synthetic-http-delegation-secret-" * 2
        settings.knowledge_upload_enabled = True
        settings.knowledge_secret = SECRET
        settings.knowledge_mcp_bindings = {"__default:" + data["project"]: "fixture"}
        settings.knowledge_connections = {
            "fixture": KnowledgeConnection(
                base_url=f"http://127.0.0.1:{data['provider_port']}",
                token=TOKEN,
                scope={"tenant_id": "__default", "project_id": data["project"]},
                knowledge_base_id="kb_" + "3" * 32,
            )
        }

        @app.get("/fixture/token")
        def token():
            return {
                "access_token": create_access_token(
                    user_id=data["user"], username="executor-fixture", settings=settings
                )
            }

        @app.post("/fixture/revoke")
        def revoke():
            with factory.begin() as session:
                member = session.scalar(select(ProjectMemberRecord))
                session.delete(member)
            return {"ok": True}

        uvicorn.run(app, fd=data["platform_fd"], log_level="error")
    else:
        from mcp.server.fastmcp import Context, FastMCP
        from mcp.types import CallToolResult, TextContent, ToolAnnotations

        server = FastMCP("knowledge-upload-fixture", stateless_http=True)
        staged, jobs = {}, {}

        @server.custom_route("/fixture/health", methods=["GET"])
        async def health(request):
            return JSONResponse({"ok": True})

        @server.custom_route(
            "/internal/knowledge/uploads/{request_id}", methods=["PUT"]
        )
        async def stage(request):
            assert request.headers["authorization"] == "Bearer " + TOKEN
            ref = json.loads(request.headers["x-knowledge-file-ref"])
            grant = json.loads(request.headers["x-knowledge-operation-grant"])
            assert (
                grant["signature"]
                == hmac.new(
                    SECRET.encode(),
                    (
                        "knowledge-operation-grant\n" + canonical(grant["values"])
                    ).encode(),
                    hashlib.sha256,
                ).hexdigest()
            )
            raw = await request.body()
            assert (
                hashlib.sha256(raw).hexdigest() == ref["sha256"]
                and len(raw) == ref["size_bytes"]
            )
            key = grant["values"]["request_id"]
            assert key == request.path_params["request_id"]
            upload_id = "ku_" + hashlib.sha256(key.encode()).hexdigest()[:32]
            staged[upload_id] = (key, ref)
            return JSONResponse({"upload_id": upload_id})

        @server.custom_route("/internal/knowledge/jobs", methods=["GET"])
        async def list_jobs(request):
            return JSONResponse(
                {"items": list(jobs.values()), "total": len(jobs), "private": "PRIVATE"}
            )

        @server.custom_route("/internal/knowledge/capabilities", methods=["GET"])
        async def capability(request):
            return JSONResponse(
                dict(
                    version=1,
                    read=True,
                    upload_enabled=True,
                    supported_mime_types=["text/markdown"],
                    max_file_bytes=20 * 1024**2,
                    disabled_reason=None,
                )
            )

        @server.custom_route("/internal/knowledge/jobs/{job_id}", methods=["GET"])
        async def job(request):
            return JSONResponse(jobs[request.path_params["job_id"]])

        @server.custom_route("/fixture/publish", methods=["POST"])
        async def publish(request):
            for job in jobs.values():
                job.update(
                    status="ready", searchable=True, updated_at="2026-10-12T00:01:00Z"
                )
            return JSONResponse({"ok": True})

        @server.custom_route("/internal/knowledge/documents", methods=["GET"])
        async def documents(request):
            items = [
                dict(
                    document_id=job["document_id"],
                    file_name=job["file_name"],
                    mime_type="text/markdown",
                    size_bytes=len("平台知识上传HTTP完整契约验证。".encode()),
                    status="ready",
                    searchable=True,
                    published_at=job["updated_at"],
                )
                for job in jobs.values()
                if job["searchable"]
            ]
            return JSONResponse({"items": items, "total": len(items)})

        @server.tool(
            annotations=ToolAnnotations(
                readOnlyHint=False,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=False,
            )
        )
        async def mcp_submit_project_knowledge_document(
            file_ref: dict, ctx: Context
        ) -> CallToolResult:
            headers = ctx.request_context.request.headers
            key, ref = staged[headers["x-knowledge-upload-id"]]
            assert file_ref == ref
            grant = json.loads(headers["x-knowledge-operation-grant"])
            assert grant["values"]["request_id"] == key
            job_id = "kj_" + hashlib.sha256(key.encode()).hexdigest()[:32]
            reused = job_id in jobs
            payload = dict(
                version=1,
                job_id=job_id,
                document_id="kd_" + "2" * 32,
                file_name=ref["file_name"],
                status="queued",
                searchable=False,
                error_code=None,
                created_at="2026-10-12T00:00:00Z",
                updated_at="2026-10-12T00:00:00Z",
                raw_data="PRIVATE",
                reused=reused,
            )
            jobs[job_id] = payload
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(payload))],
                structuredContent=payload,
            )

        @server.tool(annotations=ToolAnnotations(readOnlyHint=True))
        async def mcp_get_project_knowledge_ingest_job(job_id: str) -> CallToolResult:
            payload = jobs[job_id]
            return CallToolResult(
                content=[TextContent(type="text", text=json.dumps(payload))],
                structuredContent=payload,
            )

        uvicorn.run(
            server.streamable_http_app(), fd=data["provider_fd"], log_level="error"
        )
