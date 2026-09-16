"""K08-K11 contracts; external providers and Docker are opt-in."""
import asyncio
import hashlib
import io
import json
import os
import zipfile
from importlib.resources import files
from pathlib import Path
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import ToolException
from langgraph.types import Command
from mcp.types import CallToolResult, TextContent
from PIL import Image

from runtime_service.services.dearflow_agent.capabilities import CHART_NAMES
from runtime_service.services.dearflow_agent.tools import web_guidelines
from runtime_service.tools import chart
from runtime_service.tools.documents import build_document_tools
from runtime_service.tools.images import ImageWorkspace
from runtime_service.workspace.artifact_refs import ArtifactWorkspace
from runtime_service.workspace.documents import DocumentError, DocumentWorkspace
from runtime_service.workspace.execution import execute_in_workspace

from ..test_agent import build as graph_builder
from ..test_agent import call

build = graph_builder
SKILLS = files("runtime_service.services.dearflow_agent").joinpath("skills")
SLUGS = ["data-analysis", "chart-visualization", "frontend-design", "web-design-guidelines"]


def test_upstream_resources_and_adapted_files():
    for slug in SLUGS:
        root = SKILLS.joinpath(slug)
        provenance = json.loads(root.joinpath("provenance.json").read_text())
        for name, digest in provenance["source_files"].items():
            if name not in provenance["adapted_files"]:
                assert hashlib.sha256(root.joinpath(name).read_bytes()).hexdigest() == digest
        assert "/mnt/user-data" not in root.joinpath("SKILL.md").read_text()
    assert len(CHART_NAMES) == 26
    assert "generate_spreadsheet" in CHART_NAMES


def test_new_artifacts_are_immutable_and_statically_readable(tmp_path):
    (tmp_path / "work").mkdir()
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("index.html", '<html><input id="name"><script src="app.js"></script></html>')
        z.writestr("app.js", "throw Error('not executed')")
    for ext, data in {"html": b"<script>parent.document.cookie</script>", "csv": b"x,y\n1,2\n",
                      "json": b'[{"x":1}]', "zip": archive.getvalue()}.items():
        path = tmp_path / "work" / ("result." + ext)
        path.write_bytes(data)
        store = ArtifactWorkspace(tmp_path)
        ref = store.publish("/workspace/work/" + path.name)
        assert store.read(ref["path"])[0] == data
        result = build_document_tools(tmp_path)[0].invoke({"file_path": ref["path"]})
        assert isinstance(result, dict)
        if ext == "zip":
            assert result["entries"] == ["index.html", "app.js"]
        path.write_bytes(b"changed")
        assert store.read(ref["path"])[0] == data
    (tmp_path / "work/bad.zip").write_bytes(b"not zip")
    with pytest.raises(DocumentError):
        ArtifactWorkspace(tmp_path).publish("/workspace/work/bad.zip")


def test_excel_upload_format_validation(tmp_path):
    store = DocumentWorkspace(tmp_path)
    for mime in ("application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"):
        with pytest.raises(DocumentError):
            store.put(b"not excel", hashlib.sha256(b"not excel").hexdigest(), mime)


def test_guidelines_version_and_provider_failure(monkeypatch):
    async def provider(url):
        assert url == web_guidelines.GUIDELINES_URL
        return b"# Accessibility\nInputs need labels. Use <html lang='en'>.", {"etag": "fixed", "content-type": "text/plain"}
    monkeypatch.setattr(web_guidelines, "get_public", provider)
    result = asyncio.run(web_guidelines.fetch_web_guidelines.ainvoke({}))
    assert result["sha256"] == hashlib.sha256(result["content"].encode()).hexdigest()
    assert result["review_scope"] == "static_only" and result["etag"] == "fixed"
    async def failure(url):
        raise ToolException("research_provider_failed")
    monkeypatch.setattr(web_guidelines, "get_public", failure)
    failed = asyncio.run(web_guidelines.fetch_web_guidelines.ainvoke({"type": "tool_call", "name": "fetch_web_guidelines", "id": "failure", "args": {}}))
    assert failed.status == "error" and "research_provider_failed" in failed.content


