"""Opt-in synthetic task against the configured real model and Docker."""
import asyncio
import hashlib
import os
from pathlib import Path

import pytest
from langchain_core.messages import ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from runtime_service.services.dearflow_agent import agent
from runtime_service.services.dearflow_agent.workspace.backend import DearWorkspaceBackend
from runtime_service.workspace.artifact_refs import ArtifactWorkspace
from runtime_service.workspace.documents import DocumentWorkspace
from .test_agent import config


def test_live_txt_to_approved_artifact(monkeypatch, tmp_path):
    if os.environ.get("DEAR_LIVE_TEST") != "1":
        pytest.skip("DEAR_LIVE_TEST=1 explicitly enables a real model call")
    from dotenv import dotenv_values
    for key, value in dotenv_values(Path(".env")).items():
        if key in {"DEEPSEEK_PROXY_URL", "DEEPSEEK_PROXY_API_KEY"} and value:
            monkeypatch.setenv(key, value)
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path))
    async def run():
        cfg = config()
        workspace = DearWorkspaceBackend("tenant", "project", "dear-thread")
        workspace.prepare()
        raw = b"dear foundation verified"
        upload = DocumentWorkspace(workspace.root).put(raw, hashlib.sha256(raw).hexdigest(), "text/plain", "input.txt")
        graph = await agent.get_agent(cfg)
        graph.checkpointer = InMemorySaver()
        result = await graph.ainvoke({"messages": [("user",
            f"读取 /skills/runtime-smoke/SKILL.md 和 {upload['path']}。"
            "用 execute 在 Python 中把上传文件内容转为大写，写入 /workspace/work/result.txt，"
            "调用 present_artifacts 发布该 TXT。仅操作这个测试文件，无需提问。")]}, cfg, context={})
        approvals = []
        for _ in range(6):
            pending = result.get("__interrupt__")
            if not pending:
                break
            resumes = {}
            for item in pending:
                actions = item.value.get("action_requests", [])
                assert actions, "unexpected clarification for a fully specified task"
                for action in actions:
                    assert action["name"] in {"execute", "write_file", "edit_file", "present_artifacts"}
                    approvals.append(action["name"])
                resumes[item.id] = {"decisions": [{"type": "approve"} for _ in actions]}
            result = await graph.ainvoke(Command(resume=resumes), cfg, context={})
        assert not result.get("__interrupt__")
        assert "execute" in approvals and "present_artifacts" in approvals
        artifacts = list((workspace.root / "outputs").glob("*.txt"))
        assert artifacts
        assert any(ArtifactWorkspace(workspace.root).read("/workspace/outputs/" + p.name)[0].strip() == raw.upper() for p in artifacts)
        assert any(isinstance(m, ToolMessage) and m.name == "read_file" for m in result["messages"])
    asyncio.run(run())
