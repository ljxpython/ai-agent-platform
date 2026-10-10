"""Run three disposable native stacks without modifying existing Git worktrees.

The Git location queries are fixtures; real processes, packages, databases, Redis,
Web proxy and Runtime catalog calls use the production local-stack entrypoint.
A temporary deterministic graph verifies real Worker and Workspace ownership.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
import psycopg
from local_stack_worktree import configs, read_env, read_registry, record

BROWSER_PROBE = r"""
import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { platformUrl, testCredentials } from "./support/platform";

test("registered Worktree browser and API login", async ({ page, baseURL }) => {
  const environment = JSON.parse(readFileSync(resolve(process.cwd(), "../../.local-stack/environment.json"), "utf8"));
  expect(baseURL).toBe(`http://127.0.0.1:${environment.ports.PLATFORM_WEB_PORT}`);
  expect(platformUrl).toBe(`http://127.0.0.1:${environment.ports.PLATFORM_API_PORT}`);
  const requests: string[] = [];
  page.on("request", request => {
    if (new URL(request.url()).pathname.startsWith("/api/")) requests.push(request.url());
  });
  await page.goto("/auth/login");
  const credentials = testCredentials();
  await page.locator('input[autocomplete="username"]').fill(credentials.username);
  await page.locator('input[autocomplete="current-password"]').fill(credentials.password);
  const login = page.waitForResponse(response => new URL(response.url()).pathname === "/api/identity/session" && response.request().method() === "POST");
  await page.locator('button[type="submit"]').click();
  expect((await login).status()).toBe(200);
  await expect(page).toHaveURL(/\/workspace/);
  expect(requests.length).toBeGreaterThan(0);
  expect(requests.every(url => new URL(url).origin === baseURL)).toBe(true);
});
"""

WORKER_PROBE = """
import os
from pathlib import Path
from typing import TypedDict
from langgraph.graph import START, END, StateGraph

class State(TypedDict, total=False):
    operation: str
    observed: str
    worker_environment: str

async def probe(state):
    marker = os.environ["LOCAL_STACK_ID"]
    path = Path(os.environ["GRAPHHARBOR_WORKSPACE_ROOT"]) / "isolation.txt"
    if state["operation"] == "write":
        path.write_text(marker)
    return {"observed": path.read_text(), "worker_environment": marker}

builder = StateGraph(State)
builder.add_node("probe", probe)
builder.add_edge(START, "probe")
builder.add_edge("probe", END)
graph = builder.compile()

async def get_agent(config):
    return graph
