"""K02-K07 resource, file and provider contracts; no model quality claims."""
import asyncio
import hashlib
import io
import json
import stat
import zipfile
from importlib.resources import files
from types import SimpleNamespace

import pytest
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import ToolException

from runtime_service.runtime import RuntimeResolutionError, runtime_context_hash
from runtime_service.services.dearflow_agent.tools import (
    arxiv_search,
    github,
    research_http,
)
from runtime_service.tools.documents import build_document_tools
from runtime_service.workspace.artifact_refs import ArtifactWorkspace
from runtime_service.workspace.documents import DocumentError, DocumentWorkspace

from ..test_agent import build as graph_builder
from ..test_agent import call, config

build = graph_builder
SLUGS = ["academic-paper-review", "github-deep-research", "consulting-analysis",
         "systematic-literature-review", "code-documentation", "newsletter-generation"]


def runtime():
    return ToolRuntime(state={}, context={}, config={}, stream_writer=lambda _: None,
                       tool_call_id="batch-tool", store=None,
                       execution_info=SimpleNamespace(thread_id="thread", run_id="run", checkpoint_ns=""))


def zip_bytes(entries):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return output.getvalue()


def test_six_resource_trees_preserve_upstream_support_files():
    root = files("runtime_service.services.dearflow_agent").joinpath("skills")
    for slug in SLUGS:
        skill = root.joinpath(slug)
        provenance = json.loads(skill.joinpath("provenance.json").read_text())
        assert hashlib.sha256(skill.joinpath("LICENSE").read_bytes()).hexdigest() == provenance["license_sha256"]
        for name, digest in provenance["source_files"].items():
            if name != "SKILL.md":
                assert hashlib.sha256(skill.joinpath(name).read_bytes()).hexdigest() == digest
        text = skill.joinpath("SKILL.md").read_text()
        assert f"name: {slug}" in text
        assert "/mnt/user-data/" not in text and "present_files" not in text


@pytest.mark.parametrize("name", ["../escape.py", "/etc/evil", "a/../../evil", "a\\evil", "C:evil"])
def test_code_zip_rejects_unsafe_paths(tmp_path, name):
    data = zip_bytes([(name, b"bad")])
    with pytest.raises(DocumentError, match="unsafe_archive"):
        DocumentWorkspace(tmp_path).put(data, hashlib.sha256(data).hexdigest(), "application/zip")
    assert not list(tmp_path.iterdir())


def test_code_zip_static_read_and_archive_limits(tmp_path):
    data = zip_bytes([("src/api.py", b"def greet(name, excited=False):\n    return name\n"),
                      ("setup.py", b"raise RuntimeError('must not execute')"), ("image.bin", b"\x00\xff")])
    ref = DocumentWorkspace(tmp_path).put(data, hashlib.sha256(data).hexdigest(), "application/zip")
    parsed = build_document_tools(tmp_path)[0].invoke({"file_path": ref["path"], "query": "src/api.py"})
    assert parsed["entries"] == ["src/api.py", "setup.py", "image.bin"]
    assert parsed["files"][0]["path"] == "src/api.py"
    assert "excited=False" in parsed["files"][0]["text"]
    assert not (tmp_path / "src").exists()
    link = zipfile.ZipInfo("link")
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    for raw in (zip_bytes([(link, b"/etc/passwd")]), zip_bytes([("x", b"a"), ("X", b"b")]),
                zip_bytes([(str(n), b"x") for n in range(257)]), b"broken zip"):
        with pytest.raises(DocumentError):
            DocumentWorkspace(tmp_path).put(raw, hashlib.sha256(raw).hexdigest(), "application/zip")


def test_pdf_scanned_corrupt_and_missing_page_limits(tmp_path):
    import fitz

    from runtime_service.workspace.documents import open_pdf

    document = fitz.open()
    document.new_page()
    raw = document.tobytes()
    document.close()
    store = DocumentWorkspace(tmp_path)
    ref = store.put(raw, hashlib.sha256(raw).hexdigest(), "application/pdf")
    tool = build_document_tools(tmp_path)[0]
    result = tool.invoke({"file_path": ref["path"]})
    assert not result["text"] and "page_1_no_text_layer_ocr_required" in result["warnings"]
    assert "invalid_page_range" in tool.invoke({"file_path": ref["path"], "page_start": 2})
    for data in (b"not a PDF", b"%PDF-1.7\nbroken"):
        with pytest.raises(DocumentError):
            open_pdf(data)


@pytest.mark.parametrize("extension,mime", [("txt", "text/plain"), ("md", "text/markdown"), ("bib", "text/x-bibtex")])
def test_text_artifact_roundtrip(tmp_path, extension, mime):
    (tmp_path / "work").mkdir()
    source = tmp_path / "work" / ("result." + extension)
    source.write_text("# Verified report\n", encoding="utf-8")
    store = ArtifactWorkspace(tmp_path)
    ref = store.publish("/workspace/work/" + source.name)
    assert ref["mime_type"] == mime and ref["path"].endswith("." + extension)
    assert store.read(ref["path"])[0] == source.read_bytes()
    source.write_text("changed")
    assert store.read(ref["path"])[0] != source.read_bytes()


