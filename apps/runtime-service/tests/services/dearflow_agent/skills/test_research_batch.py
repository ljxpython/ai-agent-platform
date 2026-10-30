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
SLUGS = [
    "academic-paper-review",
    "github-deep-research",
    "consulting-analysis",
    "systematic-literature-review",
    "code-documentation",
    "newsletter-generation",
]


def runtime():
    return ToolRuntime(
        state={},
        context={},
        config={},
        stream_writer=lambda _: None,
        tool_call_id="batch-tool",
        store=None,
        execution_info=SimpleNamespace(
            thread_id="thread", run_id="run", checkpoint_ns=""
        ),
    )


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
        assert (
            hashlib.sha256(skill.joinpath("LICENSE").read_bytes()).hexdigest()
            == provenance["license_sha256"]
        )
        for name, digest in provenance["source_files"].items():
            if name != "SKILL.md":
                assert (
                    hashlib.sha256(skill.joinpath(name).read_bytes()).hexdigest()
                    == digest
                )
        text = skill.joinpath("SKILL.md").read_text()
        assert f"name: {slug}" in text
        assert "/mnt/user-data/" not in text and "present_files" not in text


@pytest.mark.parametrize(
    "name", ["../escape.py", "/etc/evil", "a/../../evil", "a\\evil", "C:evil"]
)
def test_code_zip_rejects_unsafe_paths(tmp_path, name):
    data = zip_bytes([(name, b"bad")])
    with pytest.raises(DocumentError, match="unsafe_archive"):
        DocumentWorkspace(tmp_path).put(
            data, hashlib.sha256(data).hexdigest(), "application/zip"
        )
    assert not list(tmp_path.iterdir())


def test_code_zip_static_read_and_archive_limits(tmp_path):
    data = zip_bytes(
        [
            ("src/api.py", b"def greet(name, excited=False):\n    return name\n"),
            ("setup.py", b"raise RuntimeError('must not execute')"),
            ("image.bin", b"\x00\xff"),
        ]
    )
    ref = DocumentWorkspace(tmp_path).put(
        data, hashlib.sha256(data).hexdigest(), "application/zip"
    )
    parsed = build_document_tools(tmp_path)[0].invoke(
        {"file_path": ref["path"], "query": "src/api.py"}
    )
    assert parsed["entries"] == ["src/api.py", "setup.py", "image.bin"]
    assert parsed["files"][0]["path"] == "src/api.py"
    assert "excited=False" in parsed["files"][0]["text"]
    assert not (tmp_path / "src").exists()
    link = zipfile.ZipInfo("link")
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    for raw in (
        zip_bytes([(link, b"/etc/passwd")]),
        zip_bytes([("x", b"a"), ("X", b"b")]),
        zip_bytes([(str(n), b"x") for n in range(257)]),
        b"broken zip",
    ):
        with pytest.raises(DocumentError):
            DocumentWorkspace(tmp_path).put(
                raw, hashlib.sha256(raw).hexdigest(), "application/zip"
            )


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
    assert (
        not result["text"] and "page_1_no_text_layer_ocr_required" in result["warnings"]
    )
    page_error = tool.invoke({"file_path": ref["path"], "page_start": 2})
    assert json.loads(page_error)["code"] == "tool.invalid_input"
    assert json.loads(page_error)["name"] == "parse_document"
    for data in (b"not a PDF", b"%PDF-1.7\nbroken"):
        with pytest.raises(DocumentError):
            open_pdf(data)


@pytest.mark.parametrize(
    "extension,mime",
    [("txt", "text/plain"), ("md", "text/markdown"), ("bib", "text/x-bibtex")],
)
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
        return json.dumps(
            [{"html_url": "https://github.com/owner/repo/issues/1"}]
        ).encode(), {"link": '<https://api.github.com/x?page=2>; rel="next"'}

    monkeypatch.setattr(github, "get_public", provider)
    tool = github.build_github_tool(SimpleNamespace(root=tmp_path))

    async def run():
        _, artifact = await tool.coroutine(
            "owner", "repo", runtime(), operation="issues", page=1, per_page=1
        )
        source = artifact["sources"][0]
        assert source["next_page"] == 2 and source["truncated"]
        assert "page=1" in source["source_url"]
        await tool.coroutine(
            "owner", "repo", runtime(), operation="issues", page=2, per_page=1
        )
        assert requests[-1][1]["page"] == 2
        count = len(requests)
        with pytest.raises(ToolException, match="invalid_github_path"):
            await tool.coroutine(
                "owner", "repo", runtime(), operation="file", path="../secret"
            )
        assert len(requests) == count

        async def private(*args):
            return b'{"private":true}', {}

        monkeypatch.setattr(github, "get_public", private)
        with pytest.raises(ToolException, match="private_repository_denied"):
            await tool.coroutine("owner", "repo", runtime(), operation="info")

    asyncio.run(run())


