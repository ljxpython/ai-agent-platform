"""Disposable graph and service roles for stop acceptance; never production config."""

import asyncio
import json
import os
import sys
from pathlib import Path

if __name__ != "__main__" or sys.argv[1] != "platform":
    from runtime_service.auth.platform import auth  # noqa: F401 - fixture config symbol
    from runtime_service.webapp import app  # noqa: F401 - fixture config symbol


def record(event, **fields):
    with Path(os.environ["STOP_PROBE_FACTS"]).open("a") as stream:
        stream.write(json.dumps({"event": event, "pid": os.getpid(), **fields}) + "\n")


async def reference_agent(config):
    return await graph(config, "reference_agent")


async def workflow_demo(config):
    return await graph(config, "workflow_demo")


async def showcase_demo(config):
    return await graph(config, "showcase_demo")


async def dearflow_agent(config):
    return await graph(config, "dearflow_agent")


async def graph(config, graph_id):
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from langchain_core.tools import tool
    from support import BindableFakeMessagesChatModel

    record("factory", graph_id=graph_id)
    if graph_id == "reference_agent":
        from runtime_service.services.reference_agent import agent
    elif graph_id == "workflow_demo":
        from runtime_service.services.demo.workflow_demo import agent
    elif graph_id == "showcase_demo":
        from runtime_service.services.demo.showcase_demo import agent
    else:
        from runtime_service.services.dearflow_agent import agent

    class Model(BindableFakeMessagesChatModel):
        async def _agenerate(self, messages, *args, **kwargs):
            prompt = next(
                (m.content for m in reversed(messages) if isinstance(m, HumanMessage)),
                "",
            )
            if isinstance(prompt, str) and "child-slow" in prompt:
                record("child_started", graph_id=graph_id)
                try:
                    await asyncio.sleep(60)
                finally:
                    record("child_exited", graph_id=graph_id)
            if prompt == "slow-model":
                record("model_started", graph_id=graph_id)
                try:
                    await asyncio.sleep(60)
                finally:
                    record("model_exited", graph_id=graph_id)
            if isinstance(messages[-1], ToolMessage):
                answer = AIMessage(content="probe complete")
            elif prompt == "parallel":
                kind = "research" if graph_id == "showcase_demo" else "general-purpose"
                answer = AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "task",
                            "args": {
                                "subagent_type": kind,
                                "description": "child-slow-" + str(i),
                            },
                            "id": "child-" + str(i),
                        }
                        for i in range(2)
                    ],
                )
            elif prompt == "execute":
                seconds = 8 if os.getenv("RUNTIME_BACKEND") == "docker" else 30
                answer = AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "execute",
                            "args": {
                                "command": "echo started > stop-probe-started.txt; "
                                f"sleep {seconds}; echo leaked > stop-probe-delayed.txt",
                                "timeout": 40,
                            },
                            "id": "execute-probe",
                        }
                    ],
                )
            elif prompt == "approval":
                answer = AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "write_file",
                            "args": {
                                "file_path": "/workspace/work/approved.txt",
                                "content": "once",
                            },
                            "id": "approval-probe",
                        }
                    ],
                )
            elif prompt == "slow":
                name = (
                    "read_reference"
                    if graph_id in {"reference_agent", "workflow_demo"}
                    else "search_web"
                )
                args = (
                    {"topic": "slow"} if name == "read_reference" else {"query": "slow"}
                )
                answer = AIMessage(
                    content="",
                    tool_calls=[{"name": name, "args": args, "id": "slow-probe"}],
                )
            else:
                answer = AIMessage(content="probe complete")
            self.responses = [answer]
            self.i = 0
            return await super()._agenerate(messages, **kwargs)

    @tool
    async def read_reference(topic: str) -> str:
        """Wait until cancelled in the acceptance fixture."""
        record("tool_started", graph_id=graph_id)
        try:
            await asyncio.sleep(60)
        finally:
            record("tool_exited", graph_id=graph_id)
        return "done"

    async def search_provider(*args):
        record("tool_started", graph_id=graph_id)
        try:
            await asyncio.sleep(60)
        finally:
            record("tool_exited", graph_id=graph_id)
            await asyncio.sleep(3)
        return {"results": []}

    agent.build_model = lambda *a, **kw: Model(responses=[AIMessage(content="initial")])
    if graph_id in {"reference_agent", "workflow_demo"}:
        agent.read_reference = read_reference
    if graph_id == "dearflow_agent":
        from runtime_service.services.dearflow_agent.tools import search

        search.tavily = search_provider
    return await agent.get_agent(config)


def platform_app(spec):
    from contextlib import asynccontextmanager
    from uuid import UUID

    from platform_api.core.context.runtime import DEFAULT_TENANT_ID
    from platform_api.core.db import session_scope
    from platform_api.modules.agents.infra.sqlalchemy.models import AgentRecord
    from platform_api.modules.identity.models import UserRecord
    from sqlalchemy import select
    from tool_error_platform import platform_app as base_platform

    app = base_platform(spec)
    original = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with original(application):
            with session_scope(app.state.db_session_factory) as session:
                owner = session.scalar(
                    select(UserRecord.id).where(
                        UserRecord.username == "tool-error-test"
                    )
                )
                for name in ("reference_agent", "workflow_demo", "showcase_demo"):
                    if session.scalar(
                        select(AgentRecord.id).where(
                            AgentRecord.project_id == UUID(spec["project"]),
                            AgentRecord.graph_id == name,
                        )
                    ):
                        continue
                    session.add(
                        AgentRecord(
                            project_id=UUID(spec["project"]),
                            name=name,
                            graph_id=name,
                            created_by=owner,
                            updated_by=owner,
                        )
                    )
            ready = Path(spec["ready"])
            ready.write_text(
                json.dumps(
                    {
                        **json.loads(ready.read_text()),
                        "runtime_tenant": DEFAULT_TENANT_ID,
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

        uvicorn.run(
            create_app(spec["config"], base_dir=Path(path).parent),
            host="127.0.0.1",
            port=spec["runtime_port"],
            log_level="error",
            access_log=False,
        )
    else:
        from langgraph_runtime_pg.production_worker import run_worker

        asyncio.run(run_worker(Path(path).parent / "langgraph.json"))
