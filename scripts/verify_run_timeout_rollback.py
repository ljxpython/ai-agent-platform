"""Switch matching Runtime/GraphHarbor versions using disposable PG/Redis only."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import tempfile
from pathlib import Path
from uuid import UUID

import httpx
from langgraph_runtime_pg.database import connect, start_pool, stop_pool
from langgraph_runtime_pg.models import RunRow
from sqlalchemy.engine import make_url

GRAPH = """
import asyncio
import json
import os
from importlib.metadata import version
from pathlib import Path

import runtime_service
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from typing_extensions import TypedDict
from runtime_service.services.reference_agent.agent import get_agent as reference_agent

class State(TypedDict, total=False):
    messages: list
    marker: str
    finished: bool

async def get_agent(config):
    thread_id = str(config.get("configurable", {}).get("thread_id", "schema"))
    root = Path(os.environ["RUN_RELEASE_WORKSPACE"])
    root.mkdir(parents=True, exist_ok=True)
    class Model(FakeMessagesListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self
        async def _agenerate(self, messages, **kwargs):
            text = messages[-1].text
            (root / f"{thread_id}.entered").touch()
            if text == "cancel" or (text == "drain" and version("graphharbor") == "0.13.0.post42"):
                await asyncio.sleep(600)
            return self._generate(messages, **kwargs)
    inner_config = {**config, "configurable": {
        **config.get("configurable", {}),
        "_runtime_model": Model(responses=[AIMessage(content="verified runtime result")]),
    }}
    agent = await reference_agent(inner_config)
    run_id = config.get("metadata", {}).get("run_id")
    if run_id:
        (root / f"{run_id}.facts.json").write_text(json.dumps({
            "graphharbor": version("graphharbor"),
            "runtime": version("graphharbor-runtime"),
            "source": str(Path(runtime_service.__file__).resolve()),
        }))
    async def prepare(state):
        with (root / f"{thread_id}.prepared").open("a") as log:
            log.write("prepared\\n")
        (root / f"{thread_id}.txt").write_text("committed artifact")
        return {"marker": "checkpointed"}
    async def work(state, config):
        message = state["messages"][-1]
        text = message.get("content") if isinstance(message, dict) else message.text
        if text == "approval":
            interrupt("approve")
        result = await agent.ainvoke({"messages": state["messages"]}, config)
        return {"messages": result["messages"], "finished": True}
    graph = StateGraph(State)
    graph.add_node("prepare", prepare)
    graph.add_node("work", work)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "work")
    graph.add_edge("work", END)
    return graph.compile()
"""

AUTH = """
from langgraph_sdk import Auth
from runtime_service.runtime import runtime_context_hash

auth = Auth()
@auth.authenticate
async def authenticate(headers):
    return {
        "identity": "local-user", "permissions": ["*"],
        "runtime_principal": {
            "user_id": "local-user", "tenant_id": "local-tenant",
            "project_id": "reference-project", "role": "developer",
            "permissions": ["runtime.tool.read"],
        },
        "runtime_policy": {
            "version": "release-probe-v1", "allowed_model_ids": ["deepseek:DeepSeek-V4-Flash"],
            "tool_overrides": {}, "tool_policy_version": "release-probe-v1",
        },
        "runtime_scope": {
            "tenant_id": "local-tenant", "project_id": "reference-project", "operation": "run-create",
        },
        "runtime_context_hash": runtime_context_hash(None),
    }