@pytest.mark.parametrize("operation", ["omitted", None, "invalid"])
def test_github_invalid_operation_recovers_before_http(tmp_path, monkeypatch, operation):
    import base64

    from langchain.agents import create_agent
    from langchain_core.language_models.fake_chat_models import (
        FakeMessagesListChatModel,
    )

    requests = []

    async def provider(url, params=None):
        requests.append((url, params))
        if url.endswith("/repo"):
            return b'{"private":false}', {}
        return json.dumps({
            "type": "file", "encoding": "base64", "path": "README.md",
            "sha": "synthetic-blob",
            "html_url": "https://github.com/owner/repo/blob/" + "a" * 40 + "/README.md",
            "content": base64.b64encode(b"# Synthetic contract").decode(),
        }).encode(), {}

    monkeypatch.setattr(github, "get_public", provider)

    class Model(FakeMessagesListChatModel):
        def bind_tools(self, tools, **kwargs):
            return self

    malformed = {"owner": "owner", "repo": "repo", "start_line": 1}
    if operation != "omitted":
        malformed["operation"] = operation
    responses = [
        AIMessage(content="", tool_calls=[{
            "name": "github_query", "args": malformed, "id": "missing-operation",
        }]),
        AIMessage(content="", tool_calls=[{
            "name": "github_query",
            "args": {"owner": "owner", "repo": "repo", "operation": "readme", "ref": "a" * 40},
            "id": "corrected-operation",
        }]),
        AIMessage(content="done"),
    ]
    graph = create_agent(
        Model(responses=responses),
        tools=[github.build_github_tool(SimpleNamespace(root=tmp_path))],
    )
    result = asyncio.run(graph.ainvoke({"messages": [("user", "read repository")]}))
    messages = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(requests) == 2, "Malformed arguments must never trigger a metadata HTTP lookup"
    assert messages[0].status == "error"
    assert messages[0].tool_call_id == "missing-operation"
    assert "operation" in messages[0].content
    assert messages[1].status == "success"
    assert "Synthetic contract" in messages[1].content
    assert requests[-1] == ("https://api.github.com/repos/owner/repo/readme", {"ref": "a" * 40})


@pytest.mark.parametrize("operation", ["file", "readme", "tree"])
@pytest.mark.parametrize("ref", ["", " "])
def test_github_content_requires_explicit_ref_before_http(
    tmp_path, monkeypatch, operation, ref
):
    async def forbidden(*args, **kwargs):
        pytest.fail("Missing ref must be rejected before any HTTP request")

    monkeypatch.setattr(github, "get_public", forbidden)
    tool = github.build_github_tool(SimpleNamespace(root=tmp_path))
    with pytest.raises(ToolException, match="invalid_github_ref"):
        asyncio.run(
            tool.coroutine(
                "owner",
                "repo",
                runtime(),
                operation=operation,
                ref=ref,
                path="README.md" if operation == "file" else "",
            )
        )


