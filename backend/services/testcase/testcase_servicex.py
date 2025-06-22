"""
AI测试用例生成服务 - 重新设计版本
使用AutoGen 0.5.7实现多智能体协作，支持历史消息记录和分阶段处理
参考AutoGen官方文档实现内存管理和运行时控制

设计思路：
1. 使用两个接口：/generate/sse 和 /feedback 来触发运行时的消息发布
2. 根据对话ID记录历史消息，实现内存管理
3. 封装TestCaseGenerationRuntime类来管理整个流程
4. 使用不同的智能体处理不同阶段的任务

智能体设计：
- 需求分析智能体：处理初始需求分析，发布消息：需求分析
- 用例生成智能体：生成初步测试用例，发布消息：需求分析
- 用例评审优化智能体：根据用户反馈优化用例，发布消息：用例优化
- 结构化入库智能体：处理最终结果并入库，发布消息：用例结果
- UserProxyAgent：处理用户交互
- ClosureAgent：收集结果返回前端
"""

import asyncio
import base64
import json
import os
import tempfile
import uuid
from asyncio import Queue
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Awaitable, Callable, Dict, List, Optional

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.messages import (
    ModelClientStreamingChunkEvent,
    TextMessage,
    UserInputRequestedEvent,
)
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_core import (
    CancellationToken,
    ClosureAgent,
    ClosureContext,
    DefaultTopicId,
    MessageContext,
    RoutedAgent,
    SingleThreadedAgentRuntime,
    TopicId,
    TypeSubscription,
    message_handler,
    type_subscription,
)
from autogen_core.memory import ListMemory, MemoryContent, MemoryMimeType
from autogen_core.model_context import BufferedChatCompletionContext
from autogen_ext.models.openai import OpenAIChatCompletionClient
from llama_index.core import Document, SimpleDirectoryReader
from loguru import logger
from pydantic import BaseModel, Field

from backend.core.llm import get_openai_model_client, validate_model_client
from backend.models.chat import AgentMessage, AgentType, FileUpload, TestCaseRequest
from backend.models.testcase import (
    TestCaseConversation,
    TestCaseFeedback,
    TestCaseFile,
    TestCaseMessage,
)

# 定义主题类型 - 重新设计的消息流
requirement_analysis_topic_type = "requirement_analysis"  # 需求分析
testcase_generation_topic_type = "testcase_generation"  # 用例生成
testcase_optimization_topic_type = "testcase_optimization"  # 用例优化
testcase_finalization_topic_type = "testcase_finalization"  # 用例结果
task_result_topic_type = "collect_result"  # 结果收集

# 全局队列管理 - 参考examples/topic1.py
message_queues: Dict[str, Queue] = {}  # 按对话ID隔离的流式消息队列
user_feedback_queues: Dict[str, Queue] = {}  # 按对话ID隔离的用户反馈队列


# 队列管理函数 - 参考examples/topic1.py实现
async def get_message_queue(conversation_id: str) -> Queue:
    """获取或创建流式消息队列"""
    if conversation_id not in message_queues:
        queue = Queue(maxsize=1000)  # 防止内存溢出
        message_queues[conversation_id] = queue
        logger.debug(f"📦 [队列管理] 创建新的消息队列 | 对话ID: {conversation_id}")
    return message_queues[conversation_id]


async def get_feedback_queue(conversation_id: str) -> Queue:
    """获取或创建用户反馈队列"""
    if conversation_id not in user_feedback_queues:
        queue = Queue()
        user_feedback_queues[conversation_id] = queue
        logger.debug(f"📦 [队列管理] 创建新的反馈队列 | 对话ID: {conversation_id}")
    return user_feedback_queues[conversation_id]


async def put_message_to_queue(conversation_id: str, message: str):
    """将消息放入流式队列 - 生产者"""
    queue = await get_message_queue(conversation_id)
    await queue.put(message)
    logger.debug(
        f"📤 [队列管理] 消息已放入队列 | 对话ID: {conversation_id} | 内容: {message[:100]}..."
    )


async def get_message_from_queue(conversation_id: str) -> str:
    """从流式队列获取消息 - 消费者"""
    queue = await get_message_queue(conversation_id)
    message = await queue.get()
    logger.debug(
        f"📥 [队列管理] 从队列获取消息 | 对话ID: {conversation_id} | 内容: {message[:100]}..."
    )
    return message


async def put_feedback_to_queue(conversation_id: str, feedback: str):
    """将用户反馈放入队列"""
    queue = await get_feedback_queue(conversation_id)
    await queue.put(feedback)
    logger.debug(
        f"💬 [队列管理] 用户反馈已放入队列 | 对话ID: {conversation_id} | 反馈: {feedback}"
    )


async def get_feedback_from_queue(conversation_id: str) -> str:
    """从队列获取用户反馈"""
    queue = await get_feedback_queue(conversation_id)
    feedback = await queue.get()
    logger.debug(
        f"💬 [队列管理] 从队列获取用户反馈 | 对话ID: {conversation_id} | 反馈: {feedback}"
    )
    return feedback


def cleanup_queues(conversation_id: str):
    """清理对话相关的所有队列"""
    if conversation_id in message_queues:
        del message_queues[conversation_id]
        logger.debug(f"🗑️ [队列管理] 消息队列已清理 | 对话ID: {conversation_id}")

    if conversation_id in user_feedback_queues:
        del user_feedback_queues[conversation_id]
        logger.debug(f"🗑️ [队列管理] 反馈队列已清理 | 对话ID: {conversation_id}")


async def get_user_memory_for_agent(conversation_id: str) -> Optional[ListMemory]:
    """
    获取用户历史消息的 memory 用于智能体

    根据官方文档：https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/memory.html
    为智能体提供历史消息上下文

    Args:
        conversation_id: 对话ID

    Returns:
        ListMemory: 包含历史消息的内存对象，如果没有历史则返回None
    """
    logger.debug(f"🧠 [Memory管理] 获取用户历史消息 | 对话ID: {conversation_id}")

    # 检查是否存在该对话的内存
    if conversation_id not in testcase_runtime.memories:
        logger.debug(f"   📝 无历史内存，返回None | 对话ID: {conversation_id}")
        return None

    try:
        # 获取现有的内存
        existing_memory = testcase_runtime.memories[conversation_id]

        # 使用正确的方法获取所有历史内容 - 根据ListMemory源码，使用query()方法
        query_result = await existing_memory.query("")
        memory_contents = query_result.results if query_result else []

        if not memory_contents:
            logger.debug(f"   📝 内存为空，返回None | 对话ID: {conversation_id}")
            return None

        # 创建新的内存实例用于智能体，直接使用现有内容
        user_memory = ListMemory(
            name=f"agent_memory_{conversation_id}",
            memory_contents=memory_contents.copy(),
        )

        logger.info(
            f"✅ [Memory管理] 用户历史消息已准备 | 对话ID: {conversation_id} | 历史条数: {len(memory_contents)}"
        )
        return user_memory

    except Exception as e:
        logger.error(
            f"❌ [Memory管理] 获取用户历史消息失败 | 对话ID: {conversation_id} | 错误: {e}"
        )
        return None


def create_buffered_context(buffer_size: int = 4000) -> BufferedChatCompletionContext:
    """
    创建 BufferedChatCompletionContext 防止 LLM 上下文溢出

    根据官方文档：https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/components/model-context.html
    和 BufferedChatCompletionContext 源码，使用缓冲上下文管理来防止上下文溢出

    Args:
        buffer_size: 缓冲区大小（消息数量），默认4000

    Returns:
        BufferedChatCompletionContext: 缓冲上下文对象，如果创建失败返回None
    """
    logger.debug(
        f"🔧 [Context管理] 创建BufferedChatCompletionContext | buffer_size: {buffer_size}"
    )

    try:
        # 根据源码，BufferedChatCompletionContext只接受buffer_size和initial_messages参数
        buffered_context = BufferedChatCompletionContext(
            buffer_size=buffer_size,
            initial_messages=None,  # 可选的初始消息，这里设为None
        )

        logger.debug(f"✅ [Context管理] BufferedChatCompletionContext创建成功")
        return buffered_context

    except Exception as e:
        logger.error(f"❌ [Context管理] 创建BufferedChatCompletionContext失败: {e}")
        # 如果创建失败，返回None，智能体将使用默认上下文
        return None


# 定义消息类型
class RequirementMessage(BaseModel):
    """需求分析消息"""

    text_content: Optional[str] = Field(default="", description="文本内容")
    files: Optional[List[FileUpload]] = Field(default=None, description="上传的文件")
    file_paths: Optional[List[str]] = Field(default=None, description="文件路径列表")
    conversation_id: str = Field(..., description="对话ID")
    round_number: int = Field(default=1, description="轮次")


class FeedbackMessage(BaseModel):
    """用户反馈消息"""

    feedback: str = Field(..., description="用户反馈内容")
    conversation_id: str = Field(..., description="对话ID")
    round_number: int = Field(..., description="轮次")
    previous_testcases: Optional[str] = Field(default="", description="之前的测试用例")


class ResponseMessage(BaseModel):
    """响应消息"""

    source: str = Field(..., description="消息来源")
    content: str = Field(..., description="消息内容")
    message_type: str = Field(
        default="info", description="消息类型：需求分析、用例优化、用例结果"
    )
    is_final: bool = Field(default=False, description="是否最终消息")


class StreamingChunkMessage(BaseModel):
    """流式输出块消息"""

    source: str = Field(..., description="消息来源智能体")
    content: str = Field(..., description="流式内容块")
    message_type: str = Field(default="streaming", description="消息类型")
    conversation_id: str = Field(..., description="对话ID")
    chunk_type: str = Field(default="partial", description="块类型：partial/complete")


class AgentCompleteMessage(BaseModel):
    """智能体完成消息"""

    source: str = Field(..., description="智能体名称")
    content: str = Field(..., description="完整输出内容")
    message_type: str = Field(..., description="消息类型")
    conversation_id: str = Field(..., description="对话ID")
    is_complete: bool = Field(default=True, description="是否完成")


class TaskResultMessage(BaseModel):
    """任务结果消息"""

    messages: List[Dict] = Field(..., description="所有智能体的输出消息列表")
    conversation_id: str = Field(..., description="对话ID")
    task_complete: bool = Field(default=True, description="任务是否完成")


@dataclass
class TestCaseMessage:
    """测试用例消息"""

    source: str
    content: Any
    conversation_id: str = ""
    round_number: int = 1