def test_all_skills_load_and_chart_requires_approval(build, monkeypatch):
    sent = []
    async def download(*args, **kwargs):
        sent.append(True)
    monkeypatch.setattr(chart, "download_image", download)
    async def run():
        graph, cfg = await build([
            *[call("read_file", {"file_path": f"/skills/{slug}/SKILL.md"}, slug) for slug in SLUGS],
            call("generate_bar_chart", {"data": [{"category": "Private", "value": 10}]}, "chart"),
            AIMessage(content="rejected"),
        ])
        cfg["recursion_limit"] = 100
        state = await graph.ainvoke({"messages": [("user", "Read skills and chart")]}, cfg, context={})
        assert state["__interrupt__"]
        assert not sent
        state = await graph.ainvoke(Command(resume={"decisions": [{"type": "reject", "message": "no external data"}]}), cfg, context={})
        assert not sent
        assert {m.tool_call_id for m in state["messages"] if isinstance(m, ToolMessage)} >= set(SLUGS)
    asyncio.run(run())


def chart_cases():
    category = {"data": [{"category": "A", "value": 10}, {"category": "B", "value": 20}]}
    cases = {name: category for name in CHART_NAMES}
    for name in ("area", "line"):
        cases[f"generate_{name}_chart"] = {"data": [{"time": "2024", "value": 10}, {"time": "2025", "value": 20}]}
    for name in ("boxplot", "violin"):
        cases[f"generate_{name}_chart"] = {"data": [{"category": group, "value": v} for group in ("A", "B") for v in (1, 3, 5, 7, 9)]}
    cases.update({
        "generate_histogram_chart": {"data": [1, 2, 2, 3, 5, 8]},
        "generate_liquid_chart": {"percent": 0.6},
        "generate_scatter_chart": {"data": [{"x": 1, "y": 2}, {"x": 2, "y": 4}]},
        "generate_word_cloud_chart": {"data": [{"text": "Research", "value": 10}, {"text": "Data", "value": 5}]},
        "generate_radar_chart": {"data": [{"name": n, "value": v} for n, v in [("Speed", 10), ("Cost", 20), ("Quality", 30)]]},
        "generate_treemap_chart": {"data": [{"name": "A", "value": 10}, {"name": "B", "value": 20}]},
        "generate_sankey_chart": {"data": [{"source": "A", "target": "B", "value": 10}]},
        "generate_venn_chart": {"data": [{"sets": ["A"], "value": 10}, {"sets": ["B"], "value": 8}, {"sets": ["A", "B"], "value": 3}]},
        "generate_dual_axes_chart": {"categories": ["2024", "2025"], "series": [{"type": "column", "data": [10, 20]}, {"type": "line", "data": [0.2, 0.4]}]},
        "generate_spreadsheet": {"data": [{"name": "A", "value": 10}, {"name": "B", "value": 20}]},
        "generate_pin_map": {"title": "杭州地点", "data": ["杭州市西湖", "杭州市灵隐寺"]},
        "generate_path_map": {"title": "杭州路线", "data": [{"data": ["杭州市西湖", "杭州市灵隐寺"]}]},
        "generate_district_map": {"title": "浙江地图", "data": {"name": "浙江省"}},
    })
    for name in ("mind_map", "organization_chart", "fishbone_diagram"):
        cases["generate_" + name] = {"data": {"name": "Root", "children": [{"name": "A"}, {"name": "B"}]}}
    for name in ("network_graph", "flow_diagram"):
        cases["generate_" + name] = {"data": {"nodes": [{"name": "A"}, {"name": "B"}], "edges": [{"source": "A", "target": "B"}]}}
    return cases