@pytest.mark.parametrize("directory", ["", "packages/feature", "docs/space name"])
def test_github_readme_respects_directory_and_fixed_ref(
    tmp_path, monkeypatch, directory
):
    import base64
    from urllib.parse import quote

    requests = []
    metrics = []
    monkeypatch.setattr(github, "log_context_metric", metrics.append)
    path = (directory + "/" if directory else "") + "README.md"

    async def provider(url, params=None):
        requests.append((url, params))
        if url.endswith("/repo"):
            return b'{"private":false}', {}
        return json.dumps(
            {
                "type": "file",
                "encoding": "base64",
                "path": path,
                "sha": "blob",
                "html_url": "https://github.com/owner/repo/blob/fixed-sha/" + path,
                "content": base64.b64encode(b"# Correct directory\n").decode(),
            }
        ).encode(), {}

    monkeypatch.setattr(github, "get_public", provider)
    tool = github.build_github_tool(SimpleNamespace(root=tmp_path))
    child_runtime = runtime()
    child_runtime.execution_info.checkpoint_ns = "tools:child|tools:readme"
    content, artifact = asyncio.run(
        tool.coroutine(
            "owner",
            "repo",
            child_runtime,
            operation="readme",
            path=directory,
            ref="fixed-sha",
        )
    )
    endpoint = "/readme" + ("/" + quote(directory, safe="/") if directory else "")
    assert requests[-1] == (
        "https://api.github.com/repos/owner/repo" + endpoint,
        {"ref": "fixed-sha"},
    )
    assert json.loads(content)["path"] == path
    source = artifact["sources"][0]
    assert source["query"] == {"ref": "fixed-sha"}
    assert source["namespace"] == "tools:child|tools:readme"
    assert source["content_hash"]
    assert [m["stage"] for m in metrics] == ["http_capture", "http_capture", "tool_adapter"]
    assert all(m["tool_call_id"] == "batch-tool" for m in metrics)
    assert metrics[0]["captured_bytes"] == len(b'{"private":false}')
    assert metrics[-1]["visible_chars"] == len(content)
    assert metrics[-1]["visible_bytes"] == len(content.encode("utf-8"))
    assert "Correct directory" not in json.dumps(metrics)


def test_github_info_and_tree_outputs_are_bounded(tmp_path, monkeypatch):
    requests = []

    async def provider(url, params=None):
        requests.append((url, params))
        if url.endswith("/repo"):
            return json.dumps(
                {
                    "full_name": "owner/repo",
                    "description": "repo",
                    "default_branch": "main",
                    "pushed_at": "2026-01-01T00:00:00Z",
                    "private": False,
                    "unexpected": "large private metadata",
                }
            ).encode(), {}
        return json.dumps(
            {
                "sha": "commit-sha",
                "truncated": False,
                "tree": [
                    {"path": f"file-{index}.py", "type": "blob", "sha": "x"}
                    for index in range(401)
                ],
            }
        ).encode(), {}

    monkeypatch.setattr(github, "get_public", provider)
    tool = github.build_github_tool(SimpleNamespace(root=tmp_path))

    async def run():
        info_content, _ = await tool.coroutine(
            "owner", "repo", runtime(), operation="info", ref="fixed-sha"
        )
        assert "unexpected" not in info_content
        tree_content, _ = await tool.coroutine(
            "owner", "repo", runtime(), operation="tree", ref="fixed-sha"
        )
        tree = json.loads(tree_content)
        assert tree["truncated"] and tree["next_page"] == 2
        assert len(tree["tree"]) <= 100
        assert requests[-1][1] == {}
        assert "recursive" not in str(requests)

    asyncio.run(run())


