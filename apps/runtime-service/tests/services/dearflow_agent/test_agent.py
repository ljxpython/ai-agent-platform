from __future__ import annotations

import asyncio

import pytest
from langchain_core.messages import AIMessage
from langchain_core.messages import ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from support import BindableFakeMessagesChatModel

from runtime_service.runtime import RuntimeAuthError, RuntimeResolutionError, runtime_context_hash
from runtime_service.services.dearflow_agent import agent
from runtime_service.services.dearflow_agent.workspace.backend import DearWorkspaceBackend
from runtime_service.workspace.artifact_refs import ArtifactWorkspace


class User(dict):
    identity = "dear-test"
    is_authenticated = True
    display_name = "Dear test"
    permissions = ()


def config():
    return {
        "context": {},
        "configurable": {
            "thread_id": "dear-thread",
            "assistant_id": "dearflow_agent",
            "graph_id": "dearflow_agent",
            "langgraph_auth_user": User(
                runtime_principal={
                    "user_id": "dear-test", "tenant_id": "tenant",
                    "project_id": "project", "role": "developer",
                    "permissions": sorted(set(agent._TOOL_PERMISSIONS.values())),
                },
                runtime_policy={
                    "version": "test-v1",
                    "allowed_model_ids": [agent._DEFAULTS.model_id],
                    "allowed_tool_names": list(agent._DEFAULTS.optional_tool_names),
                },
                runtime_scope={
                    "tenant_id": "tenant", "project_id": "project",
                    "thread_id": "dear-thread", "assistant_id": "dearflow_agent",
                    "operation": "run-create",
                },
                runtime_context_hash=runtime_context_hash({}),
            ),
        },
    }


def call(name, args, identifier="tool-1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": identifier}])


@pytest.fixture
def build(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path))

    async def create(responses, cfg=None, saver=None):
        cfg = cfg or config()
        model = BindableFakeMessagesChatModel(responses=responses)
        monkeypatch.setattr(agent, "build_model", lambda *args, **kwargs: model)
        graph = await agent.get_agent(cfg)
        graph.checkpointer = saver or InMemorySaver()
        return graph, cfg

    return create


@pytest.mark.parametrize("decision", ["approve", "edit", "reject"])
def test_approval_controls_file_effects(build, decision):
    async def run():
        graph, cfg = await build([
            call("write_file", {"file_path": "/workspace/work/result.txt", "content": "original"}),
            AIMessage(content="done"),
        ])
        root = DearWorkspaceBackend("tenant", "project", "dear-thread").root
        result = await graph.ainvoke({"messages": [("user", "write")]}, cfg, context={})
        assert result["__interrupt__"][0].value["action_requests"][0]["name"] == "write_file"
        assert not (root / "work/result.txt").exists()
        action = {"type": decision}
        if decision == "edit":
            action["edited_action"] = {
                "name": "write_file",
                "args": {"file_path": "/workspace/work/result.txt", "content": "reviewed"},
            }
        await graph.ainvoke(Command(resume={"decisions": [action]}), cfg, context={})
        assert (root / "work/result.txt").exists() == (decision != "reject")
        if decision != "reject":
            assert (root / "work/result.txt").read_text() == ("reviewed" if decision == "edit" else "original")
    asyncio.run(run())


def test_clarification_and_rebuilt_graph_resume(build):
    async def run():
        saver = InMemorySaver()
        question = {"question": "Language?", "fields": [
            {"name": "language", "label": "Language", "type": "select",
             "options": [{"value": "zh", "label": "中文"}]},
            {"name": "title", "label": "Title", "type": "text"},
        ]}
        graph, cfg = await build([call("request_information", question)], saver=saver)
        result = await graph.ainvoke({"messages": [("user", "report")]}, cfg, context={})
        pending = result["__interrupt__"][0]
        assert pending.value["kind"] == "clarification"
        graph, cfg = await build([AIMessage(content="done")], cfg, saver)
        answer = {"schema_version": 1, "status": "answered", "values": {"language": "zh", "title": "报告"}}
        result = await graph.ainvoke(Command(resume={pending.id: answer}), cfg, context={})
        assert result["messages"][-1].content == "done"
        assert not (await graph.aget_state(cfg)).next
    asyncio.run(run())


def test_mixed_clarification_has_no_file_effect(build):
    async def run():
        question = {"question": "Title?", "fields": [{"name": "title", "label": "Title", "type": "text"}]}
        message = call("request_information", question)
        message.tool_calls += call("write_file", {"file_path": "/workspace/work/bad.txt", "content": "bad"}, "write").tool_calls
        graph, cfg = await build([message])
        with pytest.raises(ValueError, match="clarification_requires"):
            await graph.ainvoke({"messages": [("user", "write")]}, cfg, context={})
        root = DearWorkspaceBackend("tenant", "project", "dear-thread").root
        assert not (root / "work/bad.txt").exists()
    asyncio.run(run())


