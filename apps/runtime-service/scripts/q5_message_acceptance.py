"""Start isolated source processes and run the single-browser queue contract."""

import asyncio
import json
import os
import secrets
import signal
import sys
import tempfile
from pathlib import Path

import httpx
from dotenv import dotenv_values
from r6_worker_fault_injection import _stop, _wait_for
from runtime_service.messaging import MessageInbox

ROOT = Path(__file__).resolve().parents[3]


async def main():
    runtime = ROOT / "apps/runtime-service"
    platform = ROOT / "apps/platform-api"
    web = ROOT / "apps/platform-web"
    output = Path(tempfile.mkdtemp(prefix="q5-message-"))
    print(f"Q5 logs: {output}", flush=True)
    settings = dotenv_values(platform / ".env")
    secret = settings.get("PLATFORM_API_RUNTIME_DELEGATION_SECRET")
    assert secret, "Platform Runtime delegation must be configured"
    dsn = os.environ["Q5_DATABASE_URI"]
    graphharbor_source = os.environ.get("Q5_GRAPHHARBOR_SOURCE")
    python_paths = [str(runtime / "src"), str(runtime / "scripts")]
    if graphharbor_source:
        python_paths.extend(
            str(Path(graphharbor_source).resolve() / "libs" / name / "src")
            for name in ("langhost", "langgraph-runtime-pg")
        )
    MessageInbox(dsn).initialize()
    real_graphs = os.getenv("Q5_REAL_GRAPHS") == "1"
    (output / "entry.py").write_text(
        (
            "from runtime_service.graphs.reference_agent import get_agent\n"
            "from runtime_service.graphs.workflow_demo import get_agent as get_contract_agent\n"
            if real_graphs
            else "from q5_message_graph import get_agent\nfrom web_contract_graph import get_agent as get_contract_agent\n"
        )
        + "from runtime_service.graphs.showcase_demo import get_agent as get_showcase_agent\n"
        + "from runtime_service.auth.platform import auth\nfrom runtime_service.webapp import app\n"
    )
    (output / "empty.env").touch()
    (output / "langgraph.json").write_text(
        json.dumps(
            {
                "dependencies": ["."],
                "python_version": "3.13",
                "graphs": {
                    "reference_agent": "./entry.py:get_agent",
                    "workflow_demo": "./entry.py:get_contract_agent",
                    "showcase_demo": "./entry.py:get_showcase_agent",
                },
                "auth": {"path": "./entry.py:auth"},
                "http": {"app": "./entry.py:app"},
            }
        )
    )
    env = {
        **os.environ,
        "DATABASE_URI": dsn,
        "POSTGRES_URI": dsn,
        "REDIS_URI": "redis://127.0.0.1:6379/0",
        "GRAPHHARBOR_REDIS_PREFIX": secrets.token_hex(8),
        "GRAPHHARBOR_ENV": "development",
        "LG_RUNTIME_PG_AUTO_MIGRATE": "false",
        "PLATFORM_RUNTIME_DELEGATION_SECRET": secret,
        "PLATFORM_RUNTIME_DELEGATION_ISSUER": settings.get(
            "PLATFORM_API_RUNTIME_DELEGATION_ISSUER"
        )
        or "platform-api",
        "PLATFORM_RUNTIME_DELEGATION_AUDIENCE": settings.get(
            "PLATFORM_API_RUNTIME_DELEGATION_AUDIENCE"
        )
        or "runtime-service",
        "GRAPHHARBOR_RUNTIME_CONTEXT_SECRET": secrets.token_hex(32),
        "PLATFORM_RUNTIME_MESSAGE_AUTH_URL": "http://127.0.0.1:2143/api/runtime/internal/message-authorization",
        "RUNTIME_SELF_URL": "http://127.0.0.1:8124",
        "PLATFORM_RUNTIME_MODEL_CONFIG_URL": "http://127.0.0.1:2143/api/runtime/internal/model-config",
        "RUNTIME_SHOWCASE_WORKSPACE_ROOT": str(output / "workspaces"),
        "PYTHONPATH": os.pathsep.join(python_paths),
    }
    processes, logs = [], []

    async def start(command, cwd, variables, name):
        log = (output / f"{name}.log").open("wb")
        logs.append(log)
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=cwd,
            env=variables,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
        processes.append(process)
        return process

    try:
        engine = await start(
            [
                sys.executable,
                "-m",
                "langhost.cli",
                "serve",
                "--config",
                str(output / "langgraph.json"),
                "--env-file",
                str(output / "empty.env"),
                "--host",
                "127.0.0.1",
                "--port",
                "8124",
                "--n-jobs-per-worker",
                "0",
            ],
            runtime,
            env,
            "runtime",
        )
        await start(
            [
                sys.executable,
                "-m",
                "langhost.cli",
                "worker",
                "--config",
                str(output / "langgraph.json"),
                "--env-file",
                str(output / "empty.env"),
                "--n-jobs-per-worker",
                "1",
            ],
            runtime,
            env,
            "worker",
        )
        api = await start(
            [
                str(platform / ".venv/bin/python"),
                "-m",
                "uvicorn",
                "platform_api.main:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                "2143",
            ],
            platform,
            {
                **os.environ,
                "PYTHONPATH": str(platform / "src"),
                "PLATFORM_API_LANGGRAPH_UPSTREAM_URL": "http://127.0.0.1:8124",
                "PLATFORM_API_DATABASE_URL": f"sqlite:///{output / 'platform.db'}",
                "PLATFORM_API_PLATFORM_DB_ENABLED": "true",
                "PLATFORM_API_PLATFORM_DB_AUTO_CREATE": "true",
            },
            "platform",
        )
        await start(
            ["pnpm", "exec", "vite", *(["preview"] if os.getenv("Q5_PREVIEW_WEB") == "1" else []),
             *(["--outDir", os.environ["Q5_WEB_OUTDIR"]] if os.getenv("Q5_WEB_OUTDIR") else []),
             "--host", "127.0.0.1", "--port", "3002", "--strictPort"],
            web,
            {**os.environ, "VITE_DEV_PROXY_TARGET": "http://127.0.0.1:2143"},
            "web",
        )
        async with httpx.AsyncClient(base_url="http://127.0.0.1:8124") as client:
            await _wait_for(
                client, "/ready", lambda value: value.get("ready"), 60, engine
            )
        async with httpx.AsyncClient(base_url="http://127.0.0.1:2143") as client:
            await _wait_for(
                client, "/_system/health", lambda value: bool(value), 60, api
            )
        test = await asyncio.create_subprocess_exec(
            "pnpm",
            "exec",
            "playwright",
            "test",
            os.getenv("Q5_TEST_FILE", "e2e/queue-message-refactor.spec.ts"),
            "--reporter=line,json",
            "--output",
            str(output / "browser-results"),
            "--workers=1",
            "--trace=off",
            *sys.argv[1:],
            cwd=web,
            env={
                **os.environ,
                "PLAYWRIGHT_BASE_URL": "http://127.0.0.1:3002",
                "PLATFORM_TEST_URL": "http://127.0.0.1:2143",
                "Q5_QUEUE_FIXTURE": "0" if real_graphs else "1",
                "PLATFORM_TEST_SEED_MODEL": "1" if real_graphs else "0",
                "SHOWCASE_TEST_WORKSPACES": str(output / "workspaces"),
                "PLAYWRIGHT_JSON_OUTPUT_FILE": str(output / "browser-report.json"),
            },
        )
        code = await test.wait()
        print(json.dumps({"passed": code == 0, "logs": str(output)}))
        return code
    finally:
        for process in reversed(processes):
            await _stop(process, signal.SIGTERM)
        for log in logs:
            log.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
