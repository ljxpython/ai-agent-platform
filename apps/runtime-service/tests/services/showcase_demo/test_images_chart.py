"""Image approval, local authorization, real graph delegation and bounded IO."""

import asyncio
import base64
import io
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit

import httpx
import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import ToolException, tool
from langgraph.types import Command
from PIL import Image
from runtime_service.tools import chart
from runtime_service.tools import images
from .test_agent import build as graph_builder
from .test_agent import call, config

build = graph_builder


def png():
    output = io.BytesIO()
    Image.new("RGB", (160, 160), "red").save(output, "PNG")
    return output.getvalue()


def fake_image_client(monkeypatch):
    calls = []

    class Client:
        def __init__(self, **kwargs):
            self.images = self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def generate(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                data=[
                    SimpleNamespace(b64_json=base64.b64encode(png()).decode(), url=None)
                ]
            )

        async def edit(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                data=[
                    SimpleNamespace(b64_json=base64.b64encode(png()).decode(), url=None)
                ]
            )

    monkeypatch.setattr(images, "AsyncOpenAI", Client)
    for key in ("IMAGE_25_KEY", "IMAGE_25_URL", "IMAGE_25_MODEL"):
        monkeypatch.setenv(key, "test")
    return calls


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_generate_requires_approval_without_platform_permission(
    build, monkeypatch, decision
):
    calls = fake_image_client(monkeypatch)

    async def run():
        cfg = config()
        graph, cfg, model = await build(
            [
                call("generate_image", {"prompt": "red square"}),
                AIMessage(content="done"),
            ],
            cfg,
        )
        result = await graph.ainvoke(
            {"messages": [("user", "generate")]}, cfg, context=cfg["context"]
        )
        assert (
            result["__interrupt__"][0].value["action_requests"][0]["name"]
            == "generate_image"
        )
        assert not calls
        result = await graph.ainvoke(
            Command(resume={"decisions": [{"type": decision}]}),
            cfg,
            context=cfg["context"],
        )
        assert len(calls) == (1 if decision == "approve" else 0)
        assert "generate_image" in model.seen_tools[0]
        if decision == "approve":
            message = next(m for m in result["messages"] if isinstance(m, ToolMessage))
            assert message.content.startswith("/workspace/generated/")

    asyncio.run(run())


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_edit_image_requires_approval_and_edits_existing_image(
    build, monkeypatch, decision, tmp_path
):
    calls = fake_image_client(monkeypatch)

    async def run():
        from runtime_service.services.demo.showcase_demo.backend import (
            DockerWorkspaceBackend,
        )

        backend = DockerWorkspaceBackend("tenant", "project", "teaching-thread")
        backend.prepare()
        path = images.ImageWorkspace(backend.cwd / "workspace").save(png(), "generated")

        cfg = config()
        graph, cfg, model = await build(
            [
                call("edit_image", {"image_path": path, "prompt": "turn anime"}),
                AIMessage(content="done"),
            ],
            cfg,
        )
        result = await graph.ainvoke(
            {"messages": [("user", "edit")]}, cfg, context=cfg["context"]
        )
        assert (
            result["__interrupt__"][0].value["action_requests"][0]["name"]
            == "edit_image"
        )
        assert not calls
        result = await graph.ainvoke(
            Command(resume={"decisions": [{"type": decision}]}),
            cfg,
            context=cfg["context"],
        )
        assert len(calls) == (1 if decision == "approve" else 0)
        assert "edit_image" in model.seen_tools[0]
        if decision == "approve":
            assert calls[0]["prompt"] == "turn anime"
            assert calls[0]["image"][0] == "image.png"
            message = next(m for m in result["messages"] if isinstance(m, ToolMessage))
            assert message.content.startswith("/workspace/generated/")

    asyncio.run(run())


def test_image_content_policy_violation_message(monkeypatch, tmp_path):
    class Client:
        def __init__(self, **kwargs):
            self.images = self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def generate(self, **kwargs):
            exc = Exception("Error code: 400 - content_policy_violation")
            exc.body = {"code": "content_policy_violation", "message": "Policy violation"}
            exc.status_code = 400
            raise exc

        async def edit(self, **kwargs):
            exc = Exception("Error code: 400 - content_policy_violation")
            exc.body = {"code": "content_policy_violation", "message": "Policy violation"}
            exc.status_code = 400
            raise exc

    monkeypatch.setattr(images, "AsyncOpenAI", Client)
    for key in ("IMAGE_25_KEY", "IMAGE_25_URL", "IMAGE_25_MODEL"):
        monkeypatch.setenv(key, "test")

    workspace = images.ImageWorkspace(tmp_path)
    tools = images.build_image_tools(workspace)
    generate_tool = next(t for t in tools if t.name == "generate_image")
    edit_tool = next(t for t in tools if t.name == "edit_image")
    path = workspace.save(png(), "generated")

    async def run():
        res_gen = await generate_tool.ainvoke({"prompt": "test sensitive"})
        assert "content_policy_violation" in str(res_gen)

        res_edit = await edit_tool.ainvoke({"image_path": path, "prompt": "test sensitive"})
        assert "content_policy_violation" in str(res_edit)

    asyncio.run(run())