@pytest.mark.parametrize("target", ["thread", "graph", "context"])
def test_untrusted_target_rejected(build, target):
    async def run():
        cfg = config()
        if target == "thread":
            cfg["configurable"]["thread_id"] = "other"
        elif target == "graph":
            cfg["configurable"]["langgraph_auth_user"]["runtime_scope"]["assistant_id"] = "other"
        else:
            cfg["context"] = {"temperature": 0.4}
        with pytest.raises(RuntimeAuthError):
            await build([AIMessage(content="must not run")], cfg)
    asyncio.run(run())


@pytest.mark.parametrize("path", [
    "/workspace/uploads/input.txt", "/workspace/outputs/result.txt",
    "/skills/runtime-smoke/SKILL.md", "/workspace/work/../outputs/bad.txt",
])
def test_approved_write_cannot_modify_protected_files(build, path):
    async def run():
        graph, cfg = await build([
            call("write_file", {"file_path": path, "content": "bad"}),
            AIMessage(content="done"),
        ])
        result = await graph.ainvoke({"messages": [("user", "write")]}, cfg, context={})
        if result.get("__interrupt__"):
            result = await graph.ainvoke(Command(resume={"decisions": [{"type": "approve"}]}), cfg, context={})
        output = next(m for m in result["messages"] if isinstance(m, ToolMessage))
        assert "denied" in str(output.content).lower() or "permission" in str(output.content).lower() or "traversal" in str(output.content).lower()
    asyncio.run(run())


def test_real_container_process_and_publish_after_approval(build):
    async def run():
        graph, cfg = await build([
            call("read_file", {"file_path": "/skills/runtime-smoke/SKILL.md"}, "skill"),
            call("execute", {"command": "printf 'verified result' > result.txt"}, "execute"),
            call("present_artifacts", {"file_path": "/workspace/work/result.txt"}, "publish"),
            AIMessage(content="done"),
        ])
        result = await graph.ainvoke({"messages": [("user", "produce a file")]}, cfg, context={})
        assert result["__interrupt__"][0].value["action_requests"][0]["name"] == "execute"
        result = await graph.ainvoke(Command(resume={"decisions": [{"type": "approve"}]}), cfg, context={})
        output = next(m for m in result["messages"] if isinstance(m, ToolMessage) and m.name == "execute")
        assert output.artifact["exit_code"] == 0, output.content
        assert result["__interrupt__"][0].value["action_requests"][0]["name"] == "present_artifacts"
        root = DearWorkspaceBackend("tenant", "project", "dear-thread").root
        assert not list((root / "outputs").iterdir())
        result = await graph.ainvoke(Command(resume={"decisions": [{"type": "approve"}]}), cfg, context={})
        import json
        output = next(m for m in result["messages"] if isinstance(m, ToolMessage) and m.name == "present_artifacts")
        ref = json.loads(output.content)
        assert ArtifactWorkspace(root).read(ref["path"])[0] == b"verified result"
        (root / "work/result.txt").write_text("changed")
        assert ArtifactWorkspace(root).read(ref["path"])[0] == b"verified result"
    asyncio.run(run())


def test_schema_probe_has_no_model_or_workspace_io(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path / "absent"))
    def forbidden(*args, **kwargs):
        pytest.fail("schema probe initialized external resources")
    monkeypatch.setattr(agent, "build_model", forbidden)
    monkeypatch.setattr(agent, "fetch_model_connection", forbidden)
    async def run():
        graph = await agent.get_agent({})
        assert "messages" in graph.get_input_jsonschema()["properties"]
        with pytest.raises(RuntimeAuthError):
            await graph.ainvoke({"messages": [("user", "must not execute")]}, context={})
        assert not (tmp_path / "absent").exists()
    asyncio.run(run())


@pytest.mark.parametrize("tool_name,args", [
    ("task", {"description": "delegate", "subagent_type": "general-purpose"}),
    ("write_todos", {"todos": [{"content": "plan", "status": "pending"}]}),
])
def test_standard_rejects_planning_and_delegation(build, tool_name, args):
    async def run():
        graph, cfg = await build([call(tool_name, args), AIMessage(content="done")])
        with pytest.raises(RuntimeResolutionError, match="runtime.tool.not_allowed"):
            await graph.ainvoke({"messages": [("user", "work")]}, cfg, context={})
    asyncio.run(run())


def test_consecutive_clarifications_have_distinct_interrupt_ids(build):
    async def run():
        question = {"question": "Title?", "fields": [{"name": "title", "label": "Title", "type": "text"}]}
        graph, cfg = await build([
            call("request_information", question, "first"),
            call("request_information", question, "second"),
            AIMessage(content="done"),
        ])
        result = await graph.ainvoke({"messages": [("user", "work")]}, cfg, context={})
        first = result["__interrupt__"][0]
        answer = {"schema_version": 1, "status": "answered", "values": {"title": "value"}}
        result = await graph.ainvoke(Command(resume={first.id: answer}), cfg, context={})
        second = result["__interrupt__"][0]
        assert first.id != second.id
        result = await graph.ainvoke(Command(resume={second.id: answer}), cfg, context={})
        assert result["messages"][-1].content == "done"
    asyncio.run(run())