class TestCaseGenerationRuntime:
    """测试用例生成运行时管理器 - 优化版本，使用队列模式"""

    def __init__(self):
        self.runtimes: Dict[str, SingleThreadedAgentRuntime] = {}  # 按对话ID存储运行时
        self.memories: Dict[str, ListMemory] = {}  # 按对话ID存储历史消息
        # self.collected_messages: Dict[str, List[Dict]] = {}  # 收集的消息 - 暂时注释，留待后续使用
        self.conversation_states: Dict[str, Dict] = {}  # 对话状态
        # 移除streaming_messages和agent_streams，改用全局队列管理
        logger.info("测试用例生成运行时管理器初始化完成 - 队列模式")

    async def start_requirement_analysis(self, requirement: RequirementMessage) -> None:
        """
        启动需求分析阶段

        工作流程：
        1. 初始化运行时和内存管理
        2. 保存用户输入到历史记录
        3. 发布需求分析消息到对应主题
        4. 更新对话状态为需求分析阶段

        Args:
            requirement: 需求分析消息对象，包含用户输入的文本和文件
        """
        conversation_id = requirement.conversation_id
        logger.info(
            f"🚀 [需求分析阶段] 启动需求分析流程 | 对话ID: {conversation_id} | 轮次: {requirement.round_number} | 文本内容长度: {len(requirement.text_content or '')} | 文件数量: {len(requirement.files) if requirement.files else 0}"
        )

        try:
            # 步骤1: 初始化运行时和内存
            logger.info(
                f"📦 [需求分析阶段] 步骤1: 初始化运行时和内存管理 | 对话ID: {conversation_id}"
            )
            await self._init_runtime(conversation_id)
            logger.success(
                f"✅ [需求分析阶段] 运行时初始化完成 | 对话ID: {conversation_id}"
            )

            # 步骤2: 保存用户输入历史消息
            logger.info(
                f"💾 [需求分析阶段] 步骤2: 保存用户输入到历史记录 | 对话ID: {conversation_id}"
            )
            user_input_data = {
                "type": "user_input",
                "content": requirement.text_content or "",
                "files": (
                    [f.dict() for f in requirement.files] if requirement.files else []
                ),
                "timestamp": datetime.now().isoformat(),
                "round_number": requirement.round_number,
            }
            await self._save_to_memory(conversation_id, user_input_data)
            logger.debug(f"📝 [需求分析阶段] 用户输入已保存: {user_input_data}")

            # 步骤3: 发布需求分析消息
            logger.info(
                f"📢 [需求分析阶段] 步骤3: 发布需求分析消息到主题 | 对话ID: {conversation_id}"
            )
            logger.info(f"   🎯 目标主题: {requirement_analysis_topic_type}")
            logger.info(
                f"   📦 消息内容: RequirementMessage(conversation_id={conversation_id}, round_number={requirement.round_number})"
            )

            runtime = self.runtimes[conversation_id]
            await runtime.publish_message(
                requirement,
                topic_id=DefaultTopicId(type=requirement_analysis_topic_type),
            )
            logger.success(
                f"✅ [需求分析阶段] 消息发布成功，等待需求分析智能体处理 | 对话ID: {conversation_id}"
            )

            # 步骤4: 更新对话状态
            logger.info(
                f"🔄 [需求分析阶段] 步骤4: 更新对话状态 | 对话ID: {conversation_id}"
            )
            conversation_state = {
                "stage": "requirement_analysis",
                "round_number": requirement.round_number,
                "last_update": datetime.now().isoformat(),
                "status": "processing",
            }
            self.conversation_states[conversation_id] = conversation_state
            logger.debug(f"📊 [需求分析阶段] 对话状态已更新: {conversation_state}")
            logger.success(
                f"🎉 [需求分析阶段] 需求分析流程启动完成 | 对话ID: {conversation_id}"
            )

        except Exception as e:
            logger.error(
                f"❌ [需求分析阶段] 启动需求分析失败 | 对话ID: {conversation_id}"
            )
            logger.error(f"   🐛 错误类型: {type(e).__name__}")
            logger.error(f"   📄 错误详情: {str(e)}")
            # 清理资源
            if conversation_id in self.runtimes:
                await self.cleanup_runtime(conversation_id)
            raise

    async def process_user_feedback(self, feedback: FeedbackMessage) -> None:
        """
        处理用户反馈 - 队列模式，参考examples/topic1.py

        使用队列模式处理用户反馈：
        1. 将用户反馈放入反馈队列
        2. 根据反馈内容决定后续流程
        3. 使用UserProxyAgent模式处理用户交互

        Args:
            feedback: 用户反馈消息对象，包含反馈内容和之前的测试用例
        """
        conversation_id = feedback.conversation_id
        logger.info(
            f"🔄 [用户反馈处理-队列模式] 开始处理用户反馈 | 对话ID: {conversation_id} | 轮次: {feedback.round_number} | 反馈内容: {feedback.feedback} | 之前测试用例长度: {len(feedback.previous_testcases or '')}"
        )

        try:
            # 步骤1: 将用户反馈放入队列 - 参考examples/topic1.py
            logger.info(
                f"📤 [用户反馈处理-队列模式] 步骤1: 将用户反馈放入队列 | 对话ID: {conversation_id}"
            )
            await put_feedback_to_queue(conversation_id, feedback.feedback)

            # 步骤2: 分析用户反馈类型
            is_approval = (
                "同意" in feedback.feedback or "APPROVE" in feedback.feedback.upper()
            )
            logger.info(f"🔍 [用户反馈处理-队列模式] 步骤2: 反馈类型分析:")
            logger.info(f"   📝 原始反馈: '{feedback.feedback}'")
            logger.info(f"   ✅ 是否同意: {is_approval}")

            # 步骤3: 根据反馈类型决定后续流程
            if is_approval:
                # 用户同意，进入最终化阶段
                logger.info(
                    f"👍 [用户反馈处理-队列模式] 用户同意当前测试用例，启动最终化流程 | 对话ID: {conversation_id}"
                )
                await self._finalize_testcases(conversation_id, feedback)
            else:
                # 用户提供反馈，进入优化阶段
                logger.info(
                    f"🔧 [用户反馈处理-队列模式] 用户提供优化意见，启动优化流程 | 对话ID: {conversation_id}"
                )
                await self._optimize_testcases(conversation_id, feedback)

            logger.success(
                f"✅ [用户反馈处理-队列模式] 用户反馈处理完成 | 对话ID: {conversation_id}"
            )

        except Exception as e:
            logger.error(
                f"❌ [用户反馈处理-队列模式] 处理用户反馈失败 | 对话ID: {conversation_id}"
            )
            logger.error(f"   🐛 错误类型: {type(e).__name__}")
            logger.error(f"   📄 错误详情: {str(e)}")
            raise

    async def _init_runtime(self, conversation_id: str) -> None:
        """
        初始化运行时环境

        为指定对话ID创建独立的运行时环境，包括：
        1. SingleThreadedAgentRuntime 实例
        2. ListMemory 内存管理
        3. 消息收集器
        4. 智能体注册

        Args:
            conversation_id: 对话唯一标识符
        """
        # 检查是否已经初始化
        if conversation_id in self.runtimes:
            logger.info(
                f"♻️  [运行时初始化] 运行时已存在，跳过初始化 | 对话ID: {conversation_id}"
            )
            return

        logger.info(
            f"🏗️  [运行时初始化] 开始初始化运行时环境 | 对话ID: {conversation_id}"
        )

        try:
            # 步骤1: 创建SingleThreadedAgentRuntime实例
            logger.info(f"   📦 步骤1: 创建SingleThreadedAgentRuntime实例")
            runtime = SingleThreadedAgentRuntime()
            self.runtimes[conversation_id] = runtime
            logger.debug(f"   ✅ SingleThreadedAgentRuntime创建成功: {type(runtime)}")

            # 步骤2: 创建ListMemory内存管理
            logger.info(f"   🧠 步骤2: 创建ListMemory内存管理实例")
            memory = ListMemory()
            self.memories[conversation_id] = memory
            logger.debug(f"   ✅ ListMemory创建成功: {type(memory)}")

            # 步骤3: 初始化消息收集器 - 暂时注释，留待后续使用
            # logger.info(f"   📨 步骤3: 初始化消息收集器")
            # self.collected_messages[conversation_id] = []
            # logger.debug(f"   ✅ 消息收集器初始化完成，当前消息数: 0")

            # 步骤4: 注册所有智能体到运行时
            logger.info(f"   🤖 步骤4: 注册智能体到运行时")
            await self._register_agents(runtime, conversation_id)

            # 步骤5: 启动运行时
            logger.info(f"   🚀 步骤5: 启动运行时")
            runtime.start()
            logger.debug(f"   ✅ 运行时启动成功")

            # 记录运行时状态
            logger.info(f"📊 [运行时初始化] 当前运行时统计:")
            logger.info(f"   🔢 总运行时数量: {len(self.runtimes)}")
            logger.info(f"   🧠 总内存实例数: {len(self.memories)}")
            # logger.info(f"   📨 总消息收集器数: {len(self.collected_messages)}")  # 暂时注释，留待后续使用

            logger.success(
                f"🎉 [运行时初始化] 运行时环境初始化完成 | 对话ID: {conversation_id}"
            )

        except Exception as e:
            logger.error(f"❌ [运行时初始化] 初始化失败 | 对话ID: {conversation_id}")
            logger.error(f"   🐛 错误类型: {type(e).__name__}")
            logger.error(f"   📄 错误详情: {str(e)}")
            # 清理已创建的资源
            if conversation_id in self.runtimes:
                del self.runtimes[conversation_id]
            if conversation_id in self.memories:
                del self.memories[conversation_id]
            # if conversation_id in self.collected_messages:  # 暂时注释，留待后续使用
            #     del self.collected_messages[conversation_id]
            raise

    async def _save_to_memory(self, conversation_id: str, data: Dict) -> None:
        """
        保存数据到内存

        将对话相关的数据保存到ListMemory中，用于历史记录和上下文管理

        Args:
            conversation_id: 对话唯一标识符
            data: 要保存的数据字典
        """
        logger.debug(f"💾 [内存管理] 开始保存数据到内存 | 对话ID: {conversation_id}")
        logger.debug(f"   📦 数据类型: {data.get('type', 'unknown')}")
        logger.debug(
            f"   📄 数据大小: {len(json.dumps(data, ensure_ascii=False))} 字符"
        )

        # 检查内存是否存在
        if conversation_id not in self.memories:
            logger.warning(
                f"⚠️  [内存管理] 内存实例不存在，跳过保存 | 对话ID: {conversation_id}"
            )
            return

        try:
            memory = self.memories[conversation_id]

            # 创建内存内容对象，使用安全的JSON序列化
            def safe_json_serializer(obj):
                """安全的JSON序列化器，处理不能序列化的对象"""
                if hasattr(obj, "__dict__"):
                    try:
                        return obj.__dict__
                    except:
                        return str(obj)
                elif hasattr(obj, "tobytes") or hasattr(obj, "save"):
                    # 对于图像对象，返回类型信息而不是完整数据
                    return {
                        "type": "image_object",
                        "class": obj.__class__.__name__,
                        "size": getattr(obj, "size", None),
                        "mode": getattr(obj, "mode", None),
                    }
                elif isinstance(obj, bytes):
                    # 对于字节数据，只保存长度信息
                    return {"type": "bytes", "length": len(obj)}
                else:
                    return str(obj)

            memory_content = MemoryContent(
                content=json.dumps(
                    data, ensure_ascii=False, default=safe_json_serializer
                ),
                mime_type=MemoryMimeType.JSON,
            )

            # 保存到内存
            await memory.add(memory_content)

            logger.debug(f"✅ [内存管理] 数据保存成功 | 对话ID: {conversation_id}")
            logger.debug(f"   📝 保存内容: {data}")

        except Exception as e:
            logger.error(f"❌ [内存管理] 数据保存失败 | 对话ID: {conversation_id}")
            logger.error(f"   🐛 错误类型: {type(e).__name__}")
            logger.error(f"   📄 错误详情: {str(e)}")
            logger.error(f"   📦 尝试保存的数据: {data}")
            raise

    async def get_conversation_history(self, conversation_id: str) -> List[Dict]:
        """获取对话历史 - 修复ListMemory API调用"""
        if conversation_id not in self.memories:
            return []

        memory = self.memories[conversation_id]
        history = []

        # 使用正确的 ListMemory API - 根据源码使用 query() 方法
        try:
            # 使用 query() 方法获取所有内存内容
            query_result = await memory.query("")
            memory_contents = query_result.results if query_result else []

            for content in memory_contents:
                try:
                    data = json.loads(content.content)
                    history.append(data)
                except json.JSONDecodeError:
                    logger.warning(f"解析历史消息失败: {content.content}")

        except Exception as e:
            logger.error(f"获取历史记录失败: {e}")

        return history

    def get_collected_messages(self, conversation_id: str) -> List[Dict]:
        """获取收集的消息 - 暂时注释，留待后续使用"""
        # return self.collected_messages.get(conversation_id, [])
        return []  # 暂时返回空列表

    async def _optimize_testcases(
        self, conversation_id: str, feedback: FeedbackMessage
    ) -> None:
        """
        优化测试用例流程

        处理用户反馈，启动测试用例优化智能体进行用例改进

        Args:
            conversation_id: 对话唯一标识符
            feedback: 用户反馈消息对象
        """
        logger.info(f"🔧 [用例优化流程] 开始优化测试用例流程")
        logger.info(f"   📋 对话ID: {conversation_id}")
        logger.info(f"   🔢 轮次: {feedback.round_number}")
        logger.info(f"   💬 用户反馈: {feedback.feedback}")

        try:
            # 步骤1: 保存用户反馈到内存
            logger.info(
                f"💾 [用例优化流程] 步骤1: 保存用户反馈到内存 | 对话ID: {conversation_id}"
            )
            feedback_data = {
                "type": "user_feedback",
                "feedback": feedback.feedback,
                "round_number": feedback.round_number,
                "previous_testcases_length": len(feedback.previous_testcases or ""),
                "timestamp": datetime.now().isoformat(),
            }
            await self._save_to_memory(conversation_id, feedback_data)
            logger.debug(f"   📝 反馈数据已保存: {feedback_data}")

            # 步骤2: 发布优化消息到智能体
            logger.info(
                f"📢 [用例优化流程] 步骤2: 发布优化消息到智能体 | 对话ID: {conversation_id}"
            )
            logger.info(f"   🎯 目标主题: {testcase_optimization_topic_type}")
            logger.info(f"   📦 消息类型: FeedbackMessage")

            runtime = self.runtimes[conversation_id]
            await runtime.publish_message(
                feedback, topic_id=DefaultTopicId(type=testcase_optimization_topic_type)
            )
            logger.success(
                f"✅ [用例优化流程] 优化消息发布成功，等待优化智能体处理 | 对话ID: {conversation_id}"
            )

            # 步骤3: 更新对话状态
            logger.info(
                f"🔄 [用例优化流程] 步骤3: 更新对话状态 | 对话ID: {conversation_id}"
            )
            state_update = {
                "stage": "optimization",
                "round_number": feedback.round_number,
                "last_update": datetime.now().isoformat(),
                "status": "processing",
            }
            self.conversation_states[conversation_id].update(state_update)
            logger.debug(f"   📊 状态更新: {state_update}")

            logger.success(
                f"🎉 [用例优化流程] 测试用例优化流程启动完成 | 对话ID: {conversation_id}"
            )

        except Exception as e:
            logger.error(
                f"❌ [用例优化流程] 优化流程启动失败 | 对话ID: {conversation_id}"
            )
            logger.error(f"   🐛 错误类型: {type(e).__name__}")
            logger.error(f"   📄 错误详情: {str(e)}")
            raise

    async def _finalize_testcases(
        self, conversation_id: str, feedback: FeedbackMessage
    ) -> None:
        """
        最终化测试用例流程

        用户同意当前测试用例，启动最终化处理，生成结构化JSON数据

        Args:
            conversation_id: 对话唯一标识符
            feedback: 用户反馈消息对象（包含同意信息）
        """
        logger.info(f"🏁 [用例结果流程] 开始最终化测试用例流程")
        logger.info(f"   📋 对话ID: {conversation_id}")
        logger.info(f"   🔢 轮次: {feedback.round_number}")
        logger.info(f"   👍 用户同意: {feedback.feedback}")

        try:
            # 步骤1: 保存用户同意到内存
            logger.info(
                f"💾 [用例结果流程] 步骤1: 保存用户同意到内存 | 对话ID: {conversation_id}"
            )
            approval_data = {
                "type": "user_approval",
                "feedback": feedback.feedback,
                "round_number": feedback.round_number,
                "timestamp": datetime.now().isoformat(),
            }
            await self._save_to_memory(conversation_id, approval_data)
            logger.debug(f"   📝 同意数据已保存: {approval_data}")

            # 步骤2: 获取最后的测试用例内容
            logger.info(
                f"📄 [用例结果流程] 步骤2: 获取最后的测试用例内容 | 对话ID: {conversation_id}"
            )
            state = self.conversation_states.get(conversation_id, {})
            last_testcases = state.get("last_testcases", feedback.previous_testcases)

            logger.info(f"   📊 对话状态: {state.get('stage', 'unknown')}")
            logger.info(
                f"   📄 测试用例来源: {'对话状态' if state.get('last_testcases') else '反馈参数'}"
            )
            logger.info(f"   📝 测试用例长度: {len(last_testcases or '')} 字符")
            logger.debug(f"   📋 测试用例完整内容: {last_testcases or ''}")

            # 步骤3: 创建最终化消息
            logger.info(
                f"📦 [用例结果流程] 步骤3: 创建最终化消息 | 对话ID: {conversation_id}"
            )
            finalization_message = TestCaseMessage(
                source="user_approval",
                content=last_testcases,
                conversation_id=conversation_id,
                round_number=feedback.round_number,
            )
            logger.debug(f"   📋 最终化消息: {finalization_message}")

            # 步骤4: 发布最终化消息到智能体
            logger.info(
                f"📢 [用例结果流程] 步骤4: 发布最终化消息到智能体 | 对话ID: {conversation_id}"
            )
            logger.info(f"   🎯 目标主题: {testcase_finalization_topic_type}")
            logger.info(f"   📦 消息类型: TestCaseMessage")

            runtime = self.runtimes[conversation_id]
            await runtime.publish_message(
                finalization_message,
                topic_id=DefaultTopicId(type=testcase_finalization_topic_type),
            )
            logger.success(
                f"✅ [用例结果流程] 最终化消息发布成功，等待结构化智能体处理 | 对话ID: {conversation_id}"
            )

            # 步骤5: 更新对话状态
            logger.info(
                f"🔄 [用例结果流程] 步骤5: 更新对话状态 | 对话ID: {conversation_id}"
            )
            state_update = {
                "stage": "finalization",
                "round_number": feedback.round_number,
                "last_update": datetime.now().isoformat(),
                "status": "processing",
            }
            self.conversation_states[conversation_id].update(state_update)
            logger.debug(f"   📊 状态更新: {state_update}")

            logger.success(
                f"🎉 [用例结果流程] 测试用例最终化流程启动完成 | 对话ID: {conversation_id}"
            )

        except Exception as e:
            logger.error(
                f"❌ [用例结果流程] 最终化流程启动失败 | 对话ID: {conversation_id}"
            )
            logger.error(f"   🐛 错误类型: {type(e).__name__}")
            logger.error(f"   📄 错误详情: {str(e)}")
            raise

    async def _register_agents(
        self, runtime: SingleThreadedAgentRuntime, conversation_id: str
    ) -> None:
        """注册智能体到运行时"""
        logger.info(f"[智能体注册] 开始注册智能体 | 对话ID: {conversation_id}")

        if not validate_model_client():
            logger.error("模型客户端未初始化或验证失败")
            return

        # 获取模型客户端
        model_client = get_openai_model_client()

        # 注册需求分析智能体
        await RequirementAnalysisAgent.register(
            runtime,
            requirement_analysis_topic_type,
            lambda: RequirementAnalysisAgent(model_client),
        )

        # 注册测试用例生成智能体
        await TestCaseGenerationAgent.register(
            runtime,
            testcase_generation_topic_type,
            lambda: TestCaseGenerationAgent(model_client),
        )

        # 注册测试用例优化智能体
        await TestCaseOptimizationAgent.register(
            runtime,
            testcase_optimization_topic_type,
            lambda: TestCaseOptimizationAgent(model_client),
        )

        # 注册测试用例最终化智能体
        await TestCaseFinalizationAgent.register(
            runtime,
            testcase_finalization_topic_type,
            lambda: TestCaseFinalizationAgent(model_client),
        )

        # 注册结果收集器 - 使用ClosureAgent
        async def collect_result(
            _agent: ClosureContext, message: ResponseMessage, ctx: MessageContext
        ) -> None:
            """
            收集智能体结果的闭包函数

            接收所有智能体发送的ResponseMessage，转换为统一格式并存储

            Args:
                _agent: 闭包上下文
                message: 响应消息对象
                ctx: 消息上下文
            """
            logger.info(
                f"📨 [结果收集器] 收到智能体消息 | 对话ID: {conversation_id} | 智能体: {message.source} | 消息类型: {message.message_type} | 内容长度: {len(message.content)} | 是否最终: {message.is_final} | 完整内容: {message.content}"
            )

            # 确保消息收集器已初始化 - 暂时注释，留待后续使用
            # if conversation_id not in self.collected_messages:
            #     logger.warning(
            #         f"⚠️  [结果收集器] 消息收集器未初始化，创建新的 | 对话ID: {conversation_id}"
            #     )
            #     self.collected_messages[conversation_id] = []

            # 转换为统一的字典格式 - 暂时注释，留待后续使用
            # result_dict = {
            #     "content": message.content,
            #     "agent_type": "agent",
            #     "agent_name": message.source,
            #     "conversation_id": conversation_id,
            #     "round_number": 1,  # 默认轮次，可以从上下文获取
            #     "timestamp": datetime.now().isoformat(),
            #     "is_complete": message.is_final,
            #     "message_type": message.message_type,
            # }

            # 添加到消息收集器 - 暂时注释，留待后续使用
            # self.collected_messages[conversation_id].append(result_dict)
            # current_count = len(self.collected_messages[conversation_id])
            current_count = 0  # 暂时设为0

            logger.success(
                f"✅ [结果收集器] 消息收集成功 | 当前消息总数: {current_count} | 智能体: {message.source} | 消息类型: {message.message_type}"
            )

        logger.info(f"📝 [智能体注册] 注册结果收集器 | 对话ID: {conversation_id}")
        await ClosureAgent.register_closure(
            runtime,
            "collect_result",
            collect_result,
            subscriptions=lambda: [
                TypeSubscription(
                    topic_type=task_result_topic_type, agent_type="collect_result"
                )
            ],
        )
        logger.debug(f"   ✅ 结果收集器注册成功，订阅主题: {task_result_topic_type}")

        logger.success(f"[智能体注册] 所有智能体注册完成 | 对话ID: {conversation_id}")

    async def start_streaming_generation(self, requirement: RequirementMessage) -> None:
        """
        启动流式测试用例生成 - 简化版本

        根据text_content判断是否为反馈监听模式：
        - 如果text_content为"FEEDBACK_LISTENING"，则只初始化队列，不启动新的分析流程
        - 否则启动正常的需求分析流程

        Args:
            requirement: 需求分析消息对象
        """
        conversation_id = requirement.conversation_id
        logger.info(
            f"🌊 [流式生成-简化版] 启动流式测试用例生成 | 对话ID: {conversation_id}"
        )
        logger.info(f"   📝 文本内容: {requirement.text_content}")

        try:
            # 初始化消息队列
            await get_message_queue(conversation_id)

            # 检查是否为反馈监听模式
            if requirement.text_content == "FEEDBACK_LISTENING":
                logger.info(
                    f"🎧 [流式生成-简化版] 反馈监听模式，只初始化队列 | 对话ID: {conversation_id}"
                )
                # 反馈监听模式：只初始化队列，不启动新的分析流程
                # 智能体处理反馈后会将响应放入队列，前端通过队列消费者接收
                return

            # 正常模式：启动需求分析流程，智能体会自动将流式内容放入队列
            logger.info(
                f"📋 [流式生成-简化版] 正常生成模式，启动需求分析 | 对话ID: {conversation_id}"
            )
            await self.start_requirement_analysis(requirement)

        except Exception as e:
            logger.error(
                f"❌ [流式生成-简化版] 流式生成失败 | 对话ID: {conversation_id} | 错误: {e}"
            )
            # 将错误信息放入队列
            error_message = {
                "type": "error",
                "source": "system",
                "content": f"流式生成失败: {str(e)}",
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat(),
            }
            await put_message_to_queue(
                conversation_id, json.dumps(error_message, ensure_ascii=False)
            )

    def _should_stream_message(
        self, agent_name: str, msg_type: str, content: str
    ) -> bool:
        """
        判断是否应该流式输出该消息

        只输出重要智能体的实际内容，过滤掉状态消息和辅助信息
        """
        # 过滤掉空内容
        if not content or not content.strip():
            return False

        # 过滤掉状态消息和提示信息
        status_indicators = [
            "🔍 收到用户需求",
            "开始进行专业",
            "正在分析",
            "正在生成",
            "正在优化",
            "开始执行",
            "任务完成",
            "处理完成",
        ]

        for indicator in status_indicators:
            if indicator in content:
                logger.debug(
                    f"🚫 [流式过滤] 过滤状态消息 | 智能体: {agent_name} | 内容: {content[:50]}..."
                )
                return False

        # 只允许重要智能体的实际输出内容
        important_agents = [
            "需求分析智能体",
            "测试用例生成智能体",
            "用例评审优化智能体",
            "结构化入库智能体",
        ]

        # 检查是否是重要智能体
        is_important_agent = any(agent in agent_name for agent in important_agents)

        if not is_important_agent:
            logger.debug(f"🚫 [流式过滤] 过滤非重要智能体 | 智能体: {agent_name}")
            return False

        # 只允许流式块和最终结果
        allowed_types = [
            "streaming_chunk",
            "需求分析",
            "测试用例生成",
            "用例优化",
            "用例结果",
        ]

        if msg_type not in allowed_types:
            logger.debug(
                f"🚫 [流式过滤] 过滤非允许类型 | 类型: {msg_type} | 智能体: {agent_name}"
            )
            return False

        logger.debug(
            f"✅ [流式过滤] 允许输出 | 智能体: {agent_name} | 类型: {msg_type}"
        )
        return True

    async def cleanup_runtime(self, conversation_id: str) -> None:
        """清理运行时和所有相关数据 - 包含队列清理"""
        logger.info(f"🗑️ [运行时清理] 开始清理对话数据 | 对话ID: {conversation_id}")

        # 清理运行时
        if conversation_id in self.runtimes:
            runtime = self.runtimes[conversation_id]
            try:
                await runtime.stop_when_idle()
                await runtime.close()
            except Exception as e:
                logger.warning(f"⚠️ 停止运行时时出现错误: {e}")
            del self.runtimes[conversation_id]
            logger.debug(f"   ✅ 运行时已清理")

        # 清理内存
        if conversation_id in self.memories:
            del self.memories[conversation_id]
            logger.debug(f"   ✅ 内存已清理")

        # 清理收集的消息 - 暂时注释，留待后续使用
        # if conversation_id in self.collected_messages:
        #     del self.collected_messages[conversation_id]
        #     logger.debug(f"   ✅ 收集的消息已清理")

        # 清理对话状态
        if conversation_id in self.conversation_states:
            del self.conversation_states[conversation_id]
            logger.debug(f"   ✅ 对话状态已清理")

        # 清理队列 - 新增
        cleanup_queues(conversation_id)
        logger.debug(f"   ✅ 队列已清理")

        logger.success(f"🎉 [运行时清理] 对话数据清理完成 | 对话ID: {conversation_id}")


