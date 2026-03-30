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
from langchain_core.messages import AIMessage

_PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runtime_service.services.test_case_service.schemas import (  # noqa: E402
    TestCaseServiceConfig,
    build_test_case_service_config,
    get_service_root,
    get_skills_root,
    DEFAULT_MULTIMODAL_PARSER_MODEL_ID,
    DEFAULT_MULTIMODAL_DETAIL_MODE,
    DEFAULT_MULTIMODAL_DETAIL_TEXT_MAX_CHARS,
    DEFAULT_TEST_CASE_MODEL_ID,
    DEFAULT_TEST_CASE_PROJECT_ID,
    DEFAULT_TEST_CASE_PERSISTENCE_ENABLED,
)
from runtime_service.services.test_case_service.prompts import SYSTEM_PROMPT  # noqa: E402
from runtime_service.services.test_case_service.document_persistence import (  # noqa: E402
    DocumentPersistenceOutcome,
    collect_persisted_document_ids,
)
from runtime_service.services.test_case_service.middleware import (  # noqa: E402
    TestCaseDocumentPersistenceMiddleware,
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
    assert isinstance(cfg, TestCaseServiceConfig)
    assert cfg.multimodal_parser_model_id == DEFAULT_MULTIMODAL_PARSER_MODEL_ID
    assert cfg.multimodal_detail_mode == DEFAULT_MULTIMODAL_DETAIL_MODE
    assert cfg.multimodal_detail_text_max_chars == DEFAULT_MULTIMODAL_DETAIL_TEXT_MAX_CHARS
    assert cfg.default_model_id == DEFAULT_TEST_CASE_MODEL_ID
    assert cfg.default_project_id == DEFAULT_TEST_CASE_PROJECT_ID
    assert cfg.persistence_enabled == DEFAULT_TEST_CASE_PERSISTENCE_ENABLED


def test_build_test_case_service_config_overrides() -> None:
    config: dict[str, Any] = {
        "configurable": {
            "test_case_multimodal_parser_model_id": "custom_model",
            "test_case_multimodal_detail_mode": "true",
            "test_case_multimodal_detail_text_max_chars": "5000",
            "test_case_default_model_id": "glm5_mass",
            "test_case_default_project_id": "00000000-0000-0000-0000-000000000099",
            "test_case_persistence_enabled": "false",
        }
    }
    cfg = build_test_case_service_config(config)
    assert cfg.multimodal_parser_model_id == "custom_model"
    assert cfg.multimodal_detail_mode is True
    assert cfg.multimodal_detail_text_max_chars == 5000
    assert cfg.default_model_id == "glm5_mass"
    assert cfg.default_project_id == "00000000-0000-0000-0000-000000000099"
    assert cfg.persistence_enabled is False


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


def test_system_prompt_requires_read_file_before_substantive_output() -> None:
    assert "第一件事必须是调用一次 `read_file`" in SYSTEM_PROMPT
    assert "在首个 `read_file` 完成前，不得输出需求分析" in SYSTEM_PROMPT
    assert "Skills 列表、skill 名称、skill 描述只用于发现技能" in SYSTEM_PROMPT


def test_system_prompt_requires_stage_order_for_multi_phase_requests() -> None:
    assert "必须串行读取多个 skill 文件" in SYSTEM_PROMPT
    assert "先 `requirement-analysis`，再 `test-strategy`" in SYSTEM_PROMPT
    assert "如果工具调用记录中缺少当前阶段应有的 `read_file`" in SYSTEM_PROMPT
    assert "persist_test_case_results" in SYSTEM_PROMPT


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

    async def fake_build_tools(_config: Any) -> list[str]:
        return ["tool_a"]

    def fake_create_deep_agent(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return kwargs

    monkeypatch.setattr(tc_graph, "merge_trusted_auth_context", lambda config, ctx: ctx)
    monkeypatch.setattr(tc_graph, "build_runtime_config", lambda config, ctx: DummyOptions())
    monkeypatch.setattr(tc_graph, "read_configurable", lambda config: {})
    monkeypatch.setattr(tc_graph, "resolve_model", lambda spec: "dummy_model")
    monkeypatch.setattr(tc_graph, "apply_model_runtime_params", lambda model, options: model)
    monkeypatch.setattr(tc_graph, "build_tools", fake_build_tools)
    monkeypatch.setattr(tc_graph, "build_test_case_service_config", lambda config: TestCaseServiceConfig())
    monkeypatch.setattr(tc_graph, "create_deep_agent", fake_create_deep_agent)

    result = asyncio.run(tc_graph.make_graph({"configurable": {}}, object()))

    assert captured.get("name") == "test_case_agent"
    assert captured.get("model") == "dummy_model"
    tools = captured.get("tools") or []
    assert tools[0] == "tool_a"
    assert any(getattr(tool_obj, "name", "") == "persist_test_case_results" for tool_obj in tools[1:])
    middleware = captured.get("middleware") or []
    assert len(middleware) == 2
    assert isinstance(middleware[0], MultimodalMiddleware)
    assert isinstance(middleware[1], TestCaseDocumentPersistenceMiddleware)
    assert captured.get("skills") == ["/skills/"]
    assert captured.get("context_schema") is not None


def test_make_graph_merges_system_prompt_when_options_has_one(monkeypatch: Any) -> None:
    """当 options.system_prompt 非空时，应前置拼接到服务 SYSTEM_PROMPT。"""
    captured: dict[str, Any] = {}

    class DummyOptions:
        model_spec = "dummy_spec"
        system_prompt = "RUNTIME_PREFIX"

    async def fake_build_tools(_config: Any) -> list[str]:
        return []

    def fake_create_deep_agent(**kwargs: Any) -> dict[str, Any]:
        captured.update(kwargs)
        return kwargs

    monkeypatch.setattr(tc_graph, "merge_trusted_auth_context", lambda config, ctx: ctx)
    monkeypatch.setattr(tc_graph, "build_runtime_config", lambda config, ctx: DummyOptions())
    monkeypatch.setattr(tc_graph, "read_configurable", lambda config: {})
    monkeypatch.setattr(tc_graph, "resolve_model", lambda spec: "dummy_model")
    monkeypatch.setattr(tc_graph, "apply_model_runtime_params", lambda model, options: model)
    monkeypatch.setattr(tc_graph, "build_tools", fake_build_tools)
    monkeypatch.setattr(tc_graph, "build_test_case_service_config", lambda config: TestCaseServiceConfig())
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

    async def fake_build_tools(_config: Any) -> list[str]:
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
    monkeypatch.setattr(tc_graph, "build_tools", fake_build_tools)
    monkeypatch.setattr(tc_graph, "create_deep_agent", fake_create_deep_agent)

    asyncio.run(tc_graph.make_graph({"configurable": {}}, object()))

    configurable = captured_config.get("configurable") or {}
    assert configurable.get("model_id") == DEFAULT_TEST_CASE_MODEL_ID


def test_make_graph_preserves_explicit_model_id_from_request(monkeypatch: Any) -> None:
    captured_config: dict[str, Any] = {}

    class DummyOptions:
        model_spec = "dummy_spec"
        system_prompt = ""

    async def fake_build_tools(_config: Any) -> list[str]:
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
    monkeypatch.setattr(tc_graph, "build_tools", fake_build_tools)
    monkeypatch.setattr(tc_graph, "create_deep_agent", fake_create_deep_agent)

    asyncio.run(
        tc_graph.make_graph({"configurable": {"model_id": "iflow_kimi-k2"}}, object())
    )

    configurable = captured_config.get("configurable") or {}
    assert configurable.get("model_id") == "iflow_kimi-k2"


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
    middleware = TestCaseDocumentPersistenceMiddleware(TestCaseServiceConfig())
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
