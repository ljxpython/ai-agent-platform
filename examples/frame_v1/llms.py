"""
大语言模型客户端配置
支持DeepSeek-Chat、Qwen-VL-Max-Latest和UI-TARS等模型
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.core.config import settings
from autogen_ext.models.openai import OpenAIChatCompletionClient
from loguru import logger
from openai import AsyncOpenAI

_deepseek_model_client = None
_qwenvl_model_client = None
_uitars_model_client = None


def get_deepseek_model_client() -> OpenAIChatCompletionClient:
    """获取AutoGen兼容的模型客户端"""
    global _deepseek_model_client
    if _deepseek_model_client is None:
        _deepseek_model_client = OpenAIChatCompletionClient(
            model=settings.DEEPSEEK_MODEL,
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            model_info={
                "vision": False,
                "function_calling": True,
                "json_output": True,
                "structured_output": True,  # 添加 structured_output 字段
                "family": "unknown",
                "multiple_system_messages": True,
            },
        )
    return _deepseek_model_client


def get_qwenvl_model_client() -> OpenAIChatCompletionClient:
    """获取AutoGen兼容的模型客户端"""
    global _qwenvl_model_client
    if _qwenvl_model_client is None:
        _qwenvl_model_client = OpenAIChatCompletionClient(
            model=settings.QWEN_VL_MODEL,
            api_key=settings.QWEN_VL_API_KEY,
            base_url=settings.QWEN_VL_BASE_URL,
            model_info={
                "vision": True,
                "function_calling": True,
                "json_output": True,
                "structured_output": True,
                "family": "unknown",
                "multiple_system_messages": True,
            },
        )
    return _qwenvl_model_client


def get_uitars_model_client() -> OpenAIChatCompletionClient:
    """获取AutoGen兼容的模型客户端"""
    global _uitars_model_client
    if _uitars_model_client is None:
        _uitars_model_client = OpenAIChatCompletionClient(
            model=settings.UI_TARS_MODEL,
            api_key=settings.UI_TARS_API_KEY,
            base_url=settings.UI_TARS_BASE_URL,
            model_info={
                "vision": True,
                "function_calling": True,
                "json_output": True,
                "structured_output": True,
                "family": "unknown",
                "multiple_system_messages": True,
            },
        )
    return _uitars_model_client


# 模型配置验证
def validate_model_config() -> Dict[str, bool]:
    """验证模型配置"""
    config_status = {
        "deepseek_configured": bool(settings.DEEPSEEK_API_KEY),
        "openai_configured": bool(settings.OPENAI_API_KEY),
        "qwen_vl_configured": bool(settings.QWEN_VL_API_KEY),
        "ui_tars_configured": bool(settings.UI_TARS_API_KEY),
    }

    if not any(config_status.values()):
        logger.warning("没有配置任何AI模型API密钥")

    return config_status


# 延迟初始化配置状态
_config_status = None


def get_model_config_status() -> Dict[str, bool]:
    """获取模型配置状态（延迟初始化）"""
    global _config_status
    if _config_status is None:
        _config_status = validate_model_config()
        logger.info(f"AI模型配置状态: {_config_status}")
    return _config_status
