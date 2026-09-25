"""Real checkpoints, process restart and read-only skill snapshots."""

import os
from pathlib import Path
import subprocess
import sys
import pytest

from .test_p6_governance import package
from runtime_service.services.dearflow_agent.skill_governance import SkillStorage

pytest_plugins = ("tests.services.dearflow_agent.test_p6_governance",)


@pytest.mark.parametrize("change", ["update", "disable", "delete"])
def test_skill_snapshot_survives_process_restart(dsn, tmp_path, change):
    scope = ("tenant", "project", "dear-test")
    store = SkillStorage(dsn)
    a = store.create(scope, package("VALUE_A"), source="test")
    script = r"""
import asyncio, os
from uuid import uuid4
from langchain_core.messages import AIMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command
from support import BindableFakeMessagesChatModel
from test_agent import config, call
from runtime_service.services.dearflow_agent import agent
from runtime_service.services.dearflow_agent.workspace.backend import DearWorkspaceBackend

async def run():
    cfg = config()
    cfg["run_id"] = uuid4()
    stage = os.environ["SKILL_TEST_STAGE"]
    command = '(if test -f "$RUNTIME_SKILLS_ROOT/custom/test-skill/SKILL.md"; then cat "$RUNTIME_SKILLS_ROOT/custom/test-skill/SKILL.md"; else echo ABSENT; fi) > "$RUNTIME_WORKSPACE_ROOT/work/' + stage + '.txt"'
    responses = [AIMessage(content="done")] if stage == "resume" else [call("execute", {"command": command}), AIMessage(content="done")]
    model = BindableFakeMessagesChatModel(responses=responses)
    agent.build_model = lambda *a, **kw: model
    async with AsyncPostgresSaver.from_conn_string(os.environ["DATABASE_URI"]) as saver:
        await saver.setup()
        import langgraph_runtime_pg.checkpoint as cp
        cp.get_checkpointer = lambda: saver
        graph = await agent.get_agent(cfg)
        graph.checkpointer = saver
        assert "dear_skill_snapshot" not in graph.get_input_jsonschema().get("properties", {})
        root = DearWorkspaceBackend("tenant", "project", "dear-thread").root
        if stage == "resume":
            result = await graph.ainvoke(Command(resume={"decisions": [{"type": "approve"}]}), cfg, context={})
            assert (root / "work/pause.txt").exists(), repr(result)
            assert "VALUE_A" in (root / "work/pause.txt").read_text()
        else:
            result = await graph.ainvoke({"messages": [("user", "read skill")]}, cfg, context={})
            assert result["__interrupt__"]
            if stage == "next":
                await graph.ainvoke(Command(resume={"decisions": [{"type": "approve"}]}), cfg, context={})
                assert os.environ["SKILL_TEST_NEXT"] in (root / "work/next.txt").read_text()
        state = await graph.aget_state(cfg)
        assert state.values["dear_skill_snapshot"]
asyncio.run(run())
"""
    env = {
        **os.environ,
        "DATABASE_URI": dsn,
        "RUNTIME_WORKSPACE_ROOT": str(tmp_path),
        "RUNTIME_BACKEND": "local",
        "RUNTIME_DEAR_GOVERNANCE_ENABLED": "1",
        "SKILL_TEST_NEXT": "VALUE_B" if change == "update" else "ABSENT",
        "PYTHONPATH": os.pathsep.join(
            [
                str(Path("src").resolve()),
                str(Path("tests").resolve()),
                str(Path(__file__).parent.resolve()),
            ]
        ),
    }
    for stage in ("pause", "resume", "next"):
        result = subprocess.run(
            [sys.executable, "-c", script],
            env={**env, "SKILL_TEST_STAGE": stage},
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert result.returncode == 0, result.stderr[-10000:]
        if stage == "pause":
            if change == "update":
                store.update(
                    scope,
                    "test-skill",
                    package("VALUE_B"),
                    expected_revision=a["revision"],
                )
            elif change == "disable":
                store.set_enabled(
                    scope, "test-skill", enabled=False, expected_revision=a["revision"]
                )
            else:
                store.delete(scope, "test-skill", expected_revision=a["revision"])


def test_child_file_tools_share_resumed_snapshot(dsn, tmp_path, monkeypatch):
    import asyncio
    from deepagents import create_deep_agent
    from langchain_core.messages import AIMessage, ToolMessage
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.types import Command
    from support import BindableFakeMessagesChatModel
    from .test_agent import config, call
    from runtime_service.services.dearflow_agent.middleware.skills import (
        ExecutionSkillsMiddleware,
    )
    from runtime_service.services.dearflow_agent.workspace.backend import (
        DearWorkspaceBackend,
        build_backend,
    )

    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path))
    scope = ("tenant", "project", "dear-test")
    store = SkillStorage(dsn)
    a = store.create(scope, package("CHILD_VALUE_A"), source="test")
    seen = []

    class ChildModel(BindableFakeMessagesChatModel):
        async def _agenerate(self, messages, *args, **kwargs):
            seen.extend(m.content for m in messages if isinstance(m, ToolMessage))
            return await super()._agenerate(messages, *args, **kwargs)

    saver = InMemorySaver()

    def graph(resuming):
        workspace = DearWorkspaceBackend("tenant", "project", "dear-thread")
        backend = build_backend(workspace)
        return create_deep_agent(
            model=BindableFakeMessagesChatModel(
                responses=[AIMessage(content="done")]
                if resuming
                else [
                    call(
                        "task", {"description": "Read skill", "subagent_type": "reader"}
                    )
                ]
            ),
            backend=backend,
            middleware=[
                ExecutionSkillsMiddleware(workspace, backend, custom_enabled=True)
            ],
            subagents=[
                {
                    "name": "reader",
                    "description": "Read a skill",
                    "system_prompt": "Read only",
                    "model": ChildModel(
                        responses=[
                            call(
                                "read_file",
                                {"file_path": "/skills/custom/test-skill/SKILL.md"},
                            ),
                            AIMessage(content="child done"),
                        ]
                    ),
                }
            ],
            interrupt_on={"task": True},
            checkpointer=saver,
        )

    async def run():
        cfg = config()
        result = await graph(False).ainvoke({"messages": [("user", "delegate")]}, cfg)
        assert result["__interrupt__"]
        store.update(
            scope,
            "test-skill",
            package("CHILD_VALUE_B"),
            expected_revision=a["revision"],
        )
        await graph(True).ainvoke(
            Command(resume={"decisions": [{"type": "approve"}]}), cfg
        )
        assert any("CHILD_VALUE_A" in str(text) for text in seen)
        assert not any("CHILD_VALUE_B" in str(text) for text in seen)

    asyncio.run(run())
