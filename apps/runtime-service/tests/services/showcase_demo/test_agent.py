from __future__ import annotations

import asyncio
import copy
import os
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import Field
from support import BindableFakeMessagesChatModel

from runtime_service.runtime import (
    RuntimeAuthError,
    RuntimeResolutionError,
    runtime_context_hash,
)
from runtime_service.services.demo.showcase_demo import agent
from runtime_service.services.demo.showcase_demo.backend import DockerWorkspaceBackend


class User(dict):
    identity = "teaching-user"
    is_authenticated = True
    display_name = "Teaching user"
    permissions = ()


class RecordingModel(BindableFakeMessagesChatModel):
    seen_messages: list = Field(default_factory=list)
    seen_tools: list = Field(default_factory=list)

    def bind_tools(self, tools, **kwargs):
        self.seen_tools.append([tool.name for tool in tools])
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen_messages.append(messages)
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def config(*, context=None, thread_id="teaching-thread", denied=()):
    context = context or {}
    user = User(
        runtime_principal={
            "user_id": "teaching-user",
            "tenant_id": "tenant",
            "project_id": "project",
            "role": "developer",
            "permissions": [],
        },
        runtime_policy={
            "version": "test-v1",
            "allowed_model_ids": [agent._DEFAULTS.model_id],
            "tool_overrides": dict.fromkeys(denied, False), "tool_policy_version": "test-tools-v2",
        },
        runtime_scope={
            "tenant_id": "tenant",
            "project_id": "project",
            "thread_id": thread_id,
            "assistant_id": "teaching-assistant",
            "operation": "run-create",
        },
        runtime_context_hash=runtime_context_hash(context),
    )
    return {
        "context": context,
        "configurable": {
            "langgraph_auth_user": user,
            "thread_id": thread_id,
            "assistant_id": "teaching-assistant",
            "graph_id": "showcase_demo",
        },
    }


def call(name, args, identifier="t1"):
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": identifier}]
    )


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_artifact_publication_approval_and_checkpoint(build, decision):
    import json

    from runtime_service.workspace.artifact_refs import ArtifactWorkspace
    from runtime_service.workspace.scoped import resolve_thread_workspace

    async def run():
        graph, cfg, _ = await build([
            call("present_artifacts", {"file_path": "/workspace/work/payment.yaml"}),
            AIMessage(content="Publication handled."),
        ])
        root = resolve_thread_workspace("tenant", "project", "teaching-thread", "showcase_demo")
        (root / "work").mkdir(parents=True, exist_ok=True)
        (root / "work/payment.yaml").write_text("openapi: 3.1.0")
        result = await graph.ainvoke({"messages": [("user", "Publish the OpenAPI file")]}, cfg)
        assert result["__interrupt__"][0].value["action_requests"][0]["name"] == "present_artifacts"
        assert not (root / "outputs").exists()
        result = await graph.ainvoke(Command(resume={"decisions": [{"type": decision}]}), cfg)
        if decision == "approve":
            message = next(m for m in result["messages"] if isinstance(m, ToolMessage) and m.name == "present_artifacts")
            ref = json.loads(message.content)
            assert ArtifactWorkspace(root).read(ref["path"])[0] == b"openapi: 3.1.0"
            restored = await graph.aget_state(cfg)
            assert any(isinstance(m, ToolMessage) and ref["path"] in str(m.content) for m in restored.values["messages"])
        else:
            assert not (root / "outputs").exists()

    asyncio.run(run())


@pytest.fixture
def build(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path))

    async def create(responses, cfg=None):
        cfg = cfg or config()
        model = RecordingModel(responses=responses)
        monkeypatch.setattr(agent, "build_model", lambda *args, **kwargs: model)
        graph = await agent.get_agent(cfg)
        graph.checkpointer = InMemorySaver()
        return graph, cfg, model

    return create


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_local_execute_requires_approval(build, monkeypatch, tmp_path, decision):
    monkeypatch.setenv("RUNTIME_BACKEND", "local")

    async def run():
        graph, cfg, _ = await build([
            call("execute", {"command": "python report.py > result.txt"}),
            AIMessage(content="done"),
        ])
        result = await graph.ainvoke({"messages": [("user", "run report")]}, cfg, context={})
        assert result["__interrupt__"][0].value["action_requests"][0]["name"] == "execute"
        assert not list(tmp_path.rglob("result.txt"))
        result = await graph.ainvoke(
            Command(resume={"decisions": [{"type": decision}]}), cfg, context={}
        )
        outputs = list(tmp_path.rglob("result.txt"))
        assert bool(outputs) == (decision == "approve")
        if outputs:
            assert "27.00" in outputs[0].read_text()

    asyncio.run(run())


