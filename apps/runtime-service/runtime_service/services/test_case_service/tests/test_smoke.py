"""test_case_service 冒烟测试套件。

覆盖范围：
- schemas：TestCaseServiceConfig 构建、路径解析
- prompts：SYSTEM_PROMPT 内容校验
- graph：make_graph 工厂函数（完整 monkeypatch）
- 注册：langgraph.json 中 test_case_agent 条目
"""
from __future__ import annotations

import asyncio
import importlib
import json
import sys
from pathlib import Path
from typing import Any, cast

from langchain.agents.middleware import ExtendedModelResponse, ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.services.test_case_service.schemas import (  # noqa: E402
    DEFAULT_MULTIMODAL_PARSER_MODEL_ID,
    DEFAULT_MULTIMODAL_DETAIL_MODE,
    DEFAULT_MULTIMODAL_DETAIL_TEXT_MAX_CHARS,
    DEFAULT_TEST_CASE_MODEL_ID,
    DEFAULT_TEST_CASE_KNOWLEDGE_MCP_ENABLED,
    DEFAULT_TEST_CASE_KNOWLEDGE_MCP_URL,
    DEFAULT_TEST_CASE_KNOWLEDGE_TIMEOUT_SECONDS,
    DEFAULT_TEST_CASE_KNOWLEDGE_SSE_READ_TIMEOUT_SECONDS,
    DEFAULT_TEST_CASE_PROJECT_ID,
    DEFAULT_TEST_CASE_PERSISTENCE_ENABLED,
    TestCaseServiceConfig as ServiceConfig,
    build_test_case_service_config,
    get_service_root,
    get_skills_root,
)
from runtime_service.services.test_case_service.prompts import (  # noqa: E402
    SYSTEM_PROMPT,
    build_test_case_system_prompt,
)
from runtime_service.services.test_case_service.document_persistence import (  # noqa: E402
    DocumentPersistenceOutcome,
    collect_persisted_document_ids,
)
from runtime_service.services.test_case_service.knowledge_query_guard_middleware import (  # noqa: E402
    QUERY_PROJECT_KNOWLEDGE_TOOL_NAME,
    READ_FILE_TOOL_NAME,
    REQUIREMENT_ANALYSIS_SKILL_PATH,
    TestCaseKnowledgeQueryGuardMiddleware,
)
from runtime_service.services.test_case_service.middleware import (  # noqa: E402
    TestCaseDocumentPersistenceMiddleware as DocumentPersistenceMiddleware,
)
from runtime_service.services.test_case_service.tool_runtime_context_middleware import (  # noqa: E402
    ToolRuntimeContextSanitizerMiddleware,
)
from runtime_service.middlewares.multimodal import MultimodalMiddleware  # noqa: E402

tc_graph = importlib.import_module(
    "runtime_service.services.test_case_service.graph"
)
tc_document_persistence = importlib.import_module(
    "runtime_service.services.test_case_service.document_persistence"
)
tc_middleware = importlib.import_module(
    "runtime_service.services.test_case_service.middleware"
)
tc_knowledge_guard = importlib.import_module(
    "runtime_service.services.test_case_service.knowledge_query_guard_middleware"
)


# ---------------------------------------------------------------------------
# schemas 测试
# ---------------------------------------------------------------------------


def test_get_service_root_returns_existing_directory() -> None:
    root = get_service_root()
    assert root.is_dir(), f"service root 不存在: {root}"


def test_get_skills_root_is_inside_service_root() -> None:
    skills_root = get_skills_root()
    service_root = get_service_root()
    assert skills_root == service_root / "skills"
    assert skills_root.is_dir(), f"skills 目录不存在: {skills_root}"


