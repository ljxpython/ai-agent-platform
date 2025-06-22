"""
智能体工厂
统一创建和管理智能体实例，提供智能体注册和生命周期管理
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_core import SingleThreadedAgentRuntime, TypeSubscription
from loguru import logger

from backend.ai_core.agents import BaseAgent
from backend.ai_core.llm import (
    ModelType,
    get_deepseek_client,
    get_default_client,
    get_qwen_vl_client,
    get_ui_tars_client,
)


class AgentType(Enum):
    """智能体类型枚举"""

    # 测试用例生成相关
    REQUIREMENT_ANALYSIS = "requirement_analysis"
    TESTCASE_GENERATION = "testcase_generation"
    TESTCASE_OPTIMIZATION = "testcase_optimization"
    TESTCASE_FINALIZATION = "testcase_finalization"

    # UI测试相关
    UI_ANALYSIS = "ui_analysis"
    INTERACTION_ANALYSIS = "interaction_analysis"
    YAML_GENERATION = "yaml_generation"
    PLAYWRIGHT_GENERATION = "playwright_generation"

    # 通用智能体
    ASSISTANT = "assistant"
    USER_PROXY = "user_proxy"


class AgentFactory:
    """智能体工厂类，统一管理智能体的创建和注册"""

    def __init__(self):
        """初始化智能体工厂"""
        self._registered_agents: Dict[str, Dict[str, Any]] = {}
        self._agent_classes: Dict[str, Type[BaseAgent]] = {}
        self._agent_configs: Dict[str, Dict[str, Any]] = {}

        logger.info("🏭 [智能体工厂] 初始化完成")

    def register_agent_class(
        self,
        agent_type: AgentType,
        agent_class: Type[BaseAgent],
        default_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        注册智能体类

        Args:
            agent_type: 智能体类型
            agent_class: 智能体类
            default_config: 默认配置
        """
        self._agent_classes[agent_type.value] = agent_class
        if default_config:
            self._agent_configs[agent_type.value] = default_config

        logger.info(
            f"📝 [智能体工厂] 注册智能体类: {agent_type.value} -> {agent_class.__name__}"
        )

    def create_assistant_agent(
        self,
        name: str,
        system_message: str,
        model_type: ModelType = ModelType.DEEPSEEK,
        **kwargs,
    ) -> Optional[AssistantAgent]:
        """
        创建AssistantAgent实例（增强版，完整容错机制）

        Args:
            name: 智能体名称
            system_message: 系统提示词
            model_type: 模型类型
            **kwargs: 其他参数

        Returns:
            AssistantAgent: 创建的智能体实例，失败时返回None
        """
        try:
            logger.debug(
                f"🏭 [智能体工厂] 开始创建AssistantAgent | 名称: {name} | 模型: {model_type.value}"
            )

            # 参数验证
            if not name or not name.strip():
                logger.error(f"❌ [智能体工厂] 智能体名称不能为空")
                return None

            if not system_message or not system_message.strip():
                logger.warning(f"⚠️ [智能体工厂] 系统提示词为空，使用默认提示词")
                system_message = "你是一个有用的AI助手。"

            # 根据模型类型选择客户端
            logger.debug(f"   🔍 获取模型客户端: {model_type.value}")
            model_client = None

            try:
                if model_type == ModelType.DEEPSEEK:
                    model_client = get_deepseek_client()
                elif model_type == ModelType.QWEN_VL:
                    model_client = get_qwen_vl_client()
                elif model_type == ModelType.UI_TARS:
                    model_client = get_ui_tars_client()
                else:
                    model_client = get_default_client()
            except Exception as e:
                logger.error(f"❌ [智能体工厂] 获取模型客户端失败: {e}")
                # 尝试使用默认客户端作为备选
                try:
                    logger.info(f"   🔄 尝试使用默认客户端作为备选")
                    model_client = get_default_client()
                except Exception as fallback_e:
                    logger.error(f"❌ [智能体工厂] 备选客户端也失败: {fallback_e}")
                    return None

            if not model_client:
                logger.error(f"❌ [智能体工厂] 无法获取任何可用的模型客户端")
                return None

            logger.debug(f"   ✅ 模型客户端获取成功: {type(model_client).__name__}")

            # 创建AssistantAgent
            logger.debug(f"   🤖 创建AssistantAgent实例")
            agent = AssistantAgent(
                name=name.strip(),
                model_client=model_client,
                system_message=system_message.strip(),
                model_client_stream=True,
                **kwargs,
            )

            logger.info(
                f"🤖 [智能体工厂] 创建AssistantAgent成功: {name} (模型: {model_type.value})"
            )
            logger.debug(f"   📊 智能体参数: kwargs={list(kwargs.keys())}")
            return agent

        except Exception as e:
            logger.error(
                f"❌ [智能体工厂] 创建AssistantAgent失败 | 名称: {name} | 错误: {str(e)}"
            )
            logger.error(f"   🐛 错误类型: {type(e).__name__}")
            logger.error(f"   📍 错误位置: create_assistant_agent")
            return None

    def create_user_proxy_agent(
        self, name: str = "user_proxy", input_func: Optional[Callable] = None, **kwargs
    ) -> Optional[UserProxyAgent]:
        """
        创建UserProxyAgent实例（增强版，完整容错机制）

        Args:
            name: 智能体名称
            input_func: 用户输入函数
            **kwargs: 其他参数

        Returns:
            UserProxyAgent: 用户代理智能体实例，失败时返回None
        """
        try:
            logger.debug(f"🏭 [智能体工厂] 开始创建UserProxyAgent | 名称: {name}")

            # 参数验证
            if not name or not name.strip():
                logger.warning(f"⚠️ [智能体工厂] 用户代理名称为空，使用默认名称")
                name = "user_proxy"

            logger.debug(f"   👤 创建UserProxyAgent实例")
            agent = UserProxyAgent(name=name.strip(), input_func=input_func, **kwargs)

            logger.info(f"👤 [智能体工厂] 创建UserProxyAgent成功: {name}")
            logger.debug(
                f"   📊 智能体参数: input_func={'有' if input_func else '无'}, kwargs={list(kwargs.keys())}"
            )
            return agent

        except Exception as e:
            logger.error(
                f"❌ [智能体工厂] 创建UserProxyAgent失败 | 名称: {name} | 错误: {str(e)}"
            )
            logger.error(f"   🐛 错误类型: {type(e).__name__}")
            logger.error(f"   📍 错误位置: create_user_proxy_agent")
            return None

    def create_agent(
        self,
        agent_type: AgentType,
        agent_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        model_type: ModelType = ModelType.DEEPSEEK,
        **kwargs,
    ) -> BaseAgent:
        """
        创建自定义智能体实例

        Args:
            agent_type: 智能体类型
            agent_id: 智能体ID（可选）
            agent_name: 智能体名称（可选）
            model_type: 模型类型
            **kwargs: 智能体初始化参数

        Returns:
            BaseAgent: 创建的智能体实例
        """
        try:
            if agent_type.value not in self._agent_classes:
                raise ValueError(f"未注册的智能体类型: {agent_type.value}")

            agent_class = self._agent_classes[agent_type.value]

            # 获取模型客户端
            if model_type == ModelType.DEEPSEEK:
                model_client = get_deepseek_client()
            elif model_type == ModelType.QWEN_VL:
                model_client = get_qwen_vl_client()
            elif model_type == ModelType.UI_TARS:
                model_client = get_ui_tars_client()
            else:
                model_client = get_default_client()

            if not model_client:
                raise RuntimeError(f"无法获取{model_type.value}模型客户端")

            # 准备参数
            agent_params = {
                "agent_id": agent_id or f"{agent_type.value}_{id(object())}",
                "agent_name": agent_name or agent_type.value,
                "model_client": model_client,
                **kwargs,
            }

            # 合并默认配置
            if agent_type.value in self._agent_configs:
                default_config = self._agent_configs[agent_type.value].copy()
                default_config.update(agent_params)
                agent_params = default_config

            # 创建智能体实例
            agent = agent_class(**agent_params)

            logger.info(
                f"🤖 [智能体工厂] 创建智能体: {agent_name or agent_type.value} (类型: {agent_type.value})"
            )
            return agent

        except Exception as e:
            logger.error(
                f"❌ [智能体工厂] 创建智能体失败 ({agent_type.value}): {str(e)}"
            )
            raise

    async def register_agent_to_runtime(
        self,
        runtime: SingleThreadedAgentRuntime,
        agent_type: AgentType,
        topic_type: str,
        agent_factory_func: Optional[Callable] = None,
        **kwargs,
    ) -> None:
        """
        注册智能体到运行时

        Args:
            runtime: 智能体运行时
            agent_type: 智能体类型
            topic_type: 主题类型
            agent_factory_func: 智能体工厂函数（可选）
            **kwargs: 智能体初始化参数
        """
        try:
            if agent_type.value not in self._agent_classes:
                raise ValueError(f"未注册的智能体类型: {agent_type.value}")

            agent_class = self._agent_classes[agent_type.value]

            # 使用提供的工厂函数或默认创建函数
            if agent_factory_func:
                factory_func = agent_factory_func
            else:
                factory_func = lambda: self.create_agent(agent_type, **kwargs)

            # 注册智能体
            await agent_class.register(runtime, topic_type, factory_func)

            # 记录注册信息
            self._registered_agents[agent_type.value] = {
                "agent_type": agent_type.value,
                "topic_type": topic_type,
                "agent_class": agent_class.__name__,
                "kwargs": kwargs,
            }

            logger.info(
                f"📝 [智能体工厂] 注册智能体成功: {agent_type.value} -> {topic_type}"
            )

        except Exception as e:
            logger.error(
                f"❌ [智能体工厂] 注册智能体失败 ({agent_type.value}): {str(e)}"
            )
            raise

    def get_registered_agents(self) -> List[Dict[str, Any]]:
        """获取已注册的智能体列表"""
        return list(self._registered_agents.values())

    def get_available_agent_types(self) -> List[str]:
        """获取可用的智能体类型列表"""
        return list(self._agent_classes.keys())

    def clear_registered_agents(self) -> None:
        """清空已注册的智能体记录"""
        self._registered_agents.clear()
        logger.info("🗑️ [智能体工厂] 已清空智能体注册记录")