# 全局运行时管理器实例
testcase_runtime = TestCaseGenerationRuntime()


class TestCaseService:
    """AI测试用例生成服务 - 支持流式输出版本"""

    def __init__(self):
        self.max_rounds = 3
        logger.info("AI测试用例生成服务初始化完成")

    def get_uploaded_files_content(self, conversation_id: str) -> str:
        """
        根据conversation_id获取上传的文件内容

        Args:
            conversation_id: 对话ID，与session_id一致

        Returns:
            str: 合并的文件内容，如果没有文件则返回空字符串
        """
        try:
            from backend.services.document import document_service

            # 使用conversation_id作为session_id获取文件内容
            content = document_service.get_session_content(conversation_id)

            if content:
                logger.info(
                    f"📄 [文件内容获取] 成功获取上传文件内容 | 对话ID: {conversation_id} | 内容长度: {len(content)} 字符"
                )
                return content
            else:
                logger.info(
                    f"📄 [文件内容获取] 该对话无上传文件 | 对话ID: {conversation_id}"
                )
                return ""

        except Exception as e:
            logger.error(
                f"❌ [文件内容获取] 获取文件内容失败 | 对话ID: {conversation_id} | 错误: {e}"
            )
            return ""

    def get_uploaded_files_info(self, conversation_id: str) -> List[Dict]:
        """
        根据conversation_id获取上传的文件信息

        Args:
            conversation_id: 对话ID，与session_id一致

        Returns:
            List[Dict]: 文件信息列表
        """
        try:
            from backend.services.document import document_service

            # 使用conversation_id作为session_id获取文件信息
            files_info = document_service.get_session_files(conversation_id)

            logger.info(
                f"📄 [文件信息获取] 获取文件信息 | 对话ID: {conversation_id} | 文件数量: {len(files_info)}"
            )
            return files_info

        except Exception as e:
            logger.error(
                f"❌ [文件信息获取] 获取文件信息失败 | 对话ID: {conversation_id} | 错误: {e}"
            )
            return []

    async def start_generation(self, requirement: RequirementMessage) -> None:
        """启动测试用例生成"""
        await testcase_runtime.start_requirement_analysis(requirement)

    async def start_streaming_generation(self, requirement: RequirementMessage) -> None:
        """启动流式测试用例生成 - 简化版本"""
        await testcase_runtime.start_streaming_generation(requirement)

    async def process_feedback(self, feedback: FeedbackMessage) -> None:
        """处理用户反馈"""
        await testcase_runtime.process_user_feedback(feedback)

    async def process_streaming_feedback(self, feedback: FeedbackMessage) -> None:
        """处理用户反馈 - 简化版本"""
        conversation_id = feedback.conversation_id
        logger.info(
            f"🔄 [流式反馈-简化版] 开始处理用户反馈 | 对话ID: {conversation_id}"
        )

        try:
            # 启动反馈处理，智能体会自动将流式内容放入队列
            await testcase_runtime.process_user_feedback(feedback)

        except Exception as e:
            logger.error(
                f"❌ [流式反馈-简化版] 处理失败 | 对话ID: {conversation_id} | 错误: {e}"
            )
            # 将错误信息放入队列
            error_message = {
                "type": "error",
                "source": "system",
                "content": f"反馈处理失败: {str(e)}",
                "conversation_id": conversation_id,
                "timestamp": datetime.now().isoformat(),
            }
            await put_message_to_queue(
                conversation_id, json.dumps(error_message, ensure_ascii=False)
            )

    def get_messages(self, conversation_id: str) -> List[Dict]:
        """获取消息"""
        return testcase_runtime.get_collected_messages(conversation_id)

    async def get_history(self, conversation_id: str) -> List[Dict]:
        """获取历史"""
        return await testcase_runtime.get_conversation_history(conversation_id)

    async def clear_conversation(self, conversation_id: str) -> None:
        """清除对话历史和消息"""
        await testcase_runtime.cleanup_runtime(conversation_id)