def test_skills_discovered_read_and_todos_streamed(build):
    async def run():
        pending = [{"content": "Inspect report", "status": "pending"}]
        completed = [{"content": "Inspect report", "status": "completed"}]
        graph, cfg, model = await build(
            [
                call("write_todos", {"todos": pending}),
                call(
                    "read_file", {"file_path": "/skills/showcase-notes/SKILL.md"}, "t2"
                ),
                call("write_todos", {"todos": completed}, "t3"),
                AIMessage(content="done"),
            ]
        )
        values = [
            chunk
            async for chunk in graph.astream(
                {"messages": [("user", "inspect")]},
                cfg,
                context=cfg["context"],
                stream_mode="values",
            )
        ]
        assert any(chunk.get("todos") == pending for chunk in values)
        assert values[-1]["todos"] == completed
        state = await graph.aget_state(cfg)
        assert [skill["name"] for skill in state.values["skills_metadata"]] == [
            "showcase-notes"
        ]
        assert any(
            isinstance(m, ToolMessage) and "43.50" in str(m.content)
            for m in values[-1]["messages"]
        )
        assert "showcase-notes" in str(model.seen_messages[0][0].content)

    asyncio.run(run())


def test_workspace_write_skips_file_approval(build):
    async def run():
        graph, cfg, _ = await build(
            [
                call("write_file", {"file_path": "/workspace/new.txt", "content": "approved by policy"}),
                AIMessage(content="done"),
            ],
            config(context={"access_policy": "workspace_write"}),
        )
        result = await graph.ainvoke({"messages": [("user", "write")]}, cfg, context=cfg["context"])
        assert not result.get("__interrupt__")
        workspace = DockerWorkspaceBackend("tenant", "project", "teaching-thread").cwd / "workspace"
        assert (workspace / "new.txt").read_text() == "approved by policy"

    asyncio.run(run())


@pytest.mark.parametrize("decision", ["approve", "reject", "edit"])
def test_approval_controls_actual_file_effects(build, decision):
    async def run():
        graph, cfg, _ = await build(
            [
                call(
                    "write_file",
                    {"file_path": "/workspace/new.txt", "content": "original"},
                ),
                AIMessage(content="done"),
            ]
        )
        result = await graph.ainvoke({"messages": [("user", "write")]}, cfg, context={})
        payload = result["__interrupt__"][0].value
        assert payload["action_requests"][0]["name"] == "write_file"
        assert set(payload["review_configs"][0]["allowed_decisions"]) == {
            "approve",
            "reject",
            "edit",
        }
        workspace = (
            DockerWorkspaceBackend("tenant", "project", "teaching-thread").cwd
            / "workspace"
        )
        assert not (workspace / "new.txt").exists()
        action = {"type": decision}
        if decision == "edit":
            action["edited_action"] = {
                "name": "write_file",
                "args": {
                    "file_path": "/workspace/edited.txt",
                    "content": "reviewed",
                },
            }
        await graph.ainvoke(Command(resume={"decisions": [action]}), cfg, context={})
        assert not (await graph.aget_state(cfg)).next
        assert (workspace / "new.txt").exists() == (decision == "approve")
        if decision == "edit":
            assert (workspace / "edited.txt").read_text() == "reviewed"

    asyncio.run(run())