def test_build_test_case_service_config_defaults() -> None:
    config: dict[str, Any] = {"configurable": {}}
    cfg = build_test_case_service_config(config)
    assert isinstance(cfg, ServiceConfig)
    assert cfg.multimodal_parser_model_id == DEFAULT_MULTIMODAL_PARSER_MODEL_ID
    assert cfg.multimodal_detail_mode == DEFAULT_MULTIMODAL_DETAIL_MODE
    assert cfg.multimodal_detail_text_max_chars == DEFAULT_MULTIMODAL_DETAIL_TEXT_MAX_CHARS
    assert cfg.default_model_id == DEFAULT_TEST_CASE_MODEL_ID
    assert cfg.default_project_id == DEFAULT_TEST_CASE_PROJECT_ID
    assert cfg.persistence_enabled == DEFAULT_TEST_CASE_PERSISTENCE_ENABLED
    assert cfg.knowledge_mcp_enabled == DEFAULT_TEST_CASE_KNOWLEDGE_MCP_ENABLED
    assert cfg.knowledge_mcp_url == DEFAULT_TEST_CASE_KNOWLEDGE_MCP_URL
    assert cfg.knowledge_timeout_seconds == DEFAULT_TEST_CASE_KNOWLEDGE_TIMEOUT_SECONDS
    assert (
        cfg.knowledge_sse_read_timeout_seconds
        == DEFAULT_TEST_CASE_KNOWLEDGE_SSE_READ_TIMEOUT_SECONDS
    )


def test_build_test_case_service_config_overrides() -> None:
    config: dict[str, Any] = {
        "configurable": {
            "test_case_multimodal_parser_model_id": "custom_model",
            "test_case_multimodal_detail_mode": "true",
            "test_case_multimodal_detail_text_max_chars": "5000",
            "test_case_default_model_id": "glm5_mass",
            "test_case_default_project_id": "00000000-0000-0000-0000-000000000099",
            "test_case_persistence_enabled": "false",
            "test_case_knowledge_mcp_enabled": "false",
            "test_case_knowledge_mcp_url": "http://127.0.0.1:8765/sse",
            "test_case_knowledge_timeout_seconds": "15",
            "test_case_knowledge_sse_read_timeout_seconds": "120",
        }
    }
    cfg = build_test_case_service_config(config)
    assert cfg.multimodal_parser_model_id == "custom_model"
    assert cfg.multimodal_detail_mode is True
    assert cfg.multimodal_detail_text_max_chars == 5000
    assert cfg.default_model_id == "glm5_mass"
    assert cfg.default_project_id == "00000000-0000-0000-0000-000000000099"
    assert cfg.persistence_enabled is False
    assert cfg.knowledge_mcp_enabled is False
    assert cfg.knowledge_mcp_url == "http://127.0.0.1:8765/sse"
    assert cfg.knowledge_timeout_seconds == 15
    assert cfg.knowledge_sse_read_timeout_seconds == 120


def test_build_test_case_service_config_bool_variants() -> None:
    for truthy in ("1", "true", "yes", "on", "True", "YES"):
        cfg = build_test_case_service_config(
            {"configurable": {"test_case_multimodal_detail_mode": truthy}}
        )
        assert cfg.multimodal_detail_mode is True, f"期望 True，输入: {truthy!r}"

    for falsy in ("0", "false", "no", "off", ""):
        cfg = build_test_case_service_config(
            {"configurable": {"test_case_multimodal_detail_mode": falsy}}
        )
        assert cfg.multimodal_detail_mode is False, f"期望 False，输入: {falsy!r}"


def test_build_test_case_service_config_invalid_int_falls_back_to_default() -> None:
    cfg = build_test_case_service_config(
        {"configurable": {"test_case_multimodal_detail_text_max_chars": "not_a_number"}}
    )
    assert cfg.multimodal_detail_text_max_chars == DEFAULT_MULTIMODAL_DETAIL_TEXT_MAX_CHARS


# ---------------------------------------------------------------------------
# prompts 测试
# ---------------------------------------------------------------------------


def test_system_prompt_is_non_empty_string() -> None:
    assert isinstance(SYSTEM_PROMPT, str)
    assert len(SYSTEM_PROMPT.strip()) > 0


def test_system_prompt_mentions_key_skills() -> None:
    required_skills = [
        "requirement-analysis",
        "test-strategy",
        "test-case-design",
        "quality-review",
        "output-formatter",
        "test-data-generator",
        "test-case-persistence",
    ]
    for skill in required_skills:
        assert skill in SYSTEM_PROMPT, f"SYSTEM_PROMPT 中缺少 skill: {skill}"
    assert "query_project_knowledge" in SYSTEM_PROMPT
    assert "list_project_knowledge_documents" in SYSTEM_PROMPT
    assert "get_project_knowledge_document_status" in SYSTEM_PROMPT