@pytest.mark.e2e
def test_live_main_model_delegates_chart(monkeypatch, tmp_path):
    if os.getenv("RUNTIME_CHART_LIVE_TEST") != "1":
        pytest.skip("Set RUNTIME_CHART_LIVE_TEST=1 for real model routing and MCP")
    from dotenv import dotenv_values
    from langgraph.checkpoint.memory import InMemorySaver
    from runtime_service.services.demo.showcase_demo import agent
    from runtime_service.services.demo.showcase_demo.backend import (
        DockerWorkspaceBackend,
    )

    env = dotenv_values(Path(__file__).resolve().parents[3] / ".env")
    for name in ("DEEPSEEK_PROXY_URL", "DEEPSEEK_PROXY_API_KEY"):
        monkeypatch.setenv(name, env[name])
    monkeypatch.setenv("RUNTIME_SHOWCASE_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")

    async def run():
        cfg = config()
        graph = await agent.get_agent(cfg)
        graph.checkpointer = InMemorySaver()
        result = await graph.ainvoke(
            {
                "messages": [
                    (
                        "user",
                        "请画一张条形图：A 类 12、B 类 23。使用你的图表能力生成真实图片，返回图片文件路径。不要写代码，不要执行 shell。",
                    )
                ]
            },
            cfg,
            context={},
        )
        assert not result.get("__interrupt__")
        assert any(
            isinstance(m, AIMessage)
            and any(
                t["name"] == "task" and t["args"].get("subagent_type") == "chart-agent"
                for t in m.tool_calls
            )
            for m in result["messages"]
        )
        root = (
            DockerWorkspaceBackend("tenant", "project", "teaching-thread").cwd
            / "workspace"
        )
        artifacts = list(root.joinpath("charts").glob("*"))
        assert artifacts and images.image_type(artifacts[0].read_bytes())
        print("REAL_MODEL_CHART=" + str(artifacts[0]))

    asyncio.run(run())


def test_vision_is_read_only_and_does_not_interrupt(build, monkeypatch, tmp_path):
    seen = []

    class Vision:
        def __init__(self, **kwargs):
            pass

        async def ainvoke(self, messages, **kwargs):
            seen.extend(messages)
            return AIMessage(content="A red square.")

    monkeypatch.setattr(images, "ChatOpenAI", Vision)
    for key in ("DOUBAO_MODEL", "DOUBAO_API_KEY", "DOUBAO_API_BASE"):
        monkeypatch.setenv(key, "test")

    async def run():
        from runtime_service.services.demo.showcase_demo.backend import (
            DockerWorkspaceBackend,
        )

        backend = DockerWorkspaceBackend("tenant", "project", "teaching-thread")
        backend.prepare()
        path = images.ImageWorkspace(backend.cwd / "workspace").save(png(), "generated")
        graph, cfg, _ = await build(
            [call("analyze_image", {"image_path": path}), AIMessage(content="done")]
        )
        before = list(tmp_path.rglob("*"))
        result = await graph.ainvoke(
            {"messages": [("user", "describe")]}, cfg, context={}
        )
        assert not result.get("__interrupt__")
        assert any(
            isinstance(m, ToolMessage) and m.content == "A red square."
            for m in result["messages"]
        )
        assert before == list(tmp_path.rglob("*"))
        assert seen[0]["content"][1]["image_url"]["url"].startswith(
            "data:image/png;base64,"
        )

    asyncio.run(run())


def test_workspace_rejects_escape_symlinks_and_non_images(tmp_path):
    workspace = images.ImageWorkspace(tmp_path)
    path = workspace.save(png(), "generated")
    assert workspace.read(path) == png()
    (tmp_path / "escape").symlink_to(tmp_path.parent, target_is_directory=True)
    for unsafe in ("/etc/passwd", "/workspace/../a", "/workspace/escape/a"):
        with pytest.raises(ToolException):
            workspace.read(unsafe)
    (tmp_path / "charts").symlink_to(tmp_path.parent, target_is_directory=True)
    with pytest.raises(ToolException):
        workspace.save(png(), "charts")
    with pytest.raises(ToolException):
        images.image_type(b"not an image")
    with pytest.raises(ToolException):
        images.image_type(b"x" * (images.MAX_BYTES + 1))