def test_26_chart_contracts_and_rejected_inputs(monkeypatch, tmp_path):
    intercepted = []
    monkeypatch.setattr(chart, "convert_mcp_tool_to_langchain_tool", lambda *a, **kw: intercepted.append(kw["tool_interceptors"][0]))
    image = io.BytesIO()
    Image.new("RGB", (16, 16), "red").save(image, "PNG")
    async def download(*a, **kw):
        return image.getvalue()
    monkeypatch.setattr(chart, "download_image", download)
    chart.build_chart_tools(ImageWorkspace(tmp_path), include_spreadsheet=True)
    sent = []
    async def handler(request):
        sent.append(request.name)
        if request.name.endswith("_map"):
            return CallToolResult(content=[TextContent(type="text", text="Static map preview and download URL: https://mdn.alipayobjects.com/fixture.png")],
                                  structuredContent={"imageUrl": "https://mdn.alipayobjects.com/fixture.png"})
        return CallToolResult(content=[TextContent(type="text", text="https://mdn.alipayobjects.com/fixture.png")])
    async def run():
        for name, args in chart_cases().items():
            result = await intercepted[0](SimpleNamespace(name=name, args=args), handler)
            assert not result.isError, name
            ref = result.structuredContent["runtime_images"][0]
            assert ImageWorkspace(tmp_path).read(ref["path"]) == image.getvalue()
        assert len(sent) == 26
        for args in ({"data": "invalid"}, {"data": [{"category": "a" * 140000, "value": 1}]},
                     {"data": [{"category": "A", "value": 1}], "width": 99999}):
            result = await intercepted[0](SimpleNamespace(name="generate_bar_chart", args=args), handler)
            assert result.isError
        assert len(sent) == 26
    asyncio.run(run())


@pytest.mark.integration
def test_offline_data_analysis_in_real_sandbox(tmp_path):
    if os.environ.get("DEAR_DATA_DOCKER") != "1":
        pytest.skip("DEAR_DATA_DOCKER=1 requires runtime-agent-workspace:p4")
    (tmp_path / "work").mkdir()
    (tmp_path / "uploads").mkdir()
    fixture = Path(__file__).with_name("fixtures") / "legacy.xls"
    (tmp_path / "uploads/legacy.xls").write_bytes(fixture.read_bytes())
    check = Path(__file__).with_name("sandbox_data_check.py").read_text()
    (tmp_path / "work/check.py").write_text(check)
    result = asyncio.run(execute_in_workspace(tmp_path, "python /workspace/work/check.py",
        image="runtime-agent-workspace:p4", timeout=60, protected=True, skills=Path(str(SKILLS))))
    assert result.exit_code == 0, result.output
    assert "DATA_BATCH_OK" in result.output
    assert (tmp_path / "work/results.csv").read_text().strip() == "total\n30.0"
    exhausted = asyncio.run(execute_in_workspace(tmp_path, "python -c 'x=bytearray(512*1024*1024)'",
        image="runtime-agent-workspace:p4", timeout=15, protected=True))
    assert exhausted.exit_code != 0


@pytest.mark.e2e
def test_real_chart_matrix(tmp_path):
    if os.environ.get("DEAR_CHART_E2E") != "1":
        pytest.skip("DEAR_CHART_E2E=1 sends synthetic fixtures to AntV")
    tools = {t.name: t for t in chart.build_chart_tools(ImageWorkspace(tmp_path), include_spreadsheet=True)}
    evidence = []
    selected = set(filter(None, os.environ.get("DEAR_CHART_TYPES", "").split(",")))
    assert selected <= set(CHART_NAMES)
    async def run():
        for name, args in chart_cases().items():
            if selected and name not in selected:
                continue
            result = await tools[name].ainvoke({"type": "tool_call", "name": name, "id": name, "args": args})
            evidence.append({"name": name, "args": args, "status": result.status, "content": result.content, "artifact": result.artifact})
            print(name, result.status, flush=True)
    asyncio.run(run())
    target = Path(os.environ.get("DEAR_CHART_EVIDENCE", "/tmp/dear-chart-matrix.json"))
    target.write_text(json.dumps(evidence, ensure_ascii=False, indent=2, default=str))
    assert all(e["status"] == "success" for e in evidence), [(e["name"], e["status"]) for e in evidence]
