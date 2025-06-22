"""
智能体内存管理器
提供对话历史记录、用户记忆和上下文管理功能
"""

import json
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional

from autogen_core.memory import ListMemory, MemoryContent, MemoryMimeType
from loguru import logger


class ConversationMemory:
    """对话内存管理器"""

    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        self.memory = ListMemory(name=f"conversation_{conversation_id}")
        self.created_at = datetime.now().isoformat()
        self.last_accessed = self.created_at

        logger.debug(f"🧠 [对话内存] 创建内存实例 | 对话ID: {conversation_id}")

    async def add_message(
        self, message_type: str, content: Any, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        添加消息到内存

        Args:
            message_type: 消息类型
            content: 消息内容
            metadata: 附加元数据
        """
        try:
            # 构建消息数据
            message_data = {
                "type": message_type,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "conversation_id": self.conversation_id,
                "metadata": metadata or {},
            }

            # 安全的JSON序列化
            json_content = json.dumps(
                message_data, ensure_ascii=False, default=self._safe_json_serializer
            )

            # 创建内存内容
            memory_content = MemoryContent(
                content=json_content, mime_type=MemoryMimeType.JSON
            )

            # 添加到内存
            await self.memory.add(memory_content)
            self.last_accessed = datetime.now().isoformat()

            logger.debug(
                f"💾 [对话内存] 消息已保存 | 对话ID: {self.conversation_id} | 类型: {message_type}"
            )

        except Exception as e:
            logger.error(
                f"❌ [对话内存] 保存消息失败 | 对话ID: {self.conversation_id} | 错误: {e}"
            )
            raise

    async def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        获取对话历史

        Args:
            limit: 限制返回的消息数量

        Returns:
            List[Dict]: 历史消息列表
        """
        try:
            # 查询所有内存内容
            query_result = await self.memory.query("")
            memory_contents = query_result.results if query_result else []

            history = []
            for content in memory_contents:
                try:
                    data = json.loads(content.content)
                    history.append(data)
                except json.JSONDecodeError:
                    logger.warning(f"⚠️ [对话内存] 解析历史消息失败: {content.content}")

            # 按时间戳排序
            history.sort(key=lambda x: x.get("timestamp", ""))

            # 应用限制
            if limit and limit > 0:
                history = history[-limit:]

            self.last_accessed = datetime.now().isoformat()

            logger.debug(
                f"📖 [对话内存] 获取历史记录 | 对话ID: {self.conversation_id} | 数量: {len(history)}"
            )
            return history

        except Exception as e:
            logger.error(
                f"❌ [对话内存] 获取历史失败 | 对话ID: {self.conversation_id} | 错误: {e}"
            )
            return []

    async def get_agent_memory(self) -> Optional[ListMemory]:
        """
        获取用于智能体的内存副本

        Returns:
            ListMemory: 内存副本，如果为空返回None
        """
        try:
            # 获取所有内存内容
            query_result = await self.memory.query("")
            memory_contents = query_result.results if query_result else []

            if not memory_contents:
                logger.debug(
                    f"📝 [对话内存] 内存为空，返回None | 对话ID: {self.conversation_id}"
                )
                return None

            # 创建新的内存实例用于智能体
            agent_memory = ListMemory(
                name=f"agent_memory_{self.conversation_id}",
                memory_contents=memory_contents.copy(),
            )

            logger.debug(
                f"🤖 [对话内存] 创建智能体内存副本 | 对话ID: {self.conversation_id} | 条数: {len(memory_contents)}"
            )
            return agent_memory

        except Exception as e:
            logger.error(
                f"❌ [对话内存] 创建智能体内存失败 | 对话ID: {self.conversation_id} | 错误: {e}"
            )
            return None

    def get_memory_stats(self) -> Dict[str, Any]:
        """获取内存统计信息"""
        return {
            "conversation_id": self.conversation_id,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "memory_name": self.memory.name,
        }

    @staticmethod
    def _safe_json_serializer(obj: Any) -> Any:
        """安全的JSON序列化器"""
        if hasattr(obj, "__dict__"):
            try:
                return obj.__dict__
            except:
                return str(obj)
        elif hasattr(obj, "tobytes") or hasattr(obj, "save"):
            # 处理图像对象
            return {
                "type": "image_object",
                "class": obj.__class__.__name__,
                "size": getattr(obj, "size", None),
                "mode": getattr(obj, "mode", None),
            }
        elif isinstance(obj, bytes):
            # 处理字节数据
            return {"type": "bytes", "length": len(obj)}
        else:
            return str(obj)


class MemoryManager:
    """内存管理器，管理多个对话的内存"""

    def __init__(self):
        self.memories: Dict[str, ConversationMemory] = {}
        logger.info("🧠 [内存管理器] 初始化完成")

    async def initialize_memory(self, conversation_id: str) -> ConversationMemory:
        """
        初始化对话内存

        Args:
            conversation_id: 对话ID

        Returns:
            ConversationMemory: 对话内存实例
        """
        if conversation_id not in self.memories:
            self.memories[conversation_id] = ConversationMemory(conversation_id)
            logger.info(f"🆕 [内存管理器] 创建新的对话内存 | 对话ID: {conversation_id}")
        else:
            logger.debug(f"♻️ [内存管理器] 使用现有对话内存 | 对话ID: {conversation_id}")

        return self.memories[conversation_id]

    async def get_memory(self, conversation_id: str) -> Optional[ConversationMemory]:
        """
        获取对话内存

        Args:
            conversation_id: 对话ID

        Returns:
            ConversationMemory: 对话内存实例，如果不存在返回None
        """
        return self.memories.get(conversation_id)

    async def save_to_memory(self, conversation_id: str, data: Dict[str, Any]) -> None:
        """
        保存数据到对话内存（增强版，自动初始化内存）

        Args:
            conversation_id: 对话ID
            data: 要保存的数据
        """
        try:
            # 自动初始化内存（如果不存在）
            memory = await self.get_memory(conversation_id)
            if not memory:
                memory = await self.initialize_memory(conversation_id)

            message_type = data.get("type", "unknown")
            content = data.get("content", data)
            metadata = {k: v for k, v in data.items() if k not in ["type", "content"]}

            await memory.add_message(message_type, content, metadata)
            logger.debug(
                f"💾 [内存管理器] 数据已保存 | 对话ID: {conversation_id} | 类型: {message_type}"
            )

        except Exception as e:
            logger.error(
                f"❌ [内存管理器] 保存数据失败 | 对话ID: {conversation_id} | 错误: {e}"
            )
            # 不抛出异常，保证上层调用的健壮性

    async def get_conversation_history(
        self, conversation_id: str, limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        获取对话历史（增强版，自动初始化内存）

        Args:
            conversation_id: 对话ID
            limit: 限制返回的消息数量

        Returns:
            List[Dict]: 历史消息列表
        """
        try:
            # 自动初始化内存（如果不存在）
            memory = await self.get_memory(conversation_id)
            if not memory:
                memory = await self.initialize_memory(conversation_id)

            return await memory.get_history(limit)

        except Exception as e:
            logger.error(
                f"❌ [内存管理器] 获取对话历史失败 | 对话ID: {conversation_id} | 错误: {e}"
            )
            return []

    async def get_agent_memory(self, conversation_id: str) -> Optional[ListMemory]:
        """
        获取用于智能体的内存（增强版，自动初始化内存）

        Args:
            conversation_id: 对话ID

        Returns:
            ListMemory: 智能体内存，如果不存在返回None
        """
        try:
            # 自动初始化内存（如果不存在）
            memory = await self.get_memory(conversation_id)
            if not memory:
                memory = await self.initialize_memory(conversation_id)

            return await memory.get_agent_memory()

        except Exception as e:
            logger.error(
                f"❌ [内存管理器] 获取智能体内存失败 | 对话ID: {conversation_id} | 错误: {e}"
            )
            return None

    async def cleanup_memory(self, conversation_id: str) -> None:
        """
        清理对话内存

        Args:
            conversation_id: 对话ID
        """
        if conversation_id in self.memories:
            del self.memories[conversation_id]
            logger.info(f"🗑️ [内存管理器] 清理对话内存 | 对话ID: {conversation_id}")
        else:
            logger.debug(
                f"🤷 [内存管理器] 对话内存不存在，无需清理 | 对话ID: {conversation_id}"
            )

    def get_memory_stats(self) -> Dict[str, Any]:
        """获取内存管理器统计信息"""
        stats = {
            "total_conversations": len(self.memories),
            "active_conversations": list(self.memories.keys()),
            "memory_details": {},
        }

        for conv_id, memory in self.memories.items():
            stats["memory_details"][conv_id] = memory.get_memory_stats()

        return stats


# 全局内存管理器实例
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """获取全局内存管理器实例（单例模式）"""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager


# 便捷的全局函数，供上层直接使用
async def save_to_memory(conversation_id: str, data: Dict[str, Any]) -> None:
    """
    保存数据到对话内存（全局便捷函数）

    Args:
        conversation_id: 对话ID
        data: 要保存的数据
    """
    try:
        memory_manager = get_memory_manager()
        await memory_manager.save_to_memory(conversation_id, data)
    except Exception as e:
        logger.error(
            f"❌ [全局内存] 保存数据失败 | 对话ID: {conversation_id} | 错误: {e}"
        )


async def get_conversation_history(
    conversation_id: str, limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    获取对话历史（全局便捷函数）

    Args:
        conversation_id: 对话ID
        limit: 限制返回的消息数量

    Returns:
        List[Dict]: 历史消息列表
    """
    try:
        memory_manager = get_memory_manager()
        return await memory_manager.get_conversation_history(conversation_id, limit)
    except Exception as e:
        logger.error(
            f"❌ [全局内存] 获取对话历史失败 | 对话ID: {conversation_id} | 错误: {e}"
        )
        return []


async def get_agent_memory(conversation_id: str) -> Optional[ListMemory]:
    """
    获取用于智能体的内存（全局便捷函数）

    Args:
        conversation_id: 对话ID

    Returns:
        ListMemory: 智能体内存，如果不存在返回None
    """
    try:
        memory_manager = get_memory_manager()
        return await memory_manager.get_agent_memory(conversation_id)
    except Exception as e:
        logger.error(
            f"❌ [全局内存] 获取智能体内存失败 | 对话ID: {conversation_id} | 错误: {e}"
        )
        return None


async def cleanup_memory(conversation_id: str) -> None:
    """
    清理对话内存（全局便捷函数）

    Args:
        conversation_id: 对话ID
    """
    try:
        memory_manager = get_memory_manager()
        await memory_manager.cleanup_memory(conversation_id)
    except Exception as e:
        logger.error(
            f"❌ [全局内存] 清理内存失败 | 对话ID: {conversation_id} | 错误: {e}"
        )


# 导出接口
__all__ = [
    "ConversationMemory",
    "MemoryManager",
    "get_memory_manager",
    # 便捷的全局函数
    "save_to_memory",
    "get_conversation_history",
    "get_agent_memory",
    "cleanup_memory",
]