@pytest.mark.parametrize("invalid", [False, True])
def test_batch_approval_requires_all_decisions(build, invalid):
    async def run():
        message = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "write_file",
                    "args": {"file_path": f"/workspace/{name}", "content": name},
                    "id": name,
                }
                for name in ("a.txt", "b.txt")
            ],
        )
        graph, cfg, _ = await build([message, AIMessage(content="done")])
        result = await graph.ainvoke(
            {"messages": [("user", "write two files")]}, cfg, context={}
        )
        assert len(result["__interrupt__"]) == 1
        assert len(result["__interrupt__"][0].value["action_requests"]) == 2
        if invalid:
            with pytest.raises(ValueError):
                await graph.ainvoke(
                    Command(resume={"decisions": [{"type": "approve"}]}),
                    cfg,
                    context={},
                )
            root = (
                DockerWorkspaceBackend("tenant", "project", "teaching-thread").cwd
                / "workspace"
            )
            assert not (root / "a.txt").exists()
            assert not (root / "b.txt").exists()
            return
        await graph.ainvoke(
            Command(
                resume={
                    "decisions": [
                        {"type": "approve"},
                        {"type": "reject", "message": "omit b"},
                    ]
                }
            ),
            cfg,
            context={},
        )
        root = (
            DockerWorkspaceBackend("tenant", "project", "teaching-thread").cwd
            / "workspace"
        )
        assert (root / "a.txt").read_text() == "a.txt"
        assert not (root / "b.txt").exists()

    asyncio.run(run())


def test_subagent_emits_namespaced_messages_and_cannot_write(build):
    async def run():
        graph, cfg, model = await build(
            [
                call(
                    "task",
                    {
                        "subagent_type": "research",
                        "description": "Read the sales data.",
                    },
                ),
                call("read_file", {"file_path": "/workspace/sales.csv"}, "read"),
                AIMessage(content="Found Notebook and Pen sales."),
                AIMessage(content="Analysis complete."),
            ]
        )
        events = [
            event
            async for event in graph.astream(
                {"messages": [("user", "analyze only")]},
                cfg,
                context={},
                subgraphs=True,
                version="v2",
                stream_mode=["messages", "updates"],
            )
        ]
        assert any(event["ns"] and event["type"] == "messages" for event in events)
        child_tools = [names for names in model.seen_tools if "task" not in names]
        assert child_tools and all(
            set(names) <= {"ls", "read_file", "grep", "glob"} for names in child_tools
        )
        state = await graph.aget_state(cfg)
        assert "Analysis complete." == state.values["messages"][-1].content

    asyncio.run(run())


def test_subagent_write_interrupt_can_resume(build):
    async def run():
        graph, cfg, _ = await build(
            [
                call(
                    "task",
                    {
                        "subagent_type": "general-purpose",
                        "description": "Write /workspace/sub.txt.",
                    },
                ),
                call(
                    "write_file",
                    {"file_path": "/workspace/sub.txt", "content": "child"},
                    "child-write",
                ),
                AIMessage(content="Child done."),
                AIMessage(content="Parent done."),
            ]
        )
        result = await graph.ainvoke(
            {"messages": [("user", "implement")]}, cfg, context={}
        )
        interrupts = result["__interrupt__"]
        assert interrupts[0].value["action_requests"][0]["name"] == "write_file"
        result = await graph.ainvoke(
            Command(resume={interrupts[0].id: {"decisions": [{"type": "approve"}]}}),
            cfg,
            context={},
        )
        assert result["messages"][-1].content == "Parent done."
        root = (
            DockerWorkspaceBackend("tenant", "project", "teaching-thread").cwd
            / "workspace"
        )
        assert (root / "sub.txt").read_text() == "child"

    asyncio.run(run())


def test_empty_tool_allowlist_and_wrong_context_fail_closed(build):
    async def run():
        cfg = config(denied=agent._DEFAULTS.optional_tool_names)
        graph, cfg, _ = await build([call("write_todos", {"todos": []})], cfg)
        with pytest.raises(RuntimeResolutionError, match="runtime.tool.not_allowed"):
            await graph.ainvoke(
                {"messages": [("user", "try tool")]}, cfg, context=cfg["context"]
            )
        with pytest.raises(RuntimeAuthError, match="context_hash_mismatch"):
            await graph.ainvoke(
                {"messages": [("user", "wrong context")]},
                cfg,
                context={"temperature": 0.2},
            )
        cfg["context"] = {"temperature": 0.4}
        with pytest.raises(RuntimeAuthError, match="context_hash_mismatch"):
            await agent.get_agent(cfg)

    asyncio.run(run())


