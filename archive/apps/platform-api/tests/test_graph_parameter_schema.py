from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from app.config import Settings
from app.services.graph_parameter_schema import GraphParameterSchemaService


def _runtime_service_root() -> Path:
    return Path(__file__).resolve().parents[2] / "runtime-service" / "runtime_service"


def _settings() -> Settings:
    return Settings(
        langgraph_upstream_url="http://127.0.0.1:8123",
        langgraph_upstream_api_key=None,
        interaction_data_service_url="http://127.0.0.1:8081",
        interaction_data_service_token=None,
        interaction_data_service_timeout_seconds=30,
        proxy_timeout_seconds=30,
        proxy_cors_allow_origins=["*"],
        proxy_upstream_retries=0,
        proxy_log_level="INFO",
        platform_db_enabled=True,
        platform_db_auto_create=False,
        database_url="postgresql+psycopg://x:y@localhost:5432/z",
        auth_required=True,
        langgraph_auth_required=False,
        langgraph_scope_guard_enabled=False,
        jwt_access_secret="test-access",
        jwt_refresh_secret="test-refresh",
        jwt_access_ttl_seconds=60,
        jwt_refresh_ttl_seconds=3600,
        bootstrap_admin_username="admin",
        bootstrap_admin_password="admin123456",
        logs_dir="logs",
        backend_log_file="backend.log",
        backend_log_max_bytes=1024,
        backend_log_backup_count=1,
        api_docs_enabled=False,
        langgraph_graph_source_root=str(_runtime_service_root()),
    )


def _section_map(schema: dict) -> dict[str, dict]:
    sections = schema.get("sections")
    if not isinstance(sections, list):
        return {}
    result: dict[str, dict] = {}
    for section in sections:
        if not isinstance(section, dict):
            continue
        key = section.get("key")
        if isinstance(key, str) and key:
            result[key] = section
    return result


def test_build_schema_uses_runtime_contract_v2_sections() -> None:
    service = GraphParameterSchemaService(_settings())

    schema = service.build_schema("assistant")
    sections = _section_map(schema)

    assert schema["graph_id"] == "assistant"
    assert schema["schema_version"] == "dynamic-v2"
    assert schema["dynamic"] is True
    assert list(sections.keys()) == ["config", "context", "configurable"]


def test_build_schema_moves_runtime_business_fields_into_context() -> None:
    service = GraphParameterSchemaService(_settings())

    schema = service.build_schema("assistant")
    sections = _section_map(schema)
    config_properties = sections["config"]["properties"]
    context_properties = sections["context"]["properties"]

    assert "recursion_limit" in config_properties
    assert "run_name" in config_properties
    assert "model_id" not in config_properties
    assert "system_prompt" not in config_properties
    assert "enable_local_tools" not in config_properties
    assert "local_tools" not in config_properties

    for key in (
        "project_id",
        "model_id",
        "system_prompt",
        "temperature",
        "max_tokens",
        "top_p",
        "enable_tools",
        "tools",
    ):
        assert key in context_properties

    assert sections["context"]["readonly_keys"] == [
        "user_id",
        "tenant_id",
        "role",
        "permissions",
        "project_id",
    ]


def test_build_schema_exposes_platform_and_service_private_configurable_fields() -> None:
    service = GraphParameterSchemaService(_settings())

    schema = service.build_schema("test_case_agent")
    sections = _section_map(schema)
    configurable_properties = sections["configurable"]["properties"]

    for key in (
        "thread_id",
        "checkpoint_id",
        "assistant_id",
        "graph_id",
        "langgraph_auth_user_id",
        "langgraph_auth_user",
        "test_case_multimodal_parser_model_id",
        "test_case_default_model_id",
        "test_case_knowledge_mcp_enabled",
    ):
        assert key in configurable_properties

    assert "__pregel_scratchpad" not in configurable_properties


def test_fallback_schema_keeps_new_contract_shape() -> None:
    service = GraphParameterSchemaService(_settings())

    schema = service.build_schema("graph-does-not-exist")
    sections = _section_map(schema)

    assert schema["schema_version"] == "fallback-v2"
    assert schema["dynamic"] is False
    assert list(sections.keys()) == ["config", "context", "configurable"]