# 全局工厂实例
_agent_factory: Optional[AgentFactory] = None


def get_agent_factory() -> AgentFactory:
    """获取全局智能体工厂实例（单例模式）"""
    global _agent_factory
    if _agent_factory is None:
        _agent_factory = AgentFactory()
    return _agent_factory


# 便捷函数（增强版，完整容错机制）
def create_assistant_agent(
    name: str, system_message: str, model_type: ModelType = ModelType.DEEPSEEK, **kwargs
) -> Optional[AssistantAgent]:
    """
    创建AssistantAgent的便捷函数（增强版）

    Args:
        name: 智能体名称
        system_message: 系统提示词
        model_type: 模型类型
        **kwargs: 其他参数

    Returns:
        AssistantAgent: 创建的智能体实例，失败时返回None
    """
    try:
        logger.debug(f"🚀 [便捷函数] 创建AssistantAgent | 名称: {name}")
        factory = get_agent_factory()
        agent = factory.create_assistant_agent(
            name, system_message, model_type, **kwargs
        )

        if agent:
            logger.debug(f"   ✅ 便捷函数创建成功")
        else:
            logger.warning(f"   ⚠️ 便捷函数创建失败，返回None")

        return agent

    except Exception as e:
        logger.error(f"❌ [便捷函数] 创建AssistantAgent异常 | 名称: {name} | 错误: {e}")
        return None


def create_user_proxy_agent(
    name: str = "user_proxy", input_func: Optional[Callable] = None, **kwargs
) -> Optional[UserProxyAgent]:
    """
    创建UserProxyAgent的便捷函数（增强版）

    Args:
        name: 智能体名称
        input_func: 用户输入函数
        **kwargs: 其他参数

    Returns:
        UserProxyAgent: 用户代理智能体实例，失败时返回None
    """
    try:
        logger.debug(f"🚀 [便捷函数] 创建UserProxyAgent | 名称: {name}")
        factory = get_agent_factory()
        agent = factory.create_user_proxy_agent(name, input_func, **kwargs)

        if agent:
            logger.debug(f"   ✅ 便捷函数创建成功")
        else:
            logger.warning(f"   ⚠️ 便捷函数创建失败，返回None")

        return agent

    except Exception as e:
        logger.error(f"❌ [便捷函数] 创建UserProxyAgent异常 | 名称: {name} | 错误: {e}")
        return None


# 导出接口
__all__ = [
    "AgentType",
    "AgentFactory",
    "get_agent_factory",
    "create_assistant_agent",
    "create_user_proxy_agent",
]
