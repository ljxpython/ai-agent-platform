from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from runtime_service.runtime.options import read_configurable
from langchain_core.runnables import RunnableConfig

DEFAULT_MULTIMODAL_PARSER_MODEL_ID = "iflow_qwen3-vl-plus"
DEFAULT_MULTIMODAL_DETAIL_MODE = False
DEFAULT_MULTIMODAL_DETAIL_TEXT_MAX_CHARS = 2000


@dataclass(frozen=True)
class TestCaseServiceConfig:
    multimodal_parser_model_id: str = DEFAULT_MULTIMODAL_PARSER_MODEL_ID
    multimodal_detail_mode: bool = DEFAULT_MULTIMODAL_DETAIL_MODE
    multimodal_detail_text_max_chars: int = DEFAULT_MULTIMODAL_DETAIL_TEXT_MAX_CHARS


def _parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _parse_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_test_case_service_config(config: RunnableConfig) -> TestCaseServiceConfig:
    """从 RunnableConfig 中解析服务配置，未提供则使用默认值。"""
    private_config = dict(read_configurable(config))
    return TestCaseServiceConfig(
        multimodal_parser_model_id=str(
            private_config.get("test_case_multimodal_parser_model_id")
            or DEFAULT_MULTIMODAL_PARSER_MODEL_ID
        ),
        multimodal_detail_mode=_parse_bool(
            private_config.get("test_case_multimodal_detail_mode"),
            DEFAULT_MULTIMODAL_DETAIL_MODE,
        ),
        multimodal_detail_text_max_chars=_parse_int(
            private_config.get("test_case_multimodal_detail_text_max_chars"),
            DEFAULT_MULTIMODAL_DETAIL_TEXT_MAX_CHARS,
        ),
    )


def get_service_root() -> Path:
    return Path(__file__).resolve().parent


def get_skills_root() -> Path:
    return get_service_root() / "skills"