def test_system_prompt_avoids_unnecessary_knowledge_queries_for_attachment_only_tasks() -> None:
    assert "如果当前轮上传附件和 `multimodal_summary` 已足以支撑结论" in SYSTEM_PROMPT
    assert "当前轮附件已经足够时，直接基于附件分析" in SYSTEM_PROMPT


def test_system_prompt_requires_knowledge_query_for_business_case_generation_without_attachments() -> None:
    assert "如果用户要求“生成某类业务/模块/场景相关的测试用例”" in SYSTEM_PROMPT
    assert "且当前轮没有提供附件或附件不足以支撑事实，必须先调用 `query_project_knowledge`" in SYSTEM_PROMPT
    assert "在“无附件 + 业务主题生成用例”场景下，没有命中知识库片段就不得臆造业务规则" in SYSTEM_PROMPT


def test_system_prompt_requires_read_file_before_substantive_output() -> None:
    assert "第一件事必须是调用一次 `read_file`" in SYSTEM_PROMPT
    assert "在首个 `read_file` 完成前，不得输出需求分析" in SYSTEM_PROMPT
    assert "Skills 列表、skill 名称、skill 描述只用于发现技能" in SYSTEM_PROMPT


def test_system_prompt_requires_stage_order_for_multi_phase_requests() -> None:
    assert "必须串行读取多个 skill 文件" in SYSTEM_PROMPT
    assert "先 `requirement-analysis`，再 `test-strategy`" in SYSTEM_PROMPT
    assert "如果工具调用记录中缺少当前阶段应有的 `read_file`" in SYSTEM_PROMPT
    assert "persist_test_case_results" in SYSTEM_PROMPT


def test_build_test_case_system_prompt_includes_current_project_id() -> None:
    prompt = build_test_case_system_prompt(
        runtime_system_prompt="RUNTIME_PREFIX",
        current_project_id="project-123",
    )
    assert prompt.startswith("RUNTIME_PREFIX")
    assert "当前项目 ID" in prompt
    assert "`project-123`" in prompt


def test_build_test_case_system_prompt_handles_missing_project_id() -> None:
    prompt = build_test_case_system_prompt(current_project_id=None)
    assert "未解析到 `project_id`" in prompt
    assert "不要臆造项目 ID" in prompt


# ---------------------------------------------------------------------------
# knowledge_query_guard_middleware 测试
# ---------------------------------------------------------------------------


class _DummyTool:
    def __init__(self, name: str) -> None:
        self.name = name


class _DummyRuntime:
    def __init__(self, project_id: str | None = None) -> None:
        self.context = type("Ctx", (), {"project_id": project_id})()


def _build_guard_request(
    messages: list[Any],
    *,
    project_id: str | None = "00000000-0000-0000-0000-000000000123",
    tool_names: list[str] | None = None,
) -> ModelRequest:
    return ModelRequest(
        model=cast(Any, object()),
        messages=messages,
        tools=cast(
            Any,
            [_DummyTool(name) for name in (tool_names or ["read_file", "query_project_knowledge", "persist_test_case_results"])],
        ),
        system_message=SystemMessage(content="base"),
        state=cast(Any, {}),
        runtime=cast(Any, _DummyRuntime(project_id=project_id)),
    )


def test_knowledge_guard_forces_requirement_skill_read_first() -> None:
    middleware = TestCaseKnowledgeQueryGuardMiddleware()
    captured: dict[str, Any] = {}
    request = _build_guard_request([HumanMessage(content="生成支付业务测试用例")])

    def handler(updated_request: ModelRequest) -> ModelResponse:
        captured["tool_names"] = [getattr(tool, "name", "") for tool in updated_request.tools]
        captured["system_prompt"] = tc_knowledge_guard._extract_text_from_content(
            updated_request.system_message.content
        )
        return ModelResponse(result=[AIMessage(content="直接给你测试用例")])

    response = middleware.wrap_model_call(request, handler)

    assert captured["tool_names"] == [READ_FILE_TOOL_NAME]
    assert "先读取 `/skills/requirement-analysis/SKILL.md`" in captured["system_prompt"]
    assert response.result[0].tool_calls[0]["name"] == READ_FILE_TOOL_NAME
    assert response.result[0].tool_calls[0]["args"]["file_path"] == REQUIREMENT_ANALYSIS_SKILL_PATH


