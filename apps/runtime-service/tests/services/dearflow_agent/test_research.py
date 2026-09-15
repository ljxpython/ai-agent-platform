import asyncio
import os
from types import SimpleNamespace

import pytest
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage
from langchain_core.tools import ToolException

from .test_agent import build as graph_builder, config, call
from runtime_service.runtime import runtime_context_hash, RuntimeResolutionError
from runtime_service.services.dearflow_agent.tools import search

build = graph_builder


def test_source_records_are_scoped_and_read_only(build, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "synthetic")
    async def provider(operation, payload):
        return {"results": [{"url": "https://example.com/", "title": "Source", "content": "snippet",
                             "raw_content": "verified page text"}]}
    async def public(url):
        return url
    monkeypatch.setattr(search, "tavily", provider)
    monkeypatch.setattr(search, "public_url", public)
    async def run():
        graph, cfg = await build([call("search_web", {"query": "test"}),
                                  call("fetch_page", {"url": "https://example.com/"}, "fetch"), AIMessage(content="done")])
        state = await graph.ainvoke({"messages": [("user", "research")]}, cfg, context={})
        sources = [m.artifact["sources"][0] for m in state["messages"] if getattr(m, "artifact", None)]
        assert [s["kind"] for s in sources] == ["search_snippet", "page_text"]
        assert sources[-1]["thread_id"] == "dear-thread"
        assert sources[-1]["tool_call_id"] == "fetch"
        from runtime_service.services.dearflow_agent.workspace.backend import DearWorkspaceBackend
        workspace = DearWorkspaceBackend("tenant", "project", "dear-thread")
        assert workspace.write(sources[-1]["path"], "forged").error
        from runtime_service.tools.images import ImageWorkspace
        assert ImageWorkspace(workspace.root).read(sources[-1]["path"]) == b"verified page text"
    asyncio.run(run())


@pytest.mark.parametrize("url", ["http://127.0.0.1", "http://169.254.169.254/latest", "http://[::1]", "file:///etc/passwd", "https://user:secret@example.com", "https://example.com:22"])
def test_private_or_credential_urls_rejected(url):
    with pytest.raises(ToolException):
        asyncio.run(search.public_url(url))


def test_modes_enforce_planning_and_delegation(build):
    async def run_mode(mode):
        cfg = config()
        cfg["context"] = {"execution_mode": mode}
        cfg["configurable"]["langgraph_auth_user"]["runtime_context_hash"] = runtime_context_hash(cfg["context"])
        graph, cfg = await build([call("write_todos", {"todos": [{"content": "Research", "status": "in_progress"}]}), AIMessage(content="done")], cfg)
        if mode in {"flash", "standard"}:
            with pytest.raises(RuntimeResolutionError):
                await graph.ainvoke({"messages": [("user", "plan")]}, cfg, context=cfg["context"])
        else:
            state = await graph.ainvoke({"messages": [("user", "plan")]}, cfg, context=cfg["context"])
            assert state["todos"][0]["content"] == "Research"
    async def run():
        # Each graph captures its own config even when executions overlap.
        await asyncio.gather(*(run_mode(mode) for mode in ("flash", "standard", "pro", "ultra")))
    asyncio.run(run())


def test_live_search_and_extract(tmp_path, monkeypatch):
    if os.environ.get("DEAR_RESEARCH_LIVE_TEST") != "1":
        pytest.skip("Opt-in real Tavily API usage")
    from dotenv import load_dotenv
    load_dotenv()
    from runtime_service.services.dearflow_agent.workspace.backend import DearWorkspaceBackend
    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path))
    workspace = DearWorkspaceBackend("live", "research", "thread")
    runtime = ToolRuntime(state={}, context={}, config={}, stream_writer=lambda _: None,
                          tool_call_id="live-search", store=None,
                          execution_info=SimpleNamespace(thread_id="thread", run_id="live", checkpoint_ns=""))
    async def run():
        tools = search.build_research_tools(workspace)
        content, evidence = await tools[0].coroutine("Python asyncio TaskGroup documentation", runtime)
        assert evidence["sources"]
        url = evidence["sources"][0]["source_url"]
        content, evidence = await tools[1].coroutine(url, runtime)
        assert evidence["sources"][0]["kind"] == "page_text"
        assert len(content) > 100
    asyncio.run(run())


