"""
AI智能体基础类
基于AutoGen框架的标准智能体基类，参考examples/frame_v1/base.py设计
提供统一的智能体基础功能，包括流式输出、错误处理、性能监控等
"""

import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from autogen_core import MessageContext, RoutedAgent, TopicId
from autogen_ext.models.openai import OpenAIChatCompletionClient
from loguru import logger
from pydantic import BaseModel


class AgentMessage(BaseModel):
    """智能体消息基础模型"""

    type: str
    source: str
    content: str
    conversation_id: str
    timestamp: str = None
    is_final: bool = False
    metadata: Optional[Dict[str, Any]] = None

    def __init__(self, **data):
        if not data.get("timestamp"):
            data["timestamp"] = datetime.now().isoformat()
        super().__init__(**data)


class AgentPerformanceMetrics:
    """智能体性能指标管理"""

    def __init__(self):
        self.metrics: Dict[str, Dict[str, Any]] = {}

    def start_monitoring(self, operation_name: str) -> str:
        """开始性能监控"""
        monitor_id = f"{operation_name}_{uuid.uuid4().hex[:8]}"
        self.metrics[monitor_id] = {
            "operation": operation_name,
            "start_time": time.time(),
            "status": "running",
        }
        return monitor_id

    def end_monitoring(self, monitor_id: str) -> Optional[Dict[str, Any]]:
        """结束性能监控"""
        if monitor_id not in self.metrics:
            return None

        metric = self.metrics[monitor_id]
        end_time = time.time()
        duration = end_time - metric["start_time"]

        result = {
            **metric,
            "end_time": end_time,
            "duration": duration,
            "status": "completed",
        }

        del self.metrics[monitor_id]
        return result


class BaseAgent(RoutedAgent, ABC):
    """
    智能体基础类，参考examples/frame_v1/base.py设计
    提供统一的智能体基础功能，包括流式输出、错误处理、性能监控等
    """

    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        model_client: Optional[OpenAIChatCompletionClient] = None,
        system_message: str = "",
        enable_user_feedback: bool = False,
        collector=None,
        **kwargs,
    ):
        """
        初始化基础智能体

        Args:
            agent_id: 智能体唯一标识
            agent_name: 智能体显示名称
            model_client: LLM模型客户端
            system_message: 系统提示词
            enable_user_feedback: 是否启用用户反馈
            collector: 响应收集器
            **kwargs: 其他参数
        """
        super().__init__(agent_id)
        self.agent_name = agent_name
        self.model_client = model_client
        self.system_message = system_message
        self.enable_user_feedback = enable_user_feedback
        self.collector = collector
        self._metadata = kwargs
        self.performance = AgentPerformanceMetrics()

        logger.info(f"🤖 [智能体初始化] {agent_name} (ID: {agent_id})")

    async def send_message(
        self,
        content: str,
        message_type: str = "message",
        is_final: bool = False,
        result: Optional[Dict[str, Any]] = None,
        conversation_id: str = "",
        source: Optional[str] = None,
    ) -> None:
        """
        发送消息到流输出主题，参考examples/frame_v1/base.py设计

        Args:
            content: 消息内容
            message_type: 消息类型
            is_final: 是否是最终消息
            result: 可选的结果数据
            conversation_id: 对话ID
            source: 消息来源
        """
        message = AgentMessage(
            type=message_type,
            source=source if source else self.agent_name,
            content=content,
            conversation_id=conversation_id,
            is_final=is_final,
            metadata=result,
        )

        # 发布消息到流输出主题
        await self.publish_message(
            message, topic_id=TopicId(type="stream_output", source=self.id.key)
        )

        logger.debug(f"📤 [{self.agent_name}] 发送{message_type}: {content[:50]}...")

    async def request_user_feedback(
        self, prompt: str, conversation_id: str = "", timeout: float = 300.0
    ) -> str:
        """
        请求用户反馈，参考examples/frame_v1/base.py设计

        Args:
            prompt: 反馈提示
            conversation_id: 对话ID
            timeout: 超时时间（秒）

        Returns:
            用户反馈内容
        """
        if not self.enable_user_feedback:
            logger.warning(f"⚠️ [{self.agent_name}] 用户反馈未启用，返回空字符串")
            return ""

        # 发送反馈请求消息
        await self.send_message(
            content=prompt,
            message_type="user_feedback_request",
            conversation_id=conversation_id,
        )

        # 等待用户反馈
        # TODO: 实现实际的用户反馈等待机制
        logger.info(f"💬 [{self.agent_name}] 等待用户反馈: {prompt}")
        return ""  # 暂时返回空字符串

    async def send_progress(
        self,
        content: str,
        progress_percent: Optional[float] = None,
        conversation_id: str = "",
    ) -> None:
        """发送进度消息"""
        result = (
            {"progress": progress_percent} if progress_percent is not None else None
        )
        await self.send_message(
            content=content,
            message_type="progress",
            conversation_id=conversation_id,
            result=result,
        )

    async def send_success(
        self,
        content: str,
        conversation_id: str = "",
        result: Optional[Dict[str, Any]] = None,
    ) -> None:
        """发送成功消息"""
        await self.send_message(
            content=f"✅ {content}",
            message_type="success",
            conversation_id=conversation_id,
            is_final=True,
            result=result,
        )

    async def send_error(self, error_message: str, conversation_id: str = "") -> None:
        """发送错误消息"""
        logger.error(f"❌ [{self.agent_name}] 错误: {error_message}")
        await self.send_message(
            content=f"❌ {error_message}",
            message_type="error",
            conversation_id=conversation_id,
            is_final=True,
        )

    async def handle_exception(
        self,
        func_name: str,
        exception: Exception,
        conversation_id: str = "",
        send_error_message: bool = True,
    ) -> None:
        """处理异常，参考examples/frame_v1/base.py设计"""
        error_msg = f"在{func_name}中发生错误: {str(exception)}"
        logger.error(f"❌ [{self.agent_name}] {error_msg}")

        if send_error_message:
            await self.send_error(error_msg, conversation_id)

    def start_performance_monitoring(self, operation_name: str = "operation") -> str:
        """开始性能监控"""
        monitor_id = self.performance.start_monitoring(operation_name)
        logger.debug(
            f"📊 [{self.agent_name}] 开始监控: {operation_name} (ID: {monitor_id})"
        )
        return monitor_id

    def end_performance_monitoring(
        self, monitor_id: str, log_result: bool = True
    ) -> Optional[Dict[str, Any]]:
        """结束性能监控"""
        result = self.performance.end_monitoring(monitor_id)
        if result and log_result:
            logger.info(
                f"📊 [{self.agent_name}] {result['operation']} 耗时: {result['duration']:.2f}秒"
            )
        return result

    @abstractmethod
    async def process_message(self, message: Any, ctx: MessageContext) -> None:
        """
        处理消息的抽象方法，子类必须实现

        Args:
            message: 接收到的消息
            ctx: 消息上下文
        """
        pass

    def get_agent_info(self) -> Dict[str, Any]:
        """获取智能体信息"""
        return {
            "agent_id": self.id.key,
            "agent_name": self.agent_name,
            "agent_type": self.__class__.__name__,
            "system_message": self.system_message,
            "metadata": self._metadata,
        }