# 智能体实现


@type_subscription(topic_type=requirement_analysis_topic_type)
class RequirementAnalysisAgent(RoutedAgent):
    """需求分析智能体"""

    def __init__(self, model_client) -> None:
        super().__init__(description="需求分析智能体")
        self._model_client = model_client
        self._prompt = """
你是一位资深的软件需求分析师，拥有超过10年的需求分析和软件测试经验。

你的任务是：
1. 仔细分析用户提供的内容（文本、文件等）
2. 识别出核心的功能需求和业务场景
3. 提取关键的业务规则和约束条件
4. 整理出清晰、结构化的需求描述

请用专业、清晰的语言输出分析结果，为后续的测试用例生成提供准确的需求基础。
        """

    async def get_document_from_files(self, files: List[FileUpload]) -> str:
        """
        使用 llama_index 获取文件内容

        Args:
            files: 文件上传对象列表

        Returns:
            str: 解析后的文件内容
        """
        if not files:
            return ""

        logger.info(
            f"📄 [文件解析] 开始使用llama_index解析文件 | 文件数量: {len(files)}"
        )

        try:
            # 创建临时目录存储文件
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                file_paths = []

                # 将base64编码的文件内容保存到临时文件
                for i, file in enumerate(files):
                    logger.debug(
                        f"   📁 处理文件 {i+1}: {file.filename} ({file.content_type}, {file.size} bytes)"
                    )

                    # 解码base64内容
                    try:
                        file_content = base64.b64decode(file.content)
                    except Exception as e:
                        logger.warning(f"   ⚠️ 文件 {file.filename} base64解码失败: {e}")
                        continue

                    # 确定文件扩展名
                    file_ext = Path(file.filename).suffix if file.filename else ""
                    if not file_ext:
                        # 根据content_type推断扩展名
                        if "pdf" in file.content_type.lower():
                            file_ext = ".pdf"
                        elif (
                            "word" in file.content_type.lower()
                            or "docx" in file.content_type.lower()
                        ):
                            file_ext = ".docx"
                        elif "text" in file.content_type.lower():
                            file_ext = ".txt"
                        else:
                            file_ext = ".txt"  # 默认为文本文件

                    # 保存到临时文件
                    temp_file_path = temp_path / f"file_{i+1}{file_ext}"
                    with open(temp_file_path, "wb") as f:
                        f.write(file_content)

                    file_paths.append(str(temp_file_path))
                    logger.debug(f"   ✅ 文件保存成功: {temp_file_path}")

                if not file_paths:
                    logger.warning("   ⚠️ 没有成功保存的文件，跳过解析")
                    return ""

                # 使用 llama_index 读取文件内容
                logger.info(f"   🔍 使用SimpleDirectoryReader读取文件内容")
                data = SimpleDirectoryReader(input_files=file_paths).load_data()

                if not data:
                    logger.warning("   ⚠️ SimpleDirectoryReader未读取到任何内容")
                    return ""

                # 合并所有文档内容
                doc = Document(text="\n\n".join([d.text for d in data]))
                content = doc.text

                logger.success(f"   ✅ 文件解析完成 | 总内容长度: {len(content)} 字符")
                logger.debug(f"   📄 解析内容预览: {content[:200]}...")

                return content

        except Exception as e:
            logger.error(f"❌ [文件解析] 使用llama_index解析文件失败: {e}")
            logger.error(f"   🐛 错误类型: {type(e).__name__}")
            logger.error(f"   📄 错误详情: {str(e)}")
            raise Exception(f"文件读取失败: {str(e)}")

    async def get_document_from_file_paths(self, file_paths: List[str]) -> str:
        """
        使用 llama_index 从文件路径获取文件内容 - 参考examples实现

        Args:
            file_paths: 文件路径列表

        Returns:
            str: 解析后的文件内容
        """
        if not file_paths:
            return ""

        logger.info(
            f"📄 [文件路径解析] 开始使用llama_index解析文件路径 | 文件数量: {len(file_paths)}"
        )

        try:
            # 验证文件路径是否存在
            valid_paths = []
            for i, file_path in enumerate(file_paths):
                logger.debug(f"   📁 验证文件路径 {i+1}: {file_path}")
                if Path(file_path).exists():
                    valid_paths.append(file_path)
                    logger.debug(f"   ✅ 文件路径有效: {file_path}")
                else:
                    logger.warning(f"   ⚠️ 文件路径不存在: {file_path}")

            if not valid_paths:
                logger.warning("   ⚠️ 没有有效的文件路径，跳过解析")
                return ""

            # 使用 llama_index 读取文件内容 - 参考examples的简洁实现
            logger.info(
                f"   🔍 使用SimpleDirectoryReader读取文件内容 | 有效文件: {len(valid_paths)} 个"
            )
            data = SimpleDirectoryReader(input_files=valid_paths).load_data()

            if not data:
                logger.warning("   ⚠️ SimpleDirectoryReader未读取到任何内容")
                return ""

            # 合并所有文档内容 - 参考examples实现
            doc = Document(text="\n\n".join([d.text for d in data]))
            content = doc.text

            logger.success(f"   ✅ 文件路径解析完成 | 总内容长度: {len(content)} 字符")
            logger.debug(f"   📄 解析内容预览: {content[:200]}...")

            return content

        except Exception as e:
            logger.error(f"❌ [文件路径解析] 文件路径解析失败: {str(e)}")
            raise Exception(f"文件路径读取失败: {str(e)}")

    @message_handler
    async def handle_requirement_analysis(
        self, message: RequirementMessage, ctx: MessageContext
    ) -> None:
        """
        处理需求分析消息

        接收用户需求，进行专业的需求分析，并将结果发送给测试用例生成智能体

        Args:
            message: 需求分析消息对象
            ctx: 消息上下文
        """
        conversation_id = message.conversation_id
        logger.info(
            f"🔍 [需求分析智能体] 收到需求分析任务 | 对话ID: {conversation_id} | 轮次: {message.round_number} | 文本内容长度: {len(message.text_content or '')} | 文件数量: {len(message.files) if message.files else 0} | 智能体ID: {self.id}"
        )

        # 检查模型客户端
        if not self._model_client:
            logger.error(
                f"❌ [需求分析智能体] 模型客户端未初始化 | 对话ID: {conversation_id}"
            )
            # await self.publish_message(  # 暂时注释，留待后续使用
            #     ResponseMessage(
            #         source="需求分析智能体",
            #         content="❌ 模型客户端未初始化，无法进行需求分析",
            #         message_type="需求分析",
            #     ),
            #     topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            # )
            return

        try:
            # 步骤1: 流式输出用户的原始需求内容
            logger.info(
                f"📢 [需求分析智能体] 步骤1: 流式输出用户需求内容 | 对话ID: {conversation_id}"
            )

            # 1.1 流式输出用户的文本需求 message.text_content
            if message.text_content and message.text_content.strip():
                logger.info(
                    f"   📝 开始流式输出用户文本需求，长度: {len(message.text_content)} 字符"
                )

                # 构建用户需求消息
                user_text_message = {
                    "type": "text_message",
                    "source": "用户模块",
                    "content": message.text_content.strip(),
                    "message_type": "用户需求",
                    "conversation_id": conversation_id,
                    "timestamp": datetime.now().isoformat(),
                    "is_final": False,
                }

                # 发送到队列进行流式输出
                await put_message_to_queue(
                    conversation_id, json.dumps(user_text_message, ensure_ascii=False)
                )

                logger.success(
                    f"   ✅ 用户文本需求已流式输出 | 对话ID: {conversation_id} | 内容: {message.text_content[:100]}..."
                )
            else:
                logger.info(f"   📝 无用户文本需求内容")

            # 1.2 获取并流式输出每个文档解析的内容
            uploaded_files_info = testcase_service.get_uploaded_files_info(
                conversation_id
            )
            uploaded_file_content = testcase_service.get_uploaded_files_content(
                conversation_id
            )

            if uploaded_files_info and uploaded_file_content:
                logger.info(
                    f"   📎 开始流式输出文档解析内容，文档数量: {len(uploaded_files_info)} 个，总内容长度: {len(uploaded_file_content)} 字符"
                )

                # 构建文档解析结果消息
                document_parse_message = {
                    "type": "text_message",
                    "source": "用户模块",
                    "content": uploaded_file_content,
                    "message_type": "文档解析结果",
                    "conversation_id": conversation_id,
                    "timestamp": datetime.now().isoformat(),
                    "is_final": False,
                }

                # 发送到队列进行流式输出
                await put_message_to_queue(
                    conversation_id,
                    json.dumps(document_parse_message, ensure_ascii=False),
                )

                logger.success(
                    f"   ✅ 文档解析内容已流式输出 | 对话ID: {conversation_id} | 文档数量: {len(uploaded_files_info)} | 内容长度: {len(uploaded_file_content)} 字符"
                )
                logger.debug(f"   📄 文档内容预览: {uploaded_file_content[:200]}...")
            else:
                logger.info(f"   📎 无上传文档或文档解析内容")

            logger.success(
                f"✅ [需求分析智能体] 用户需求和文档内容流式输出完成 | 对话ID: {conversation_id}"
            )

            # 步骤2: 准备分析内容
            logger.info(
                f"📝 [需求分析智能体] 步骤2: 准备分析内容 | 对话ID: {conversation_id}"
            )
            analysis_content = message.text_content or ""
            logger.debug(f"   📄 基础文本内容长度: {len(analysis_content)} 字符")

            # 从document_service获取文件内容
            uploaded_file_content = testcase_service.get_uploaded_files_content(
                conversation_id
            )
            document_content_display = ""

            if uploaded_file_content:
                logger.info(
                    f"   📎 从document_service获取文件内容成功，内容长度: {len(uploaded_file_content)} 字符"
                )
                logger.debug(f"   📄 文件内容预览: {uploaded_file_content[:200]}...")

                # 将文件内容添加到分析内容中
                analysis_content += f"\n\n📎 附件文件内容:\n{uploaded_file_content}"

                # 构建文档内容展示
                document_content_display = "## 📄 文档内容解析\n\n"
                document_content_display += f"成功解析 {len(uploaded_files_info)} 个文档，总内容长度: {len(uploaded_file_content)} 字符\n\n"
                document_content_display += "### 📋 解析内容\n\n"
                # 限制显示长度，避免前端显示过长内容
                if len(uploaded_file_content) > 2000:
                    document_content_display += f"{uploaded_file_content[:2000]}...\n\n*（内容过长，已截取前2000字符显示）*"
                else:
                    document_content_display += uploaded_file_content
                logger.success(
                    f"   ✅ document_service文件内容获取成功，内容长度: {len(uploaded_file_content)} 字符"
                )

            logger.debug(f"   📋 最终分析内容长度: {len(analysis_content)} 字符")

            # 发送文档内容到前端（如果有文档内容）- 暂时注释，留待后续使用
            if document_content_display:
                # await self.publish_message(
                #     ResponseMessage(
                #         source="需求分析智能体",
                #         content=document_content_display,
                #         message_type="文档解析结果",
                #         is_final=False,
                #     ),
                #     topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
                # )
                logger.success(
                    f"✅ [需求分析智能体] 文档内容已准备完成 | 对话ID: {conversation_id}"
                )

            # 步骤3: 获取用户历史消息memory - 参考官方文档
            logger.info(
                f"🧠 [需求分析智能体] 步骤3a: 获取用户历史消息memory | 对话ID: {conversation_id}"
            )
            user_memory = await get_user_memory_for_agent(conversation_id)
            if user_memory:
                logger.info(f"   ✅ 用户历史消息已加载，将用于智能体上下文")
            else:
                logger.info(f"   📝 无历史消息，智能体将使用空上下文")

            # 步骤3b: 创建BufferedChatCompletionContext防止上下文溢出 - 参考官方文档
            logger.info(
                f"🔧 [需求分析智能体] 步骤3b: 创建BufferedChatCompletionContext | 对话ID: {conversation_id}"
            )
            buffered_context = create_buffered_context(buffer_size=4000)
            if buffered_context:
                logger.info(
                    f"   ✅ BufferedChatCompletionContext创建成功，max_tokens: 4000"
                )
            else:
                logger.info(
                    f"   📝 BufferedChatCompletionContext创建失败，将使用默认上下文"
                )

            # 步骤3c: 创建需求分析智能体实例 - 添加memory和context支持
            logger.info(
                f"🤖 [需求分析智能体] 步骤3c: 创建AssistantAgent实例 | 对话ID: {conversation_id}"
            )

            # 构建智能体参数
            agent_params = {
                "name": "requirement_analyst",
                "model_client": self._model_client,
                "system_message": self._prompt,
                "model_client_stream": True,
            }

            # 添加memory支持 - 参考官方文档，memory参数期望List[Memory]
            if user_memory:
                agent_params["memory"] = [user_memory]  # AssistantAgent期望memory为列表
                logger.debug(f"   🧠 已添加用户历史消息memory到智能体")

            # 添加BufferedChatCompletionContext支持 - 参考官方文档
            if buffered_context:
                agent_params["model_context"] = buffered_context
                logger.debug(f"   🔧 已添加BufferedChatCompletionContext到智能体")

            analyst_agent = AssistantAgent(**agent_params)
            logger.debug(f"   ✅ AssistantAgent创建成功: {analyst_agent.name}")
            logger.info(
                f"   📊 智能体配置: memory={'有' if user_memory else '无'}, context={'缓冲' if buffered_context else '默认'}"
            )

            # 步骤4: 发送分析开始标识 - 暂时注释，留待后续使用
            analysis_start_display = (
                "\n\n---\n\n## 🤖 AI需求分析\n\n正在对上述需求进行专业分析...\n\n"
            )
            # await self.publish_message(
            #     ResponseMessage(
            #         source="需求分析智能体",
            #         content=analysis_start_display,
            #         message_type="需求分析",
            #         is_final=False,
            #     ),
            #     topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            # )
            logger.info(
                f"📢 [需求分析智能体] 分析开始标识已准备 | 对话ID: {conversation_id}"
            )

            # 步骤5: 执行需求分析（流式输出）
            logger.info(
                f"⚡ [需求分析智能体] 步骤5: 开始执行需求分析流式输出 | 对话ID: {conversation_id}"
            )
            analysis_task = f"请分析以下需求：\n\n{analysis_content}"
            logger.debug(f"   📋 分析任务: {analysis_task}")

            requirements_parts = []
            final_requirements = ""
            user_input = ""

            # 使用队列模式处理流式结果 - 参考examples/topic1.py
            async for item in analyst_agent.run_stream(task=analysis_task):
                if isinstance(item, ModelClientStreamingChunkEvent):
                    # 将流式块放入队列而不是直接发送
                    if item.content:
                        requirements_parts.append(item.content)
                        # 构建队列消息
                        queue_message = {
                            "type": "streaming_chunk",
                            "source": "需求分析智能体",
                            "content": item.content,
                            "message_type": "streaming",
                            "timestamp": datetime.now().isoformat(),
                        }
                        await put_message_to_queue(
                            conversation_id,
                            json.dumps(queue_message, ensure_ascii=False),
                        )
                        logger.debug(
                            f"📡 [需求分析智能体] 流式块已放入队列 | 对话ID: {conversation_id} | 内容长度: {len(item.content)} | 内容: {item.content}"
                        )

                elif isinstance(item, TextMessage):
                    # 记录智能体的完整输出
                    final_requirements = item.content
                    logger.info(
                        f"📝 [需求分析智能体] 收到完整输出 | 对话ID: {conversation_id} | 内容长度: {len(item.content)}"
                    )

                elif isinstance(item, TaskResult):
                    # 只记录TaskResult最终结果到内存，不保存中间流式块
                    if item.messages:
                        user_input = item.messages[0].content  # 用户的输入
                        final_requirements = item.messages[
                            -1
                        ].content  # 智能体的最终输出
                        logger.info(
                            f"📊 [需求分析智能体] TaskResult | 对话ID: {conversation_id} | 用户输入长度: {len(user_input)} | 最终输出长度: {len(final_requirements)}"
                        )
                        # 保存TaskResult到内存
                        task_result_data = {
                            "type": "task_result",
                            "user_input": user_input,
                            "final_output": final_requirements,
                            "agent": "需求分析智能体",
                            "timestamp": datetime.now().isoformat(),
                        }
                        await testcase_runtime._save_to_memory(
                            conversation_id, task_result_data
                        )

            # 使用最终结果，优先使用TaskResult或TextMessage的内容
            requirements = final_requirements or "".join(requirements_parts)

            # 发送完整消息到队列
            complete_message = {
                "type": "text_message",
                "source": "需求分析智能体",
                "content": requirements,
                "message_type": "需求分析",
                "is_complete": True,
                "timestamp": datetime.now().isoformat(),
            }
            await put_message_to_queue(
                conversation_id, json.dumps(complete_message, ensure_ascii=False)
            )

            # 同时发送到结果收集器 - 暂时注释，留待后续使用
            # await self.publish_message(
            #     ResponseMessage(
            #         source="需求分析智能体",
            #         content=requirements,
            #         message_type="需求分析",
            #         is_final=True,
            #     ),
            #     topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            # )
            logger.success(
                f"✅ [需求分析智能体] 需求分析执行完成 | 对话ID: {conversation_id} | 分析结果长度: {len(requirements)} 字符"
            )

            # 步骤6: 保存分析结果到内存
            logger.info(
                f"💾 [需求分析智能体] 步骤6: 保存分析结果到内存 | 对话ID: {conversation_id}"
            )
            memory_data = {
                "type": "requirement_analysis",
                "content": requirements,
                "timestamp": datetime.now().isoformat(),
                "agent": "需求分析智能体",
                "round_number": message.round_number,
            }
            await testcase_runtime._save_to_memory(conversation_id, memory_data)

            # 步骤7: 记录分析结果（仅日志记录，不重复发送）
            logger.info(
                f"📢 [需求分析智能体] 步骤7: 分析结果已保存 | 对话ID: {conversation_id} | 结果长度: {len(requirements)}"
            )

            # 步骤8: 发送到测试用例生成智能体
            logger.info(
                f"🚀 [需求分析智能体] 步骤8: 发送到测试用例生成智能体 | 对话ID: {conversation_id}"
            )
            logger.info(f"   🎯 目标主题: {testcase_generation_topic_type}")
            testcase_message = TestCaseMessage(
                source="requirement_analyst",
                content=requirements,
                conversation_id=conversation_id,
            )
            await self.publish_message(  # 暂时注释，留待后续使用
                testcase_message,
                topic_id=TopicId(
                    type=testcase_generation_topic_type, source=self.id.key
                ),
            )
            logger.success(
                f"🎉 [需求分析智能体] 需求分析流程完成，已转发给测试用例生成智能体 | 对话ID: {conversation_id}"
            )

        except Exception as e:
            logger.error(
                f"❌ [需求分析智能体] 需求分析过程发生错误 | 对话ID: {conversation_id}"
            )
            logger.error(f"   🐛 错误类型: {type(e).__name__}")
            logger.error(f"   📄 错误详情: {str(e)}")
            logger.error(f"   📍 错误位置: 需求分析智能体处理过程")

            # 发送错误消息 - 暂时注释，留待后续使用
            # await self.publish_message(
            #     ResponseMessage(
            #         source="需求分析智能体",
            #         content=f"❌ 需求分析失败: {str(e)}",
            #         message_type="需求分析",
            #     ),
            #     topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            # )


