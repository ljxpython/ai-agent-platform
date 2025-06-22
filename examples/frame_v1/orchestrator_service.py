"""
Web编排器
负责协调Web智能体的执行流程，支持完整的业务流程编排
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

# 导入智能体工厂
from app.agents.factory import AgentFactory, agent_factory
from app.core.agents import StreamResponseCollector

# 导入消息类型
from app.core.messages import (
    AnalysisType,
    PlaywrightExecutionRequest,
    WebMultimodalAnalysisRequest,
    YAMLExecutionRequest,
)
from app.core.types import AgentTypes, TopicTypes
from autogen_core import (
    ClosureAgent,
    SingleThreadedAgentRuntime,
    TopicId,
    TypeSubscription,
)
from loguru import logger


class WebOrchestrator:
    """Web智能体编排器 - 支持完整业务流程"""

    def __init__(self, collector: Optional[StreamResponseCollector] = None):
        self.runtime: Optional[SingleThreadedAgentRuntime] = None

        # 使用智能体工厂
        self.agent_factory = agent_factory
        self.response_collector = collector

        # 会话管理
        self.active_sessions: Dict[str, Dict[str, Any]] = {}

        logger.info("Web智能体编排器初始化完成，使用智能体工厂模式")

    async def _setup_runtime(self, session_id: str) -> None:
        """设置运行时和所有智能体"""
        try:
            # 创建运行时
            self.runtime = SingleThreadedAgentRuntime()
            # 启动运行时
            self.runtime.start()
            # 创建响应收集器
            if self.response_collector is None:
                self.response_collector = StreamResponseCollector()

            # 使用智能体工厂注册Web平台智能体
            await self.agent_factory.register_web_agents(
                runtime=self.runtime,
                collector=self.response_collector,
                enable_user_feedback=False,
            )
            # 使用智能体工厂注册流式响应收集器
            await self.agent_factory.register_stream_collector(
                runtime=self.runtime, collector=self.response_collector
            )
            # 记录会话信息
            self.active_sessions[session_id] = {
                "status": "running",
                "started_at": datetime.now().isoformat(),
                "runtime_id": id(self.runtime),
                "registered_agents": len(self.agent_factory.list_registered_agents()),
            }

            logger.info(
                f"Web运行时设置完成，已注册 {len(self.agent_factory.list_registered_agents())} 个智能体: {session_id}"
            )

        except Exception as e:
            logger.error(f"设置Web运行时失败: {session_id}, 错误: {str(e)}")
            raise

    def get_agent_factory_info(self) -> Dict[str, Any]:
        """获取智能体工厂信息"""
        try:
            return {
                "available_agents": self.agent_factory.list_available_agents(),
                "registered_agents": self.agent_factory.list_registered_agents(),
                "factory_status": "active",
            }
        except Exception as e:
            logger.error(f"获取智能体工厂信息失败: {str(e)}")
            return {
                "available_agents": [],
                "registered_agents": [],
                "factory_status": "error",
                "error": str(e),
            }

    async def _cleanup_runtime(self) -> None:
        """清理运行时"""
        try:
            if self.runtime:
                await self.runtime.stop_when_idle()
                await self.runtime.close()
                self.runtime = None

            # 清理智能体工厂注册记录
            self.agent_factory.clear_registered_agents()

            # 重置响应收集器
            if self.response_collector:
                self.response_collector = None

            logger.debug("Web运行时清理完成")

        except Exception as e:
            logger.error(f"清理Web运行时失败: {str(e)}")

    # ==================== 业务流程1: 图片分析 → 脚本生成（支持格式选择） ====================

    async def analyze_image_to_scripts(
        self,
        session_id: str,
        image_data: str,
        test_description: str,
        additional_context: Optional[str] = None,
        generate_formats: Optional[List[str]] = None,
    ):
        """
        业务流程1: 图片分析 → 脚本生成（支持多种格式）

        Args:
            session_id: 会话ID
            image_data: Base64图片数据
            test_description: 测试描述
            additional_context: 额外上下文
            generate_formats: 生成格式列表，如 ["yaml", "playwright"]

        Returns:
            Dict[str, Any]: 包含分析结果和生成脚本的完整结果
        """
        try:
            if generate_formats is None:
                generate_formats = ["yaml"]

            logger.info(
                f"开始业务流程1 - 图片分析→脚本生成: {session_id}, 格式: {generate_formats}"
            )

            # 设置运行时
            await self._setup_runtime(session_id)

            # 构建图片分析请求
            analysis_request = WebMultimodalAnalysisRequest(
                session_id=session_id,
                analysis_type=AnalysisType.IMAGE,
                image_data=image_data,
                test_description=test_description,
                additional_context=additional_context,
                generate_formats=generate_formats,
            )

            # 发送到图片分析智能体
            await self.runtime.publish_message(
                analysis_request,
                topic_id=TopicId(type=TopicTypes.IMAGE_ANALYZER.value, source="user"),
            )
            logger.info(f"业务流程1完成: {session_id}")

        except Exception as e:
            logger.error(f"业务流程1失败: {session_id}, 错误: {str(e)}")
            raise
        finally:
            await self._cleanup_runtime()

    # ==================== 兼容性方法：保持向后兼容 ====================

    async def analyze_image_to_yaml(
        self,
        session_id: str,
        image_data: str,
        test_description: str,
        additional_context: Optional[str] = None,
    ):
        """
        兼容性方法: 图片分析 → YAML脚本生成
        """
        return await self.analyze_image_to_scripts(
            session_id=session_id,
            image_data=image_data,
            test_description=test_description,
            additional_context=additional_context,
            generate_formats=["yaml"],
        )

    async def analyze_image_to_playwright(
        self,
        session_id: str,
        image_data: str,
        test_description: str,
        additional_context: Optional[str] = None,
    ):
        """
        兼容性方法: 图片分析 → Playwright脚本生成
        """
        return await self.analyze_image_to_scripts(
            session_id=session_id,
            image_data=image_data,
            test_description=test_description,
            additional_context=additional_context,
            generate_formats=["playwright"],
        )

    # ==================== 业务流程3: YAML脚本执行 ====================

    async def execute_yaml_script(
        self,
        session_id: str,
        yaml_content: str,
        execution_config: Optional[Dict[str, Any]] = None,
    ):
        """
        业务流程3: YAML脚本执行

        Args:
            session_id: 会话ID
            yaml_content: YAML脚本内容
            execution_config: 执行配置

        Returns:
            Dict[str, Any]: 执行结果
        """
        try:
            logger.info(f"开始业务流程3 - YAML脚本执行: {session_id}")

            # 设置运行时
            await self._setup_runtime(session_id)

            # 构建YAML执行请求（使用正确的消息类型）
            execution_request = YAMLExecutionRequest(
                yaml_content=yaml_content, execution_config=execution_config
            )

            # 发送到YAML执行智能体
            await self.runtime.publish_message(
                execution_request,
                topic_id=TopicId(
                    type=TopicTypes.YAML_EXECUTOR.value, source="orchestrator"
                ),
            )

            # 等待执行完成
            await self.runtime.stop_when_idle()

            logger.info(f"业务流程3完成: {session_id}")
        except Exception as e:
            logger.error(f"业务流程3失败: {session_id}, 错误: {str(e)}")
            raise
        finally:
            await self._cleanup_runtime()

    # ==================== 业务流程4: Playwright脚本执行 ====================

    async def execute_playwright_script(self, request: PlaywrightExecutionRequest):
        """
        业务流程4: Playwright脚本执行（支持script_name和test_content）

        Args:
            request: Playwright执行请求

        Returns:
            Dict[str, Any]: 执行结果
        """
        try:
            logger.info(f"开始业务流程4 - Playwright脚本执行: {request.session_id}")

            if request.script_name:
                logger.info(f"执行现有脚本: {request.script_name}")
            else:
                logger.info(f"执行动态脚本内容")

            # 设置运行时
            await self._setup_runtime(request.session_id)

            # 发送到Playwright执行智能体
            await self.runtime.publish_message(
                request,
                topic_id=TopicId(
                    type=TopicTypes.PLAYWRIGHT_EXECUTOR.value, source="orchestrator"
                ),
            )

            logger.info(f"业务流程4完成: {request.session_id}")

        except Exception as e:
            logger.error(f"业务流程4失败: {request.session_id}, 错误: {str(e)}")
            raise
        finally:
            await self._cleanup_runtime()

    # 兼容性方法
    async def execute_playwright_script_legacy(
        self,
        session_id: str,
        playwright_content: str,
        execution_config: Optional[Dict[str, Any]] = None,
    ):
        """
        兼容性方法: Playwright脚本执行（旧版本接口）
        """
        request = PlaywrightExecutionRequest(
            session_id=session_id,
            test_content=playwright_content,
            execution_config=execution_config,
        )
        return await self.execute_playwright_script(request)

    # ==================== 会话管理方法 ====================

    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话状态"""
        session_info = self.active_sessions.get(session_id)
        if session_info:
            # 添加智能体工厂信息
            session_info["agent_factory_info"] = self.get_agent_factory_info()
        return session_info

    def list_active_sessions(self) -> List[str]:
        """列出活跃会话"""
        return list(self.active_sessions.keys())

    def get_available_agents(self) -> List[Dict[str, Any]]:
        """获取可用的智能体列表"""
        return self.agent_factory.list_available_agents()

    def get_registered_agents(self) -> List[Dict[str, Any]]:
        """获取已注册的智能体列表"""
        return self.agent_factory.list_registered_agents()

    async def create_custom_agent_workflow(
        self, session_id: str, agent_types: List[str], workflow_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """创建自定义智能体工作流

        Args:
            session_id: 会话ID
            agent_types: 要使用的智能体类型列表
            workflow_config: 工作流配置

        Returns:
            Dict[str, Any]: 工作流执行结果
        """
        try:
            logger.info(f"开始创建自定义智能体工作流: {session_id}")

            # 设置运行时
            await self._setup_runtime(session_id)

            # 验证智能体类型
            available_types = [
                agent["agent_type"]
                for agent in self.agent_factory.list_available_agents()
            ]
            invalid_types = [t for t in agent_types if t not in available_types]

            if invalid_types:
                raise ValueError(f"无效的智能体类型: {invalid_types}")

            # 记录工作流信息
            workflow_info = {
                "agent_types": agent_types,
                "config": workflow_config,
                "status": "running",
                "started_at": datetime.now().isoformat(),
            }

            self.active_sessions[session_id]["custom_workflow"] = workflow_info

            logger.info(f"自定义智能体工作流创建完成: {session_id}")

            return {
                "status": "success",
                "workflow_id": session_id,
                "agent_types": agent_types,
                "message": "自定义工作流创建成功",
            }

        except Exception as e:
            logger.error(f"创建自定义智能体工作流失败: {session_id}, 错误: {str(e)}")
            return {"status": "error", "message": str(e), "workflow_id": session_id}

    async def cancel_session(self, session_id: str) -> bool:
        """取消会话"""
        try:
            if session_id in self.active_sessions:
                self.active_sessions[session_id]["status"] = "cancelled"
                self.active_sessions[session_id][
                    "cancelled_at"
                ] = datetime.now().isoformat()

                # 如果是当前运行的会话，停止运行时
                if self.runtime:
                    await self.runtime.close()

                logger.info(f"会话已取消: {session_id}")
                return True
            return False

        except Exception as e:
            logger.error(f"取消会话失败: {str(e)}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            # 简单的运行时创建测试
            test_runtime = SingleThreadedAgentRuntime()
            test_runtime.start()
            await test_runtime.stop_when_idle()
            await test_runtime.close()

            # 获取智能体工厂信息
            factory_info = self.get_agent_factory_info()

            return {
                "status": "healthy",
                "message": "Web编排器运行正常",
                "active_sessions": len(self.active_sessions),
                "agent_factory": factory_info,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "message": f"Web编排器异常: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            }


# ==================== 全局实例管理 ====================

# 全局编排器实例
_web_orchestrator: Optional[WebOrchestrator] = None


def get_web_orchestrator(
    collector: Optional[StreamResponseCollector] = None,
) -> WebOrchestrator:
    """获取Web编排器实例"""
    # global _web_orchestrator
    # if _web_orchestrator is None:
    _web_orchestrator = WebOrchestrator(collector)
    return _web_orchestrator