class StreamingAgent(BaseAgent):
    """
    支持流式输出的智能体基类，参考examples/frame_v1/base.py设计
    提供流式响应生成和实时输出功能
    """

    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        model_client: Optional[OpenAIChatCompletionClient] = None,
        system_message: str = "",
        enable_user_feedback: bool = False,
        collector=None,
        **kwargs,
    ):
        super().__init__(
            agent_id=agent_id,
            agent_name=agent_name,
            model_client=model_client,
            system_message=system_message,
            enable_user_feedback=enable_user_feedback,
            collector=collector,
            **kwargs,
        )
        self.streaming_enabled = True
        logger.info(f"🌊 [流式智能体] {agent_name} 初始化完成")

    async def send_streaming_chunk(
        self, content: str, conversation_id: str = "", chunk_type: str = "partial"
    ) -> None:
        """发送流式内容块"""
        if not self.streaming_enabled:
            return

        await self.send_message(
            content=content,
            message_type="streaming_chunk",
            conversation_id=conversation_id,
            result={"chunk_type": chunk_type},
        )

    async def send_streaming_complete(
        self, final_content: str, conversation_id: str = ""
    ) -> None:
        """发送流式输出完成消息"""
        await self.send_message(
            content=final_content,
            message_type="streaming_complete",
            conversation_id=conversation_id,
            is_final=True,
        )

    async def stream_response(
        self,
        prompt: str,
        conversation_id: str = "",
        system_message: Optional[str] = None,
    ):
        """
        流式生成响应，参考examples/frame_v1/base.py设计

        Args:
            prompt: 用户提示
            conversation_id: 对话ID
            system_message: 可选的系统消息

        Yields:
            str: 流式内容块
        """
        if not self.model_client:
            logger.error(f"❌ [{self.agent_name}] 模型客户端未初始化")
            return

        try:
            # 使用系统消息
            messages = []
            if system_message or self.system_message:
                messages.append(
                    {"role": "system", "content": system_message or self.system_message}
                )
            messages.append({"role": "user", "content": prompt})

            # 发送开始流式输出的信号
            await self.send_streaming_chunk("", conversation_id, "start")

            # 流式生成响应
            response = await self.model_client.create(messages=messages, stream=True)

            full_content = ""
            async for chunk in response:
                if chunk.content:
                    full_content += chunk.content
                    await self.send_streaming_chunk(
                        chunk.content, conversation_id, "partial"
                    )
                    yield chunk.content

            # 发送完成信号
            await self.send_streaming_complete(full_content, conversation_id)

        except Exception as e:
            logger.error(f"❌ [{self.agent_name}] 流式响应生成失败: {e}")
            await self.send_error(f"流式响应生成失败: {str(e)}", conversation_id)


# 导出接口
__all__ = ["AgentMessage", "AgentPerformanceMetrics", "BaseAgent", "StreamingAgent"]
