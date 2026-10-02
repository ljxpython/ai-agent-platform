import asyncio
import os
from types import SimpleNamespace

import pytest
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage
from langchain_core.tools import ToolException

from runtime_service.runtime import RuntimeResolutionError, runtime_context_hash
from runtime_service.services.dearflow_agent.tools import search

from .test_agent import build as graph_builder
from .test_agent import call, config

build = graph_builder


def test_source_records_are_scoped_and_read_only(build, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "synthetic")

    async def provider(operation, payload):
        return {
            "results": [
                {
                    "url": "https://example.com/",
                    "title": "Source",
                    "content": "snippet",
                    "raw_content": "verified page text",
                }
            ]
        }

    async def public(url):
        return url

    monkeypatch.setattr(search, "tavily", provider)
    monkeypatch.setattr(search, "public_url", public)

    async def run():
        graph, cfg = await build(
            [
                call("search_web", {"query": "test"}),
                call("fetch_page", {"url": "https://example.com/"}, "fetch"),
                AIMessage(content="done"),
            ]
        )
        state = await graph.ainvoke(
            {"messages": [("user", "research")]}, cfg, context={}
        )
        sources = [
            m.artifact["sources"][0]
            for m in state["messages"]
            if getattr(m, "artifact", None)
        ]
        assert [s["kind"] for s in sources] == ["search_snippet", "page_text"]
        assert sources[-1]["thread_id"] == "dear-thread"
        assert sources[-1]["tool_call_id"] == "fetch"
        from runtime_service.services.dearflow_agent.workspace.backend import (
            DearWorkspaceBackend,
        )

        workspace = DearWorkspaceBackend("tenant", "project", "dear-thread")
        assert workspace.write(sources[-1]["path"], "forged").error
        from runtime_service.tools.images import ImageWorkspace

        assert (
            ImageWorkspace(workspace.root).read(sources[-1]["path"])
            == b"verified page text"
        )

    asyncio.run(run())


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1",
        "http://169.254.169.254/latest",
        "http://[::1]",
        "file:///etc/passwd",
        "https://user:secret@example.com",
        "https://example.com:22",
    ],
)
def test_private_or_credential_urls_rejected(url):
    with pytest.raises(ToolException):
        asyncio.run(search.public_url(url))


def test_modes_enforce_planning_and_delegation(build):
    async def run_mode(mode):
        cfg = config()
        cfg["context"] = {"execution_mode": mode}
        cfg["configurable"]["langgraph_auth_user"]["runtime_context_hash"] = (
            runtime_context_hash(cfg["context"])
        )
        graph, cfg = await build(
            [
                call(
                    "write_todos",
                    {"todos": [{"content": "Research", "status": "in_progress"}]},
                ),
                AIMessage(content="done"),
            ],
            cfg,
        )
        if mode in {"flash", "standard"}:
            with pytest.raises(RuntimeResolutionError):
                await graph.ainvoke(
                    {"messages": [("user", "plan")]}, cfg, context=cfg["context"]
                )
        else:
            state = await graph.ainvoke(
                {"messages": [("user", "plan")]}, cfg, context=cfg["context"]
            )
            assert state["todos"][0]["content"] == "Research"

    async def run():
        # Each graph captures its own config even when executions overlap.
        await asyncio.gather(
            *(run_mode(mode) for mode in ("flash", "standard", "pro", "ultra"))
        )

    asyncio.run(run())


def test_live_search_and_extract(tmp_path, monkeypatch):
    if os.environ.get("DEAR_RESEARCH_LIVE_TEST") != "1":
        pytest.skip("Opt-in real Tavily API usage")
    from dotenv import load_dotenv

    load_dotenv()
    from runtime_service.services.dearflow_agent.workspace.backend import (
        DearWorkspaceBackend,
    )

    monkeypatch.setenv("RUNTIME_WORKSPACE_ROOT", str(tmp_path))
    workspace = DearWorkspaceBackend("live", "research", "thread")
    runtime = ToolRuntime(
        state={},
        context={},
        config={},
        stream_writer=lambda _: None,
        tool_call_id="live-search",
        store=None,
        execution_info=SimpleNamespace(
            thread_id="thread", run_id="live", checkpoint_ns=""
        ),
    )

    async def run():
        tools = search.build_research_tools(workspace)
        content, evidence = await tools[0].coroutine(
            "Python asyncio TaskGroup documentation", runtime
        )
        assert evidence["sources"]
        url = evidence["sources"][0]["source_url"]
        content, evidence = await tools[1].coroutine(url, runtime)
        assert evidence["sources"][0]["kind"] == "page_text"
        assert len(content) > 100

    asyncio.run(run())


