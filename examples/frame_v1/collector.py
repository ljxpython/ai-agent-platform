"""
UI自动化测试系统 - 统一流式响应收集器
基于AutoGen框架的标准响应收集器，适用于所有平台和模块
"""

from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

from app.core.messages import StreamMessage
from app.core.types import AgentPlatform
from autogen_core import ClosureContext, MessageContext
from loguru import logger


class StreamResponseCollector:
    """统一流式响应收集器，用于收集智能体产生的流式输出"""

    def __init__(
        self,
        platform: AgentPlatform = AgentPlatform.COMMON,
        buffer_flush_interval: float = 0.3,
    ):
        """初始化流式响应收集器

        Args:
            platform: 平台类型
            buffer_flush_interval: 缓冲区刷新间隔（秒）
        """
        self.platform = platform
        self.callback: Optional[
            Callable[[ClosureContext, Dict[str, Any], MessageContext], Awaitable[None]]
        ] = None
        self.user_input: Optional[Callable[[str, Any], Awaitable[str]]] = None
        self.message_buffers: Dict[str, str] = {}  # 用于缓存各智能体的消息
        self.last_flush_time: Dict[str, float] = {}  # 记录最后一次刷新缓冲区的时间
        self.buffer_flush_interval: float = (
            buffer_flush_interval  # 缓冲区刷新间隔（秒）
        )

        # 通用结果存储
        self.results: Dict[str, Any] = {}
        self.collected_data: List[Dict[str, Any]] = []
        self.session_metadata: Dict[str, Any] = {}

        logger.info(f"{platform.value}流式响应收集器初始化完成")

    def set_callback(
        self,
        callback: Callable[
            [ClosureContext, StreamMessage, MessageContext], Awaitable[None]
        ],
    ) -> None:
        """设置回调函数

        Args:
            callback: 用于处理响应消息的异步回调函数
        """
        self.callback = callback
        logger.debug("设置流式响应回调函数")

    def set_user_input(self, user_input: Callable[[str, Any], Awaitable[str]]) -> None:
        """设置用户输入函数

        Args:
            user_input: 用于获取用户输入的异步函数
        """
        self.user_input = user_input
        logger.debug("设置用户输入函数")

    def set_session_metadata(self, metadata: Dict[str, Any]) -> None:
        """设置会话元数据

        Args:
            metadata: 会话元数据
        """
        self.session_metadata.update(metadata)
        logger.debug(f"设置会话元数据: {list(metadata.keys())}")

    def add_result(self, key: str, value: Any) -> None:
        """添加结果数据

        Args:
            key: 结果键
            value: 结果值
        """
        self.results[key] = value
        logger.debug(f"添加结果数据: {key}")

    def get_result(self, key: str, default: Any = None) -> Any:
        """获取结果数据

        Args:
            key: 结果键
            default: 默认值

        Returns:
            Any: 结果值
        """
        return self.results.get(key, default)

    def add_collected_data(self, data: Dict[str, Any]) -> None:
        """添加收集的数据

        Args:
            data: 数据字典
        """
        data_with_timestamp = {
            **data,
            "collected_at": datetime.now().isoformat(),
            "platform": self.platform.value,
        }
        self.collected_data.append(data_with_timestamp)
        logger.debug(f"添加收集数据: {data.get('type', 'unknown')}")

    def get_all_results(self) -> Dict[str, Any]:
        """获取所有结果数据

        Returns:
            Dict[str, Any]: 所有结果数据
        """
        return {
            "platform": self.platform.value,
            "results": self.results,
            "collected_data": self.collected_data,
            "session_metadata": self.session_metadata,
            "summary": {
                "total_results": len(self.results),
                "total_collected_items": len(self.collected_data),
                "collection_completed_at": datetime.now().isoformat(),
            },
        }

    def clear_all_data(self) -> None:
        """清空所有数据"""
        self.results.clear()
        self.collected_data.clear()
        self.session_metadata.clear()
        self.message_buffers.clear()
        self.last_flush_time.clear()
        logger.info("已清空所有收集器数据")
