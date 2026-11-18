"""Real signed HTTP tools and API authorization, with a deterministic tool-calling model."""

import asyncio
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from support import BindableFakeMessagesChatModel

from runtime_service.services.platform_assistant.agent import CurrentAuthorization
from runtime_service.services.platform_assistant.approval import create_platform_agent
from runtime_service.services.platform_assistant.tools import make_tools


def test_signed_diagnostics_logs_and_source_directory_chain(monkeypatch, tmp_path):
    repo = Path(__file__).resolve().parents[3]
    api = repo / "apps/platform-api"
    process = subprocess.Popen(
        [
            str(api / ".venv/bin/python"),
            str(api / "tests/assistant_validation_server.py"),
            str(tmp_path),
        ],
        cwd=api,
        env={**os.environ, "ASSISTANT_VALIDATION_NO_MODEL": "1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        line = process.stdout.readline()
        assert line, "Synthetic API fixture failed to start"
        config = json.loads(line)
        monkeypatch.setenv(
            "PLATFORM_RUNTIME_MODEL_CONFIG_URL", f"http://127.0.0.1:{config['port']}"
        )
        monkeypatch.setenv("PLATFORM_RUNTIME_DELEGATION_SECRET", config["secret"])
        facts = SimpleNamespace(
            principal=SimpleNamespace(
                user_id=config["actor_id"],
                project_id=config["project_id"],
            )
        )
        model = BindableFakeMessagesChatModel(
            responses=[
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "read_run_diagnostics",
                            "args": {
                                "thread_id": config["target_thread_id"],
                                "run_id": config["cases"]["pre_agent"],
                            },
                            "id": "diagnostics",
                            "type": "tool_call",
                        },
                        {
                            "name": "read_run_logs",
                            "args": {
                                "thread_id": config["target_thread_id"],
                                "run_id": config["cases"]["request_fallback"],
                            },
                            "id": "logs",
                            "type": "tool_call",
                        },
                        {
                            "name": "list_databases",
                            "args": {},
                            "id": "databases",
                            "type": "tool_call",
                        },
                    ],
                ),
                AIMessage(content="已读取工具证据。"),
            ]
        )
        agent = create_platform_agent(
            model, tools=make_tools(facts), middleware=[CurrentAuthorization(facts)]
        )
        state = asyncio.run(
            agent.ainvoke(
                {"messages": [HumanMessage(content="排查合成运行")]},
                {
                    "configurable": {"thread_id": config["thread_id"]},
                    "metadata": {"run_id": str(uuid4())},
                },
            )
        )
        evidence = {
            message.name: json.loads(message.content)
            for message in state["messages"]
            if isinstance(message, ToolMessage)
        }
        assert set(evidence) == {
            "read_run_diagnostics",
            "read_run_logs",
            "list_databases",
        }
        diagnostic = evidence["read_run_diagnostics"]
        assert diagnostic["scope"] == {
            "project_id": config["project_id"],
            "target_project_id": diagnostic["scope"]["target_project_id"],
        }
        assert diagnostic["scope"]["target_project_id"] != config["project_id"]
        assert (
            diagnostic["data"]["persistent_state"]["failed_tasks"][0]["node"]
            == "ExecutionSkillsMiddleware.before_agent"
        )
        assert diagnostic["data"]["persistent_state"]["approval_pending"] is False
        assert (
            evidence["read_run_logs"]["data"]["correlation_type"]
            == "execution_request_id"
        )
        assert evidence["read_run_logs"]["data"]["total"] == 1
        assert (
            evidence["list_databases"]["data"]["empty_reason"] == "no_readable_sources"
        )
        assert all(
            item["audit_recorded"] and len(item["evidence_id"]) == 36
            for item in evidence.values()
        )
        assert "SYNTHETIC-DO-NOT-RETURN" not in json.dumps(evidence)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