def test_knowledge_guard_forces_query_after_requirement_skill_read() -> None:
    middleware = TestCaseKnowledgeQueryGuardMiddleware()
    captured: dict[str, Any] = {}
    request = _build_guard_request(
        [
            HumanMessage(content="生成支付业务测试用例"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": READ_FILE_TOOL_NAME,
                        "args": {"file_path": REQUIREMENT_ANALYSIS_SKILL_PATH},
                        "id": "tc_read_skill",
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(
                content="skill content",
                tool_call_id="tc_read_skill",
                name=READ_FILE_TOOL_NAME,
            ),
        ]
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        captured["tool_names"] = [getattr(tool, "name", "") for tool in updated_request.tools]
        captured["system_prompt"] = tc_knowledge_guard._extract_text_from_content(
            updated_request.system_message.content
        )
        return ModelResponse(result=[AIMessage(content="我准备直接写用例")])

    response = middleware.wrap_model_call(request, handler)

    assert captured["tool_names"] == [QUERY_PROJECT_KNOWLEDGE_TOOL_NAME]
    assert "下一步必须先调用 `query_project_knowledge`" in captured["system_prompt"]
    assert response.result[0].tool_calls[0]["name"] == QUERY_PROJECT_KNOWLEDGE_TOOL_NAME
    assert (
        response.result[0].tool_calls[0]["args"]["project_id"]
        == "00000000-0000-0000-0000-000000000123"
    )
    assert response.result[0].tool_calls[0]["args"]["query"] == "生成支付业务测试用例"


def test_knowledge_guard_releases_after_query_has_been_called() -> None:
    middleware = TestCaseKnowledgeQueryGuardMiddleware()
    captured: dict[str, Any] = {}
    request = _build_guard_request(
        [
            HumanMessage(content="生成支付业务测试用例"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": READ_FILE_TOOL_NAME,
                        "args": {"file_path": REQUIREMENT_ANALYSIS_SKILL_PATH},
                        "id": "tc_read_skill",
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(
                content="skill content",
                tool_call_id="tc_read_skill",
                name=READ_FILE_TOOL_NAME,
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": QUERY_PROJECT_KNOWLEDGE_TOOL_NAME,
                        "args": {
                            "project_id": "00000000-0000-0000-0000-000000000123",
                            "query": "生成支付业务测试用例",
                        },
                        "id": "tc_query",
                        "type": "tool_call",
                    }
                ],
            ),
            ToolMessage(
                content='{"count": 0, "items": []}',
                tool_call_id="tc_query",
                name=QUERY_PROJECT_KNOWLEDGE_TOOL_NAME,
            ),
        ]
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        captured["tool_names"] = [getattr(tool, "name", "") for tool in updated_request.tools]
        return ModelResponse(result=[AIMessage(content="知识依据不足，当前不生成正式测试用例。")])

    response = middleware.wrap_model_call(request, handler)

    assert captured["tool_names"] == [
        READ_FILE_TOOL_NAME,
        QUERY_PROJECT_KNOWLEDGE_TOOL_NAME,
        "persist_test_case_results",
    ]
    assert response.result[0].text == "知识依据不足，当前不生成正式测试用例。"


def test_knowledge_guard_skips_attachment_requests() -> None:
    middleware = TestCaseKnowledgeQueryGuardMiddleware()
    captured: dict[str, Any] = {}
    request = _build_guard_request(
        [
            HumanMessage(
                content=[
                    {"type": "text", "text": "生成支付业务测试用例"},
                    {"type": "file", "data": "ZmFrZQ==", "mimeType": "application/pdf"},
                ]
            )
        ]
    )

    def handler(updated_request: ModelRequest) -> ModelResponse:
        captured["tool_names"] = [getattr(tool, "name", "") for tool in updated_request.tools]
        return ModelResponse(result=[AIMessage(content="基于附件继续处理")])

    response = middleware.wrap_model_call(request, handler)

    assert captured["tool_names"] == [
        READ_FILE_TOOL_NAME,
        QUERY_PROJECT_KNOWLEDGE_TOOL_NAME,
        "persist_test_case_results",
    ]
    assert response.result[0].text == "基于附件继续处理"


# ---------------------------------------------------------------------------
# graph._resolve_backend_root_dir_path 测试
# ---------------------------------------------------------------------------


def test_resolve_backend_root_dir_path_defaults_to_service_root() -> None:
    path = tc_graph._resolve_backend_root_dir_path({}, agent_name="test_case_agent")
    assert path == get_service_root()


def test_resolve_backend_root_dir_path_respects_override(tmp_path: Path) -> None:
    path = tc_graph._resolve_backend_root_dir_path(
        {"test_case_backend_root_dir": str(tmp_path)},
        agent_name="test_case_agent",
    )
    assert path == tmp_path


def test_resolve_backend_root_dir_path_ignores_blank_override() -> None:
    path = tc_graph._resolve_backend_root_dir_path(
        {"test_case_backend_root_dir": "   "},
        agent_name="test_case_agent",
    )
    assert path == get_service_root()


# ---------------------------------------------------------------------------
# graph.make_graph 工厂函数测试（完整 monkeypatch）
# ---------------------------------------------------------------------------


def test_make_graph_wires_create_deep_agent_correctly(monkeypatch: Any) -> None:
    """验证 make_graph 正确组装 create_deep_agent 的所有参数。"""
    captured: dict[str, Any] = {}

    class DummyOptions:
        model_spec = "dummy_spec"
        system_prompt = ""

    async def fake_knowledge_tools(_config: Any) -> list[str]:
        return ["query_project_knowledge", "list_project_knowledge_documents"]

    def fake_create_deep_agent(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return kwargs

    monkeypatch.setattr(tc_graph, "merge_trusted_auth_context", lambda config, ctx: ctx)
    monkeypatch.setattr(tc_graph, "build_runtime_config", lambda config, ctx: DummyOptions())
    monkeypatch.setattr(tc_graph, "read_configurable", lambda config: {})
    monkeypatch.setattr(tc_graph, "resolve_model", lambda spec: "dummy_model")
    monkeypatch.setattr(tc_graph, "apply_model_runtime_params", lambda model, options: model)
    monkeypatch.setattr(tc_graph, "aget_test_case_knowledge_tools", fake_knowledge_tools)
    monkeypatch.setattr(tc_graph, "build_test_case_service_config", lambda config: ServiceConfig())
    monkeypatch.setattr(tc_graph, "create_deep_agent", fake_create_deep_agent)

    result = asyncio.run(tc_graph.make_graph({"configurable": {}}, object()))

    assert captured.get("name") == "test_case_agent"
    assert captured.get("model") == "dummy_model"
    tools = captured.get("tools") or []
    assert tools[:2] == ["query_project_knowledge", "list_project_knowledge_documents"]
    assert any(getattr(tool_obj, "name", "") == "persist_test_case_results" for tool_obj in tools[2:])
    middleware = captured.get("middleware") or []
    assert len(middleware) == 4
    assert isinstance(middleware[0], MultimodalMiddleware)
    assert isinstance(middleware[1], DocumentPersistenceMiddleware)
    assert isinstance(middleware[2], TestCaseKnowledgeQueryGuardMiddleware)
    assert isinstance(middleware[3], ToolRuntimeContextSanitizerMiddleware)
    assert captured.get("skills") == ["/skills/"]
    assert captured.get("context_schema") is not None
    assert result["system_prompt"]


def test_make_graph_merges_system_prompt_when_options_has_one(monkeypatch: Any) -> None:
    """当 options.system_prompt 非空时，应前置拼接到服务 SYSTEM_PROMPT。"""
    captured: dict[str, Any] = {}

    class DummyOptions:
        model_spec = "dummy_spec"
        system_prompt = "RUNTIME_PREFIX"

    async def fake_knowledge_tools(_config: Any) -> list[str]:
        return []

    def fake_create_deep_agent(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return kwargs

    monkeypatch.setattr(tc_graph, "merge_trusted_auth_context", lambda config, ctx: ctx)
    monkeypatch.setattr(tc_graph, "build_runtime_config", lambda config, ctx: DummyOptions())
    monkeypatch.setattr(tc_graph, "read_configurable", lambda config: {})
    monkeypatch.setattr(tc_graph, "resolve_model", lambda spec: "dummy_model")
    monkeypatch.setattr(tc_graph, "apply_model_runtime_params", lambda model, options: model)
    monkeypatch.setattr(tc_graph, "aget_test_case_knowledge_tools", fake_knowledge_tools)
    monkeypatch.setattr(tc_graph, "build_test_case_service_config", lambda config: ServiceConfig())
    monkeypatch.setattr(tc_graph, "create_deep_agent", fake_create_deep_agent)

    asyncio.run(tc_graph.make_graph({"configurable": {}}, object()))

    system_prompt = captured.get("system_prompt", "")
    assert system_prompt.startswith("RUNTIME_PREFIX")
    assert SYSTEM_PROMPT in system_prompt


def test_make_graph_uses_service_default_model_when_request_does_not_provide_one(
    monkeypatch: Any,
) -> None:
    captured_config: dict[str, Any] = {}

    class DummyOptions:
        model_spec = "dummy_spec"
        system_prompt = ""

    async def fake_knowledge_tools(_config: Any) -> list[str]:
        return []

    def fake_create_deep_agent(**kwargs: Any) -> dict[str, Any]:
        return kwargs

    def fake_build_runtime_config(config: Any, ctx: Any) -> DummyOptions:
        del ctx
        captured_config.update(dict(config))
        return DummyOptions()

    monkeypatch.setattr(tc_graph, "merge_trusted_auth_context", lambda config, ctx: ctx)
    monkeypatch.setattr(tc_graph, "build_runtime_config", fake_build_runtime_config)
    monkeypatch.setattr(tc_graph, "resolve_model", lambda spec: "dummy_model")
    monkeypatch.setattr(tc_graph, "apply_model_runtime_params", lambda model, options: model)
    monkeypatch.setattr(tc_graph, "aget_test_case_knowledge_tools", fake_knowledge_tools)
    monkeypatch.setattr(tc_graph, "create_deep_agent", fake_create_deep_agent)

    asyncio.run(tc_graph.make_graph({"configurable": {}}, object()))

    configurable = captured_config.get("configurable") or {}
    assert configurable.get("model_id") == DEFAULT_TEST_CASE_MODEL_ID


def test_make_graph_preserves_explicit_model_id_from_request(monkeypatch: Any) -> None:
    captured_config: dict[str, Any] = {}

    class DummyOptions:
        model_spec = "dummy_spec"
        system_prompt = ""

    async def fake_knowledge_tools(_config: Any) -> list[str]:
        return []

    def fake_create_deep_agent(**kwargs: Any) -> dict[str, Any]:
        return kwargs

    def fake_build_runtime_config(config: Any, ctx: Any) -> DummyOptions:
        del ctx
        captured_config.update(dict(config))
        return DummyOptions()

    monkeypatch.setattr(tc_graph, "merge_trusted_auth_context", lambda config, ctx: ctx)
    monkeypatch.setattr(tc_graph, "build_runtime_config", fake_build_runtime_config)
    monkeypatch.setattr(tc_graph, "resolve_model", lambda spec: "dummy_model")
    monkeypatch.setattr(tc_graph, "apply_model_runtime_params", lambda model, options: model)
    monkeypatch.setattr(tc_graph, "aget_test_case_knowledge_tools", fake_knowledge_tools)
    monkeypatch.setattr(tc_graph, "create_deep_agent", fake_create_deep_agent)

    asyncio.run(
        tc_graph.make_graph({"configurable": {"model_id": "iflow_kimi-k2"}}, object())
    )

    configurable = captured_config.get("configurable") or {}
    assert configurable.get("model_id") == "iflow_kimi-k2"


def test_make_graph_includes_project_id_in_system_prompt(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    class DummyOptions:
        model_spec = "dummy_spec"
        system_prompt = ""

    async def fake_knowledge_tools(_config: Any) -> list[str]:
        return []

    def fake_create_deep_agent(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return kwargs

    monkeypatch.setattr(tc_graph, "merge_trusted_auth_context", lambda config, ctx: ctx)
    monkeypatch.setattr(tc_graph, "build_runtime_config", lambda config, ctx: DummyOptions())
    monkeypatch.setattr(tc_graph, "read_configurable", lambda config: {})
    monkeypatch.setattr(tc_graph, "resolve_model", lambda spec: "dummy_model")
    monkeypatch.setattr(tc_graph, "apply_model_runtime_params", lambda model, options: model)
    monkeypatch.setattr(tc_graph, "aget_test_case_knowledge_tools", fake_knowledge_tools)
    monkeypatch.setattr(tc_graph, "build_test_case_service_config", lambda config: ServiceConfig())
    monkeypatch.setattr(tc_graph, "create_deep_agent", fake_create_deep_agent)

    asyncio.run(
        tc_graph.make_graph({"configurable": {}, "metadata": {"project_id": "project-xyz"}}, object())
    )

    system_prompt = captured.get("system_prompt", "")
    assert "`project-xyz`" in system_prompt


# ---------------------------------------------------------------------------
# langgraph.json 注册测试
# ---------------------------------------------------------------------------


def test_langgraph_registers_test_case_agent() -> None:
    langgraph_file = _PROJECT_ROOT / "runtime_service" / "langgraph.json"
    data = json.loads(langgraph_file.read_text(encoding="utf-8"))
    assert "test_case_agent" in data["graphs"], (
        "test_case_agent 未在 langgraph.json 中注册"
    )
    entry = data["graphs"]["test_case_agent"]
    assert "graph.py" in entry["path"]
    assert "test_case_service" in entry["path"]


def test_collect_persisted_document_ids_deduplicates_and_filters() -> None:
    state = {
        "multimodal_attachments": [
            {
                "persist_status": "persisted",
                "persisted_document_id": "doc-1",
            },
            {
                "persist_status": "persisted",
                "persisted_document_id": "doc-1",
            },
            {
                "persist_status": "failed",
                "persisted_document_id": "doc-2",
            },
            {
                "persist_status": "persisted",
                "persisted_document_id": "doc-3",
            },
        ]
    }
    assert collect_persisted_document_ids(state) == ["doc-1", "doc-3"]


def test_get_runtime_config_falls_back_to_langgraph_context(monkeypatch: Any) -> None:
    class RuntimeWithoutConfig:
        context = None

    expected = {"configurable": {"batch_id": "batch-from-context"}}
    monkeypatch.setattr(tc_document_persistence, "get_config", lambda: expected)
    assert tc_document_persistence._get_runtime_config(RuntimeWithoutConfig()) == expected


def test_document_persistence_middleware_writes_state_back(monkeypatch: Any) -> None:
    outcome = DocumentPersistenceOutcome(
        status="persisted",
        project_id="project-1",
        batch_id="batch-1",
        attachments=[
            {
                "attachment_id": "attachment-1",
                "kind": "pdf",
                "mime_type": "application/pdf",
                "status": "parsed",
                "source_type": "upload",
                "name": "demo.pdf",
                "summary_for_model": "summary",
                "parsed_text": "parsed text",
                "structured_data": None,
                "provenance": {"fingerprint": "fp-1"},
                "confidence": 0.9,
                "error": None,
                "persist_status": "persisted",
                "persisted_document_id": "doc-1",
            }
        ],
    )

    monkeypatch.setattr(tc_middleware, "persist_runtime_documents", lambda **_: outcome)
    middleware = DocumentPersistenceMiddleware(ServiceConfig())
    request = ModelRequest(
        model=cast(Any, object()),
        messages=[],
        state={
            "messages": [],
            "multimodal_attachments": [
                {
                    "attachment_id": "attachment-1",
                    "kind": "pdf",
                    "status": "parsed",
                    "summary_for_model": "summary",
                    "provenance": {"fingerprint": "fp-1"},
                }
            ],
        },
        runtime=cast(Any, object()),
    )

    result = middleware.wrap_model_call(
        request,
        lambda _request: ModelResponse(result=[AIMessage(content="ok")]),
    )

    assert isinstance(result, ExtendedModelResponse)
    assert result.command is not None
    assert result.command.update["multimodal_attachments"][0]["persisted_document_id"] == "doc-1"