@pytest.mark.parametrize(
    "forbidden,args",
    [
        ("execute", {"command": "touch /workspace/work/forbidden"}),
        (
            "write_file",
            {"file_path": "/workspace/work/forbidden", "content": "forbidden"},
        ),
        (
            "task",
            {"description": "nested delegation", "subagent_type": "general-purpose"},
        ),
    ],
)
def test_ultra_uses_restricted_child_and_pro_cannot_delegate(build, forbidden, args):
    async def run():
        for mode in ("pro", "ultra"):
            cfg = config()
            cfg["context"] = {"execution_mode": mode}
            cfg["configurable"]["langgraph_auth_user"]["runtime_context_hash"] = (
                runtime_context_hash(cfg["context"])
            )
            graph, cfg = await build(
                [
                    call(
                        "task",
                        {
                            "description": "Research without writing",
                            "subagent_type": "general-purpose",
                        },
                    ),
                    AIMessage(content="No external evidence collected; cannot verify."),
                    AIMessage(content="No verified sources."),
                ],
                cfg,
            )
            if mode == "pro":
                with pytest.raises(RuntimeResolutionError):
                    await graph.ainvoke(
                        {"messages": [("user", "delegate")]},
                        cfg,
                        context=cfg["context"],
                    )
            else:
                state = await graph.ainvoke(
                    {"messages": [("user", "delegate")]}, cfg, context=cfg["context"]
                )
                assert any(getattr(m, "name", "") == "task" for m in state["messages"])
        cfg = config()
        cfg["context"] = {"execution_mode": "ultra"}
        cfg["configurable"]["langgraph_auth_user"]["runtime_context_hash"] = (
            runtime_context_hash(cfg["context"])
        )
        graph, cfg = await build(
            [
                call(
                    "task",
                    {
                        "description": "Try forbidden operation",
                        "subagent_type": "general-purpose",
                    },
                ),
                call(forbidden, args),
            ],
            cfg,
        )
        with pytest.raises(RuntimeResolutionError):
            await graph.ainvoke(
                {"messages": [("user", "delegate")]}, cfg, context=cfg["context"]
            )

    asyncio.run(run())


def test_provider_errors_and_large_results(monkeypatch, tmp_path):
    import hashlib

    import httpx

    original = httpx.AsyncClient
    monkeypatch.setenv("TAVILY_API_KEY", "synthetic")

    async def run():
        for response in (
            httpx.Response(500),
            httpx.Response(200, content=b"x" * (1024 * 1024 + 1)),
            httpx.Response(200, json={"results": [{"url": 1}]}),
        ):
            monkeypatch.setattr(
                search.httpx,
                "AsyncClient",
                lambda _resp=response, **kw: original(
                    transport=httpx.MockTransport(lambda request, _r=_resp: _r), **kw
                ),
            )
            with pytest.raises(ToolException):
                await search.tavily("search", {"query": "test"})
        monkeypatch.setattr(
            search.httpx,
            "AsyncClient",
            lambda **kw: original(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(
                        200,
                        json={
                            "results": [
                                {
                                    "url": "https://example.com",
                                    "content": "snippet",
                                    "raw_content": None,
                                }
                            ]
                        },
                    )
                ),
                **kw,
            ),
        )
        assert (await search.tavily("search", {"query": "test"}))["results"][0][
            "content"
        ] == "snippet"
        monkeypatch.delenv("TAVILY_API_KEY")
        with pytest.raises(ToolException, match="research_unavailable"):
            await search.tavily("search", {"query": "test"})

    asyncio.run(run())
    runtime = SimpleNamespace(
        tool_call_id="call",
        execution_info=SimpleNamespace(
            thread_id="thread", run_id="run", checkpoint_ns=""
        ),
    )
    workspace = SimpleNamespace(root=tmp_path)
    full = "bounded evidence " * 3000
    content, artifact = search._evidence(
        workspace, runtime, [{"source_url": "https://example.com", "content": full}]
    )
    import json

    assert json.loads(content)[0]["truncated"] is True
    source = artifact["sources"][0]
    assert (
        tmp_path / "sources" / (source["content_hash"] + ".txt")
    ).read_text() == full
    assert source["content_hash"] == hashlib.sha256(full.encode()).hexdigest()


