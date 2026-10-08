from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from langchain.agents import create_agent
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from services.showcase_demo.test_agent import config
from support import BindableFakeMessagesChatModel

from runtime_service.middlewares.run_prepare import (
    RunPrepareMiddleware,
    merge_preparations,
)
from runtime_service.runtime import RuntimeAuthError, RuntimeResolutionError
from runtime_service.services.demo.showcase_demo.backend import (
    DockerWorkspaceBackend,
    WorkspaceMiddleware,
)


class Preparation(RunPrepareMiddleware):
    def __init__(self, component="workspace", *, revision=1):
        super().__init__(component, "config", revision=revision)
        self.checks = self.prepared = 0
        self.ready = False

    def _validate(self, runtime):
        self.checks += 1

    def _is_prepared(self):
        return self.ready

    def _prepare(self):
        self.prepared += 1
        self.ready = True


def test_committed_prepare_rebuilt_factory_new_runs_components_and_revision():
    async def run():
        saver = InMemorySaver()
        cfg = config()
        cfg["metadata"] = {"run_id": "first"}
        workspace, resource = Preparation(), Preparation("resource")

        def graph(*middlewares):
            return create_agent(
                BindableFakeMessagesChatModel(responses=[AIMessage(content="ok")]),
                middleware=list(middlewares),
                checkpointer=saver,
            )

        first = graph(workspace, resource)
        assert "runtime_prepare" not in first.get_input_jsonschema()["properties"]
        await first.ainvoke({"messages": [("user", "same")]}, cfg)
        rebuilt = Preparation()
        rebuilt.ready = True
        second = graph(rebuilt, resource)
        await second.ainvoke({"messages": [("user", "same")]}, cfg)
        # A completed invocation is not scheduled again by LangGraph, even if
        # the factory is rebuilt. The checkpoint remains the source of truth.
        assert rebuilt.prepared == 0 and rebuilt.checks == 0
        state = await second.aget_state(cfg)
        assert set(state.values["runtime_prepare"]) == {"workspace", "resource"}
        await second.aupdate_state(cfg, {}, as_node="__start__")
        await second.ainvoke(None, cfg)
        assert rebuilt.prepared == 0 and rebuilt.checks == 1
        cfg["metadata"]["run_id"] = "second"
        await second.ainvoke({}, cfg)
        assert rebuilt.prepared == 1
        revised = Preparation(revision=2)
        revised.ready = True
        revised_graph = graph(revised)
        await revised_graph.aupdate_state(cfg, {}, as_node="__start__")
        await revised_graph.ainvoke(None, cfg)
        assert revised.prepared == 1

    asyncio.run(run())


def test_failed_prepare_replays_without_committed_marker_and_no_identity_latch():
    class Failing(Preparation):
        def _prepare(self):
            super()._prepare()
            if self.prepared == 1:
                raise RuntimeError("crash before checkpoint")

    async def run():
        cfg = config()
        cfg["metadata"] = {"run_id": "first"}
        prep = Failing()
        graph = create_agent(
            BindableFakeMessagesChatModel(responses=[AIMessage(content="ok")]),
            middleware=[prep],
            checkpointer=InMemorySaver(),
        )
        with pytest.raises(RuntimeError):
            await graph.ainvoke({"messages": [("user", "prepare")]}, cfg)
        assert not (await graph.aget_state(cfg)).values.get("runtime_prepare")
        await graph.ainvoke(None, cfg)
        assert prep.prepared == 2
        cfg.pop("metadata")
        await graph.ainvoke({"messages": [("user", "offline")]}, cfg)
        assert prep.prepared == 3

    asyncio.run(run())


def test_matching_marker_checks_resources_and_never_overwrites_user_files(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path))
    workspace = DockerWorkspaceBackend("tenant", "project", "teaching-thread")
    cfg = config()
    cfg["metadata"] = {"run_id": "first"}

    async def run():
        graph = create_agent(
            BindableFakeMessagesChatModel(responses=[AIMessage(content="ok")]),
            middleware=[WorkspaceMiddleware(workspace, "config")],
            checkpointer=InMemorySaver(),
        )
        await graph.ainvoke({"messages": [("user", "prepare")]}, cfg)
        user_file = workspace.cwd / "workspace/report.py"
        user_file.write_text("user version")
        marker = workspace.cwd / ".initialized"
        marker.rename(workspace.cwd / ".old-marker")
        await graph.aupdate_state(cfg, {}, as_node="__start__")
        await graph.ainvoke(None, cfg)
        assert marker.is_file() and user_file.read_text() == "user version"
        marker.rename(workspace.cwd / ".new-marker")
        marker.symlink_to(user_file)
        cfg["metadata"]["run_id"] = "new"
        with pytest.raises(RuntimeAuthError):
            await graph.ainvoke({"messages": [("user", "unsafe")]}, cfg)

    asyncio.run(run())


def test_marker_bounds_and_identity_conflict():
    assert merge_preparations({"first": "a" * 64}, {"second": "b" * 64}) == {
        "first": "a" * 64,
        "second": "b" * 64,
    }
    for markers in ({"workspace": "canary"}, {f"item{i}": "a" * 64 for i in range(17)}):
        with pytest.raises(RuntimeResolutionError):
            merge_preparations({}, markers)
    prep = Preparation()
    cfg = config()
    runtime = SimpleNamespace(
        server_info=SimpleNamespace(user=cfg["configurable"]["langgraph_auth_user"]),
        execution_info=SimpleNamespace(run_id="first"),
    )
    with pytest.raises(RuntimeAuthError, match="identity_mismatch"):
        prep._fingerprint(runtime, {"metadata": {"run_id": "other"}})


def test_fingerprint_uses_graph_namespace_not_rescheduled_hook_task():
    cfg = config()
    prep = Preparation()
    runtime = SimpleNamespace(
        server_info=SimpleNamespace(
            user=cfg["configurable"]["langgraph_auth_user"], graph_id="showcase_demo"
        ),
        execution_info=SimpleNamespace(run_id="first", thread_id="teaching-thread"),
    )

    def fingerprint(namespace):
        return prep._fingerprint(
            runtime,
            {"metadata": {"run_id": "first", "langgraph_checkpoint_ns": namespace}},
        )

    assert fingerprint("hook:one") == fingerprint("hook:two")
    assert fingerprint("tools:child-one|hook:one") == fingerprint(
        "tools:child-one|hook:two"
    )
    assert fingerprint("tools:child-one|hook:one") != fingerprint(
        "tools:child-two|hook:one"
    )
    first = fingerprint("hook:one")
    prep.config_hash = "updated"
    assert fingerprint("hook:one") != first
    prep.config_hash = "config"
    runtime.execution_info.thread_id = "forked-thread"
    assert fingerprint("hook:one") != first
    runtime.execution_info.thread_id = "teaching-thread"
    runtime.server_info.graph_id = "other-graph"
    assert fingerprint("hook:one") != first