def test_github_directory_pagination_and_numbered_file_ranges(tmp_path, monkeypatch):
    import base64
    import hashlib

    requests = []
    source_text = "\n".join(f"source line {i}" for i in range(1, 251))

    async def provider(url, params=None):
        requests.append((url, params))
        if url.endswith("/repo"):
            return b'{"private":false,"default_branch":"main"}', {}
        if "/contents/" in url:
            assert params == {"ref": "fixed-sha"}
            return json.dumps(
                {
                    "path": "src/main.py",
                    "sha": "blob-sha",
                    "type": "file",
                    "encoding": "base64",
                    "html_url": "https://github.com/owner/repo/blob/fixed-sha/src/main.py",
                    "content": base64.b64encode(source_text.encode()).decode(),
                }
            ).encode(), {}
        if url.endswith("/fixed-sha"):
            data = {"tree": [{"path": "src", "type": "tree", "sha": "directory-sha"}]}
        else:
            assert url.endswith("/directory-sha")
            data = {
                "sha": "directory-sha",
                "tree": [{"path": f"{i}.py", "type": "blob"} for i in range(4)],
            }
        return json.dumps(data).encode(), {}

    monkeypatch.setattr(github, "get_public", provider)
    tool = github.build_github_tool(SimpleNamespace(root=tmp_path))

    async def run():
        content, artifact = await tool.coroutine(
            "owner",
            "repo",
            runtime(),
            operation="tree",
            ref="fixed-sha",
            path="src",
            page=2,
            per_page=2,
        )
        data = json.loads(content)
        assert [entry["path"] for entry in data["tree"]] == ["2.py", "3.py"]
        assert artifact["sources"][0]["next_page"] is None
        content, artifact = await tool.coroutine(
            "owner",
            "repo",
            runtime(),
            operation="file",
            ref="fixed-sha",
            path="src/main.py",
            start_line=201,
            max_lines=10,
        )
        data = json.loads(content)
        assert data["text"].startswith("201: source line 201\n")
        assert data["end_line"] == 210 and data["next_line"] == 211
        assert data["html_url"].endswith("#L201-L210")
        evidence = artifact["sources"][0]
        raw = (tmp_path / "sources" / evidence["path"].split("/")[-1]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == evidence["content_hash"]
        assert json.loads(raw)["text"] == source_text
        content, _ = await tool.coroutine(
            "owner",
            "repo",
            runtime(),
            operation="file",
            ref="fixed-sha",
            path="src/main.py",
            max_lines=400,
        )
        assert json.loads(content)["end_line"] <= 200
        with pytest.raises(ToolException, match="invalid_github_path"):
            await tool.coroutine(
                "owner", "repo", runtime(), operation="tree", path="../private"
            )
        assert all(not params or "recursive" not in params for _, params in requests)

    asyncio.run(run())


def test_github_file_literal_query_preserves_source_and_line_numbers(
    tmp_path, monkeypatch
):
    import base64

    lines = [f"source line {i}" for i in range(1, 601)]
    lines[430] = lines[549] = "Straße 😀 literal [x]"
    source = "\n".join(lines)
    requests = []

    async def provider(url, params=None):
        requests.append((url, params))
        if url.endswith("/repo"):
            return b'{"private":false}', {}
        assert params == {"ref": "fixed-sha"}
        return json.dumps(
            {
                "type": "file",
                "encoding": "base64",
                "path": "README.md",
                "sha": "blob",
                "html_url": "https://github.com/owner/repo/blob/fixed-sha/README.md",
                "content": base64.b64encode(source.encode()).decode(),
            }
        ).encode(), {}

    monkeypatch.setattr(github, "get_public", provider)
    tool = github.build_github_tool(SimpleNamespace(root=tmp_path))

    async def run():
        nonlocal source
        for operation, start, expected in [("file", 1, 431), ("readme", 432, 550)]:
            content, artifact = await tool.coroutine(
                "owner",
                "repo",
                runtime(),
                operation=operation,
                path="README.md" if operation == "file" else "",
                ref="fixed-sha",
                query="STRASSE 😀 literal [x]",
                start_line=start,
                max_lines=5,
            )
            result = json.loads(content)
            assert result["matched_line"] == expected
            assert result["start_line"] == expected - 3
            assert f"{expected}: Straße 😀 literal [x]" in result["text"]
            assert len(result["text"]) <= 12000
            assert result["html_url"].endswith(f"#L{expected - 3}-L{expected + 1}")
            evidence = artifact["sources"][0]
            raw = (tmp_path / "sources" / evidence["path"].split("/")[-1]).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == evidence["content_hash"]
            assert json.loads(raw)["text"] == source
        content, _ = await tool.coroutine(
            "owner",
            "repo",
            runtime(),
            operation="file",
            path="README.md",
            ref="fixed-sha",
            query="missing",
        )
        result = json.loads(content)
        assert result["match_found"] is False
        assert result["searched_from_line"] == 1
        assert "text" not in result and "start_line" not in result
        for max_lines in (1, 5):
            source = "\n".join(["x" * 4100] * 3 + ["needle", "tail"])
            content, _ = await tool.coroutine(
                "owner",
                "repo",
                runtime(),
                operation="file",
                path="README.md",
                ref="fixed-sha",
                query="needle",
                max_lines=max_lines,
            )
            result = json.loads(content)
            assert result["start_line"] == result["matched_line"] == 4
            assert "4: needle" in result["text"]
            assert len(result["text"]) <= 12000
        previous = len(requests)
        for invalid in [
            {"operation": "tree", "query": "needle"},
            {"query": "x" * 257},
            {"query": "x\n"},
        ]:
            kwargs = {"operation": "file", "path": "README.md", **invalid}
            with pytest.raises(ToolException, match="invalid_github_query"):
                await tool.coroutine("owner", "repo", runtime(), **kwargs)
        assert len(requests) == previous

    asyncio.run(run())


@pytest.mark.parametrize("operation", ["file", "readme"])
def test_github_markdown_query_keeps_bounded_document_intro(tmp_path, monkeypatch, operation):
    import base64

    commit = "b" * 40
    path = "docs/storage.md"
    url = f"https://github.com/owner/repo/blob/{commit}/{path}"
    rows = ["# Harbor storage", "", "English | 中文", "",
            "Harbor stores only opaque blobs; callers own recovery.", ""]
    rows += [f"Details {i} " + "x" * 85 for i in range(7, 301)]
    rows[219] = "AdvancedBatchOptions applies to batch uploads."
    source = "\n".join(rows)
    requests = []

    async def provider(endpoint, params=None):
        requests.append((endpoint, params))
        if endpoint.endswith("/repo"):
            return b'{"private":false}', {}
        assert params == {"ref": commit}
        return json.dumps({
            "type": "file", "encoding": "base64", "path": path, "sha": "blob",
            "html_url": url, "content": base64.b64encode(source.encode()).decode(),
        }).encode(), {}

    monkeypatch.setattr(github, "get_public", provider)
    tool = github.build_github_tool(SimpleNamespace(root=tmp_path))
    child_runtime = runtime()
    child_runtime.execution_info.checkpoint_ns = "tools:storage|tools:read"
    content, artifact = asyncio.run(tool.coroutine(
        "owner", "repo", child_runtime, operation=operation,
        path=path if operation == "file" else "docs", ref=commit,
        query="AdvancedBatchOptions", max_lines=200,
    ))
    result = json.loads(content)
    intro = result["document_intro"]
    assert result["matched_line"] == 220 and "220: AdvancedBatchOptions" in result["text"]
    assert intro["start_line"] == 1 and intro["line_truncated"] is False
    assert 1 <= intro["end_line"] <= 20 and len(intro["text"]) <= 2000
    assert len(intro["text"]) + len(result["text"]) <= 12000
    assert intro["text"].splitlines() == [f"{i + 1}: {row}" for i, row in enumerate(rows[:intro["end_line"]])]
    assert len(requests) == 2
    evidence = artifact["sources"][0]
    assert evidence["namespace"] == child_runtime.execution_info.checkpoint_ns
    raw = (tmp_path / "sources" / evidence["path"].split("/")[-1]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == evidence["content_hash"]
    assert json.loads(raw)["text"] == source
@pytest.mark.parametrize("case", ["plain", "near_start", "no_query", "unmatched", "long_intro", "long_match"])
def test_github_document_intro_preserves_query_and_page_boundaries(tmp_path, monkeypatch, case):
    import base64

    rows = ["Heading " + "x" * 110 for _ in range(280)]
    rows[219] = "needle" + ("x" * 13000 if case == "long_match" else "")
    if case == "near_start":
        rows[4] = "needle"
    if case == "long_intro":
        rows[0] = "x" * 2100
    path = "data.txt" if case == "plain" else "README.md"

    async def provider(url, params=None):
        if url.endswith("/repo"):
            return b'{"private":false}', {}
        return json.dumps({
            "type": "file", "encoding": "base64", "path": path, "sha": "blob",
            "html_url": "https://github.com/owner/repo/blob/fixed-sha/" + path,
            "content": base64.b64encode("\n".join(rows).encode()).decode(),
        }).encode(), {}

    monkeypatch.setattr(github, "get_public", provider)
    tool = github.build_github_tool(SimpleNamespace(root=tmp_path))
    content, _ = asyncio.run(tool.coroutine(
        "owner", "repo", runtime(), operation="file", path=path, ref="fixed-sha",
        query="" if case == "no_query" else "missing" if case == "unmatched" else "needle",
        max_lines=200,
    ))
    result = json.loads(content)
    if case == "unmatched":
        assert result["match_found"] is False and "document_intro" not in result
        return
    if case != "long_match":
        assert "document_intro" not in result
    else:
        intro = result["document_intro"]
        assert result["start_line"] == result["matched_line"] == 220
        assert result["line_truncated"] is True and result["text"].startswith("220: needle")
        assert len(intro["text"]) + len(result["text"]) <= 12000
        assert intro["text"].splitlines() == [f"{i + 1}: {row}" for i, row in enumerate(rows[:intro["end_line"]])]
    assert result["next_line"] == (result["end_line"] + 1 if result["end_line"] < len(rows) else None)


def test_github_source_pages_preserve_lifecycle_sections_with_bounded_pagination(
    tmp_path, monkeypatch
):
    import base64

    source = "\n".join(f"section {i}: " + "x" * 90 for i in range(200))

    async def provider(url, params=None):
        if url.endswith("/repo"):
            return b'{"private":false}', {}
        return json.dumps({
            "type": "file", "encoding": "base64", "path": "README.md",
            "sha": "blob", "html_url": "https://github.com/owner/repo/blob/fixed-sha/README.md",
            "content": base64.b64encode(source.encode()).decode(),
        }).encode(), {}

    monkeypatch.setattr(github, "get_public", provider)
    tool = github.build_github_tool(SimpleNamespace(root=tmp_path))

    async def read(**kwargs):
        content, artifact = await tool.coroutine(
            "owner", "repo", runtime(), operation="file", path="README.md",
            ref="fixed-sha", max_lines=200, **kwargs,
        )
        result = json.loads(content)
        assert len(result["text"]) <= 12000
        assert len(content) < 24000
        evidence = artifact["sources"][0]
        raw = (tmp_path / "sources" / evidence["path"].split("/")[-1]).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == evidence["content_hash"]
        assert json.loads(raw)["text"] == source
        return result

    async def run():
        nonlocal source
        first = await read()
        assert first["end_line"] > 100
        assert not first["line_truncated"]
        second = await read(start_line=first["next_line"])
        assert second["start_line"] == first["end_line"] + 1
        assert second["end_line"] == 200 and second["next_line"] is None
        assert len(first["text"].splitlines()) + len(second["text"].splitlines()) == 200
        source = "x" * 13000 + "\ntail"
        long_line = await read()
        assert long_line["line_truncated"] and long_line["end_line"] == 1
        assert long_line["next_line"] == 2
        assert len(long_line["text"]) == 12000
        assert (await read(start_line=2))["text"] == "2: tail"

    asyncio.run(run())


def test_arxiv_version_dedup_missing_fields_and_date_query(tmp_path, monkeypatch):
    async def provider(url, params=None):
        assert "submittedDate:[202401010000 TO 202512312359]" in params["search_query"]
        return (
            b"""<feed xmlns="http://www.w3.org/2005/Atom">
        <entry><id>http://arxiv.org/abs/1706.03762v1</id><title>Old</title><updated>2017-01-01</updated></entry>
        <entry><id>http://arxiv.org/abs/1706.03762v5</id><title>New</title><updated>2024-01-01</updated><summary>Abstract only</summary></entry>
        </feed>""",
            {},
        )

    monkeypatch.setattr(arxiv_search, "get_public", provider)
    tool = arxiv_search.build_arxiv_tool(SimpleNamespace(root=tmp_path))

    async def run():
        content, artifact = await tool.coroutine(
            "attention", runtime(), start_date="2024-01-01", end_date="2025-12-31"
        )
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
        for name, args in [
            ("github_query", {"owner": "owner", "repo": "repo"}),
            ("arxiv_search", {"query": "test"}),
        ]:
            cfg = config()
            cfg["configurable"]["langgraph_auth_user"]["runtime_policy"][
                "tool_overrides"
            ] = {name: False}
            cfg["configurable"]["langgraph_auth_user"]["runtime_context_hash"] = (
                runtime_context_hash(cfg["context"])
            )
            graph, cfg = await build([call(name, args)], cfg)
            with pytest.raises(
                RuntimeResolutionError, match="runtime.tool.not_allowed"
            ):
                await graph.ainvoke(
                    {"messages": [("user", "research")]}, cfg, context=cfg["context"]
                )

    asyncio.run(run())


def test_all_six_skills_load_through_official_graph(build):
    async def run():
        graph, cfg = await build(
            [
                *[
                    call("read_file", {"file_path": f"/skills/{slug}/SKILL.md"}, slug)
                    for slug in SLUGS
                ],
                AIMessage(content="done"),
            ]
        )
        cfg["recursion_limit"] = 100
        state = await graph.ainvoke(
            {"messages": [("user", "Read skills")]}, cfg, context={}
        )
        loaded = {
            m.tool_call_id
            for m in state["messages"]
            if isinstance(m, ToolMessage) and m.status == "success"
        }
        assert set(SLUGS) <= loaded

    asyncio.run(run())


def test_provider_host_and_rate_limit(monkeypatch):
    import httpx

    async def run():
        with pytest.raises(ToolException, match="endpoint_denied"):
            await research_http.get_public("http://127.0.0.1/private")
        original = httpx.AsyncClient
        monkeypatch.setattr(
            research_http.httpx,
            "AsyncClient",
            lambda **kwargs: original(
                transport=httpx.MockTransport(lambda req: httpx.Response(429)), **kwargs
            ),
        )
        with pytest.raises(ToolException, match="rate_limited"):
            await research_http.get_public("https://api.github.com/repos/owner/repo")

    asyncio.run(run())


def test_github_token_injection_and_unauthorized_mapping(monkeypatch):
    import httpx

    captured_headers = []

    def mock_handler(req):
        captured_headers.append(dict(req.headers))
        if req.headers.get("authorization") == "Bearer invalid_pat":
            return httpx.Response(401, json={"message": "Bad credentials"})
        return httpx.Response(200, json={"full_name": "owner/repo"})

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        research_http.httpx,
        "AsyncClient",
        lambda **kwargs: original_client(
            transport=httpx.MockTransport(mock_handler), **kwargs
        ),
    )

    async def run():
        # 1. 设置 GITHUB_TOKEN
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_mock_token_123")
        monkeypatch.delenv("GIT_TOKEN", raising=False)
        captured_headers.clear()
        await research_http.get_public("https://api.github.com/repos/owner/repo")
        assert captured_headers[-1].get("authorization") == "Bearer ghp_mock_token_123"

        # 2. 兼容 GIT_TOKEN
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setenv("GIT_TOKEN", "ghp_git_token_456")
        captured_headers.clear()
        await research_http.get_public("https://api.github.com/repos/owner/repo")
        assert captured_headers[-1].get("authorization") == "Bearer ghp_git_token_456"

        # 3. 无 Token 时保持匿名请求
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GIT_TOKEN", raising=False)
        captured_headers.clear()
        await research_http.get_public("https://api.github.com/repos/owner/repo")
        assert "authorization" not in captured_headers[-1]

        # 4. 401 Bad credentials 被安全映射为受控 ToolException
        monkeypatch.setenv("GITHUB_TOKEN", "invalid_pat")
        with pytest.raises(ToolException, match="rate_limited_or_forbidden"):
            await research_http.get_public("https://api.github.com/repos/owner/repo")

    asyncio.run(run())


def test_remote_workspace_evidence_tuple_conversion_in_tool(monkeypatch):
    from runtime_service.workspace.target import RemoteWorkspace

    class MockRemoteWorkspace(RemoteWorkspace):
        def __init__(self):
            pass

        def call(self, operation, **kwargs):
            assert operation == "research_evidence"
            # 模拟远端 RPC JSON 反序列化后返回 list 而非 tuple
            return [json.dumps([{"summary": "ok"}]), {"version": 1, "sources": []}]

    mock_remote = MockRemoteWorkspace()
    workspace = SimpleNamespace(root=mock_remote)

    async def provider(url, params=None):
        return b'{"private":false,"default_branch":"main"}', {}

    monkeypatch.setattr(github, "get_public", provider)
    tool = github.build_github_tool(workspace)

    async def run():
        # 1. 验证 _evidence 底层直接返回为标准 tuple 且长度为 2
        content_and_artifact = await tool.coroutine(
            "owner", "repo", runtime(), operation="info"
        )
        assert isinstance(content_and_artifact, tuple)
        assert len(content_and_artifact) == 2
        content, artifact = content_and_artifact
        assert "ok" in content
        assert artifact["version"] == 1

        # 2. 验证经由 LangChain 框架层解析时，content_and_artifact 元组契约严格成立，不触发 ValueError
        content_output = await tool.arun(
            {
                "owner": "owner",
                "repo": "repo",
                "operation": "info",
                "runtime": runtime(),
            }
        )
        assert isinstance(content_output, str)
        assert "ok" in content_output

        # 3. 验证传入 tool_call_id 时正确生成包含 artifact 的 ToolMessage
        tool_msg = await tool.arun(
            {
                "owner": "owner",
                "repo": "repo",
                "operation": "info",
                "runtime": runtime(),
            },
            tool_call_id="call_test_123",
        )
        assert isinstance(tool_msg, ToolMessage)
        assert tool_msg.artifact["version"] == 1
        assert "ok" in tool_msg.content

    asyncio.run(run())