@type_subscription(topic_type=testcase_generation_topic_type)
class TestCaseGenerationAgent(RoutedAgent):
    """测试用例生成智能体"""

    def __init__(self, model_client):
        super().__init__(description="测试用例生成智能体")
        self._model_client = model_client
        self._prompt = """
你是一名拥有超过10年经验的资深软件测试架构师，精通各种测试方法论（如：等价类划分、边界值分析、因果图、场景法等），并且对用户体验和系统性能有深刻的理解。

你的任务是为接收到的功能需求，设计一份专业、全面、且易于执行的高质量测试用例。

测试要求：
1. 全面性：覆盖功能测试、UI/UX测试、兼容性测试、异常/边界测试、场景组合测试
2. 专业性：每个测试用例都应遵循标准格式，步骤清晰，预期结果明确
3. 输出格式：使用Markdown表格格式，包含用例ID、模块、优先级、测试类型、用例标题、前置条件、测试步骤、预期结果

请基于提供的需求，生成高质量的测试用例。
        """

    @message_handler
    async def handle_testcase_generation(
        self, message: TestCaseMessage, ctx: MessageContext
    ) -> None:
        """
        处理测试用例生成消息 - 使用RoundRobinGroupChat团队模式

        接收需求分析结果，生成专业的测试用例，并等待用户反馈确认

        Args:
            message: 测试用例生成消息对象
            ctx: 消息上下文
        """
        conversation_id = message.conversation_id
        logger.info(
            f"📋 [测试用例生成智能体-团队模式] 收到测试用例生成任务 | 对话ID: {conversation_id} | 来源: {message.source} | 需求内容长度: {len(str(message.content))} | 智能体ID: {self.id}"
        )

        # 检查模型客户端
        if not self._model_client:
            logger.error(
                f"❌ [测试用例生成智能体-团队模式] 模型客户端未初始化 | 对话ID: {conversation_id}"
            )
            return

        try:
            # 步骤1: 记录开始生成状态（仅日志记录，不发送到流式输出）
            logger.info(
                f"📢 [测试用例生成智能体-团队模式] 步骤1: 开始测试用例生成 | 对话ID: {conversation_id}"
            )
            logger.info(f"   📋 收到需求分析结果，开始生成专业测试用例...")

            # 步骤2: 准备生成任务内容
            logger.info(
                f"📝 [测试用例生成智能体-团队模式] 步骤2: 准备生成任务内容 | 对话ID: {conversation_id}"
            )
            requirements_content = str(message.content)
            logger.debug(f"   📄 需求分析内容: {requirements_content}")

            # 步骤3: 获取用户历史消息memory - 参考官方文档
            logger.info(
                f"🧠 [测试用例生成智能体-团队模式] 步骤3a: 获取用户历史消息memory | 对话ID: {conversation_id}"
            )
            user_memory = await get_user_memory_for_agent(conversation_id)
            if user_memory:
                logger.info(f"   ✅ 用户历史消息已加载，将用于智能体上下文")
            else:
                logger.info(f"   📝 无历史消息，智能体将使用空上下文")

            # 步骤3b: 创建BufferedChatCompletionContext防止上下文溢出 - 参考官方文档
            logger.info(
                f"🔧 [测试用例生成智能体-团队模式] 步骤3b: 创建BufferedChatCompletionContext | 对话ID: {conversation_id}"
            )
            buffered_context = create_buffered_context(buffer_size=4000)
            if buffered_context:
                logger.info(
                    f"   ✅ BufferedChatCompletionContext创建成功，max_tokens: 4000"
                )
            else:
                logger.info(
                    f"   📝 BufferedChatCompletionContext创建失败，将使用默认上下文"
                )

            # 步骤3c: 创建测试用例生成智能体实例 - 添加memory和context支持
            logger.info(
                f"🤖 [测试用例生成智能体-团队模式] 步骤3c: 创建AssistantAgent实例 | 对话ID: {conversation_id}"
            )

            # 构建智能体参数
            agent_params = {
                "name": "testcase_generator",
                "model_client": self._model_client,
                "system_message": self._prompt,
                "model_client_stream": True,
            }

            # 添加memory支持 - 参考官方文档，memory参数期望List[Memory]
            if user_memory:
                agent_params["memory"] = [user_memory]  # AssistantAgent期望memory为列表
                logger.debug(f"   🧠 已添加用户历史消息memory到智能体")

            # 添加BufferedChatCompletionContext支持 - 参考官方文档
            if buffered_context:
                agent_params["model_context"] = buffered_context
                logger.debug(f"   🔧 已添加BufferedChatCompletionContext到智能体")

            generator_agent = AssistantAgent(**agent_params)
            logger.debug(f"   ✅ AssistantAgent创建成功: {generator_agent.name}")
            logger.info(
                f"   📊 智能体配置: memory={'有' if user_memory else '无'}, context={'缓冲' if buffered_context else '默认'}"
            )

            # 步骤4: 创建用户反馈智能体 - 参考examples/topic1.py
            logger.info(
                f"👤 [测试用例生成智能体-团队模式] 步骤4: 创建UserProxyAgent实例 | 对话ID: {conversation_id}"
            )

            # 定义符合 UserProxyAgent 要求的 input_func（捕获当前消息的 conversation_id）
            async def user_feedback_input_func(
                prompt: str,  # 必须保留的 prompt 参数（尽管当前场景可能不需要使用）
                cancellation_token: Optional[
                    CancellationToken
                ],  # 必须保留的取消令牌参数
            ) -> str:
                logger.info(
                    f"💬 [测试用例生成智能体-团队模式] 等待用户反馈 | 对话ID: {conversation_id}"
                )

                # 流式输出告知前端需要用户反馈
                logger.info(
                    f"📢 [测试用例生成智能体-团队模式] 发送用户反馈请求到前端 | 对话ID: {conversation_id}"
                )

                # 构建用户反馈请求消息
                feedback_request_message = {
                    "type": "user_input_request",
                    "source": "用户模块",
                    "content": "测试用例已生成完成，请您查看并提供反馈意见。如果满意请回复'同意'，如有修改建议请详细说明。",
                    "message_type": "用户反馈请求",
                    "conversation_id": conversation_id,
                    "timestamp": datetime.now().isoformat(),
                    "is_final": False,
                    "requires_user_input": True,
                }

                # 发送到队列进行流式输出
                await put_message_to_queue(
                    conversation_id,
                    json.dumps(feedback_request_message, ensure_ascii=False),
                )

                logger.success(
                    f"✅ [测试用例生成智能体-团队模式] 用户反馈请求已发送到前端 | 对话ID: {conversation_id}"
                )

                # 调用 get_feedback_from_queue 获取当前对话的反馈（使用 conversation_id）
                logger.info(
                    f"⏳ [测试用例生成智能体-团队模式] 开始等待用户反馈输入 | 对话ID: {conversation_id}"
                )
                feedback = await get_feedback_from_queue(conversation_id)

                logger.success(
                    f"✅ [测试用例生成智能体-团队模式] 收到用户反馈 | 对话ID: {conversation_id} | 反馈内容: {feedback}"
                )

                return feedback

            user_feedback_agent = UserProxyAgent(
                name="user_approve",
                description="用户反馈智能体",
                input_func=user_feedback_input_func,
            )
            logger.debug(f"   ✅ UserProxyAgent创建成功: {user_feedback_agent.name}")

            # 步骤5: 创建RoundRobinGroupChat团队 - 参考examples/topic1.py
            logger.info(
                f"🏢 [测试用例生成智能体-团队模式] 步骤5: 创建RoundRobinGroupChat团队 | 对话ID: {conversation_id}"
            )
            team = RoundRobinGroupChat(
                [generator_agent, user_feedback_agent],
                termination_condition=TextMentionTermination("同意"),
            )
            logger.debug(f"   ✅ RoundRobinGroupChat团队创建成功，成员数: 2")

            # 步骤6: 执行团队协作流式输出 - 参考examples/topic1.py
            logger.info(
                f"⚡ [测试用例生成智能体-团队模式] 步骤6: 开始执行团队协作流式输出 | 对话ID: {conversation_id}"
            )
            generation_task = f"请为以下需求生成测试用例：\n\n{requirements_content}"
            logger.debug(f"   📋 生成任务: {generation_task}")

            testcases_parts = []
            final_testcases = ""
            user_input = ""

            # 使用团队模式处理流式结果 - 参考examples/topic1.py
            async for item in team.run_stream(task=generation_task):
                logger.debug(
                    f"🔄 [测试用例生成智能体-团队模式] 收到团队输出项: {type(item)} | 对话ID: {conversation_id}"
                )

                if isinstance(item, ModelClientStreamingChunkEvent):
                    # 将流式块放入队列而不是直接发送
                    if item.content:
                        testcases_parts.append(item.content)
                        # 构建队列消息
                        queue_message = {
                            "type": "streaming_chunk",
                            "source": "测试用例生成智能体",
                            "content": item.content,
                            "message_type": "streaming",
                            "timestamp": datetime.now().isoformat(),
                        }
                        await put_message_to_queue(
                            conversation_id,
                            json.dumps(queue_message, ensure_ascii=False),
                        )
                        logger.debug(
                            f"📡 [测试用例生成智能体-团队模式] 流式块已放入队列 | 对话ID: {conversation_id} | 内容长度: {len(item.content)} | 内容:{item.content}"
                        )

                elif isinstance(item, TextMessage):
                    # 记录智能体的完整输出
                    final_testcases = item.content
                    logger.info(
                        f"📝 [测试用例生成智能体-团队模式] 收到完整输出 | 对话ID: {conversation_id} | 内容长度: {len(item.content)}"
                    )

                elif isinstance(item, TaskResult):
                    # 只记录TaskResult最终结果到内存，不保存中间流式块
                    if item.messages:
                        user_input = item.messages[0].content  # 用户的输入
                        final_testcases = item.messages[-1].content  # 智能体的最终输出
                        logger.info(
                            f"📊 [测试用例生成智能体-团队模式] TaskResult | 对话ID: {conversation_id} | 用户输入长度: {len(user_input)} | 最终输出长度: {len(final_testcases)}"
                        )
                        # 保存TaskResult到内存
                        task_result_data = {
                            "type": "task_result",
                            "user_input": user_input,
                            "final_output": final_testcases,
                            "agent": "测试用例生成智能体-团队模式",
                            "timestamp": datetime.now().isoformat(),
                        }
                        await testcase_runtime._save_to_memory(
                            conversation_id, task_result_data
                        )

            # 使用最终结果，优先使用TaskResult或TextMessage的内容
            testcases = final_testcases or "".join(testcases_parts)

            # 发送完整消息到队列
            complete_message = {
                "type": "text_message",
                "source": "测试用例生成智能体",
                "content": testcases,
                "message_type": "测试用例生成",
                "is_complete": True,
                "timestamp": datetime.now().isoformat(),
            }
            await put_message_to_queue(
                conversation_id, json.dumps(complete_message, ensure_ascii=False)
            )

            # 发送结束信号到队列
            await put_message_to_queue(conversation_id, "CLOSE")

            logger.success(
                f"✅ [测试用例生成智能体-团队模式] 团队协作执行完成 | 对话ID: {conversation_id} | 生成结果长度: {len(testcases)} 字符"
            )

            # 步骤7: 保存生成结果到内存
            logger.info(
                f"💾 [测试用例生成智能体-团队模式] 步骤7: 保存生成结果到内存 | 对话ID: {conversation_id}"
            )
            memory_data = {
                "type": "testcase_generation_team",
                "content": testcases,
                "timestamp": datetime.now().isoformat(),
                "agent": "测试用例生成智能体-团队模式",
                "source_agent": message.source,
                "team_members": ["testcase_generator", "user_approve"],
                "termination_condition": "TextMentionTermination(同意)",
            }
            await testcase_runtime._save_to_memory(conversation_id, memory_data)

            # 步骤8: 更新对话状态
            logger.info(
                f"🔄 [测试用例生成智能体-团队模式] 步骤8: 更新对话状态 | 对话ID: {conversation_id}"
            )
            conversation_state = {
                "stage": "testcase_generated_with_feedback",
                "round_number": getattr(message, "round_number", 1),
                "last_testcases": testcases,
                "last_update": datetime.now().isoformat(),
                "status": "completed",
                "team_mode": True,
                "user_approved": True,  # 由于使用了"同意"终止条件，说明用户已同意
            }
            testcase_runtime.conversation_states[conversation_id] = conversation_state
            logger.debug(f"   📊 对话状态已更新: {conversation_state}")

            # 步骤9: 记录生成结果（仅日志记录，不重复发送）
            logger.info(
                f"📢 [测试用例生成智能体-团队模式] 步骤9: 生成结果已保存 | 对话ID: {conversation_id} | 结果长度: {len(testcases)}"
            )

            logger.success(
                f"🎉 [测试用例生成智能体-团队模式] 测试用例生成流程完成 | 对话ID: {conversation_id}"
            )

        except Exception as e:
            logger.error(
                f"❌ [测试用例生成智能体-团队模式] 测试用例生成过程发生错误 | 对话ID: {conversation_id}"
            )
            logger.error(f"   🐛 错误类型: {type(e).__name__}")
            logger.error(f"   📄 错误详情: {str(e)}")
            logger.error(f"   📍 错误位置: 测试用例生成智能体-团队模式处理过程")


