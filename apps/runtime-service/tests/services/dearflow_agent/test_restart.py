"""Real process restart against an explicitly provided disposable PostgreSQL DB."""
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest


def test_process_restart_preserves_pending_approval_and_workspace(tmp_path):
    dsn = os.environ.get("DEAR_TEST_DATABASE_URI")
    if not dsn:
        pytest.skip("DEAR_TEST_DATABASE_URI must point at a disposable PostgreSQL database")
    script = """
import asyncio, os
import faulthandler
faulthandler.dump_traceback_later(60)
from pathlib import Path
from langchain_core.messages import AIMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from support import BindableFakeMessagesChatModel
from test_agent import config, call
from runtime_service.services.dearflow_agent import agent
from runtime_service.services.dearflow_agent.workspace.backend import DearWorkspaceBackend

async def run():
    cfg = config()
    cfg["configurable"]["thread_id"] = os.environ["DEAR_TEST_THREAD"]
    cfg["configurable"]["langgraph_auth_user"]["runtime_scope"]["thread_id"] = os.environ["DEAR_TEST_THREAD"]
    responses = [call("write_file", {"file_path": "/workspace/work/restarted.txt", "content": "once"})] if os.environ["DEAR_TEST_STAGE"] == "pause" else [AIMessage(content="done")]
    model = BindableFakeMessagesChatModel(responses=responses)
    agent.build_model = lambda *args, **kwargs: model
    async with AsyncPostgresSaver.from_conn_string(os.environ["DEAR_TEST_DATABASE_URI"]) as saver:
        await saver.setup()
        graph = await agent.get_agent(cfg)
        graph.checkpointer = saver
        root = DearWorkspaceBackend("tenant", "project", os.environ["DEAR_TEST_THREAD"]).root
        if os.environ["DEAR_TEST_STAGE"] == "pause":
            result = await graph.ainvoke({"messages": [("user", "write")]}, cfg, context={})
            assert result["__interrupt__"]
            assert not (root / "work/restarted.txt").exists()
        else:
            before = await graph.aget_state(cfg)
            assert before.next
            await graph.ainvoke(Command(resume={"decisions": [{"type": "approve"}]}), cfg, context={})
            assert (root / "work/restarted.txt").read_text() == "once"
            assert not (await graph.aget_state(cfg)).next
asyncio.run(run())
faulthandler.cancel_dump_traceback_later()
"""
    env = {
        **os.environ, "RUNTIME_WORKSPACE_ROOT": str(tmp_path),
        "DEAR_TEST_THREAD": str(uuid4()),
        "PYTHONPATH": os.pathsep.join([str(Path("src").resolve()), str(Path("tests").resolve()), str(Path(__file__).parent.resolve())]),
    }
    for stage in ("pause", "resume"):
        try:
            result = subprocess.run([sys.executable, "-c", script], env={**env, "DEAR_TEST_STAGE": stage},
                                    capture_output=True, text=True, timeout=240)
        except subprocess.TimeoutExpired as exc:
            pytest.fail(str(exc.stderr)[-6000:])
        assert result.returncode == 0, result.stderr