def test_jina_extract_direct(monkeypatch):
    import httpx

    original = httpx.AsyncClient
    monkeypatch.setenv("JINA_API_KEY", "synthetic-jina")

    # 1. 成功解析 JSON 格式
    resp_json = httpx.Response(
        200,
        json={
            "data": {
                "title": "Jina Post",
                "url": "https://example.com/post",
                "content": "# Extracted Markdown Header",
            }
        },
    )
    monkeypatch.setattr(
        search.httpx,
        "AsyncClient",
        lambda _resp=resp_json, **kw: original(
            transport=httpx.MockTransport(lambda request, _r=_resp: _r), **kw
        ),
    )
    res = asyncio.run(search.jina_extract("https://example.com/post"))
    assert res["title"] == "Jina Post"
    assert res["content"] == "# Extracted Markdown Header"
    assert res["url"] == "https://example.com/post"

    # 2. 成功解析纯文本 Markdown 格式
    resp_text = httpx.Response(200, text="# Plain Markdown Text")
    monkeypatch.setattr(
        search.httpx,
        "AsyncClient",
        lambda _resp=resp_text, **kw: original(
            transport=httpx.MockTransport(lambda request, _r=_resp: _r), **kw
        ),
    )
    res = asyncio.run(search.jina_extract("https://example.com/text"))
    assert res["content"] == "# Plain Markdown Text"

    # 3. 超过 1MB 报错
    resp_large = httpx.Response(200, content=b"a" * (1024 * 1024 + 1))
    monkeypatch.setattr(
        search.httpx,
        "AsyncClient",
        lambda _resp=resp_large, **kw: original(
            transport=httpx.MockTransport(lambda request, _r=_resp: _r), **kw
        ),
    )
    with pytest.raises(ToolException, match="research_response_too_large"):
        asyncio.run(search.jina_extract("https://example.com/large"))

    # 4. HTTP 500 报错
    resp_err = httpx.Response(500)
    monkeypatch.setattr(
        search.httpx,
        "AsyncClient",
        lambda _resp=resp_err, **kw: original(
            transport=httpx.MockTransport(lambda request, _r=_resp: _r), **kw
        ),
    )
    with pytest.raises(ToolException, match="jina_provider_failed"):
        asyncio.run(search.jina_extract("https://example.com/error"))


