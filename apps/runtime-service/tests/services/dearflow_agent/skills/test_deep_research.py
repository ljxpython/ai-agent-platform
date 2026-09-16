"""K01 resource and real graph contracts; scripted outputs are not model-quality evidence."""
import asyncio
import hashlib
import json
from importlib.resources import files
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command

from runtime_service.runtime import RuntimeResolutionError, runtime_context_hash
from runtime_service.services.dearflow_agent.tools import search
from runtime_service.services.dearflow_agent.workspace import backend

from ..test_agent import build as graph_builder
from ..test_agent import call, config

build = graph_builder

def test_k01_resources_and_fingerprint(monkeypatch, tmp_path):
    root = files(backend.PACKAGE).joinpath("skills/deep-research")
    text = root.joinpath("SKILL.md").read_text()
    source = json.loads(root.joinpath("provenance.json").read_text())
    original = text.replace("search_web", "WebSearch").replace("fetch_page", "web_fetch")
    assert hashlib.sha256(original.encode()).hexdigest() == source["source_sha256"]
    assert hashlib.sha256(root.joinpath("LICENSE").read_bytes()).hexdigest() == source["license_sha256"]
    assert source["revision"] == "dear-k01-v1"
    resource = tmp_path / "skills/deep-research/references"
    resource.mkdir(parents=True)
    (resource / "method.md").write_text("first")
    monkeypatch.setattr(backend, "files", lambda _: tmp_path)
    before = backend.skills_hash()
    (resource / "method.md").write_text("second")
    assert backend.skills_hash() != before


def test_k01_progressive_load_and_conflicting_evidence(build, monkeypatch):
    records = json.loads((Path(__file__).parent / "fixtures/deep-research/conflicting-sources.json").read_text())
    monkeypatch.setenv("TAVILY_API_KEY", "synthetic")

    async def provider(operation, payload):
        return {"results": [{"url": r["source_url"], "title": r["title"],
                             "raw_content": r["content"]} for r in records if r["source_url"] == payload["urls"][0]]}

    monkeypatch.setattr(search, "tavily", provider)

    async def run():
        graph, cfg = await build([
            call("read_file", {"file_path": "/skills/deep-research/SKILL.md"}, "skill"),
            *[call("fetch_page", {"url": r["source_url"]}, f"source-{i}") for i, r in enumerate(records)],
            AIMessage(content="Sources conflict; no universal speedup can be established."),
        ])
        state = await graph.ainvoke({"messages": [("user", "Compare evidence")]}, cfg, context={})
        snapshot = (await graph.aget_state(cfg)).values
        skill = next(s for s in snapshot["skills_metadata"] if s["name"] == "deep-research")
        assert skill["path"] == "/skills/deep-research/SKILL.md"
        loaded = next(m for m in state["messages"] if isinstance(m, ToolMessage) and m.tool_call_id == "skill")
        assert "Phase 4: Synthesis Check" in str(loaded.content)
        sources = [m.artifact["sources"][0] for m in state["messages"] if getattr(m, "artifact", None)]
        assert {s["source_url"] for s in sources} == {r["source_url"] for r in records}
        workspace = backend.DearWorkspaceBackend("tenant", "project", "dear-thread")
        for evidence, record in zip(sources, records, strict=True):
            assert evidence["kind"] == "page_text"
            assert evidence["content_hash"] == hashlib.sha256(record["content"].encode()).hexdigest()
            assert workspace.write(evidence["path"], "overwrite").error
        assert not (workspace.root / "work/injected.txt").exists()
    asyncio.run(run())


def test_k01_read_only_and_unavailable_page(build, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "synthetic")

    async def empty(operation, payload):
        return {"results": []}

    monkeypatch.setattr(search, "tavily", empty)

    async def run():
        graph, cfg = await build([
            call("fetch_page", {"url": "https://example.org/missing"}, "missing"),
            call("write_file", {"file_path": "/skills/deep-research/SKILL.md", "content": "replace"}, "write"),
            AIMessage(content="No verified sources available."),
        ])
        state = await graph.ainvoke({"messages": [("user", "Research")]}, cfg, context={})
        if state.get("__interrupt__"):
            state = await graph.ainvoke(Command(resume={"decisions": [{"type": "approve"}]}), cfg, context={})
        outputs = {m.tool_call_id: m for m in state["messages"] if isinstance(m, ToolMessage)}
        assert "research_extract_failed" in str(outputs["missing"].content)
        assert not getattr(outputs["missing"], "artifact", None)
        assert "denied" in str(outputs["write"].content).lower() or "permission" in str(outputs["write"].content).lower()
        assert "Deep Research Skill" in files(backend.PACKAGE).joinpath("skills/deep-research/SKILL.md").read_text()
    asyncio.run(run())


def test_k01_loading_does_not_grant_search_permission(build, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "synthetic")

    async def run():
        cfg = config()
        cfg["context"] = {"tools": ["read_file"]}
        cfg["configurable"]["langgraph_auth_user"]["runtime_context_hash"] = runtime_context_hash(cfg["context"])
        graph, cfg = await build([
            call("read_file", {"file_path": "/skills/deep-research/SKILL.md"}, "skill"),
            call("search_web", {"query": "forbidden"}, "search"),
        ], cfg)
        with pytest.raises(RuntimeResolutionError, match="runtime.tool.not_allowed"):
            await graph.ainvoke({"messages": [("user", "Research")]}, cfg, context=cfg["context"])
    asyncio.run(run())