"""


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current-python", type=Path, required=True)
    parser.add_argument("--legacy-python", type=Path, required=True)
    parser.add_argument("--current-source", type=Path, required=True)
    parser.add_argument("--legacy-source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    uri = make_url(os.environ["DATABASE_URI"])
    assert uri.host == "127.0.0.1"
    assert uri.database == "graphharbor_event_retention_verify"
    assert os.environ["GRAPHHARBOR_REDIS_PREFIX"] == "graphharbor:run-release:e7dd"
    evidence = []
    with tempfile.TemporaryDirectory(prefix="run-runtime-rollback-") as directory:
        root = Path(directory)
        (root / "graph.py").write_text(GRAPH, encoding="utf-8")
        (root / "auth.py").write_text(AUTH, encoding="utf-8")
        config = root / "langgraph.json"
        config.write_text(
            json.dumps(
                {
                    "dependencies": ["."],
                    "graphs": {"release": "./graph.py:get_agent"},
                    "auth": {"path": "./auth.py:auth"},
                }
            )
        )
        processes, logs = [], []
        env = dict(os.environ)
        for name in (
            "LANGSMITH_API_KEY",
            "LANGCHAIN_API_KEY",
            "LANGGRAPH_AUTH",
            "LANGSERVE_GRAPHS",
        ):
            env.pop(name, None)
        env.update(
            GRAPHHARBOR_ENV="development",
            GRAPHHARBOR_RUNTIME_CONTEXT_SECRET="isolated-runtime-release-secret-32-bytes",
            GRAPHHARBOR_RUNTIME_CONTEXT_ISSUER="graphharbor",
            GRAPHHARBOR_RUNTIME_CONTEXT_AUDIENCE="graphharbor-worker",
            LANGSMITH_TRACING="false",
            LANGCHAIN_TRACING_V2="false",
            GRAPHHARBOR_RUN_TIMEOUT_SECONDS="60",
            AGENT_RUN_WRAPUP_RESERVE_SECONDS="0",
            GRAPHHARBOR_SHUTDOWN_DRAIN_SECONDS="0.1",
            RUN_RELEASE_WORKSPACE=str(root / "workspace"),
        )

        async def launch(python, source, *command):
            log = (root / f"process-{len(processes)}.log").open("w")
            logs.append(log)
            process = await asyncio.create_subprocess_exec(
                str(python.with_name("graphharbor")),
                *command,
                cwd=root,
                env={**env, "PYTHONPATH": str(source.resolve())},
                stdout=log,
                stderr=log,
            )
            processes.append(process)
            return process

        async def stop(process):
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), 20)
                except TimeoutError:
                    process.kill()
                    await process.wait()
                    raise

        async def server(python, source):
            port = free_port()
            process = await launch(
                python,
                source,
                "serve",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--config",
                str(config),
                "--n-jobs-per-worker",
                "0",
                "--no-browser",
            )
            client = httpx.AsyncClient(
                base_url=f"http://127.0.0.1:{port}", timeout=20, trust_env=False
            )
            try:
                async with asyncio.timeout(60):
                    while True:
                        assert process.returncode is None
                        try:
                            if (await client.get("/ok")).is_success:
                                return process, client
                        except httpx.HTTPError:
                            pass
                        await asyncio.sleep(0.1)
            except BaseException:
                await client.aclose()
                raise

        async def request(client, method, path, **kwargs):
            response = await client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json() if response.content else None

        async def submit(client, text, thread_id=None, command=None):
            if thread_id is None:
                thread_id = (await request(client, "POST", "/threads", json={}))[
                    "thread_id"
                ]
            payload = {
                "assistant_id": "release",
                "multitask_strategy": "enqueue",
                "durability": "sync",
            }
            payload.update(
                {"command": command}
                if command
                else {"input": {"messages": [{"role": "user", "content": text}]}}
            )
            run = await request(
                client, "POST", f"/threads/{thread_id}/runs", json=payload
            )
            return thread_id, run["run_id"]

        async def wait_run(client, tid, rid, status):
            async with asyncio.timeout(90):
                while True:
                    run = await request(client, "GET", f"/threads/{tid}/runs/{rid}")
                    async with connect() as conn:
                        row = await conn.session.get(RunRow, UUID(rid))
                        released = row.lease_owner is None
                    if run["status"] == status and released:
                        return run
                    assert run["status"] in {"pending", "running", status}, run
                    await asyncio.sleep(0.1)

        async def entered(tid):
            async with asyncio.timeout(60):
                while not (root / "workspace" / f"{tid}.entered").exists():
                    await asyncio.sleep(0.1)

        def facts(rid, version, source):
            value = json.loads((root / "workspace" / f"{rid}.facts.json").read_text())
            assert value["graphharbor"] == value["runtime"] == version, value
            assert Path(value["source"]).is_relative_to(source.resolve()), value
            return value

        client = None
        await start_pool()
        try:
            api, client = await server(args.current_python, args.current_source)
            worker = await launch(
                args.current_python,
                args.current_source,
                "worker",
                "--config",
                str(config),
                "--n-jobs-per-worker",
                "1",
            )
            old_tid, old_rid = await submit(client, "short")
            await wait_run(client, old_tid, old_rid, "success")
            evidence.append(
                {
                    "case": "post42-runtime",
                    "run_id": old_rid,
                    **facts(old_rid, "0.13.0.post42", args.current_source),
                }
            )
            tid, rid = await submit(client, "drain")
            await entered(tid)
            _, queued = await submit(client, "short", tid)
            assert (await request(client, "GET", f"/threads/{tid}/runs/{queued}"))[
                "status"
            ] == "pending"
            # Pause new submissions, drain the only Worker, then switch both processes.
            await stop(worker)
            assert worker.returncode == 0
            await wait_run(client, tid, rid, "pending")
            prepared = root / "workspace" / f"{tid}.prepared"
            assert prepared.read_text() == "prepared\n"
            await client.aclose()
            client = None
            await stop(api)
            api, client = await server(args.legacy_python, args.legacy_source)
            worker = await launch(
                args.legacy_python,
                args.legacy_source,
                "worker",
                "--config",
                str(config),
                "--n-jobs-per-worker",
                "1",
            )
            await wait_run(client, tid, rid, "success")
            assert prepared.read_text() == "prepared\n"
            await wait_run(client, tid, queued, "success")
            assert prepared.read_text() == "prepared\nprepared\n"
            for target_tid, target_rid in (
                (old_tid, old_rid),
                (tid, rid),
                (tid, queued),
            ):
                assert (
                    await request(
                        client, "GET", f"/threads/{target_tid}/runs/{target_rid}"
                    )
                )["status"] == "success"
                assert (
                    root / "workspace" / f"{target_tid}.txt"
                ).read_text() == "committed artifact"
                assert await request(
                    client, "POST", f"/threads/{target_tid}/history", json={}
                )
            evidence.append(
                {
                    "case": "matching-post41-rollback",
                    "run_id": rid,
                    "queued_run_id": queued,
                    "worker_exit": 0,
                    "checkpoint_resumed": True,
                    "history_and_artifacts_preserved": True,
                    "schema_migration": False,
                    **facts(rid, "0.13.0.post41", args.legacy_source),
                }
            )
            ordinary_tid, ordinary_rid = await submit(client, "short")
            await wait_run(client, ordinary_tid, ordinary_rid, "success")
            cancel_tid, cancel_rid = await submit(client, "cancel")
            await entered(cancel_tid)
            await request(
                client, "POST", f"/threads/{cancel_tid}/runs/{cancel_rid}/cancel"
            )
            await wait_run(client, cancel_tid, cancel_rid, "interrupted")
            approval_tid, approval_rid = await submit(client, "approval")
            await wait_run(client, approval_tid, approval_rid, "interrupted")
            state = await request(client, "GET", f"/threads/{approval_tid}/state")
            interrupt_id = state["tasks"][0]["interrupts"][0]["id"]
            _, resumed = await submit(
                client, "", approval_tid, {"resume": {interrupt_id: "approve"}}
            )
            assert resumed != approval_rid
            await wait_run(client, approval_tid, resumed, "success")
            evidence.append(
                {
                    "case": "post41-ordinary-cancel-hitl",
                    "ordinary_run": ordinary_rid,
                    "cancel_run": cancel_rid,
                    "approval_run": approval_rid,
                    "resumed_run": resumed,
                    "lease_released": True,
                    **facts(resumed, "0.13.0.post41", args.legacy_source),
                }
            )
        except BaseException:
            for index in range(len(processes)):
                print((root / f"process-{index}.log").read_text()[-6000:])
            raise
        finally:
            if client:
                await client.aclose()
            for process in reversed(processes):
                await stop(process)
            for log in logs:
                log.close()
            await stop_pool()
    args.output.write_text(
        json.dumps({"results": evidence}, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