def test_bound_workspace_cannot_be_reused_by_another_tenant(build):
    async def run():
        graph, cfg, _ = await build([AIMessage(content="ok")])
        other = copy.deepcopy(cfg)
        user = other["configurable"]["langgraph_auth_user"]
        user["runtime_principal"]["tenant_id"] = "other"
        user["runtime_scope"]["tenant_id"] = "other"
        with pytest.raises(RuntimeAuthError, match="workspace.scope_mismatch"):
            await graph.ainvoke(
                {"messages": [("user", "wrong tenant")]}, other, context={}
            )

    asyncio.run(run())


def test_probe_has_no_io_and_cannot_be_invoked(monkeypatch, tmp_path):
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path / "absent"))

    def forbidden(*args, **kwargs):
        pytest.fail("Probe attempted external model/backend initialization")

    monkeypatch.setattr(agent, "build_model", forbidden)
    monkeypatch.setattr(agent, "fetch_model_connection", forbidden)
    monkeypatch.setattr(DockerWorkspaceBackend, "prepare", forbidden)

    async def run():
        graph = await agent.get_agent({})
        assert "todos" in graph.get_output_jsonschema()["properties"]
        assert not (tmp_path / "absent").exists()
        with pytest.raises(RuntimeAuthError):
            await graph.ainvoke({"messages": [("user", "do not execute")]})
        with pytest.raises(RuntimeAuthError, match="test_adapter_forbidden"):
            await agent.get_agent({"configurable": {"_runtime_test_local_auth": True}})

    asyncio.run(run())


def test_skill_write_and_edited_unauthorized_action_are_denied(build):
    async def run():
        resource = Path(agent.__file__).parent / "skills/showcase-notes/SKILL.md"
        original = resource.read_bytes()
        graph, cfg, _ = await build(
            [
                call(
                    "write_file",
                    {
                        "file_path": "/skills/showcase-notes/SKILL.md",
                        "content": "replace",
                    },
                ),
                AIMessage(content="denied"),
            ]
        )
        await graph.ainvoke({"messages": [("user", "try write")]}, cfg, context={})
        result = await graph.ainvoke(
            Command(resume={"decisions": [{"type": "approve"}]}), cfg, context={}
        )
        assert resource.read_bytes() == original
        assert any(
            isinstance(m, ToolMessage) and "denied" in str(m.content).lower()
            for m in result["messages"]
        )

        cfg = config(denied=("execute",), thread_id="edited-action")
        graph, cfg, _ = await build(
            [
                call(
                    "write_file", {"file_path": "/workspace/a.txt", "content": "text"}
                ),
                AIMessage(content="must not execute"),
            ],
            cfg,
        )
        await graph.ainvoke(
            {"messages": [("user", "write")]}, cfg, context=cfg["context"]
        )
        with pytest.raises(RuntimeResolutionError, match="runtime.tool.not_allowed"):
            await graph.ainvoke(
                Command(
                    resume={
                        "decisions": [
                            {
                                "type": "edit",
                                "edited_action": {
                                    "name": "execute",
                                    "args": {"command": "echo forbidden"},
                                },
                            }
                        ]
                    }
                ),
                cfg,
                context=cfg["context"],
            )

    asyncio.run(run())


@pytest.mark.integration
def test_graph_approval_runs_real_python_and_preserves_exit_code(build):
    async def run():
        graph, cfg, _ = await build(
            [
                call(
                    "edit_file",
                    {
                        "file_path": "/workspace/report.py",
                        "old_string": 'Decimal(row["unit_price"])',
                        "new_string": 'Decimal(row["unit_price"]) * int(row["quantity"])',
                    },
                ),
                call(
                    "execute",
                    {"command": "python report.py > result.txt && cat result.txt"},
                    "execute",
                ),
                AIMessage(content="Verified 43.50."),
            ]
        )
        result = await graph.ainvoke(
            {"messages": [("user", "fix and verify")]}, cfg, context={}
        )
        assert (
            result["__interrupt__"][0].value["action_requests"][0]["name"]
            == "edit_file"
        )
        result = await graph.ainvoke(
            Command(resume={"decisions": [{"type": "approve"}]}), cfg, context={}
        )
        assert (
            result["__interrupt__"][0].value["action_requests"][0]["name"] == "execute"
        )
        result = await graph.ainvoke(
            Command(resume={"decisions": [{"type": "approve"}]}), cfg, context={}
        )
        output = next(
            m
            for m in result["messages"]
            if isinstance(m, ToolMessage) and m.name == "execute"
        )
        assert output.artifact["exit_code"] == 0, output.content
        assert "43.50" in str(output.content)
        workspace = (
            DockerWorkspaceBackend("tenant", "project", "teaching-thread").cwd
            / "workspace"
        )
        assert "43.50" in (workspace / "result.txt").read_text()

    asyncio.run(run())