def test_fetch_page_dual_channel_fallback(tmp_path, monkeypatch):
    workspace = SimpleNamespace(root=tmp_path)
    runtime = ToolRuntime(
        state={},
        context={},
        config={},
        stream_writer=lambda _: None,
        tool_call_id="call-fetch",
        store=None,
        execution_info=SimpleNamespace(
            thread_id="test-thread", run_id="test-run", checkpoint_ns=""
        ),
    )
    tools = search.build_research_tools(workspace)
    fetch_tool = tools[1]

    async def fake_public(url):
        return url

    monkeypatch.setattr(search, "public_url", fake_public)

    # 场景 1: Jina 优先成功提取
    monkeypatch.setenv("JINA_API_KEY", "synthetic-jina")
    monkeypatch.setenv("TAVILY_API_KEY", "synthetic-tavily")

    async def jina_ok(url):
        return {
            "url": url,
            "title": "Jina Title",
            "content": "# Jina Markdown Verified",
        }

    async def tavily_should_not_call(*args, **kwargs):
        raise AssertionError("Tavily should not be called when Jina succeeds")

    monkeypatch.setattr(search, "jina_extract", jina_ok)
    monkeypatch.setattr(search, "tavily", tavily_should_not_call)

    content, artifact = asyncio.run(
        fetch_tool.coroutine("https://example.com/article", runtime)
    )
    source = artifact["sources"][0]
    assert source["title"] == "Jina Title"
    assert source["kind"] == "page_text"
    assert (
        tmp_path / "sources" / (source["content_hash"] + ".txt")
    ).read_text() == "# Jina Markdown Verified"

    # 场景 2: Jina 失败（抛异常），平滑降级到 Tavily
    async def jina_fail(url):
        raise ToolException("jina_provider_failed")

    async def tavily_ok(operation, payload):
        return {
            "results": [
                {
                    "url": payload["urls"][0],
                    "title": "Tavily Title",
                    "raw_content": "Tavily fallback raw content",
                }
            ]
        }

    monkeypatch.setattr(search, "jina_extract", jina_fail)
    monkeypatch.setattr(search, "tavily", tavily_ok)

    content, artifact = asyncio.run(
        fetch_tool.coroutine("https://example.com/article2", runtime)
    )
    source2 = artifact["sources"][0]
    assert source2["title"] == "Tavily Title"
    assert (
        tmp_path / "sources" / (source2["content_hash"] + ".txt")
    ).read_text() == "Tavily fallback raw content"

    # 场景 3: Jina 返回空内容，降级到 Tavily
    async def jina_empty(url):
        return {"url": url, "title": "Empty", "content": "   "}

    monkeypatch.setattr(search, "jina_extract", jina_empty)
    content, artifact = asyncio.run(
        fetch_tool.coroutine("https://example.com/article3", runtime)
    )
    source3 = artifact["sources"][0]
    assert source3["title"] == "Tavily Title"

    # 场景 4: Jina 与 Tavily 双双失败
    async def tavily_fail(operation, payload):
        raise ToolException("research_provider_failed")

    monkeypatch.setattr(search, "tavily", tavily_fail)
    with pytest.raises(ToolException, match="research_extract_failed"):
        asyncio.run(fetch_tool.coroutine("https://example.com/article4", runtime))

    # 场景 5: Tavily 返回空页面
    async def tavily_empty(operation, payload):
        return {
            "results": [
                {
                    "url": payload["urls"][0],
                    "title": "Empty",
                    "raw_content": " ",
                }
            ]
        }

    monkeypatch.setattr(search, "tavily", tavily_empty)
    with pytest.raises(ToolException, match="research_empty_page"):
        asyncio.run(fetch_tool.coroutine("https://example.com/empty", runtime))

    # 场景 6: 无任何 Provider 配置
    monkeypatch.delenv("JINA_API_KEY", raising=False)
    monkeypatch.delenv("JINA_KEY", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    with pytest.raises(ToolException, match="research_unavailable"):
        asyncio.run(fetch_tool.coroutine("https://example.com/article5", runtime))


def test_agent_available_tools_with_jina_only(build, monkeypatch):
    monkeypatch.setenv("JINA_API_KEY", "synthetic-jina")
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)

    async def fake_jina(url):
        return {
            "url": url,
            "title": "Jina Only",
            "content": "Jina content without tavily",
        }

    async def fake_public(url):
        return url

    monkeypatch.setattr(search, "jina_extract", fake_jina)
    monkeypatch.setattr(search, "public_url", fake_public)

    async def run():
        # fetch_page 应当成功执行，因为 Jina 可用
        graph, cfg = await build(
            [
                call("fetch_page", {"url": "https://example.com/jina-only"}, "call-1"),
                AIMessage(content="done"),
            ]
        )
        state = await graph.ainvoke(
            {"messages": [("user", "fetch without tavily")]}, cfg, context={}
        )
        sources = [
            m.artifact["sources"][0]
            for m in state["messages"]
            if getattr(m, "artifact", None)
        ]
        assert len(sources) == 1
        assert sources[0]["title"] == "Jina Only"

        # search_web 应当不可用，因为 Tavily 缺失
        graph2, cfg2 = await build(
            [
                call("search_web", {"query": "test query"}, "call-2"),
                AIMessage(content="done"),
            ]
        )
        with pytest.raises(RuntimeResolutionError):
            await graph2.ainvoke(
                {"messages": [("user", "search should fail")]}, cfg2, context={}
            )

    asyncio.run(run())
