"""
智能体运行时管理器
提供运行时生命周期管理、消息队列管理和状态跟踪
"""

import asyncio
from abc import ABC, abstractmethod
from asyncio import Queue
from datetime import datetime
from typing import Any, Dict, List, Optional

from autogen_core import SingleThreadedAgentRuntime
from loguru import logger

from backend.ai_core.factory import AgentFactory, AgentType, get_agent_factory
from backend.ai_core.memory import ConversationMemory, get_memory_manager


class RuntimeState:
    """运行时状态管理"""

    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        self.stage = "initialized"
        self.status = "idle"
        self.round_number = 1
        self.last_update = datetime.now().isoformat()
        self.metadata: Dict[str, Any] = {}

    def update_stage(self, stage: str, status: str = "processing") -> None:
        """更新运行时阶段"""
        self.stage = stage
        self.status = status
        self.last_update = datetime.now().isoformat()
        logger.debug(
            f"🔄 [运行时状态] 更新阶段: {stage} | 状态: {status} | 对话ID: {self.conversation_id}"
        )

    def update_round(self, round_number: int) -> None:
        """更新轮次"""
        self.round_number = round_number
        self.last_update = datetime.now().isoformat()
        logger.debug(
            f"🔢 [运行时状态] 更新轮次: {round_number} | 对话ID: {self.conversation_id}"
        )

    def set_metadata(self, key: str, value: Any) -> None:
        """设置元数据"""
        self.metadata[key] = value
        self.last_update = datetime.now().isoformat()

    def get_state_dict(self) -> Dict[str, Any]:
        """获取状态字典"""
        return {
            "conversation_id": self.conversation_id,
            "stage": self.stage,
            "status": self.status,
            "round_number": self.round_number,
            "last_update": self.last_update,
            "metadata": self.metadata,
        }


class MessageQueue:
    """消息队列管理器"""

    def __init__(self, conversation_id: str, max_size: int = 1000):
        self.conversation_id = conversation_id
        self.message_queue: Queue = Queue(maxsize=max_size)
        self.feedback_queue: Queue = Queue()
        self.created_at = datetime.now().isoformat()

        logger.debug(
            f"📦 [消息队列] 创建队列 | 对话ID: {conversation_id} | 最大大小: {max_size}"
        )

    async def put_message(self, message: str) -> None:
        """放入消息到队列"""
        await self.message_queue.put(message)
        logger.debug(
            f"📤 [消息队列] 消息入队 | 对话ID: {self.conversation_id} | 内容: {message[:100]}..."
        )

    async def get_message(self) -> str:
        """从队列获取消息"""
        message = await self.message_queue.get()
        logger.debug(
            f"📥 [消息队列] 消息出队 | 对话ID: {self.conversation_id} | 内容: {message[:100]}..."
        )
        return message

    async def put_feedback(self, feedback: str) -> None:
        """放入用户反馈到队列"""
        await self.feedback_queue.put(feedback)
        logger.debug(
            f"💬 [消息队列] 反馈入队 | 对话ID: {self.conversation_id} | 反馈: {feedback}"
        )

    async def get_feedback(self) -> str:
        """从队列获取用户反馈"""
        feedback = await self.feedback_queue.get()
        logger.debug(
            f"💬 [消息队列] 反馈出队 | 对话ID: {self.conversation_id} | 反馈: {feedback}"
        )
        return feedback

    def get_queue_sizes(self) -> Dict[str, int]:
        """获取队列大小"""
        return {
            "message_queue_size": self.message_queue.qsize(),
            "feedback_queue_size": self.feedback_queue.qsize(),
        }