def test_chart_delegation_and_role_boundary(build, monkeypatch):
    from runtime_service.services.demo.showcase_demo import agent

    called = []

    @tool
    async def generate_bar_chart(data: list[dict]) -> str:
        """Generate a chart for a graph contract test."""
        called.append(data)
        return "/workspace/charts/test.png"

    monkeypatch.setattr(agent, "build_chart_tools", lambda _: [generate_bar_chart])

    async def run():
        graph, cfg, model = await build(
            [
                call(
                    "task",
                    {"subagent_type": "chart-agent", "description": "Plot A=12."},
                ),
                call(
                    "generate_bar_chart",
                    {"data": [{"category": "A", "value": 12}]},
                    "bar",
                ),
                AIMessage(content="/workspace/charts/test.png"),
                AIMessage(content="Chart ready."),
            ]
        )
        result = await graph.ainvoke({"messages": [("user", "chart")]}, cfg, context={})
        assert called and result["messages"][-1].content == "Chart ready."
        assert "generate_bar_chart" not in model.seen_tools[0]
        child = next(
            names for names in model.seen_tools if "generate_bar_chart" in names
        )
        assert not {"task", "execute", "write_file", "generate_image"} & set(child)

    asyncio.run(run())


def test_chart_interceptor_downloads_into_workspace(monkeypatch, tmp_path):
    from mcp.types import CallToolResult, TextContent

    intercepted = []

    def convert(*args, **kwargs):
        intercepted.extend(kwargs["tool_interceptors"])

    async def download(url, **kwargs):
        assert kwargs["allowed_hosts"] == {"mdn.alipayobjects.com"}
        return png()

    monkeypatch.setattr(chart, "convert_mcp_tool_to_langchain_tool", convert)
    monkeypatch.setattr(chart, "download_image", download)
    chart.build_chart_tools(images.ImageWorkspace(tmp_path))

    async def handler(request):
        return CallToolResult(
            content=[
                TextContent(type="text", text="https://mdn.alipayobjects.com/test")
            ]
        )

    result = asyncio.run(intercepted[0](SimpleNamespace(name="generate_bar_chart", args={"data": [{"category": "A", "value": 12}]}), handler))
    assert result.content[0].text.startswith("/workspace/charts/")
    assert len(list((tmp_path / "charts").glob("*.png"))) == 1


@pytest.mark.parametrize(
    "url",
    [
        "http://mdn.alipayobjects.com/x",
        "https://localhost/x",
        "https://user:secret@mdn.alipayobjects.com/x",
    ],
)
def test_download_rejects_unapproved_urls(url):
    with pytest.raises(ToolException):
        asyncio.run(images.download_image(url, allowed_hosts={"mdn.alipayobjects.com"}))


def test_download_rejects_redirects(monkeypatch):
    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(
        lambda req: httpx.Response(302, headers={"location": "https://localhost/x"})
    )
    monkeypatch.setattr(
        images.httpx, "AsyncClient", lambda **kw: real_client(transport=transport, **kw)
    )
    with pytest.raises(ToolException):
        asyncio.run(
            images.download_image(
                "https://mdn.alipayobjects.com/x",
                allowed_hosts={"mdn.alipayobjects.com"},
            )
        )


