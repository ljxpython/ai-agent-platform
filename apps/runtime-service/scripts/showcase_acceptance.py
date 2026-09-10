"""Verify a real Showcase run across API/worker restart on dedicated test infra."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import secrets
import signal
import sys
import time
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values
from r6_worker_fault_injection import ROOT, _stop, _wait_for

from runtime_service.runtime import runtime_context_hash
from runtime_service.services.demo.showcase_demo.agent import (
    _DEFAULTS,
    _TOOL_PERMISSIONS,
)
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

    def headers(operation="read", thread_id=None, assistant_id=None):
        now = int(time.time())
        claims = {
            "type": "runtime_delegation",
            "sub": "showcase-acceptance",
            "tenant_id": "showcase-acceptance",
            "project_id": "showcase-acceptance",
            "role": "developer",
            "permissions": sorted(set(_TOOL_PERMISSIONS.values())),
            "policy_version": "showcase-acceptance-v1",
            "allowed_model_ids": [_DEFAULTS.model_id],
            "allowed_tool_names": list(_DEFAULTS.optional_tool_names),
            "iat": now,
            "exp": now + 300,
            "iss": env["PLATFORM_RUNTIME_DELEGATION_ISSUER"],
            "aud": env["PLATFORM_RUNTIME_DELEGATION_AUDIENCE"],
            "scope": {
                "tenant_id": "showcase-acceptance",
                "project_id": "showcase-acceptance",
                "thread_id": thread_id,
                "assistant_id": assistant_id,
                "operation": operation,
            },
            "context_hash": runtime_context_hash(context),
        }
        return {
            "Authorization": "Bearer "
            + jwt.encode(
                claims, env["PLATFORM_RUNTIME_DELEGATION_SECRET"], algorithm="HS256"
            )
        }

    api = worker = None
    try:
        api, worker = await start("serve", 1), await start("worker", 1)
        async with httpx.AsyncClient(
            base_url=f"http://127.0.0.1:{args.port}", timeout=15, trust_env=False
        ) as client:
            await _wait_for(
                client, "/ready", lambda x: x.get("ready") is True, 120, api
            )

            async def request(
                method,
                path,
                payload=None,
                *,
                operation="read",
                thread=None,
                assistant=None,
            ):
                response = await client.request(
                    method,
                    path,
                    json=payload,
                    headers=headers(operation, thread, assistant),
                )
                response.raise_for_status()
                return response.json()

            assistant = await request(
                "POST",
                "/assistants",
                {"graph_id": "showcase_demo", "name": "showcase-acceptance"},
            )
            thread = await request("POST", "/threads", {})
            tid, aid = thread["thread_id"], assistant["assistant_id"]
            path = f"/threads/{tid}"
            runs = []

            async def invoke(payload):
                created = await request(
                    "POST",
                    path + "/runs",
                    {
                        "assistant_id": aid,
                        "context": context,
                        "durability": "sync",
                        **payload,
                    },
                    operation="run-create",
                    thread=tid,
                    assistant=aid,
                )
                for _ in range(240):
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
                raise TimeoutError("Showcase run did not finish within 120 seconds")

            state = await invoke(
                {
                    "input": {
                        "messages": [
                            {
                                "role": "user",
                                "content": "请读取 /workspace/report.py 和 sales.csv，修复金额汇总错误，补一个 test_report.py 回归检查，"
                                "用 python 运行检查和 report.py，将最终报表输出保存为 /workspace/result.txt。"
                                "直接完成这个小任务，不要委派；修改和执行等待审批，不要只给建议。",
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

            pending = interrupts(state)
            assert pending, state
            assert state["values"]["messages"] and state["next"], state
            original_ids = {item["id"] for item in pending}
            await _stop(worker, signal.SIGTERM)
            await _stop(api, signal.SIGTERM)
            api, worker = await start("serve", 2), await start("worker", 2)
            await _wait_for(
                client, "/ready", lambda x: x.get("ready") is True, 120, api
            )
            restored = await request("GET", path + "/state")
            assert restored["values"] == state["values"]
            assert {item["id"] for item in interrupts(restored)} == original_ids
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
                    "showcase-acceptance", "showcase-acceptance", tid
                )
            finally:
                if previous is None:
                    os.environ.pop("RUNTIME_SHOWCASE_WORKSPACE_ROOT", None)
                else:
                    os.environ["RUNTIME_SHOWCASE_WORKSPACE_ROOT"] = previous
            workspace = backend.cwd / "workspace"
            result = await asyncio.to_thread(
                backend.execute, "python test_report.py && python report.py"
            )
            assert result.exit_code == 0 and "43.50" in result.output, result
            assert "43.50" in (workspace / "result.txt").read_text()
            evidence = {
                "status": "passed",
                "thread_id": tid,
                "runs": runs,
                "restored_interrupt_ids": sorted(original_ids),
                "reviewed_tools": reviewed,
                "independent_execution": result.output,
                "exit_code": result.exit_code,
                "api_worker_restarted": True,
            }
            (output / "evidence.json").write_text(json.dumps(evidence, indent=2))
            return evidence
    finally:
        await _stop(worker, signal.SIGTERM)
        await _stop(api, signal.SIGTERM)
        for log in logs:
            log.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=31339)
    args = parser.parse_args()
    if not os.getenv("DATABASE_URI") or not os.getenv("REDIS_URI"):
        parser.error(
            "DATABASE_URI and REDIS_URI must point to migrated, dedicated test infrastructure"
        )
    print(json.dumps(asyncio.run(run(args)), ensure_ascii=False, indent=2))