class BaseRuntime(ABC):
    """智能体运行时基类"""

    def __init__(self):
        self.runtimes: Dict[str, SingleThreadedAgentRuntime] = {}
        self.states: Dict[str, RuntimeState] = {}
        self.queues: Dict[str, MessageQueue] = {}
        self.agent_factory: AgentFactory = get_agent_factory()
        self.memory_manager = get_memory_manager()

        logger.info("🏗️ [运行时基类] 初始化完成")

    async def initialize_runtime(self, conversation_id: str) -> None:
        """
        初始化运行时环境（增强版，完整容错机制）

        Args:
            conversation_id: 对话ID
        """
        try:
            # 参数验证
            if not conversation_id or not conversation_id.strip():
                logger.error(f"❌ [运行时管理] 对话ID不能为空")
                raise ValueError("对话ID不能为空")

            conversation_id = conversation_id.strip()

            if conversation_id in self.runtimes:
                logger.info(
                    f"♻️ [运行时管理] 运行时已存在，跳过初始化 | 对话ID: {conversation_id}"
                )
                return

            logger.info(
                f"🚀 [运行时管理] 开始初始化运行时环境 | 对话ID: {conversation_id}"
            )

            # 步骤1: 创建运行时实例
            logger.debug(f"   🏗️ 步骤1: 创建SingleThreadedAgentRuntime实例")
            try:
                runtime = SingleThreadedAgentRuntime()
                self.runtimes[conversation_id] = runtime
                logger.debug(f"   ✅ 运行时实例创建成功")
            except Exception as e:
                logger.error(f"   ❌ 创建运行时实例失败: {e}")
                raise

            # 步骤2: 创建状态管理
            logger.debug(f"   📊 步骤2: 创建状态管理")
            try:
                self.states[conversation_id] = RuntimeState(conversation_id)
                logger.debug(f"   ✅ 状态管理创建成功")
            except Exception as e:
                logger.error(f"   ❌ 创建状态管理失败: {e}")
                # 清理已创建的运行时
                if conversation_id in self.runtimes:
                    del self.runtimes[conversation_id]
                raise

            # 步骤3: 创建消息队列
            logger.debug(f"   📦 步骤3: 创建消息队列")
            try:
                self.queues[conversation_id] = MessageQueue(conversation_id)
                logger.debug(f"   ✅ 消息队列创建成功")
            except Exception as e:
                logger.error(f"   ❌ 创建消息队列失败: {e}")
                # 清理已创建的资源
                if conversation_id in self.runtimes:
                    del self.runtimes[conversation_id]
                if conversation_id in self.states:
                    del self.states[conversation_id]
                raise

            # 步骤4: 初始化内存
            logger.debug(f"   🧠 步骤4: 初始化内存管理")
            try:
                await self.memory_manager.initialize_memory(conversation_id)
                logger.debug(f"   ✅ 内存管理初始化成功")
            except Exception as e:
                logger.error(f"   ❌ 初始化内存管理失败: {e}")
                # 内存初始化失败不应该阻止运行时创建，只记录警告
                logger.warning(f"   ⚠️ 内存管理初始化失败，继续运行时创建")

            # 步骤5: 注册智能体
            logger.debug(f"   🤖 步骤5: 注册智能体")
            try:
                await self.register_agents(runtime, conversation_id)
                logger.debug(f"   ✅ 智能体注册成功")
            except Exception as e:
                logger.error(f"   ❌ 注册智能体失败: {e}")
                # 清理所有已创建的资源
                await self.cleanup_runtime(conversation_id)
                raise

            # 步骤6: 启动运行时
            logger.debug(f"   🚀 步骤6: 启动运行时")
            try:
                runtime.start()
                logger.debug(f"   ✅ 运行时启动成功")
            except Exception as e:
                logger.error(f"   ❌ 启动运行时失败: {e}")
                # 清理所有已创建的资源
                await self.cleanup_runtime(conversation_id)
                raise

            # 更新状态
            if conversation_id in self.states:
                self.states[conversation_id].update_stage("initialized", "ready")

            logger.success(
                f"✅ [运行时管理] 运行时初始化完成 | 对话ID: {conversation_id}"
            )
            logger.debug(f"   📊 运行时统计: {self.get_runtime_stats()}")

        except Exception as e:
            logger.error(
                f"❌ [运行时管理] 初始化失败 | 对话ID: {conversation_id} | 错误: {str(e)}"
            )
            logger.error(f"   🐛 错误类型: {type(e).__name__}")
            logger.error(f"   📍 错误位置: initialize_runtime")
            # 确保清理资源
            try:
                await self.cleanup_runtime(conversation_id)
            except Exception as cleanup_e:
                logger.error(f"   ❌ 清理资源也失败: {cleanup_e}")
            raise

    @abstractmethod
    async def register_agents(
        self, runtime: SingleThreadedAgentRuntime, conversation_id: str
    ) -> None:
        """
        注册智能体到运行时（抽象方法，子类必须实现）

        Args:
            runtime: 运行时实例
            conversation_id: 对话ID
        """
        pass

    async def cleanup_runtime(self, conversation_id: str) -> None:
        """
        清理运行时资源（增强版，完整容错机制）

        Args:
            conversation_id: 对话ID
        """
        try:
            if not conversation_id:
                logger.warning(f"⚠️ [运行时管理] 对话ID为空，跳过清理")
                return

            logger.info(
                f"🗑️ [运行时管理] 开始清理运行时资源 | 对话ID: {conversation_id}"
            )

            cleanup_errors = []

            # 步骤1: 停止并清理运行时
            logger.debug(f"   🛑 步骤1: 停止运行时")
            try:
                if conversation_id in self.runtimes:
                    runtime = self.runtimes[conversation_id]
                    await runtime.stop()
                    del self.runtimes[conversation_id]
                    logger.debug(f"   ✅ 运行时停止并清理成功")
                else:
                    logger.debug(f"   📝 运行时不存在，跳过")
            except Exception as e:
                error_msg = f"停止运行时失败: {e}"
                logger.error(f"   ❌ {error_msg}")
                cleanup_errors.append(error_msg)
                # 强制删除运行时引用
                try:
                    if conversation_id in self.runtimes:
                        del self.runtimes[conversation_id]
                except:
                    pass

            # 步骤2: 清理状态
            logger.debug(f"   📊 步骤2: 清理状态管理")
            try:
                if conversation_id in self.states:
                    del self.states[conversation_id]
                    logger.debug(f"   ✅ 状态管理清理成功")
                else:
                    logger.debug(f"   📝 状态管理不存在，跳过")
            except Exception as e:
                error_msg = f"清理状态管理失败: {e}"
                logger.error(f"   ❌ {error_msg}")
                cleanup_errors.append(error_msg)

            # 步骤3: 清理队列
            logger.debug(f"   📦 步骤3: 清理消息队列")
            try:
                if conversation_id in self.queues:
                    # 获取队列大小信息
                    queue_info = self.queues[conversation_id].get_queue_sizes()
                    logger.debug(f"   📊 队列状态: {queue_info}")
                    del self.queues[conversation_id]
                    logger.debug(f"   ✅ 消息队列清理成功")
                else:
                    logger.debug(f"   📝 消息队列不存在，跳过")
            except Exception as e:
                error_msg = f"清理消息队列失败: {e}"
                logger.error(f"   ❌ {error_msg}")
                cleanup_errors.append(error_msg)

            # 步骤4: 清理内存
            logger.debug(f"   🧠 步骤4: 清理内存管理")
            try:
                await self.memory_manager.cleanup_memory(conversation_id)
                logger.debug(f"   ✅ 内存管理清理成功")
            except Exception as e:
                error_msg = f"清理内存管理失败: {e}"
                logger.error(f"   ❌ {error_msg}")
                cleanup_errors.append(error_msg)
                # 内存清理失败不应该阻止其他清理操作

            # 总结清理结果
            if cleanup_errors:
                logger.warning(
                    f"⚠️ [运行时管理] 资源清理完成，但有错误 | 对话ID: {conversation_id}"
                )
                logger.warning(f"   🐛 清理错误: {cleanup_errors}")
            else:
                logger.success(
                    f"✅ [运行时管理] 资源清理完成 | 对话ID: {conversation_id}"
                )

            logger.debug(f"   📊 清理后统计: {self.get_runtime_stats()}")

        except Exception as e:
            logger.error(
                f"❌ [运行时管理] 资源清理异常 | 对话ID: {conversation_id} | 错误: {str(e)}"
            )
            logger.error(f"   🐛 错误类型: {type(e).__name__}")
            logger.error(f"   📍 错误位置: cleanup_runtime")

    def get_runtime(self, conversation_id: str) -> Optional[SingleThreadedAgentRuntime]:
        """获取运行时实例（增强版）"""
        try:
            if not conversation_id:
                logger.warning(f"⚠️ [运行时管理] 对话ID为空")
                return None

            runtime = self.runtimes.get(conversation_id)
            if runtime:
                logger.debug(
                    f"🔍 [运行时管理] 获取运行时成功 | 对话ID: {conversation_id}"
                )
            else:
                logger.debug(
                    f"📝 [运行时管理] 运行时不存在 | 对话ID: {conversation_id}"
                )

            return runtime

        except Exception as e:
            logger.error(
                f"❌ [运行时管理] 获取运行时失败 | 对话ID: {conversation_id} | 错误: {e}"
            )
            return None

    def get_state(self, conversation_id: str) -> Optional[RuntimeState]:
        """获取运行时状态（增强版）"""
        try:
            if not conversation_id:
                logger.warning(f"⚠️ [运行时管理] 对话ID为空")
                return None

            state = self.states.get(conversation_id)
            if state:
                logger.debug(
                    f"📊 [运行时管理] 获取状态成功 | 对话ID: {conversation_id} | 阶段: {state.stage}"
                )
            else:
                logger.debug(f"📝 [运行时管理] 状态不存在 | 对话ID: {conversation_id}")

            return state

        except Exception as e:
            logger.error(
                f"❌ [运行时管理] 获取状态失败 | 对话ID: {conversation_id} | 错误: {e}"
            )
            return None

    def get_queue(self, conversation_id: str) -> Optional[MessageQueue]:
        """获取消息队列（增强版）"""
        try:
            if not conversation_id:
                logger.warning(f"⚠️ [运行时管理] 对话ID为空")
                return None

            queue = self.queues.get(conversation_id)
            if queue:
                queue_info = queue.get_queue_sizes()
                logger.debug(
                    f"📦 [运行时管理] 获取队列成功 | 对话ID: {conversation_id} | 队列状态: {queue_info}"
                )
            else:
                logger.debug(f"📝 [运行时管理] 队列不存在 | 对话ID: {conversation_id}")

            return queue

        except Exception as e:
            logger.error(
                f"❌ [运行时管理] 获取队列失败 | 对话ID: {conversation_id} | 错误: {e}"
            )
            return None

    async def update_state(
        self, conversation_id: str, stage: str, status: str = "processing"
    ) -> None:
        """更新运行时状态（增强版）"""
        try:
            if not conversation_id:
                logger.warning(f"⚠️ [运行时管理] 对话ID为空，无法更新状态")
                return

            if not stage:
                logger.warning(
                    f"⚠️ [运行时管理] 阶段为空，无法更新状态 | 对话ID: {conversation_id}"
                )
                return

            if conversation_id in self.states:
                self.states[conversation_id].update_stage(stage, status)
                logger.debug(
                    f"🔄 [运行时管理] 状态更新成功 | 对话ID: {conversation_id} | 阶段: {stage} | 状态: {status}"
                )
            else:
                logger.warning(
                    f"⚠️ [运行时管理] 状态不存在，无法更新 | 对话ID: {conversation_id}"
                )

        except Exception as e:
            logger.error(
                f"❌ [运行时管理] 更新状态失败 | 对话ID: {conversation_id} | 错误: {e}"
            )

    async def save_to_memory(self, conversation_id: str, data: Dict[str, Any]) -> None:
        """保存数据到内存（增强版）"""
        try:
            if not conversation_id:
                logger.warning(f"⚠️ [运行时管理] 对话ID为空，无法保存到内存")
                return

            if not data:
                logger.warning(
                    f"⚠️ [运行时管理] 数据为空，无法保存到内存 | 对话ID: {conversation_id}"
                )
                return

            await self.memory_manager.save_to_memory(conversation_id, data)
            logger.debug(
                f"💾 [运行时管理] 数据保存到内存成功 | 对话ID: {conversation_id} | 类型: {data.get('type', 'unknown')}"
            )

        except Exception as e:
            logger.error(
                f"❌ [运行时管理] 保存到内存失败 | 对话ID: {conversation_id} | 错误: {e}"
            )

    async def get_conversation_history(
        self, conversation_id: str
    ) -> List[Dict[str, Any]]:
        """获取对话历史（增强版）"""
        try:
            if not conversation_id:
                logger.warning(f"⚠️ [运行时管理] 对话ID为空，返回空历史")
                return []

            history = await self.memory_manager.get_conversation_history(
                conversation_id
            )
            logger.debug(
                f"📚 [运行时管理] 获取对话历史成功 | 对话ID: {conversation_id} | 消息数量: {len(history)}"
            )
            return history

        except Exception as e:
            logger.error(
                f"❌ [运行时管理] 获取对话历史失败 | 对话ID: {conversation_id} | 错误: {e}"
            )
            return []

    def get_runtime_stats(self) -> Dict[str, Any]:
        """获取运行时统计信息（增强版）"""
        try:
            stats = {
                "total_runtimes": len(self.runtimes),
                "total_states": len(self.states),
                "total_queues": len(self.queues),
                "active_conversations": list(self.runtimes.keys()),
                "timestamp": datetime.now().isoformat(),
            }

            logger.debug(f"📊 [运行时管理] 统计信息: {stats}")
            return stats

        except Exception as e:
            logger.error(f"❌ [运行时管理] 获取统计信息失败: {e}")
            return {
                "total_runtimes": 0,
                "total_states": 0,
                "total_queues": 0,
                "active_conversations": [],
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
            }


# 导出接口
__all__ = ["RuntimeState", "MessageQueue", "BaseRuntime"]
