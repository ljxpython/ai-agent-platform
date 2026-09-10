"""Verify a real Showcase run across API/worker restart on dedicated test infra."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import signal
import sys
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values
ROOT = Path(__file__).resolve().parents[1] / "apps" / "runtime-service"
sys.path.insert(0, str(ROOT / "scripts"))
from r6_worker_fault_injection import _stop, _wait_for

from runtime_service.services.demo.showcase_demo.backend import DockerWorkspaceBackend


async def run(args: argparse.Namespace) -> dict:
    """Only start/stop processes owned by this probe; never reset databases."""
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ)
    for key in ("DEEPSEEK_PROXY_URL", "DEEPSEEK_PROXY_API_KEY"):
        value = dotenv_values(ROOT / ".env").get(key)
        if value:
            env[key] = value
    env.update(
        GRAPHHARBOR_ENV="development",
        LG_RUNTIME_PG_AUTO_MIGRATE="false",
        GRAPHHARBOR_REDIS_PREFIX=f"showcase-acceptance:{secrets.token_hex(8)}",
        PLATFORM_RUNTIME_DELEGATION_SECRET=secrets.token_hex(32),
        PLATFORM_RUNTIME_DELEGATION_ISSUER="showcase-acceptance",
        PLATFORM_RUNTIME_DELEGATION_AUDIENCE="runtime-service",
        GRAPHHARBOR_RUNTIME_CONTEXT_SECRET=secrets.token_hex(32),
        GRAPHHARBOR_RUNTIME_CONTEXT_ISSUER="showcase-acceptance",
        GRAPHHARBOR_RUNTIME_CONTEXT_AUDIENCE="graphharbor-worker",
        RUNTIME_SHOWCASE_WORKSPACE_ROOT=str(output / "workspaces"),
    )
    # Select explicit graph/auth paths and no dotenv override for the isolated instance.
    config = json.loads((ROOT / "langgraph.demo.json").read_text())
    config.pop("env", None)
    config["graphs"] = {"showcase_demo": config["graphs"]["showcase_demo"]}
    # GraphHarbor accepts files within the config directory; re-export installed symbols.
    (output / "entry.py").write_text(
        "from runtime_service.graphs.showcase_demo import get_agent\n"
        "from runtime_service.auth.platform import auth\n"
        "from runtime_service.webapp import app\n"
    )
    config["graphs"]["showcase_demo"]["path"] = "./entry.py:get_agent"
    config["auth"]["path"] = "./entry.py:auth"
    config["http"]["app"] = "./entry.py:app"
    config_file = output / "langgraph.json"
    config_file.write_text(json.dumps(config))
    empty_env = output / "empty.env"
    empty_env.touch()
    command = [sys.executable, "-m", "langhost.cli"]
    logs = []

    async def start(role: str, generation: int):
        log = (output / f"{role}-{generation}.log").open("wb")
        logs.append(log)
        options = [
            role,
            "--config",
            str(config_file),
            "--env-file",
            str(empty_env),
            "--n-jobs-per-worker",
            "0" if role == "serve" else "1",
        ]
        if role == "serve":
            options += ["--host", "127.0.0.1", "--port", str(args.port)]
        return await asyncio.create_subprocess_exec(
            *command,
            *options,
            cwd=ROOT,
            env=env,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )

    context = {
        "tools": [
            "ls",
            "read_file",
            "glob",
            "grep",
            "write_file",
            "edit_file",
            "execute",
            "write_todos",
        ]
    }

    platform_root = ROOT.parent / "platform-api"
    platform_python = platform_root / ".venv/bin/python"
    env.update(
        PLATFORM_API_PLATFORM_DB_ENABLED="true",
        PLATFORM_API_PLATFORM_DB_AUTO_CREATE="false",
        PLATFORM_API_DATABASE_URL=args.database_url,
        PLATFORM_API_BOOTSTRAP_ADMIN_ENABLED="true",
        PLATFORM_API_BOOTSTRAP_ADMIN_USERNAME="acceptance-admin",
        PLATFORM_API_BOOTSTRAP_ADMIN_PASSWORD=secrets.token_urlsafe(24),
        PLATFORM_API_JWT_ACCESS_SECRET=secrets.token_hex(32),
        PLATFORM_API_JWT_REFRESH_SECRET=secrets.token_hex(32),
        PLATFORM_API_RUNTIME_DELEGATION_SECRET=env["PLATFORM_RUNTIME_DELEGATION_SECRET"],
        PLATFORM_API_RUNTIME_DELEGATION_ISSUER=env["PLATFORM_RUNTIME_DELEGATION_ISSUER"],
        PLATFORM_API_RUNTIME_DELEGATION_AUDIENCE=env["PLATFORM_RUNTIME_DELEGATION_AUDIENCE"],
        PLATFORM_API_LANGGRAPH_UPSTREAM_URL=f"http://127.0.0.1:{args.port}",
        PLATFORM_RUNTIME_MODEL_CONFIG_URL=f"http://127.0.0.1:{args.platform_port}/api/runtime/internal/model-config",
    )
    from cryptography.fernet import Fernet
    env["PLATFORM_API_MODEL_CONFIG_MASTER_KEY"] = Fernet.generate_key().decode()
    migration = await asyncio.create_subprocess_exec(
        str(platform_python), "-m", "alembic", "upgrade", "head",
        cwd=platform_root, env=env)
    assert await migration.wait() == 0

    async def start_platform(generation):
        log = (output / f"platform-{generation}.log").open("wb")
        logs.append(log)
        return await asyncio.create_subprocess_exec(
            str(platform_python), "-m", "uvicorn", "platform_api.main:create_app", "--factory",
            "--host", "127.0.0.1", "--port", str(args.platform_port),
            cwd=platform_root, env=env, stdout=log, stderr=log, start_new_session=True)

    async def wait_runtime(api):
        async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{args.port}",
                                     timeout=60, trust_env=False) as runtime_client:
            await _wait_for(runtime_client, "/ready", lambda x: x.get("ready") is True, 600, api)

    private_env = output / "process-env.json"
    private_env.touch(mode=0o600, exist_ok=False)
    private_env.write_text(json.dumps(env))
    api = worker = platform = None
    try:
        api = await start("serve", 1)
        platform = await start_platform(1)
        await wait_runtime(api)
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{args.platform_port}", timeout=45, trust_env=False
        ) as client:
            await _wait_for(
                client, "/_system/probes/ready", lambda x: x.get("status") == "ready", 600, platform
            )

            login = await client.post("/api/identity/session", json={
                "username": "acceptance-admin", "password": env["PLATFORM_API_BOOTSTRAP_ADMIN_PASSWORD"]})
            login.raise_for_status()
            token = login.json()["tokens"]["access_token"]
            client.headers["authorization"] = f"Bearer {token}"
            created_project = await client.post("/api/projects", json={"name": "showcase-acceptance"})
            created_project.raise_for_status()
            project_id = created_project.json()["id"]
            client.headers["x-project-id"] = project_id
            for resource in ("graphs", "tools"):
                for _ in range(90):
                    response = await client.post(f"/api/runtime/{resource}/refresh")
                    if response.status_code == 200:
                        break
                    await asyncio.sleep(2)
                response.raise_for_status()
            model = await client.post("/api/runtime/models", json={
                "provider": "deepseek", "display_name": "Acceptance model",
                "base_url": env["DEEPSEEK_PROXY_URL"], "protocol": "openai",
                "model": "DeepSeek-V4-Flash", "api_key": "pending-rotation"})
            model.raise_for_status()
            context["model_id"] = model.json()["id"]
            agent = await client.post(f"/api/projects/{project_id}/agents", json={
                "graph_id": "showcase_demo", "name": "showcase-acceptance", "context": context})
            agent.raise_for_status()

            async def request(method, path, payload=None, **kwargs):
                for attempt in range(3):
                    try:
                        response = await client.request(method, "/api/langgraph" + path, json=payload)
                        break
                    except httpx.ReadTimeout:
                        # Read polling is safe to repeat; never replay a mutation here.
                        if method != "GET" or attempt == 2:
                            raise
                response.raise_for_status()
                value = response.json()
                encoded = json.dumps(value)
                assert "runtime_model_ref" not in encoded and env["DEEPSEEK_PROXY_API_KEY"] not in encoded
                return value

            # Real pending-run cancellation and reject concurrency, before starting our worker.
            cancel_thread = await request("POST", "/threads", {"graph_id": "showcase_demo"})
            cancel_path = "/threads/" + cancel_thread["thread_id"]
            cancel_payload = {"assistant_id": "showcase_demo", "context": context,
                              "input": {"messages": [{"role": "user", "content": "cancel probe"}]}}
            cancelled_runs = []
            for _ in range(2):
                probe = await request("POST", cancel_path + "/runs", cancel_payload)
                busy = await client.post("/api/langgraph" + cancel_path + "/runs", json=cancel_payload)
                assert busy.status_code == 409
                await request("POST", cancel_path + "/runs/" + probe["run_id"] + "/cancel", {"action": "interrupt"})
                observed = await request("GET", cancel_path + "/runs/" + probe["run_id"])
                assert observed["status"] not in {"pending", "running"}
                cancelled_runs.append(probe["run_id"])
            assert cancelled_runs[0] != cancelled_runs[1]

            thread = await request("POST", "/threads", {"graph_id": "showcase_demo"})
            tid, aid = thread["thread_id"], "showcase_demo"
            path = f"/threads/{tid}"
            runs = []

            async def invoke(payload):
                nonlocal worker
                if "command" in payload:
                    created = await request("POST", path + "/runs", {
                        "assistant_id": aid, **payload})
                else:
                    key = secrets.token_hex(16)
                    client.headers["Idempotency-Key"] = key
                    data = {"assistant_id": aid, "context": context, "config": {"recursion_limit": 100}, "durability": "sync", **payload}
                    created = await request("POST", path + "/runs", data)
                    repeated = await request("POST", path + "/runs", data)
                    assert created["run_id"] == repeated["run_id"]
                    conflict = await client.post("/api/langgraph" + path + "/runs",
                        json={**data, "input": {"messages": [{"role": "user", "content": "different"}]}})
                    assert conflict.status_code == 409
                    del client.headers["Idempotency-Key"]
                    if worker is None:
                        # Actual delay exceeds the default 60-second model reference TTL.
                        await asyncio.sleep(31)
                        await asyncio.sleep(31)
                        rotated = await client.patch("/api/runtime/models/" + model.json()["id"],
                            json={"api_key": env["DEEPSEEK_PROXY_API_KEY"]})
                        rotated.raise_for_status()
                        worker = await start("worker", 1)
                for _ in range(840):
                    observed = await request("GET", path + "/runs/" + created["run_id"])
                    if observed["status"] not in {"pending", "running"}:
                        runs.append(
                            {"run_id": created["run_id"], "status": observed["status"]}
                        )
                        assert observed["status"] in {"success", "interrupted"}, (
                            observed
                        )
                        return await request("GET", path + "/state")
                    await asyncio.sleep(0.5)
                raise TimeoutError("Showcase run did not finish within 420 seconds")

            state = await invoke(
                {
                    "input": {
                        "messages": [
                            {
                                "role": "user",
                                "content": ("请只读 /workspace/report.py 和 /workspace/sales.csv，指出汇总错误及正确金额。只读分析，不写文件，不执行命令，不委派。" if args.read_only else "请读取 /workspace/report.py 和 sales.csv，修复金额汇总错误，补一个 test_report.py 回归检查，"
                                "用 python 运行检查和 report.py，将最终报表输出保存为 /workspace/result.txt。"
                                "直接完成这个小任务，不要委派；修改和执行等待审批，不要只给建议。"),
                            }
                        ]
                    }
                }
            )

            def interrupts(snapshot):
                return snapshot.get("interrupts") or [
                    item
                    for task in snapshot.get("tasks", [])
                    for item in task.get("interrupts", [])
                ]

            if args.read_only:
                assert not interrupts(state) and not state.get("next"), state
                assert state["values"]["messages"]
            else:
                pending = interrupts(state)
                assert pending, state
                assert state["values"]["messages"] and state["next"], state
                original_ids = {item["id"] for item in pending}
                await _stop(platform, signal.SIGTERM)
                await _stop(worker, signal.SIGTERM)
                await _stop(api, signal.SIGTERM)
                api, worker = await start("serve", 2), await start("worker", 2)
                platform = await start_platform(2)
                await wait_runtime(api)
                await _wait_for(
                    client, "/_system/probes/ready", lambda x: x.get("status") == "ready", 600, platform
                )
                restored = await request("GET", path + "/state")
                assert restored["values"] == state["values"]
                assert {item["id"] for item in interrupts(restored)} == original_ids
                # A disabled Agent must block approval without consuming the interrupt.
                disabled = await client.patch("/api/agents/" + agent.json()["id"], json={"status": "disabled"})
                disabled.raise_for_status()
                pending = interrupts(restored)[0]
                denied = await client.post("/api/langgraph" + path + "/commands", json={
                    "id": 3, "method": "input.respond", "params": {
                        "interrupt_id": pending["id"], "response": {"decisions": [
                            {"type": "approve"} for _ in pending["value"]["action_requests"]]}}})
                assert denied.status_code == 403
                enabled = await client.patch("/api/agents/" + agent.json()["id"], json={"status": "active"})
                enabled.raise_for_status()
                reviewed = []
                for _ in range(12):
                    pending = interrupts(state)
                    if not pending:
                        break
                    resume = {}
                    for item in pending:
                        actions = item["value"]["action_requests"]
                        assert all(
                            action["name"] in {"write_file", "edit_file", "execute"}
                            for action in actions
                        )
                        reviewed.extend(action["name"] for action in actions)
                        resume[item["id"]] = {
                            "decisions": [{"type": "approve"} for _ in actions]
                        }
                    state = await invoke({"command": {"resume": resume}})
                assert not interrupts(state) and not state.get("next"), state
                assert state["values"]["messages"], state
                assert "execute" in reviewed and {"write_file", "edit_file"} & set(reviewed)
                # Independent real execution verifies the model did not merely claim success.
                previous = os.environ.get("RUNTIME_SHOWCASE_WORKSPACE_ROOT")
                os.environ["RUNTIME_SHOWCASE_WORKSPACE_ROOT"] = env[
                    "RUNTIME_SHOWCASE_WORKSPACE_ROOT"
                ]
                try:
                    backend = DockerWorkspaceBackend(
                        jwt.decode(token, options={"verify_signature": False}).get("tenant_id", "__default"), project_id, tid
                    )
                finally:
                    if previous is None:
                        os.environ.pop("RUNTIME_SHOWCASE_WORKSPACE_ROOT", None)
                    else:
                        os.environ["RUNTIME_SHOWCASE_WORKSPACE_ROOT"] = previous
                workspace = backend.cwd / "workspace"
                result = await asyncio.to_thread(
                    backend.execute,
                    "python test_report.py && "
                    "python -c \"import runpy; ns=runpy.run_path('test_report.py'); "
                    "[f() for n,f in ns.items() if n.startswith('test_') and callable(f)]\" "
                    "&& python report.py"
                )
                assert result.exit_code == 0 and "43.50" in result.output, result
                assert "43.50" in (workspace / "result.txt").read_text()
            async with client.stream("GET", "/api/langgraph" + path + "/runs/" + runs[-1]["run_id"] + "/stream") as events:
                events.raise_for_status()
                received = []
                async for chunk in events.aiter_bytes():
                    received.append(chunk)
                body = b"".join(received)
                assert b"data:" in body and b"runtime_model_ref" not in body
            other_project = await client.post("/api/projects", json={"name": "isolation-check"})
            other_project.raise_for_status()
            forbidden = await client.get("/api/langgraph" + path,
                headers={"x-project-id": other_project.json()["id"]})
            assert forbidden.status_code in {403, 404}
            for retired in ("/api/operations", "/api/agents/anything/resync"):
                gone = await client.post(retired, json={})
                assert gone.status_code == 404
            evidence = {
                "status": "passed",
                "scope": "read-only" if args.read_only else "full Showcase",
                "thread_id": tid,
                "runs": runs,
                "restored_interrupt_ids": sorted(original_ids) if not args.read_only else [],
                "reviewed_tools": reviewed if not args.read_only else [],
                "independent_execution": result.output if not args.read_only else None,
                "exit_code": result.exit_code if not args.read_only else None,
                "api_worker_restarted": not args.read_only,
                "platform_restarted": not args.read_only,
                "project_id": project_id,
                "idempotency_conflict_verified": True,
                "agent_revocation_verified": not args.read_only,
                "cross_project_denied": True,
                "sse_bytes": len(body),
                "queued_beyond_model_reference_ttl": True,
                "credential_rotated_before_worker_started": True,
                "standard_resume_verified": not args.read_only,
                "pending_cancel_and_resend_verified": True,
                "server_reject_concurrency_verified": True,
            }
            (output / "evidence.json").write_text(json.dumps(evidence, indent=2))
            return evidence
    finally:
        await _stop(platform, signal.SIGTERM)
        await _stop(worker, signal.SIGTERM)
        await _stop(api, signal.SIGTERM)
        for log in logs:
            log.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=18324)
    parser.add_argument("--platform-port", type=int, default=18424)
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--read-only", action="store_true", help="Verify local infrastructure without Docker tool execution")
    args = parser.parse_args()
    if not os.getenv("DATABASE_URI") or not os.getenv("REDIS_URI"):
        parser.error(
            "DATABASE_URI and REDIS_URI must point to migrated, dedicated test infrastructure"
        )
    print(json.dumps(asyncio.run(run(args)), ensure_ascii=False, indent=2))