@pytest.mark.parametrize("forbidden,args", [
    ("execute", {"command": "touch /workspace/work/forbidden"}),
    ("write_file", {"file_path": "/workspace/work/forbidden", "content": "forbidden"}),
    ("task", {"description": "nested delegation", "subagent_type": "general-purpose"}),
])
def test_ultra_uses_restricted_child_and_pro_cannot_delegate(build, forbidden, args):
    async def run():
        for mode in ("pro", "ultra"):
            cfg = config()
            cfg["context"] = {"execution_mode": mode}
            cfg["configurable"]["langgraph_auth_user"]["runtime_context_hash"] = runtime_context_hash(cfg["context"])
            graph, cfg = await build([
                call("task", {"description": "Research without writing", "subagent_type": "general-purpose"}),
                AIMessage(content="No external evidence collected; cannot verify."),
                AIMessage(content="No verified sources."),
            ], cfg)
            if mode == "pro":
                with pytest.raises(RuntimeResolutionError):
                    await graph.ainvoke({"messages": [("user", "delegate")]}, cfg, context=cfg["context"])
            else:
                state = await graph.ainvoke({"messages": [("user", "delegate")]}, cfg, context=cfg["context"])
                assert any(getattr(m, "name", "") == "task" for m in state["messages"])
        cfg = config()
        cfg["context"] = {"execution_mode": "ultra"}
        cfg["configurable"]["langgraph_auth_user"]["runtime_context_hash"] = runtime_context_hash(cfg["context"])
        graph, cfg = await build([
            call("task", {"description": "Try forbidden operation", "subagent_type": "general-purpose"}),
            call(forbidden, args),
        ], cfg)
        with pytest.raises(RuntimeResolutionError):
            await graph.ainvoke({"messages": [("user", "delegate")]}, cfg, context=cfg["context"])
    asyncio.run(run())


def test_provider_errors_and_large_results(monkeypatch, tmp_path):
    import httpx
    import hashlib
    original = httpx.AsyncClient
    monkeypatch.setenv("TAVILY_API_KEY", "synthetic")
    async def run():
        for response in (httpx.Response(500), httpx.Response(200, content=b"x" * (1024 * 1024 + 1)),
                         httpx.Response(200, json={"results": [{"url": 1}]})):
            monkeypatch.setattr(search.httpx, "AsyncClient", lambda **kw: original(
                transport=httpx.MockTransport(lambda request: response), **kw))
            with pytest.raises(ToolException):
                await search.tavily("search", {"query": "test"})
        monkeypatch.setattr(search.httpx, "AsyncClient", lambda **kw: original(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json={
                "results": [{"url": "https://example.com", "content": "snippet", "raw_content": None}]
            })), **kw))
        assert (await search.tavily("search", {"query": "test"}))["results"][0]["content"] == "snippet"
        monkeypatch.delenv("TAVILY_API_KEY")
        with pytest.raises(ToolException, match="research_unavailable"):
            await search.tavily("search", {"query": "test"})
    asyncio.run(run())
    runtime = SimpleNamespace(tool_call_id="call", execution_info=SimpleNamespace(thread_id="thread", run_id="run", checkpoint_ns=""))
    workspace = SimpleNamespace(root=tmp_path)
    full = "bounded evidence " * 3000
    content, artifact = search._evidence(workspace, runtime, [{"source_url": "https://example.com", "content": full}])
    import json
    assert json.loads(content)[0]["truncated"] is True
    source = artifact["sources"][0]
    assert (tmp_path / "sources" / (source["content_hash"] + ".txt")).read_text() == full
    assert source["content_hash"] == hashlib.sha256(full.encode()).hexdigest()
