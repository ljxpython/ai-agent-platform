"""
大语言模型客户端管理器
支持DeepSeek-Chat、Qwen-VL-Max-Latest和UI-TARS等模型
提供统一的模型客户端管理和配置验证
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional, Union

from autogen_core.models import ModelFamily
from autogen_ext.models.openai import OpenAIChatCompletionClient
from loguru import logger
from openai import AsyncOpenAI

from backend.conf.config import settings


class ModelType(Enum):
    """模型类型枚举"""

    DEEPSEEK = "deepseek"
    QWEN_VL = "qwen_vl"
    UI_TARS = "ui_tars"


class LLMClientManager:
    """LLM客户端管理器"""

    def __init__(self):
        self._clients: Dict[ModelType, Optional[OpenAIChatCompletionClient]] = {
            ModelType.DEEPSEEK: None,
            ModelType.QWEN_VL: None,
            ModelType.UI_TARS: None,
        }
        self._async_clients: Dict[ModelType, Optional[AsyncOpenAI]] = {
            ModelType.DEEPSEEK: None,
            ModelType.QWEN_VL: None,
            ModelType.UI_TARS: None,
        }
        self._config_status: Optional[Dict[str, bool]] = None

    def _create_autogen_client(
        self, model_type: ModelType
    ) -> Optional[OpenAIChatCompletionClient]:
        """创建AutoGen兼容的模型客户端（增强版，完整容错机制）"""
        try:
            logger.debug(f"🏭 [LLM客户端] 开始创建{model_type.value}模型客户端")

            # 获取配置和模型信息
            config = None
            model_info = None

            try:
                if model_type == ModelType.DEEPSEEK:
                    config = settings.aimodel
                    model_info = {
                        "vision": False,
                        "function_calling": True,
                        "json_output": True,
                        "structured_output": True,
                        "family": ModelFamily.UNKNOWN,
                        "multiple_system_messages": True,
                    }
                elif model_type == ModelType.QWEN_VL:
                    config = settings.qwen_model
                    model_info = {
                        "vision": True,
                        "function_calling": True,
                        "json_output": True,
                        "structured_output": True,
                        "family": ModelFamily.UNKNOWN,
                        "multiple_system_messages": True,
                    }
                elif model_type == ModelType.UI_TARS:
                    config = settings.ui_tars_model
                    model_info = {
                        "vision": True,
                        "function_calling": True,
                        "json_output": True,
                        "structured_output": True,
                        "family": ModelFamily.UNKNOWN,
                        "multiple_system_messages": True,
                    }
                else:
                    logger.error(f"❌ [LLM客户端] 不支持的模型类型: {model_type}")
                    return None
            except Exception as e:
                logger.error(f"❌ [LLM客户端] 获取{model_type.value}配置失败: {e}")
                return None

            # 验证配置
            if not config:
                logger.error(f"❌ [LLM客户端] {model_type.value}配置为空")
                return None

            if not hasattr(config, "api_key") or not config.api_key:
                logger.warning(f"⚠️ [LLM客户端] {model_type.value} API密钥未配置")
                return None

            if not hasattr(config, "model") or not config.model:
                logger.error(f"❌ [LLM客户端] {model_type.value}模型名称未配置")
                return None

            if not hasattr(config, "base_url") or not config.base_url:
                logger.error(f"❌ [LLM客户端] {model_type.value}基础URL未配置")
                return None

            logger.debug(f"   ✅ 配置验证通过")
            logger.info(f"🤖 [LLM客户端] 创建{model_type.value}模型客户端")
            logger.info(f"   📋 模型: {config.model}")
            logger.info(f"   🌐 基础URL: {config.base_url}")
            logger.info(
                f"   🔑 API密钥: {'*' * (len(config.api_key) - 8) + config.api_key[-8:] if len(config.api_key) > 8 else '***'}"
            )

            # 创建客户端
            logger.debug(f"   🔧 创建OpenAIChatCompletionClient实例")
            client = OpenAIChatCompletionClient(
                model=config.model,
                api_key=config.api_key,
                base_url=config.base_url,
                model_info=model_info,
            )

            logger.success(f"✅ [LLM客户端] {model_type.value}模型客户端创建成功")
            logger.debug(
                f"   📊 模型能力: vision={model_info.get('vision', False)}, function_calling={model_info.get('function_calling', False)}"
            )
            return client

        except Exception as e:
            logger.error(
                f"❌ [LLM客户端] 创建{model_type.value}模型客户端失败: {str(e)}"
            )
            logger.error(f"   🐛 错误类型: {type(e).__name__}")
            logger.error(f"   📍 错误位置: _create_autogen_client")
            return None

    def _create_async_client(self, model_type: ModelType) -> Optional[AsyncOpenAI]:
        """创建异步OpenAI客户端"""
        try:
            if model_type == ModelType.DEEPSEEK:
                config = settings.aimodel
            elif model_type == ModelType.QWEN_VL:
                config = settings.qwen_model
            elif model_type == ModelType.UI_TARS:
                config = settings.ui_tars_model
            else:
                logger.error(f"❌ [异步客户端] 不支持的模型类型: {model_type}")
                return None

            if not config.api_key:
                logger.warning(f"⚠️ [异步客户端] {model_type.value} API密钥未配置")
                return None

            client = AsyncOpenAI(api_key=config.api_key, base_url=config.base_url)

            logger.success(f"✅ [异步客户端] {model_type.value}异步客户端创建成功")
            return client

        except Exception as e:
            logger.error(f"❌ [异步客户端] 创建{model_type.value}异步客户端失败: {e}")
            return None

    def get_autogen_client(
        self, model_type: ModelType
    ) -> Optional[OpenAIChatCompletionClient]:
        """获取AutoGen兼容的模型客户端（单例模式，增强版）"""
        try:
            logger.debug(f"🔍 [LLM客户端] 获取{model_type.value}客户端")

            if self._clients[model_type] is None:
                logger.debug(f"   🔄 客户端不存在，开始创建")
                self._clients[model_type] = self._create_autogen_client(model_type)

                if self._clients[model_type]:
                    logger.debug(f"   ✅ 客户端创建并缓存成功")
                else:
                    logger.warning(f"   ⚠️ 客户端创建失败")
            else:
                logger.debug(f"   ♻️ 使用缓存的客户端")

            return self._clients[model_type]

        except Exception as e:
            logger.error(f"❌ [LLM客户端] 获取{model_type.value}客户端失败: {e}")
            return None

    def get_async_client(self, model_type: ModelType) -> Optional[AsyncOpenAI]:
        """获取异步OpenAI客户端（单例模式）"""
        if self._async_clients[model_type] is None:
            self._async_clients[model_type] = self._create_async_client(model_type)
        return self._async_clients[model_type]

    def validate_configs(self) -> Dict[str, bool]:
        """验证所有模型配置"""
        if self._config_status is None:
            self._config_status = {
                "deepseek_configured": bool(getattr(settings.aimodel, "api_key", None)),
                "qwen_vl_configured": bool(
                    getattr(settings.qwen_model, "api_key", None)
                ),
                "ui_tars_configured": bool(
                    getattr(settings.ui_tars_model, "api_key", None)
                ),
            }

            if not any(self._config_status.values()):
                logger.warning("⚠️ [LLM配置] 没有配置任何AI模型API密钥")
            else:
                configured_models = [k for k, v in self._config_status.items() if v]
                logger.info(f"✅ [LLM配置] 已配置的模型: {configured_models}")

        return self._config_status

    def get_default_client(self) -> Optional[OpenAIChatCompletionClient]:
        """获取默认模型客户端（优先级：DeepSeek > Qwen-VL > UI-TARS）"""
        configs = self.validate_configs()

        if configs.get("deepseek_configured"):
            return self.get_autogen_client(ModelType.DEEPSEEK)
        elif configs.get("qwen_vl_configured"):
            return self.get_autogen_client(ModelType.QWEN_VL)
        elif configs.get("ui_tars_configured"):
            return self.get_autogen_client(ModelType.UI_TARS)
        else:
            logger.error("❌ [LLM客户端] 没有可用的模型配置")
            return None


# 创建全局客户端管理器实例
_client_manager = LLMClientManager()


# 便捷函数（增强版，完整容错机制）
def get_deepseek_client() -> Optional[OpenAIChatCompletionClient]:
    """获取DeepSeek模型客户端（增强版）"""
    try:
        logger.debug(f"🚀 [便捷函数] 获取DeepSeek客户端")
        client = _client_manager.get_autogen_client(ModelType.DEEPSEEK)

        if client:
            logger.debug(f"   ✅ DeepSeek客户端获取成功")
        else:
            logger.warning(f"   ⚠️ DeepSeek客户端获取失败")

        return client

    except Exception as e:
        logger.error(f"❌ [便捷函数] 获取DeepSeek客户端异常: {e}")
        return None


def get_qwen_vl_client() -> Optional[OpenAIChatCompletionClient]:
    """获取Qwen-VL模型客户端（增强版）"""
    try:
        logger.debug(f"🚀 [便捷函数] 获取Qwen-VL客户端")
        client = _client_manager.get_autogen_client(ModelType.QWEN_VL)

        if client:
            logger.debug(f"   ✅ Qwen-VL客户端获取成功")
        else:
            logger.warning(f"   ⚠️ Qwen-VL客户端获取失败")

        return client

    except Exception as e:
        logger.error(f"❌ [便捷函数] 获取Qwen-VL客户端异常: {e}")
        return None


def get_ui_tars_client() -> Optional[OpenAIChatCompletionClient]:
    """获取UI-TARS模型客户端（增强版）"""
    try:
        logger.debug(f"🚀 [便捷函数] 获取UI-TARS客户端")
        client = _client_manager.get_autogen_client(ModelType.UI_TARS)

        if client:
            logger.debug(f"   ✅ UI-TARS客户端获取成功")
        else:
            logger.warning(f"   ⚠️ UI-TARS客户端获取失败")

        return client

    except Exception as e:
        logger.error(f"❌ [便捷函数] 获取UI-TARS客户端异常: {e}")
        return None


def get_default_client() -> Optional[OpenAIChatCompletionClient]:
    """获取默认模型客户端（增强版）"""
    try:
        logger.debug(f"🚀 [便捷函数] 获取默认客户端")
        client = _client_manager.get_default_client()

        if client:
            logger.debug(f"   ✅ 默认客户端获取成功")
        else:
            logger.warning(f"   ⚠️ 默认客户端获取失败")

        return client

    except Exception as e:
        logger.error(f"❌ [便捷函数] 获取默认客户端异常: {e}")
        return None


def validate_model_configs() -> Dict[str, bool]:
    """验证模型配置（增强版）"""
    try:
        logger.debug(f"🔍 [便捷函数] 验证模型配置")
        configs = _client_manager.validate_configs()

        logger.debug(f"   📊 配置状态: {configs}")
        return configs

    except Exception as e:
        logger.error(f"❌ [便捷函数] 验证模型配置异常: {e}")
        return {
            "deepseek_configured": False,
            "qwen_vl_configured": False,
            "ui_tars_configured": False,
        }


def get_model_config_status() -> Dict[str, bool]:
    """获取模型配置状态（增强版）"""
    try:
        logger.debug(f"🔍 [便捷函数] 获取模型配置状态")
        status = _client_manager.validate_configs()

        logger.debug(f"   📊 配置状态: {status}")
        return status

    except Exception as e:
        logger.error(f"❌ [便捷函数] 获取模型配置状态异常: {e}")
        return {
            "deepseek_configured": False,
            "qwen_vl_configured": False,
            "ui_tars_configured": False,
        }


# 向后兼容接口（已移除旧的core/llm.py文件）
def get_openai_model_client() -> Optional[OpenAIChatCompletionClient]:
    """获取OpenAI模型客户端（向后兼容）"""
    return get_default_client()


# 导出接口
__all__ = [
    "ModelType",
    "LLMClientManager",
    "get_deepseek_client",
    "get_qwen_vl_client",
    "get_ui_tars_client",
    "get_default_client",
    "validate_model_configs",
    "get_model_config_status",
    "get_openai_model_client",  # 向后兼容
]