def test_github_pagination_private_and_invalid_path(tmp_path, monkeypatch):
    requests = []
    async def provider(url, params=None):
        requests.append((url, params))
        if url.endswith("/repo"):
            return b'{"private":false,"default_branch":"trunk"}', {}
        return json.dumps([{"html_url": "https://github.com/owner/repo/issues/1"}]).encode(), {"link": '<https://api.github.com/x?page=2>; rel="next"'}
    monkeypatch.setattr(github, "get_public", provider)
    tool = github.build_github_tool(SimpleNamespace(root=tmp_path))
    async def run():
        _, artifact = await tool.coroutine("owner", "repo", runtime(), operation="issues", page=1, per_page=1)
        source = artifact["sources"][0]
        assert source["next_page"] == 2 and source["truncated"]
        assert "page=1" in source["source_url"]
        await tool.coroutine("owner", "repo", runtime(), operation="issues", page=2, per_page=1)
        assert requests[-1][1]["page"] == 2
        count = len(requests)
        with pytest.raises(ToolException, match="invalid_github_path"):
            await tool.coroutine("owner", "repo", runtime(), operation="file", path="../secret")
        assert len(requests) == count
        async def private(*args):
            return b'{"private":true}', {}
        monkeypatch.setattr(github, "get_public", private)
        with pytest.raises(ToolException, match="private_repository_denied"):
            await tool.coroutine("owner", "repo", runtime())
    asyncio.run(run())


def test_arxiv_version_dedup_missing_fields_and_date_query(tmp_path, monkeypatch):
    async def provider(url, params=None):
        assert 'submittedDate:[202401010000 TO 202512312359]' in params["search_query"]
        return b'''<feed xmlns="http://www.w3.org/2005/Atom">
        <entry><id>http://arxiv.org/abs/1706.03762v1</id><title>Old</title><updated>2017-01-01</updated></entry>
        <entry><id>http://arxiv.org/abs/1706.03762v5</id><title>New</title><updated>2024-01-01</updated><summary>Abstract only</summary></entry>
        </feed>''', {}
    monkeypatch.setattr(arxiv_search, "get_public", provider)
    tool = arxiv_search.build_arxiv_tool(SimpleNamespace(root=tmp_path))
    async def run():
        content, artifact = await tool.coroutine("attention", runtime(), start_date="2024-01-01", end_date="2025-12-31")
        result = json.loads(content)
        assert result["duplicates_removed"] == 1 and result["returned"] == 1
        assert result["papers"][0]["title"] == "New"
        assert "authors" in result["papers"][0]["missing_fields"]
        assert result["read_scope"] == "abstract_only"
        assert artifact["sources"][0]["kind"] == "arxiv_metadata"
        with pytest.raises(ToolException, match="invalid_arxiv_date"):
            await tool.coroutine("attention", runtime(), start_date="2025-02-30")
        async def broken(*args):
            return b"<not-xml", {}
        monkeypatch.setattr(arxiv_search, "get_public", broken)
        with pytest.raises(ToolException, match="invalid_arxiv_response"):
            await tool.coroutine("attention", runtime())
    asyncio.run(run())


def test_new_tools_obey_signed_denial(build):
    async def run():
        for name, args in [("github_query", {"owner": "owner", "repo": "repo"}), ("arxiv_search", {"query": "test"})]:
            cfg = config()
            cfg["configurable"]["langgraph_auth_user"]["runtime_policy"]["tool_overrides"] = {name: False}
            cfg["configurable"]["langgraph_auth_user"]["runtime_context_hash"] = runtime_context_hash(cfg["context"])
            graph, cfg = await build([call(name, args)], cfg)
            with pytest.raises(RuntimeResolutionError, match="runtime.tool.not_allowed"):
                await graph.ainvoke({"messages": [("user", "research")]}, cfg, context=cfg["context"])
    asyncio.run(run())


def test_all_six_skills_load_through_official_graph(build):
    async def run():
        graph, cfg = await build([*[call("read_file", {"file_path": f"/skills/{slug}/SKILL.md"}, slug) for slug in SLUGS], AIMessage(content="done")])
        cfg["recursion_limit"] = 100
        state = await graph.ainvoke({"messages": [("user", "Read skills")]}, cfg, context={})
        loaded = {m.tool_call_id for m in state["messages"] if isinstance(m, ToolMessage) and m.status == "success"}
        assert set(SLUGS) <= loaded
    asyncio.run(run())


def test_provider_host_and_rate_limit(monkeypatch):
    import httpx
    async def run():
        with pytest.raises(ToolException, match="endpoint_denied"):
            await research_http.get_public("http://127.0.0.1/private")
        original = httpx.AsyncClient
        monkeypatch.setattr(research_http.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(lambda req: httpx.Response(429)), **kwargs))
        with pytest.raises(ToolException, match="rate_limited"):
            await research_http.get_public("https://api.github.com/repos/owner/repo")
    asyncio.run(run())