@type_subscription(topic_type=testcase_optimization_topic_type)
class TestCaseOptimizationAgent(RoutedAgent):
    """测试用例评审优化智能体"""

    def __init__(self, model_client):
        super().__init__(description="测试用例评审优化智能体")
        self._model_client = model_client
        self._prompt = """
你是资深测试用例评审专家，关注用例质量与测试覆盖有效性。请根据用户提供的反馈意见对测试用例进行优化。

## 评审重点
1. 需求覆盖度：确保每个需求点都有对应测试用例
2. 测试深度：正常流/边界/异常流全面覆盖
3. 用例可执行性：步骤清晰、数据明确
4. 用户反馈：重点关注用户提出的具体意见和建议

## 输出格式
请输出优化后的测试用例，使用Markdown表格格式，包含用例ID、模块、优先级、测试类型、用例标题、前置条件、测试步骤、预期结果。
        """

    @message_handler
    async def handle_testcase_optimization(
        self, message: FeedbackMessage, ctx: MessageContext
    ) -> None:
        """
        处理测试用例优化消息

        接收用户反馈，根据反馈意见优化测试用例

        Args:
            message: 用户反馈消息对象
            ctx: 消息上下文
        """
        conversation_id = message.conversation_id
        logger.info(
            f"🔧 [用例评审优化智能体] 收到测试用例优化任务 | 对话ID: {conversation_id} | 轮次: {message.round_number} | 用户反馈: {message.feedback} | 原测试用例长度: {len(message.previous_testcases or '')} | 智能体ID: {self.id}"
        )

        # 检查模型客户端
        if not self._model_client:
            logger.error(
                f"❌ [用例评审优化智能体] 模型客户端未初始化 | 对话ID: {conversation_id}"
            )
            # await self.publish_message(  # 暂时注释，留待后续使用
            #     ResponseMessage(
            #         source="用例评审优化智能体",
            #         content="❌ 模型客户端未初始化，无法优化测试用例",
            #         message_type="用例优化",
            #     ),
            #     topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            # )
            return

        try:
            # 步骤1: 记录开始优化状态（仅日志记录，不发送到流式输出）
            logger.info(
                f"📢 [用例评审优化智能体] 步骤1: 开始测试用例优化 | 对话ID: {conversation_id}"
            )
            logger.info(f"   🔧 收到用户反馈，开始优化测试用例...")

            # 步骤2: 准备优化任务内容
            logger.info(
                f"📝 [用例评审优化智能体] 步骤2: 准备优化任务内容 | 对话ID: {conversation_id}"
            )
            optimization_task = f"""
用户反馈：{message.feedback}

原测试用例：
{message.previous_testcases}

请根据用户反馈优化测试用例。
            """
            logger.debug(f"   📋 优化任务长度: {len(optimization_task)} 字符")
            logger.debug(f"   💬 用户反馈详情: {message.feedback}")
            logger.debug(
                f"   📄 原测试用例完整内容: {message.previous_testcases or ''}"
            )

            # 步骤3: 获取用户历史消息memory - 参考官方文档
            logger.info(
                f"🧠 [用例评审优化智能体] 步骤3a: 获取用户历史消息memory | 对话ID: {conversation_id}"
            )
            user_memory = await get_user_memory_for_agent(conversation_id)
            if user_memory:
                logger.info(f"   ✅ 用户历史消息已加载，将用于智能体上下文")
            else:
                logger.info(f"   📝 无历史消息，智能体将使用空上下文")

            # 步骤3b: 创建BufferedChatCompletionContext防止上下文溢出 - 参考官方文档
            logger.info(
                f"🔧 [用例评审优化智能体] 步骤3b: 创建BufferedChatCompletionContext | 对话ID: {conversation_id}"
            )
            buffered_context = create_buffered_context(buffer_size=4000)
            if buffered_context:
                logger.info(
                    f"   ✅ BufferedChatCompletionContext创建成功，max_tokens: 4000"
                )
            else:
                logger.info(
                    f"   📝 BufferedChatCompletionContext创建失败，将使用默认上下文"
                )

            # 步骤3c: 创建优化智能体实例 - 添加memory和context支持
            logger.info(
                f"🤖 [用例评审优化智能体] 步骤3c: 创建AssistantAgent实例 | 对话ID: {conversation_id}"
            )

            # 构建智能体参数
            agent_params = {
                "name": "testcase_optimizer",
                "model_client": self._model_client,
                "system_message": self._prompt,
                "model_client_stream": True,
            }

            # 添加memory支持 - 参考官方文档，memory参数期望List[Memory]
            if user_memory:
                agent_params["memory"] = [user_memory]  # AssistantAgent期望memory为列表
                logger.debug(f"   🧠 已添加用户历史消息memory到智能体")

            # 添加BufferedChatCompletionContext支持 - 参考官方文档
            if buffered_context:
                agent_params["model_context"] = buffered_context
                logger.debug(f"   🔧 已添加BufferedChatCompletionContext到智能体")

            optimizer_agent = AssistantAgent(**agent_params)
            logger.debug(f"   ✅ AssistantAgent创建成功: {optimizer_agent.name}")
            logger.info(
                f"   📊 智能体配置: memory={'有' if user_memory else '无'}, context={'缓冲' if buffered_context else '默认'}"
            )

            # 步骤4: 执行测试用例优化（流式输出）
            logger.info(
                f"⚡ [用例评审优化智能体] 步骤4: 开始执行测试用例优化流式输出 | 对话ID: {conversation_id}"
            )

            optimized_parts = []
            final_optimized = ""
            user_input = ""

            # 使用队列模式处理流式结果 - 参考examples/topic1.py
            async for item in optimizer_agent.run_stream(task=optimization_task):
                if isinstance(item, ModelClientStreamingChunkEvent):
                    # 将流式块放入队列而不是直接发送
                    if item.content:
                        optimized_parts.append(item.content)
                        # 构建队列消息
                        queue_message = {
                            "type": "streaming_chunk",
                            "source": "用例评审优化智能体",
                            "content": item.content,
                            "message_type": "streaming",
                            "timestamp": datetime.now().isoformat(),
                        }
                        await put_message_to_queue(
                            conversation_id,
                            json.dumps(queue_message, ensure_ascii=False),
                        )
                        logger.debug(
                            f"📡 [用例评审优化智能体] 流式块已放入队列 | 对话ID: {conversation_id} | 内容长度: {len(item.content)}"
                        )

                elif isinstance(item, TextMessage):
                    # 记录智能体的完整输出
                    final_optimized = item.content
                    logger.info(
                        f"📝 [用例评审优化智能体] 收到完整输出 | 对话ID: {conversation_id} | 内容长度: {len(item.content)}"
                    )

                elif isinstance(item, TaskResult):
                    # 只记录TaskResult最终结果到内存，不保存中间流式块
                    if item.messages:
                        user_input = item.messages[0].content  # 用户的输入
                        final_optimized = item.messages[-1].content  # 智能体的最终输出
                        logger.info(
                            f"📊 [用例评审优化智能体] TaskResult | 对话ID: {conversation_id} | 用户输入长度: {len(user_input)} | 最终输出长度: {len(final_optimized)}"
                        )
                        # 保存TaskResult到内存
                        task_result_data = {
                            "type": "task_result",
                            "user_input": user_input,
                            "final_output": final_optimized,
                            "agent": "用例评审优化智能体",
                            "timestamp": datetime.now().isoformat(),
                        }
                        await testcase_runtime._save_to_memory(
                            conversation_id, task_result_data
                        )

            # 使用最终结果，优先使用TaskResult或TextMessage的内容
            optimized_testcases = final_optimized or "".join(optimized_parts)

            # 发送完整消息到队列
            complete_message = {
                "type": "text_message",
                "source": "用例评审优化智能体",
                "content": optimized_testcases,
                "message_type": "用例优化",
                "is_complete": True,
                "timestamp": datetime.now().isoformat(),
            }
            await put_message_to_queue(
                conversation_id, json.dumps(complete_message, ensure_ascii=False)
            )

            # 发送结束信号到队列
            await put_message_to_queue(conversation_id, "CLOSE")

            # 同时发送到结果收集器 - 暂时注释，留待后续使用
            # await self.publish_message(
            #     ResponseMessage(
            #         source="用例评审优化智能体",
            #         content=optimized_testcases,
            #         message_type="用例优化",
            #         is_final=True,
            #     ),
            #     topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            # )
            logger.success(
                f"✅ [用例评审优化智能体] 测试用例优化执行完成 | 对话ID: {conversation_id} | 优化结果长度: {len(optimized_testcases)} 字符"
            )

            # 步骤5: 保存优化结果到内存
            logger.info(
                f"💾 [用例评审优化智能体] 步骤5: 保存优化结果到内存 | 对话ID: {conversation_id}"
            )
            memory_data = {
                "type": "testcase_optimization",
                "user_feedback": message.feedback,
                "optimized_content": optimized_testcases,
                "timestamp": datetime.now().isoformat(),
                "agent": "用例评审优化智能体",
                "round_number": message.round_number,
            }
            await testcase_runtime._save_to_memory(conversation_id, memory_data)

            # 步骤6: 更新对话状态
            logger.info(
                f"🔄 [用例评审优化智能体] 步骤6: 更新对话状态 | 对话ID: {conversation_id}"
            )
            conversation_state = {
                "stage": "testcase_optimized",
                "round_number": message.round_number,
                "last_testcases": optimized_testcases,
                "last_update": datetime.now().isoformat(),
                "status": "completed",
            }
            testcase_runtime.conversation_states[conversation_id] = conversation_state
            logger.debug(f"   📊 对话状态已更新: {conversation_state}")

            # 步骤7: 记录优化结果（仅日志记录，不重复发送）
            logger.info(
                f"📢 [用例评审优化智能体] 步骤7: 优化结果已保存 | 对话ID: {conversation_id} | 结果长度: {len(optimized_testcases)}"
            )

            logger.success(
                f"🎉 [用例评审优化智能体] 测试用例优化流程完成 | 对话ID: {conversation_id}"
            )

        except Exception as e:
            logger.error(
                f"❌ [用例评审优化智能体] 测试用例优化过程发生错误 | 对话ID: {conversation_id}"
            )
            logger.error(f"   🐛 错误类型: {type(e).__name__}")
            logger.error(f"   📄 错误详情: {str(e)}")
            logger.error(f"   📍 错误位置: 用例评审优化智能体处理过程")

            # 发送错误消息 - 暂时注释，留待后续使用
            # await self.publish_message(
            #     ResponseMessage(
            #         source="用例评审优化智能体",
            #         content=f"❌ 测试用例优化失败: {str(e)}",
            #         message_type="用例优化",
            #     ),
            #     topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            # )