"""


def run(root: Path, action: str, env: dict, *arguments: str) -> None:
    log = root / f"{action}.log"
    with log.open("w") as stream:
        result = subprocess.run(
            ["bash", str(root / "scripts/local-stack.sh"), action, *arguments],
            env=env,
            stdout=stream,
            stderr=subprocess.STDOUT,
            check=False,
        )
    if result.returncode:
        raise RuntimeError(f"{root.name}: {action} failed; inspect private log {log}")
    print(f"[verified] {root.name} {action}", flush=True)


def verify_baseline(root: Path, common: Path) -> dict:
    sys.path.insert(0, str(root / "apps/platform-api/src"))
    from platform_api.modules.runtime_catalog.application.credentials import (
        decrypt_api_key,
    )

    entry = record(root, common)
    runtime, platform = configs(root, entry)
    if (
        platform["PLATFORM_API_BOOTSTRAP_ADMIN_USERNAME"],
        platform["PLATFORM_API_BOOTSTRAP_ADMIN_PASSWORD"],
    ) != ("admin", "admin123"):
        raise RuntimeError("Worktree local administrator defaults differ")
    report = {}
    for kind, uri, history in (
        (
            "platform",
            platform["PLATFORM_API_DATABASE_URL"].replace(
                "postgresql+psycopg:", "postgresql:"
            ),
            (
                "thread_access",
                "run_requests",
                "refresh_tokens",
                "service_account_tokens",
            ),
        ),
        (
            "runtime",
            runtime["DATABASE_URI"],
            (
                "threads",
                "runs",
                "checkpoints",
                "crons",
                "runtime_message_inbox",
                "runtime_usage_calls",
                "dear_memory",
            ),
        ),
    ):
        with psycopg.connect(uri) as connection:
            marker, tables = connection.execute(
                "SELECT environment_id, report FROM public._local_stack_seed"
            ).fetchone()
            if marker != entry["id"]:
                raise RuntimeError("Missing owned baseline marker")
            for table in history:
                if connection.execute(
                    psycopg.sql.SQL("SELECT count(*) FROM {}").format(
                        psycopg.sql.Identifier(table)
                    )
                ).fetchone()[0]:
                    raise RuntimeError(f"History was copied: {table}")
            if kind == "platform":
                for (ciphertext,) in connection.execute(
                    "SELECT api_key_ciphertext FROM runtime_catalog_models"
                ):
                    if ciphertext:
                        decrypt_api_key(
                            ciphertext,
                            master_key=platform["PLATFORM_API_MODEL_CONFIG_MASTER_KEY"],
                        )
                # Health requests write fresh audit rows after startup; none may come from the source.
                audit_ids = [
                    row[0] for row in connection.execute("SELECT id FROM audit_logs")
                ]
                baseline = read_env(
                    Path(__file__).resolve().parents[1] / "apps/platform-api/.env"
                )
                with psycopg.connect(
                    baseline["PLATFORM_API_DATABASE_URL"].replace(
                        "postgresql+psycopg:", "postgresql:"
                    )
                ) as source:
                    source.execute("SET TRANSACTION READ ONLY")
                    if source.execute(
                        "SELECT 1 FROM audit_logs WHERE id = ANY(%s) LIMIT 1",
                        (audit_ids,),
                    ).fetchone():
                        raise RuntimeError("Source audit rows were copied")
            report[kind] = tables
    print(
        f"[baseline] {entry['id']}: copied configuration, valid model encryption and empty history",
        flush=True,
    )
    return report


def verify_chain(root: Path, common: Path, *, create: bool) -> dict:
    entry = record(root, common)
    _, platform = configs(root, entry)
    web = f"http://127.0.0.1:{entry['ports']['PLATFORM_WEB_PORT']}"
    with httpx.Client(base_url=web, timeout=45, trust_env=False) as client:
        page = client.get("/")
        page.raise_for_status()
        if '<div id="app">' not in page.text:
            raise RuntimeError("Web application did not render its entrypoint")
        health = client.get("/_system/health")
        health.raise_for_status()
        login = client.post(
            "/api/identity/session",
            json={
                "username": platform.get(
                    "PLATFORM_API_BOOTSTRAP_ADMIN_USERNAME", "admin"
                ),
                "password": platform["PLATFORM_API_BOOTSTRAP_ADMIN_PASSWORD"],
            },
        )
        login.raise_for_status()
        client.headers["authorization"] = (
            "Bearer " + login.json()["tokens"]["access_token"]
        )
        if create:
            response = client.post("/api/projects", json={"name": entry["id"]})
            response.raise_for_status()
            project = response.json()
            (root / "probe-project.json").write_text(json.dumps(project))
        else:
            project = json.loads((root / "probe-project.json").read_text())
        client.headers["x-project-id"] = project["id"]
        catalog = client.post("/api/runtime/graphs/refresh")
        catalog.raise_for_status()
        if catalog.json()["count"] < 1:
            raise RuntimeError("Platform did not receive the Runtime catalog")
        projects = client.get("/api/projects")
        projects.raise_for_status()
        if entry["id"] not in projects.text:
            raise RuntimeError("Environment project was not persisted")
        thread_id = verify_worker(client, root, entry, project, create=create)
        print(
            f"[chain] {entry['id']}: Web -> Platform API -> authenticated Runtime catalog ({catalog.json()['count']} graphs)",
            flush=True,
        )
        return {
            "id": entry["id"],
            "ports": entry["ports"],
            "graph_count": catalog.json()["count"],
            "project_id": project["id"],
            "worker_thread_id": thread_id,
        }


def verify_worker(
    client: httpx.Client, root: Path, entry: dict, project: dict, *, create: bool
) -> str:
    def request(method: str, path: str, body: dict | None = None):
        response = client.request(method, path, json=body)
        if response.is_error:
            error = response.json().get("error", {})
            raise RuntimeError(
                f"{entry['id']}: {method} {path}: HTTP {response.status_code}; code={error.get('code', 'unavailable')}"
            )
        response.raise_for_status()
        return response.json()

    if create:
        graph = next(
            graph
            for graph in request("GET", "/api/runtime/graphs")["graphs"]
            if graph["graph_id"] == "worktree_probe"
        )
        request(
            "PUT",
            f"/api/projects/{project['id']}/runtime-policies/graphs/{graph['id']}",
            {"is_enabled": True},
        )
        model = request(
            "POST",
            "/api/runtime/models",
            {
                "provider": "openai",
                "protocol": "openai",
                "display_name": "Worktree deterministic probe",
                "model": "worktree-probe",
                "base_url": "https://example.com/v1",
                "api_key": "fixture-only-no-model-call",
                "enabled": True,
            },
        )
        request(
            "PUT",
            f"/api/projects/{project['id']}/runtime-policies/models/{model['id']}",
            {"is_enabled": True, "is_default_for_project": True},
        )
        agents = request(
            "GET", f"/api/projects/{project['id']}/agents?graph_id=worktree_probe"
        )["items"]
        if not agents:
            raise RuntimeError(
                "Authorized Workspace graph did not produce a project Agent"
            )
        thread_id = request(
            "POST", "/api/langgraph/threads", {"graph_id": "worktree_probe"}
        )["thread_id"]
        (root / "probe-thread.json").write_text(json.dumps(thread_id))
    else:
        thread_id = json.loads((root / "probe-thread.json").read_text())
    path = f"/api/langgraph/threads/{thread_id}"
    for operation in ["write", "read"] if create else ["read"]:
        run = request(
            "POST",
            path + "/runs",
            {
                "assistant_id": "worktree_probe",
                "input": {"operation": operation},
            },
        )
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            observed_run = request("GET", path + "/runs/" + run["run_id"])
            status = observed_run["status"]
            if status not in {"pending", "running"}:
                break
            time.sleep(0.2)
        if status != "success":
            raise RuntimeError(f"{entry['id']}: Worker {operation} ended as {status}")
        state = request("GET", path + "/state")["values"]
        if (
            state["observed"] != entry["id"]
            or state["worker_environment"] != entry["id"]
        ):
            raise RuntimeError("Worker read another environment's Workspace marker")
    files = list((root / ".local-stack/workspaces/graphharbor").rglob("isolation.txt"))
    if len(files) != 1 or files[0].read_text().strip() != entry["id"]:
        raise RuntimeError("Worker did not write only this Worktree's Workspace")
    print(f"[worker] {entry['id']}: own queue and Workspace read/write", flush=True)
    return thread_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    evidence = {
        "scope": "three disposable native stacks; Git path queries are fixtures",
        "checks": [],
    }
    with tempfile.TemporaryDirectory(prefix="local-stack-acceptance-") as temporary:
        base = Path(temporary).resolve()
        common = base / "common"
        common.mkdir()
        binary = base / "bin"
        binary.mkdir()
        fake_git = binary / "git"
        fake_git.write_text(
            "#!/usr/bin/env python3\n"
            "import os,sys\nfrom pathlib import Path\n"
            "root=Path(sys.argv[2]); command=sys.argv[3:]\n"
            'if command[0]=="rev-parse":\n'
            ' print(os.environ["LOCAL_STACK_TEST_COMMON"] if "--git-common-dir" in command else root/"git-private")\n'
            'elif command==["worktree","list","--porcelain","-z"]:\n'
            ' sys.stdout.write("worktree "+os.environ["LOCAL_STACK_TEST_PRIMARY"]+"\\0\\0")\n'
            "else: sys.exit(1)\n"
        )
        fake_git.chmod(0o700)
        env = {
            **os.environ,
            "PATH": str(binary) + os.pathsep + os.environ["PATH"],
            "LOCAL_STACK_TEST_COMMON": str(common),
            "LOCAL_STACK_TEST_PRIMARY": str(repository),
        }
        for key in (
            "VIRTUAL_ENV",
            "UV_PROJECT_ENVIRONMENT",
            "PYTHONPATH",
            "PLAYWRIGHT_BASE_URL",
            "PLATFORM_TEST_URL",
            "LOCAL_STACK_LOCKED_ROOT",
            "PLATFORM_TEST_USERNAME",
            "PLATFORM_TEST_PASSWORD",
            "PLATFORM_TEST_ENV_FILE",
            "RUNTIME_TEST_ENV_FILE",
        ):
            env.pop(key, None)
        roots = [base / f"worktree {index}" for index in range(3)]
        starts = []
        try:
            for root in roots:
                (root / "git-private").mkdir(parents=True)
                (root / "scripts").mkdir()
                shutil.copytree(repository / "docs", root / "docs")
                for script in (
                    "local-stack.sh",
                    "local_stack_worktree.py",
                    "local_stack_seed.py",
                    "local_stack_processes.py",
                ):
                    shutil.copy2(
                        repository / "scripts" / script, root / "scripts" / script
                    )
                for app in ("runtime-service", "platform-api", "platform-web"):
                    shutil.copytree(
                        repository / "apps" / app,
                        root / "apps" / app,
                        ignore=shutil.ignore_patterns(
                            ".venv",
                            "node_modules",
                            ".env",
                            ".env.*",
                            ".data",
                            ".runtime",
                            "dist",
                            "coverage",
                            "test-results",
                            "playwright-report",
                            "__pycache__",
                            "*.pyc",
                        ),
                    )
                config_path = root / "apps/runtime-service/langgraph.json"
                config = json.loads(config_path.read_text())
                (
                    root
                    / "apps/runtime-service/src/runtime_service/graphs/worktree_probe.py"
                ).write_text(WORKER_PROBE)
                config["graphs"]["worktree_probe"] = {
                    "path": "./src/runtime_service/graphs/worktree_probe.py:get_agent",
                    "description": "Temporary deterministic Worktree acceptance graph",
                }
                config_path.write_text(json.dumps(config))
                (root / "apps/platform-web/e2e/worktree-isolation.spec.ts").write_text(
                    BROWSER_PROBE
                )
                run(root, "init", env)
                run(root, "deps", env)
                run(root, "doctor", env)
                result = subprocess.run(
                    [
                        "pnpm",
                        "--dir",
                        str(root / "apps/platform-web"),
                        "exec",
                        "playwright",
                        "test",
                        "--list",
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode:
                    raise RuntimeError(
                        f"Worktree Playwright configuration failed to load: {result.stderr}"
                    )
                stream = (root / "start.log").open("w")
                process = subprocess.Popen(
                    ["bash", str(root / "scripts/local-stack.sh"), "start"],
                    env=env,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                )
                stream.close()
                starts.append((root, process))
            deadline = time.monotonic() + 240
            while any(process.poll() is None for _, process in starts):
                if time.monotonic() > deadline:
                    raise RuntimeError(
                        "Concurrent native stacks did not finish starting in 240 seconds"
                    )
                time.sleep(0.2)
            for root, process in starts:
                if process.returncode:
                    raise RuntimeError(
                        f"{root.name}: start failed; inspect private log {root / 'start.log'}"
                    )
            evidence["baseline_copies"] = [
                verify_baseline(root, common) for root in roots
            ]
            evidence["checks"].append(
                "real main-workspace configuration data copied once; model keys reencrypted; admin defaults and empty history verified"
            )
            with ThreadPoolExecutor(max_workers=3) as executor:
                evidence["environments"] = list(
                    executor.map(
                        lambda root: verify_chain(root, common, create=True), roots
                    )
                )
            evidence["checks"].append(
                "three concurrent real native stacks and isolated-source dependency installations"
            )
            for root in roots:
                run(root, "status", env)
                with (root / "browser.log").open("w") as stream:
                    result = subprocess.run(
                        [
                            "pnpm",
                            "--dir",
                            str(root / "apps/platform-web"),
                            "exec",
                            "playwright",
                            "test",
                            "worktree-isolation.spec.ts",
                            "--workers=1",
                            "--retries=0",
                        ],
                        env=env,
                        stdout=stream,
                        stderr=subprocess.STDOUT,
                        check=False,
                    )
                if result.returncode:
                    raise RuntimeError(
                        f"{root.name}: browser login failed; inspect {root / 'browser.log'}"
                    )
                print(
                    f"[browser] {root.name}: registered Web/API and real login",
                    flush=True,
                )
            evidence["checks"].extend(
                [
                    "three real Workers consume only their own queues and write/read independent same-name Workspace files",
                    "three independent Chromium contexts log in through registered Web/API addresses",
                ]
            )
            # Verify Playwright resolves the assigned addresses before running browsers.
            run(roots[0], "start", env)
            result = subprocess.run(
                [
                    "pnpm",
                    "--dir",
                    str(roots[0] / "apps/platform-web"),
                    "exec",
                    "playwright",
                    "test",
                    "--list",
                ],
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode:
                raise RuntimeError(
                    f"Worktree Playwright configuration failed to load: {result.stderr}"
                )
            evidence["checks"].append(
                "idempotent start and registered Playwright configuration"
            )
            run(roots[0], "stop", env)
            for root in roots[1:]:
                verify_chain(root, common, create=False)
            evidence["checks"].append(
                "stopping the first stack leaves the other two chains available"
            )
            run(roots[0], "start", env)
            restored = verify_chain(roots[0], common, create=False)
            if restored != evidence["environments"][0]:
                raise RuntimeError(
                    "Restart changed the environment allocation or project data"
                )
            evidence["checks"].append(
                "restart retains allocation, credentials and persisted project"
            )
        except Exception:
            for root in roots:
                log = root / "start.log"
                if log.is_file():
                    for line in log.read_text().splitlines():
                        if line.startswith("ERROR "):
                            print(f"[startup-error] {root.name}: {line}", flush=True)
            raise
        finally:
            for _, process in starts:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=30)
            for root in roots:
                entry = read_registry(common)["environments"].get(str(root))
                if entry and (root / ".local-stack/environment.json").is_file():
                    run(root, "stop", env)
                    run(root, "destroy", env, "--confirm", entry["id"])
        evidence["checks"].append(
            "only disposable test resources stopped and explicitly destroyed"
        )
    evidence["result"] = "passed"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(f"[evidence] {args.output}", flush=True)


if __name__ == "__main__":
    main()