@pytest.mark.e2e
def test_live_model_reads_real_project_and_streams(monkeypatch, tmp_path):
    if os.getenv("RUNTIME_SHOWCASE_LIVE_TEST") != "1":
        pytest.skip(
            "Set RUNTIME_SHOWCASE_LIVE_TEST=1 to call the configured real model"
        )
    from dotenv import dotenv_values

    for key, value in dotenv_values(
        Path(__file__).resolve().parents[3] / ".env"
    ).items():
        if value is not None and key in {
            "DEEPSEEK_PROXY_URL",
            "DEEPSEEK_PROXY_API_KEY",
        }:
            monkeypatch.setenv(key, value)
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path))

    async def run():
        cfg = config(
            denied=("write_file", "edit_file", "execute"),
            thread_id="live-model",
        )
        graph = await agent.get_agent(cfg)
        graph.checkpointer = InMemorySaver()
        events = [
            event
            async for event in graph.astream(
                {
                    "messages": [
                        (
                            "user",
                            "读取技能和 /workspace/report.py、sales.csv，解释统计错误。只读，不修改不运行。给出正确金额。",
                        )
                    ]
                },
                cfg,
                context=cfg["context"],
                stream_mode=["messages", "values"],
                version="v2",
            )
        ]
        values = [e["data"] for e in events if e["type"] == "values"]
        assert any(e["type"] == "messages" for e in events)
        messages = values[-1]["messages"]
        assert any(
            isinstance(m, ToolMessage) and m.name == "read_file" for m in messages
        )
        assert "43.5" in str(messages[-1].content)

    asyncio.run(run())


def test_parallel_subagent_interrupts_resume_by_id(build):
    async def run():
        delegates = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "task",
                    "args": {
                        "subagent_type": "general-purpose",
                        "description": f"Write /workspace/{name}.txt",
                    },
                    "id": name,
                }
                for name in ("first", "second")
            ],
        )
        graph, cfg, _ = await build(
            [
                delegates,
                call(
                    "write_file",
                    {"file_path": "/workspace/first.txt", "content": "first"},
                    "write-first",
                ),
                call(
                    "write_file",
                    {"file_path": "/workspace/second.txt", "content": "second"},
                    "write-second",
                ),
                AIMessage(content="Child done."),
                AIMessage(content="Child done."),
                AIMessage(content="Parent done."),
            ]
        )
        result = await graph.ainvoke(
            {"messages": [("user", "Delegate both tasks")]}, cfg, context={}
        )
        pending = result["__interrupt__"]
        assert len(pending) == 2
        assert len({item.id for item in pending}) == 2
        root = (
            DockerWorkspaceBackend("tenant", "project", "teaching-thread").cwd
            / "workspace"
        )
        assert not (root / "first.txt").exists()
        assert not (root / "second.txt").exists()
        decisions = {}
        for item in reversed(pending):
            action = item.value["action_requests"][0]
            approved = action["args"]["file_path"] == "/workspace/first.txt"
            decisions[item.id] = {
                "decisions": [{"type": "approve" if approved else "reject"}]
            }
        result = await graph.ainvoke(Command(resume=decisions), cfg, context={})
        assert not result.get("__interrupt__")
        assert not (await graph.aget_state(cfg)).next
        assert (root / "first.txt").read_text() == "first"
        assert not (root / "second.txt").exists()
        assert result["messages"][-1].content == "Parent done."

    asyncio.run(run())
