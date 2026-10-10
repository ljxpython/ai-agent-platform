"""Controlled evidence through production factories on the disposable stack."""

import json
import runpy
import shlex
import sys
from contextlib import asynccontextmanager
from hashlib import sha256
from pathlib import Path
from uuid import UUID, uuid4

from fixtures.tool_error_platform import platform_app as base_platform_app
from fixtures.tool_error_platform import record

if sys.argv[1:2] != ["platform"]:
    from runtime_service.auth.platform import auth  # noqa: F401 - graph config symbol


def evidence(label):
    lines = [f"ROW_{i:04d} " + "x" * 64 for i in range(1500)]
    lines[600] = "F04_MIDDLE_" + label
    lines[1000] = "F04_RESTORED_" + label
    return "\n".join(lines)


def result_path(label, *, executed=False):
    raw = evidence(label) + (
        "\n[Command succeeded with exit code 0]" if executed else ""
    )
    return f"/large_tool_results/{sha256(raw.encode()).hexdigest()}/budget-large"


async def graph(config, *, showcase=False):
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_core.tools import tool
    from support import BindableFakeMessagesChatModel

    from runtime_service.middlewares import documents
    from runtime_service.services.dearflow_agent import agent as dear
    from runtime_service.services.demo.showcase_demo import agent as demo

    @tool
    def parse_document(path: str) -> str:
        """Return fixed document evidence without external requests."""
        record("large-tool", label=path)
        return evidence(path)

    @tool
    def search_web(query: str) -> str:
        """Return fixed research evidence without external requests."""
        record("large-tool", label=query)
        return evidence(query)

    class EvidenceModel(BindableFakeMessagesChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            prompt = next(
                m.content for m in reversed(messages) if isinstance(m, HumanMessage)
            )
            last = messages[-1]
            record(
                "model-input",
                chars=sum(len(str(m.content)) for m in messages),
                summary="nostream" in (self.tags or []),
                last_type=last.type,
                last_name=getattr(last, "name", None),
                last_tool_call_id=getattr(last, "tool_call_id", None),
            )
            if isinstance(last, ToolMessage):
                if last.name in {"parse_document", "search_web", "execute"}:
                    label = "child" if prompt == "child-budget" else "main"
                    path = result_path(label, executed=last.name == "execute")
                    assert path in str(last.content)
                    response = self.call(
                        "read_file",
                        {
                            "file_path": path,
                            "offset": 600,
                            "limit": 1,
                        },
                        "read-middle",
                    )
                elif last.name == "read_file":
                    canary = "F04_RESTORED_" if prompt == "recover" else "F04_MIDDLE_"
                    assert canary in str(last.content), str(last.content)
                    record("model-read", canary=str(last.content))
                    response = AIMessage(content=str(last.content))
                else:
                    response = AIMessage(content="completed")
            elif prompt == "recover":
                response = self.call(
                    "read_file",
                    {
                        "file_path": result_path("main"),
                        "offset": 1000,
                        "limit": 1,
                    },
                    "read-restored",
                )
            elif prompt == "delegate":
                response = self.call(
                    "task",
                    {
                        "subagent_type": "general-purpose",
                        "description": "child-budget",
                    },
                    "budget-child",
                )
            elif prompt == "child-budget":
                response = self.call(
                    "execute" if showcase else "search_web",
                    {
                        "command": "python -c "
                        + shlex.quote(
                            "import sys; lines=[f'ROW_{i:04d} '+64*'x' for i in range(1500)]; lines[600]='F04_MIDDLE_child'; lines[1000]='F04_RESTORED_child'; sys.stdout.write('\\n'.join(lines))"
                        )
                    }
                    if showcase
                    else {"query": "child"},
                    "budget-large",
                )
            elif prompt == "approval":
                response = self.call(
                    "write_file",
                    {
                        "file_path": "/workspace/work/approved.txt",
                        "content": evidence("approval"),
                    },
                    "budget-write",
                )
            else:
                response = self.call("parse_document", {"path": "main"}, "budget-large")
            return ChatResult(generations=[ChatGeneration(message=response)])

        @staticmethod
        def call(name, args, identifier):
            if name == "read_file":
                identifier += "-" + uuid4().hex[:12]
            return AIMessage(
                content="", tool_calls=[{"name": name, "args": args, "id": identifier}]
            )

    agent = demo if showcase else dear
    agent.build_model = lambda resolved, **kwargs: EvidenceModel(
        responses=[AIMessage(content="initial")],
        profile={"max_input_tokens": 32_000, "max_output_tokens": 2048},
    )
    documents.build_document_tools = lambda workspace: [parse_document]
    dear.build_research_tools = lambda workspace: [search_web]
    return await agent.get_agent(config)


async def showcase_graph(config):
    return await graph(config, showcase=True)


def platform_app(spec):
    from platform_api.adapters.langgraph import threads_sdk_adapter
    from platform_api.core.db import session_scope
    from platform_api.modules.runtime_catalog.infra.sqlalchemy.models import (
        RuntimeCatalogModelRecord,
    )
    from sqlalchemy import select

    app = base_platform_app(spec)
    original_error = threads_sdk_adapter.raise_runtime_upstream_error

    def upstream_error(exc, **kwargs):
        record("upstream-error", error_type=type(exc).__name__, message=str(exc)[:1000])
        return original_error(exc, **kwargs)

    threads_sdk_adapter.raise_runtime_upstream_error = upstream_error
    original = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with original(application):
            with session_scope(app.state.db_session_factory) as session:
                model = session.scalar(
                    select(RuntimeCatalogModelRecord).where(
                        RuntimeCatalogModelRecord.id == UUID(spec["model"])
                    )
                )
                model.context_window_tokens = 32_000
            yield

    app.router.lifespan_context = lifespan
    return app


if __name__ == "__main__":
    if sys.argv[1] == "platform":
        import uvicorn

        spec = json.loads(Path(sys.argv[2]).read_text())
        uvicorn.run(
            platform_app(spec),
            host="127.0.0.1",
            port=spec["platform_port"],
            log_level="error",
            access_log=False,
        )
    else:
        runpy.run_module("fixtures.tool_error_platform", run_name="__main__")
