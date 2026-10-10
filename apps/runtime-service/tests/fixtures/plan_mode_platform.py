"""Controlled model, production graph factories and disposable HTTP/Worker roles."""

import os
import runpy
import sys
from importlib import import_module
from uuid import uuid4

from fixtures.tool_error_platform import record  # noqa: F401 - config symbol

if sys.argv[1:2] != ["platform"]:
    from runtime_service.auth.platform import auth  # noqa: F401 - config symbol


async def _graph(config, module, *, writable=False):
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from support import BindableFakeMessagesChatModel

    root = import_module(module)
    if os.getenv("PLAN_MODE_LIVE_TEST") == "1":
        return await root.get_agent(config)

    class PlanningModel(BindableFakeMessagesChatModel):
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            prompt = next(
                (m.content for m in reversed(messages) if isinstance(m, HumanMessage)),
                "plan",
            )
            latest = messages[-1]
            if isinstance(latest, ToolMessage):
                if latest.name == "save_plan" or "Plan draft saved" in str(
                    latest.content
                ):
                    response = self.call("submit_plan", {})
                elif "Plan changes requested" in str(latest.content):
                    response = self.call(
                        "save_plan",
                        {
                            "title": "Revised plan",
                            "markdown": "Read, validate, then execute with existing permissions.",
                        },
                    )
                elif "Plan approved" in str(latest.content) and writable:
                    record("business_write_requested")
                    response = self.call(
                        "write_file",
                        {
                            "file_path": "/workspace/work/approved.txt",
                            "content": "once",
                        },
                    )
                else:
                    response = AIMessage(content="done")
            elif prompt == "denied":
                response = self.call("execute", {"command": "touch leaked.txt"})
            else:
                response = self.call(
                    "save_plan",
                    {
                        "title": "Implementation plan",
                        "markdown": "Read, validate, then execute with existing permissions.",
                    },
                )
            self.responses, self.i = [response], 0
            return super()._generate(
                messages, stop=stop, run_manager=run_manager, **kwargs
            )

        @staticmethod
        def call(name, args):
            return AIMessage(
                content="",
                tool_calls=[{"name": name, "args": args, "id": uuid4().hex}],
            )

    root.build_model = lambda *args, **kwargs: PlanningModel(
        responses=[AIMessage(content="initial")]
    )
    return await root.get_agent(config)


async def graph(config):
    return await _graph(
        config, "runtime_service.services.dearflow_agent.agent", writable=True
    )


async def showcase_graph(config):
    return await _graph(
        config, "runtime_service.services.demo.showcase_demo.agent", writable=True
    )


async def reference_graph(config):
    return await _graph(config, "runtime_service.services.reference_agent.agent")


async def workflow_graph(config):
    return await _graph(config, "runtime_service.services.demo.workflow_demo.agent")


if __name__ == "__main__":
    runpy.run_module("fixtures.tool_error_platform", run_name="__main__")