@type_subscription(topic_type=testcase_finalization_topic_type)
class TestCaseFinalizationAgent(RoutedAgent):
    """结构化入库智能体"""

    def __init__(self, model_client):
        super().__init__(description="结构化入库智能体")
        self._model_client = model_client
        self._prompt = """
你是测试用例结构化处理专家，负责将测试用例转换为标准的JSON格式并进行数据验证。

请严格按如下JSON数组格式输出，必须满足:
1. 首尾无任何多余字符
2. 不使用Markdown代码块
3. 每个测试用例必须包含required字段

JSON格式要求：
[
  {
    "case_id": "TC001",
    "title": "测试用例标题",
    "module": "功能模块",
    "priority": "高/中/低",
    "test_type": "功能测试/性能测试/兼容性测试等",
    "preconditions": "前置条件",
    "test_steps": "测试步骤",
    "expected_result": "预期结果",
    "description": "用例描述"
  }
]
        """

    @message_handler
    async def handle_testcase_finalization(
        self, message: TestCaseMessage, ctx: MessageContext
    ) -> None:
        """
        处理测试用例最终化消息

        将测试用例转换为结构化JSON格式并进行数据验证

        Args:
            message: 测试用例消息对象
            ctx: 消息上下文
        """
        conversation_id = message.conversation_id
        logger.info(
            f"🏁 [结构化入库智能体] 收到测试用例最终化任务 | 对话ID: {conversation_id} | 轮次: {message.round_number} | 来源: {message.source} | 测试用例内容长度: {len(str(message.content))} | 智能体ID: {self.id}"
        )

        # 检查模型客户端
        if not self._model_client:
            logger.error(
                f"❌ [结构化入库智能体] 模型客户端未初始化 | 对话ID: {conversation_id}"
            )
            # await self.publish_message(  # 暂时注释，留待后续使用
            #     ResponseMessage(
            #         source="结构化入库智能体",
            #         content="❌ 模型客户端未初始化，无法进行结构化处理",
            #         message_type="用例结果",
            #     ),
            #     topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            # )
            return

        try:
            # 步骤1: 记录开始处理状态（仅日志记录，不发送到流式输出）
            logger.info(
                f"📢 [结构化入库智能体] 步骤1: 开始结构化处理 | 对话ID: {conversation_id}"
            )
            logger.info(f"   🏗️ 开始进行数据结构化和入库处理...")

            # 步骤2: 准备结构化任务内容
            logger.info(
                f"📝 [结构化入库智能体] 步骤2: 准备结构化任务内容 | 对话ID: {conversation_id}"
            )
            testcase_content = str(message.content)
            logger.debug(f"   📄 测试用例内容: {testcase_content}")

            # 步骤3: 获取用户历史消息memory - 参考官方文档
            logger.info(
                f"🧠 [结构化入库智能体] 步骤3a: 获取用户历史消息memory | 对话ID: {conversation_id}"
            )
            user_memory = await get_user_memory_for_agent(conversation_id)
            if user_memory:
                logger.info(f"   ✅ 用户历史消息已加载，将用于智能体上下文")
            else:
                logger.info(f"   📝 无历史消息，智能体将使用空上下文")

            # 步骤3b: 创建BufferedChatCompletionContext防止上下文溢出 - 参考官方文档
            logger.info(
                f"🔧 [结构化入库智能体] 步骤3b: 创建BufferedChatCompletionContext | 对话ID: {conversation_id}"
            )
            buffered_context = create_buffered_context(buffer_size=4000)
            if buffered_context:
                logger.info(
                    f"   ✅ BufferedChatCompletionContext创建成功，max_tokens: 4000"
                )
            else:
                logger.info(
                    f"   📝 BufferedChatCompletionContext创建失败，将使用默认上下文"
                )

            # 步骤3c: 创建结构化智能体实例 - 添加memory和context支持
            logger.info(
                f"🤖 [结构化入库智能体] 步骤3c: 创建AssistantAgent实例 | 对话ID: {conversation_id}"
            )

            # 构建智能体参数
            agent_params = {
                "name": "testcase_finalizer",
                "model_client": self._model_client,
                "system_message": self._prompt,
                "model_client_stream": True,
            }

            # 添加memory支持 - 参考官方文档，memory参数期望List[Memory]
            if user_memory:
                agent_params["memory"] = [user_memory]  # AssistantAgent期望memory为列表
                logger.debug(f"   🧠 已添加用户历史消息memory到智能体")

            # 添加BufferedChatCompletionContext支持 - 参考官方文档
            if buffered_context:
                agent_params["model_context"] = buffered_context
                logger.debug(f"   🔧 已添加BufferedChatCompletionContext到智能体")

            finalizer_agent = AssistantAgent(**agent_params)
            logger.debug(f"   ✅ AssistantAgent创建成功: {finalizer_agent.name}")
            logger.info(
                f"   📊 智能体配置: memory={'有' if user_memory else '无'}, context={'缓冲' if buffered_context else '默认'}"
            )

            # 步骤4: 执行结构化处理（流式输出）
            logger.info(
                f"⚡ [结构化入库智能体] 步骤4: 开始执行结构化处理流式输出 | 对话ID: {conversation_id}"
            )
            finalization_task = (
                f"请将以下测试用例转换为JSON格式：\n\n{testcase_content}"
            )
            logger.debug(f"   📋 结构化任务: {finalization_task}")

            structured_parts = []
            final_structured = ""
            user_input = ""

            # 使用队列模式处理流式结果 - 参考examples/topic1.py
            async for item in finalizer_agent.run_stream(task=finalization_task):
                if isinstance(item, ModelClientStreamingChunkEvent):
                    # 将流式块放入队列而不是直接发送
                    if item.content:
                        structured_parts.append(item.content)
                        # 构建队列消息
                        queue_message = {
                            "type": "streaming_chunk",
                            "source": "结构化入库智能体",
                            "content": item.content,
                            "message_type": "streaming",
                            "timestamp": datetime.now().isoformat(),
                        }
                        await put_message_to_queue(
                            conversation_id,
                            json.dumps(queue_message, ensure_ascii=False),
                        )
                        logger.debug(
                            f"📡 [结构化入库智能体] 流式块已放入队列 | 对话ID: {conversation_id} | 内容长度: {len(item.content)}"
                        )

                elif isinstance(item, TextMessage):
                    # 记录智能体的完整输出
                    final_structured = item.content
                    logger.info(
                        f"📝 [结构化入库智能体] 收到完整输出 | 对话ID: {conversation_id} | 内容长度: {len(item.content)}"
                    )

                elif isinstance(item, TaskResult):
                    # 只记录TaskResult最终结果到内存，不保存中间流式块
                    if item.messages:
                        user_input = item.messages[0].content  # 用户的输入
                        final_structured = item.messages[-1].content  # 智能体的最终输出
                        logger.info(
                            f"📊 [结构化入库智能体] TaskResult | 对话ID: {conversation_id} | 用户输入长度: {len(user_input)} | 最终输出长度: {len(final_structured)}"
                        )
                        # 保存TaskResult到内存
                        task_result_data = {
                            "type": "task_result",
                            "user_input": user_input,
                            "final_output": final_structured,
                            "agent": "结构化入库智能体",
                            "timestamp": datetime.now().isoformat(),
                        }
                        await testcase_runtime._save_to_memory(
                            conversation_id, task_result_data
                        )

            # 使用最终结果，优先使用TaskResult或TextMessage的内容
            structured_testcases = final_structured or "".join(structured_parts)

            # 发送完整消息到队列
            complete_message = {
                "type": "text_message",
                "source": "结构化入库智能体",
                "content": structured_testcases,
                "message_type": "用例结果",
                "is_complete": True,
                "timestamp": datetime.now().isoformat(),
            }
            await put_message_to_queue(
                conversation_id, json.dumps(complete_message, ensure_ascii=False)
            )

            # 发送结束信号到队列
            await put_message_to_queue(conversation_id, "CLOSE")

            # 同时发送到结果收集器 - 暂时注释，留待后续使用
            # await self.publish_message(
            #     ResponseMessage(
            #         source="结构化入库智能体",
            #         content=structured_testcases,
            #         message_type="用例结果",
            #         is_final=True,
            #     ),
            #     topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            # )
            logger.success(
                f"✅ [结构化入库智能体] 结构化处理执行完成 | 对话ID: {conversation_id} | 结构化结果长度: {len(structured_testcases)} 字符 | 完整内容: {structured_testcases}"
            )

            # 步骤5: JSON格式验证
            logger.info(
                f"🔍 [结构化入库智能体] 步骤5: 进行JSON格式验证 | 对话ID: {conversation_id}"
            )
            try:
                testcase_list = json.loads(structured_testcases)
                logger.success(f"✅ [结构化入库智能体] JSON格式验证通过")
                logger.info(f"   📊 测试用例数量: {len(testcase_list)}")
                logger.debug(f"   📋 测试用例列表: {testcase_list}")

                # 验证每个测试用例的必要字段
                for i, testcase in enumerate(testcase_list, 1):
                    required_fields = [
                        "case_id",
                        "title",
                        "test_steps",
                        "expected_result",
                    ]
                    missing_fields = [
                        field for field in required_fields if field not in testcase
                    ]
                    if missing_fields:
                        logger.warning(f"   ⚠️  测试用例{i}缺少字段: {missing_fields}")
                    else:
                        logger.debug(
                            f"   ✅ 测试用例{i}字段完整: {testcase.get('case_id', 'unknown')}"
                        )

            except json.JSONDecodeError as e:
                logger.warning(
                    f"⚠️  [结构化入库智能体] JSON格式验证失败 | 对话ID: {conversation_id}"
                )
                logger.warning(f"   🐛 JSON错误: {str(e)}")
                logger.warning(f"   📄 原始结果: {structured_testcases}")
                logger.info(f"   🔄 使用原始内容作为备选方案")
                structured_testcases = testcase_content

            # 步骤6: 保存结构化结果到内存
            logger.info(
                f"💾 [结构化入库智能体] 步骤6: 保存结构化结果到内存 | 对话ID: {conversation_id}"
            )
            memory_data = {
                "type": "testcase_finalization",
                "structured_content": structured_testcases,
                "timestamp": datetime.now().isoformat(),
                "agent": "结构化入库智能体",
                "source_agent": message.source,
                "round_number": message.round_number,
            }
            await testcase_runtime._save_to_memory(conversation_id, memory_data)

            # 步骤7: 更新对话状态为完成
            logger.info(
                f"🔄 [结构化入库智能体] 步骤7: 更新对话状态为完成 | 对话ID: {conversation_id}"
            )
            conversation_state = {
                "stage": "completed",
                "round_number": message.round_number,
                "final_testcases": structured_testcases,
                "last_update": datetime.now().isoformat(),
                "status": "completed",
            }
            testcase_runtime.conversation_states[conversation_id] = conversation_state
            logger.debug(f"   📊 最终对话状态: {conversation_state}")

            # 步骤8: 发送最终结果到结果收集器 - 暂时注释，留待后续使用
            logger.info(
                f"📢 [结构化入库智能体] 步骤8: 最终结果已准备完成 | 对话ID: {conversation_id}"
            )
            # await self.publish_message(
            #     ResponseMessage(
            #         source="结构化入库智能体",
            #         content=structured_testcases,
            #         message_type="用例结果",
            #         is_final=True,
            #     ),
            #     topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            # )

            logger.success(
                f"🎉 [结构化入库智能体] 测试用例最终化流程完成 | 对话ID: {conversation_id}"
            )
            logger.info(f"   🏁 流程状态: 已完成")
            logger.info(f"   📄 最终结果长度: {len(structured_testcases)} 字符")

        except Exception as e:
            logger.error(
                f"❌ [结构化入库智能体] 测试用例结构化过程发生错误 | 对话ID: {conversation_id}"
            )
            logger.error(f"   🐛 错误类型: {type(e).__name__}")
            logger.error(f"   📄 错误详情: {str(e)}")
            logger.error(f"   📍 错误位置: 结构化入库智能体处理过程")

            # 发送错误消息 - 暂时注释，留待后续使用
            # await self.publish_message(
            #     ResponseMessage(
            #         source="结构化入库智能体",
            #         content=f"❌ 测试用例结构化失败: {str(e)}",
            #         message_type="用例结果",
            #     ),
            #     topic_id=TopicId(type=task_result_topic_type, source=self.id.key),
            # )


# 全局服务实例
testcase_service = TestCaseService()