def test_missing_mcp_executable_returns_error_without_artifact(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", "")
    tools = chart.build_chart_tools(images.ImageWorkspace(tmp_path))
    bar = next(t for t in tools if t.name == "generate_bar_chart")
    result = asyncio.run(
        bar.ainvoke(
            {
                "type": "tool_call",
                "id": "missing-npx",
                "name": bar.name,
                "args": {"data": [{"category": "A", "value": 12}]},
            }
        )
    )
    assert result.status == "error"
    assert not list(tmp_path.iterdir())
    assert "Chart MCP failed" in str(result.content)


def test_edited_file_action_cannot_skip_generation_approval(build, monkeypatch):
    calls = fake_image_client(monkeypatch)

    async def run():
        graph, cfg, _ = await build(
            [
                call("write_file", {"file_path": "/workspace/a.txt", "content": "a"}),
                AIMessage(content="done"),
            ]
        )
        await graph.ainvoke({"messages": [("user", "write")]}, cfg, context={})
        result = await graph.ainvoke(
            Command(
                resume={
                    "decisions": [
                        {
                            "type": "edit",
                            "edited_action": {
                                "name": "generate_image",
                                "args": {"prompt": "red square"},
                            },
                        }
                    ]
                }
            ),
            cfg,
            context={},
        )
        assert not calls
        assert (
            result["__interrupt__"][0].value["action_requests"][0]["name"]
            == "generate_image"
        )

    asyncio.run(run())


@pytest.mark.e2e
def test_live_image_approval_vision_and_chart_delegation(build, monkeypatch):
    """Opt-in: one paid generation, one vision call and one real MCP chart."""
    if os.getenv("RUNTIME_IMAGE_LIVE_TEST") != "1":
        pytest.skip("Set RUNTIME_IMAGE_LIVE_TEST=1 for real external calls")
    from dotenv import dotenv_values

    env = dotenv_values(Path(__file__).resolve().parents[3] / ".env")
    for name in (
        "IMAGE_25_KEY",
        "IMAGE_25_URL",
        "IMAGE_25_MODEL",
        "DOUBAO_API_BASE",
        "DOUBAO_MODEL",
        "DOUBAO_API_KEY",
        "DOUBAO_MAX_TOKENS",
        "RUNTIME_IMAGE_ASSET_HOSTS",
    ):
        if env.get(name):
            monkeypatch.setenv(name, env[name])
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    original_download = images.download_image

    # Report the non-secret host; production download restrictions remain active.
    async def observed_download(url, *, allowed_hosts):
        print("IMAGE_ASSET_HOST=" + str(urlsplit(url).hostname))
        return await original_download(url, allowed_hosts=allowed_hosts)

    monkeypatch.setattr(images, "download_image", observed_download)

    async def run():
        from runtime_service.services.demo.showcase_demo.backend import (
            DockerWorkspaceBackend,
        )

        generated = call(
            "generate_image",
            {"prompt": "A solid blue circle on a white background. No text."},
        )
        graph, cfg, model = await build([generated, AIMessage(content="generated")])
        result = await graph.ainvoke(
            {"messages": [("user", "generate one image")]}, cfg, context={}
        )
        assert result.get("__interrupt__")
        result = await graph.ainvoke(
            Command(resume={"decisions": [{"type": "approve"}]}), cfg, context={}
        )
        message = next(
            m
            for m in result["messages"]
            if isinstance(m, ToolMessage) and m.name == "generate_image"
        )
        assert message.status == "success", message.content
        path = message.content
        workspace = images.ImageWorkspace(
            DockerWorkspaceBackend("tenant", "project", "teaching-thread").cwd
            / "workspace"
        )
        assert images.image_type(workspace.read(path))
        model.responses = [
            call(
                "analyze_image",
                {"image_path": path, "question": "Name the shape and its color."},
                "vision-live",
            ),
            AIMessage(content="analyzed"),
        ]
        model.i = 0
        result = await graph.ainvoke(
            {"messages": [("user", "analyze it")]}, cfg, context={}
        )
        vision = next(
            m
            for m in result["messages"]
            if isinstance(m, ToolMessage) and m.name == "analyze_image"
        )
        assert vision.status == "success" and vision.content
        print("VISION_RESULT=" + str(vision.content))
        model.responses = [
            call(
                "task",
                {"subagent_type": "chart-agent", "description": "Plot A=12 and B=23."},
                "chart-live",
            ),
            call(
                "generate_bar_chart",
                {
                    "data": [
                        {"category": "A", "value": 12},
                        {"category": "B", "value": 23},
                    ]
                },
                "bar-live",
            ),
            AIMessage(content="chart complete"),
            AIMessage(content="done"),
        ]
        model.i = 0
        await graph.ainvoke({"messages": [("user", "make a chart")]}, cfg, context={})
        artifacts = list(workspace.root.joinpath("charts").glob("*"))
        assert artifacts and images.image_type(artifacts[0].read_bytes())
        print("LIVE_WORKSPACE=" + str(workspace.root))

    asyncio.run(run())


def test_normalize_chart_args_flow_diagram():
    # 1. 顶层 edges 缺失 data 与 nodes，包含残缺边与重复边
    raw_args = {
        "edges": [
            {"name": "broken", "source": "A"},  # 缺少 target
            {"name": "step1", "source": "A", "target": "B"},
            {"name": "step2", "source": "A", "target": "B"},  # 重复边
            {"name": "step3", "source": "B", "target": "C"},
        ],
        "title": "Test Flow",
    }
    normalized = chart.normalize_chart_args("generate_flow_diagram", raw_args)
    assert "data" in normalized
    data = normalized["data"]
    # 验证重复边已合并
    assert len(data["edges"]) == 2
    edge_ab = next(e for e in data["edges"] if e["source"] == "A" and e["target"] == "B")
    assert edge_ab["name"] == "step1 / step2"
    # 验证自动推导补齐了 nodes
    node_names = {n["name"] for n in data["nodes"]}
    assert node_names == {"A", "B", "C"}
    # 验证 title 等其它属性保留
    assert normalized["title"] == "Test Flow"


def test_normalize_chart_args_tree_and_items():
    # 2. 针对思维导图平铺参数
    tree_args = {
        "name": "Root",
        "children": [{"name": "Child1"}],
    }
    normalized_tree = chart.normalize_chart_args("generate_mind_map", tree_args)
    assert normalized_tree["data"]["name"] == "Root"
    assert normalized_tree["data"]["children"] == [{"name": "Child1"}]

    # 3. 针对 items 平铺到常规图表
    bar_args = {"items": [{"category": "X", "value": 10}]}
    normalized_bar = chart.normalize_chart_args("generate_bar_chart", bar_args)
    assert normalized_bar["data"] == [{"category": "X", "value": 10}]


def test_chart_flow_diagram_interceptor_normalizes_and_succeeds(monkeypatch, tmp_path):
    from mcp.types import CallToolResult, TextContent

    intercepted = []

    def convert(*args, **kwargs):
        intercepted.extend(kwargs["tool_interceptors"])

    async def download(url, **kwargs):
        return png()

    monkeypatch.setattr(chart, "convert_mcp_tool_to_langchain_tool", convert)
    monkeypatch.setattr(chart, "download_image", download)
    chart.build_chart_tools(images.ImageWorkspace(tmp_path))

    received_request = None

    async def handler(request):
        nonlocal received_request
        received_request = request
        return CallToolResult(
            content=[
                TextContent(type="text", text="https://mdn.alipayobjects.com/chart.png")
            ]
        )

    # 传入大模型常犯错的平铺 edges（无 data，无 nodes，有重复边）
    raw_input = {
        "edges": [
            {"source": "支付服务", "target": "订单服务", "name": "支付地址"},
            {"source": "支付服务", "target": "订单服务", "name": "支付回调"},
        ]
    }
    result = asyncio.run(
        intercepted[0](
            SimpleNamespace(name="generate_flow_diagram", args=raw_input),
            handler,
        )
    )
    assert not result.isError
    assert result.content[0].text.startswith("/workspace/charts/")
    # 验证透传给底层 handler 的参数已自动规范化与去重
    assert len(received_request.args["data"]["edges"]) == 1
    assert received_request.args["data"]["edges"][0]["name"] == "支付地址 / 支付回调"
    assert len(received_request.args["data"]["nodes"]) == 2


def test_chart_validation_error_returns_friendly_message(monkeypatch, tmp_path):
    intercepted = []

    def convert(*args, **kwargs):
        intercepted.extend(kwargs["tool_interceptors"])

    monkeypatch.setattr(chart, "convert_mcp_tool_to_langchain_tool", convert)
    chart.build_chart_tools(images.ImageWorkspace(tmp_path))

    async def handler(request):
        raise AssertionError("handler should not be called on validation error")

    # 传入无效类型的参数（非法的 width）
    result = asyncio.run(
        intercepted[0](
            SimpleNamespace(name="generate_bar_chart", args={"data": [{"category": "A", "value": 1}], "width": "invalid_number"}),
            handler,
        )
    )
    assert result.isError
    assert "Chart argument validation failed" in result.content[0].text


def test_chart_mcp_error_returns_friendly_message(monkeypatch, tmp_path):
    from mcp.shared.exceptions import McpError
    from mcp.types import ErrorData

    intercepted = []

    def convert(*args, **kwargs):
        intercepted.extend(kwargs["tool_interceptors"])

    monkeypatch.setattr(chart, "convert_mcp_tool_to_langchain_tool", convert)
    chart.build_chart_tools(images.ImageWorkspace(tmp_path))

    async def handler(request):
        raise McpError(ErrorData(code=-32603, message="Failed to generate chart: Something went wrong in AntV\nError: internal stack"))

    result = asyncio.run(
        intercepted[0](
            SimpleNamespace(name="generate_bar_chart", args={"data": [{"category": "A", "value": 1}]}),
            handler,
        )
    )
    assert result.isError
    assert "Chart generation failed: Failed to generate chart: Something went wrong in AntV" in result.content[0].text
