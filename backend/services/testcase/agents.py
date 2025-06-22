"""
测试用例生成智能体实现
包括文件处理、流式输出、用户反馈、智能体memory的使用
"""

import base64
import json
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.messages import ModelClientStreamingChunkEvent, TextMessage
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_core import (
    CancellationToken,
    MessageContext,
    RoutedAgent,
    TopicId,
    message_handler,
    type_subscription,
)
from autogen_core.memory import ListMemory
from autogen_core.model_context import BufferedChatCompletionContext
from llama_index.core import Document, SimpleDirectoryReader
from loguru import logger
from pydantic import BaseModel

from backend.models.chat import FileUpload


class RequirementAnalysisMessage(BaseModel):
    text_content: Optional[str] = ""
    files: Optional[List[FileUpload]] = None
    file_paths: Optional[List[str]] = None
    conversation_id: str
    round_number: int = 1


class TestCaseGenerationMessage(BaseModel):
    source: str
    content: str
    conversation_id: str


class OptimizationMessage(BaseModel):
    conversation_id: str
    feedback: str
    previous_testcases: str = ""


class FinalizationMessage(BaseModel):
    """最终化消息"""

    conversation_id: str
    content: str


# 复用testcase_service.py中的队列管理方法
async def put_message_to_queue(conversation_id: str, message: str):
    """将消息放入流式队列 - 使用testcase_service的_put_message_to_queue方法"""
    from backend.services.testcase.testcase_service import testcase_service

    await testcase_service._put_message_to_queue(conversation_id, message)


async def get_feedback_from_queue(conversation_id: str) -> str:
    """从队列获取用户反馈 - 使用testcase_service的队列管理"""
    try:
        from backend.services.testcase.testcase_service import testcase_service

        # 获取队列
        queue = testcase_service._get_message_queue(conversation_id)
        if queue:
            # 从反馈队列获取用户反馈
            feedback = await queue.get_feedback()
            logger.debug(
                f"💬 [队列管理] 从队列获取用户反馈 | 对话ID: {conversation_id} | 反馈: {feedback}"
            )
            return feedback
        else:
            logger.warning(f"⚠️ [队列管理] 队列不存在 | 对话ID: {conversation_id}")
            return ""

    except Exception as e:
        logger.error(
            f"❌ [队列管理] 获取用户反馈失败 | 对话ID: {conversation_id} | 错误: {e}"
        )
        return ""


# 直接导入AI核心框架的便捷函数
from backend.ai_core.memory import get_agent_memory as get_user_memory_for_agent
from backend.ai_core.memory import save_to_memory


def create_buffered_context(
    buffer_size: int = 4000,
) -> Optional[BufferedChatCompletionContext]:
    """创建BufferedChatCompletionContext防止LLM上下文溢出"""
    try:
        return BufferedChatCompletionContext(
            buffer_size=buffer_size, initial_messages=None
        )
    except Exception as e:
        logger.error(f"❌ [Context] 创建BufferedChatCompletionContext失败: {e}")
        return None


def get_testcase_service():
    from backend.services.testcase.testcase_service import testcase_service

    return testcase_service


def get_testcase_runtime():
    from backend.services.testcase.testcase_service import testcase_service

    return testcase_service.runtime


@type_subscription(topic_type="requirement_analysis")
class RequirementAnalysisAgent(RoutedAgent):

    def __init__(self) -> None:
        super().__init__(description="需求分析智能体")
        self._prompt = """
你是一位资深的软件需求分析师，拥有超过10年的需求分析和软件测试经验。

你的任务是：
1. 仔细分析用户提供的内容（文本、文件等）
2. 识别出核心的功能需求和业务场景
3. 提取关键的业务规则和约束条件
4. 整理出清晰、结构化的需求描述

请用专业、清晰的语言输出分析结果，为后续的测试用例生成提供准确的需求基础。
        """

    def _create_assistant_agent(
        self, name: str = "requirement_analyst"
    ) -> AssistantAgent:
        """使用工厂方法创建AssistantAgent"""
        from backend.ai_core.factory import create_assistant_agent

        return create_assistant_agent(name=name, system_message=self._prompt)

    async def get_document_from_files(self, files: List[FileUpload]) -> str:
        """

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
        self, message: RequirementAnalysisMessage, ctx: MessageContext
    ) -> None:
        """

        接收用户需求，进行专业的需求分析，并将结果发送给测试用例生成智能体

        Args:
            message: 需求分析消息对象
            ctx: 消息上下文
        """
        conversation_id = message.conversation_id
        logger.info(
            f"🔍 [需求分析智能体] 收到需求分析任务 | 对话ID: {conversation_id} | 轮次: {message.round_number} | 文本内容长度: {len(message.text_content or '')} | 文件数量: {len(message.files) if message.files else 0} | 智能体ID: {self.id}"
        )

        # 不再需要检查模型客户端，因为使用工厂方法创建

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
            testcase_service = get_testcase_service()
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

            # 发送文档内容到前端（如果有文档内容）
            if document_content_display:
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

            # 步骤3c: 创建需求分析智能体实例 - 使用工厂方法
            logger.info(
                f"🤖 [需求分析智能体] 步骤3c: 创建AssistantAgent实例 | 对话ID: {conversation_id}"
            )

            # 使用工厂方法创建AssistantAgent
            analyst_agent = self._create_assistant_agent("requirement_analyst")

            # 添加memory支持 - 如果有用户历史记忆
            if user_memory:
                # 重新创建带memory的智能体
                from backend.ai_core.factory import create_assistant_agent

                analyst_agent = create_assistant_agent(
                    name="requirement_analyst",
                    system_message=self._prompt,
                    memory=[user_memory],  # AssistantAgent期望memory为列表
                    model_context=buffered_context if buffered_context else None,
                )
                logger.debug(f"   🧠 已添加用户历史消息memory到智能体")
            elif buffered_context:
                # 重新创建带context的智能体
                from backend.ai_core.factory import create_assistant_agent

                analyst_agent = create_assistant_agent(
                    name="requirement_analyst",
                    system_message=self._prompt,
                    model_context=buffered_context,
                )
                logger.debug(f"   🔧 已添加BufferedChatCompletionContext到智能体")

            logger.debug(f"   ✅ AssistantAgent创建成功: {analyst_agent.name}")
            logger.info(
                f"   📊 智能体配置: memory={'有' if user_memory else '无'}, context={'缓冲' if buffered_context else '默认'}"
            )

            # 步骤4: 发送分析开始标识
            analysis_start_display = (
                "\n\n---\n\n## 🤖 AI需求分析\n\n正在对上述需求进行专业分析...\n\n"
            )
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
            logger.info(f"🌊 [需求分析智能体] 开始流式处理 | 对话ID: {conversation_id}")
            stream_count = 0
            chunk_count = 0
            text_message_count = 0
            task_result_count = 0

            async for item in analyst_agent.run_stream(task=analysis_task):
                stream_count += 1
                logger.debug(
                    f"🔄 [需求分析智能体] 流式项目 #{stream_count} | 类型: {type(item).__name__} | 对话ID: {conversation_id}"
                )

                if isinstance(item, ModelClientStreamingChunkEvent):
                    chunk_count += 1
                    logger.debug(
                        f"📦 [需求分析智能体] ModelClientStreamingChunkEvent #{chunk_count} | 对话ID: {conversation_id}"
                    )
                    logger.debug(
                        f"   📊 事件属性: content={'有' if item.content else '无'}, content_length={len(item.content) if item.content else 0}"
                    )

                    # 将流式块放入队列而不是直接发送
                    if item.content:
                        logger.debug(
                            f"   📝 内容详情: '{item.content}' (长度: {len(item.content)})"
                        )
                        requirements_parts.append(item.content)

                        # 构建队列消息
                        queue_message = {
                            "type": "streaming_chunk",
                            "source": "需求分析智能体",
                            "content": item.content,
                            "message_type": "streaming",
                            "timestamp": datetime.now().isoformat(),
                        }

                        logger.debug(f"   🏗️ 构建队列消息: {queue_message}")

                        try:
                            # 序列化消息
                            serialized_message = json.dumps(
                                queue_message, ensure_ascii=False
                            )
                            logger.debug(
                                f"   📄 序列化消息长度: {len(serialized_message)} 字符"
                            )
                            logger.debug(
                                f"   📄 序列化消息内容: {serialized_message[:200]}..."
                            )

                            # 放入队列
                            logger.debug(
                                f"   📤 准备放入队列 | 对话ID: {conversation_id}"
                            )
                            await put_message_to_queue(
                                conversation_id, serialized_message
                            )
                            logger.info(
                                f"   ✅ 流式块已成功放入队列 | 对话ID: {conversation_id} | 块#{chunk_count} | 内容长度: {len(item.content)}"
                            )

                        except Exception as queue_e:
                            logger.error(
                                f"   ❌ 放入队列失败 | 对话ID: {conversation_id} | 错误: {queue_e}"
                            )
                            logger.error(
                                f"   🐛 队列错误类型: {type(queue_e).__name__}"
                            )
                            logger.error(f"   📍 队列错误位置: put_message_to_queue")
                    else:
                        logger.warning(
                            f"   ⚠️ ModelClientStreamingChunkEvent内容为空 | 对话ID: {conversation_id}"
                        )
                        logger.debug(f"   📊 空内容事件详情: {vars(item)}")

                elif isinstance(item, TextMessage):
                    text_message_count += 1
                    logger.debug(
                        f"💬 [需求分析智能体] TextMessage #{text_message_count} | 对话ID: {conversation_id}"
                    )
                    logger.debug(
                        f"   📊 消息属性: content={'有' if item.content else '无'}, content_length={len(item.content) if item.content else 0}"
                    )
                    logger.debug(
                        f"   📝 消息内容预览: '{item.content[:200]}...' (总长度: {len(item.content)})"
                    )

                    # 记录智能体的完整输出
                    final_requirements = item.content
                    logger.info(
                        f"   ✅ TextMessage已记录为最终需求 | 对话ID: {conversation_id} | 内容长度: {len(item.content)}"
                    )
                    logger.info(
                        f"📝 [需求分析智能体] 收到完整输出 | 对话ID: {conversation_id} | 内容长度: {len(item.content)}"
                    )

                elif isinstance(item, TaskResult):
                    task_result_count += 1
                    logger.debug(
                        f"🎯 [需求分析智能体] TaskResult #{task_result_count} | 对话ID: {conversation_id}"
                    )
                    logger.debug(
                        f"   📊 TaskResult属性: messages={'有' if item.messages else '无'}, messages_count={len(item.messages) if item.messages else 0}"
                    )

                    # 只记录TaskResult最终结果到内存，不保存中间流式块
                    if item.messages:
                        logger.debug(
                            f"   📝 处理TaskResult消息列表，共 {len(item.messages)} 条消息"
                        )

                        user_input = item.messages[0].content  # 用户的输入
                        final_requirements = item.messages[
                            -1
                        ].content  # 智能体的最终输出

                        logger.debug(
                            f"   👤 用户输入: '{user_input[:100]}...' (长度: {len(user_input)})"
                        )
                        logger.debug(
                            f"   🤖 智能体输出: '{final_requirements[:100]}...' (长度: {len(final_requirements)})"
                        )
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

                        logger.debug(
                            f"   💾 准备保存TaskResult到内存: {task_result_data}"
                        )

                        try:
                            await save_to_memory(conversation_id, task_result_data)
                            logger.info(
                                f"   ✅ TaskResult已保存到内存 | 对话ID: {conversation_id}"
                            )
                        except Exception as memory_e:
                            logger.error(
                                f"   ❌ 保存TaskResult到内存失败 | 对话ID: {conversation_id} | 错误: {memory_e}"
                            )
                    else:
                        logger.warning(
                            f"   ⚠️ TaskResult没有消息列表 | 对话ID: {conversation_id}"
                        )
                        logger.debug(f"   📊 空TaskResult详情: {vars(item)}")

                else:
                    logger.warning(
                        f"⚠️ [需求分析智能体] 未知的流式项目类型: {type(item).__name__} | 对话ID: {conversation_id}"
                    )
                    logger.debug(f"   📊 未知项目详情: {vars(item)}")

            # 流式处理总结
            logger.info(f"🏁 [需求分析智能体] 流式处理完成 | 对话ID: {conversation_id}")
            logger.info(
                f"   📊 流式统计: 总项目={stream_count}, 流式块={chunk_count}, 文本消息={text_message_count}, 任务结果={task_result_count}"
            )
            logger.info(f"   📝 收集到的流式块数量: {len(requirements_parts)}")
            logger.info(
                f"   📄 最终需求长度: {len(final_requirements) if final_requirements else 0} 字符"
            )

            # 使用最终结果，优先使用TaskResult或TextMessage的内容
            requirements = final_requirements or "".join(requirements_parts)
            logger.info(
                f"   🎯 最终使用的需求来源: {'TaskResult/TextMessage' if final_requirements else '流式块拼接'}"
            )
            logger.info(f"   📏 最终需求总长度: {len(requirements)} 字符")

            # 发送完整消息到队列
            logger.info(
                f"📤 [需求分析智能体] 准备发送完整消息到队列 | 对话ID: {conversation_id}"
            )
            complete_message = {
                "type": "text_message",
                "source": "需求分析智能体",
                "content": requirements,
                "message_type": "需求分析",
                "is_complete": True,
                "timestamp": datetime.now().isoformat(),
            }

            logger.debug(f"   📋 完整消息内容: {complete_message}")
            logger.debug(f"   📏 完整消息内容长度: {len(requirements)} 字符")

            try:
                serialized_complete = json.dumps(complete_message, ensure_ascii=False)
                logger.debug(
                    f"   📄 序列化完整消息长度: {len(serialized_complete)} 字符"
                )

                await put_message_to_queue(conversation_id, serialized_complete)
                logger.info(
                    f"   ✅ 完整消息已成功发送到队列 | 对话ID: {conversation_id}"
                )

            except Exception as complete_e:
                logger.error(
                    f"   ❌ 发送完整消息失败 | 对话ID: {conversation_id} | 错误: {complete_e}"
                )
                logger.error(f"   🐛 完整消息错误类型: {type(complete_e).__name__}")

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
            await save_to_memory(conversation_id, memory_data)

            # 步骤7: 记录分析结果（仅日志记录，不重复发送）
            logger.info(
                f"📢 [需求分析智能体] 步骤7: 分析结果已保存 | 对话ID: {conversation_id} | 结果长度: {len(requirements)}"
            )

            # 步骤8: 发送到测试用例生成智能体
            logger.info(
                f"🚀 [需求分析智能体] 步骤8: 发送到测试用例生成智能体 | 对话ID: {conversation_id}"
            )
            logger.info(f"   🎯 目标主题: testcase_generation")
            testcase_message = TestCaseGenerationMessage(
                source="requirement_analyst",
                content=requirements,
                conversation_id=conversation_id,
            )
            await self.publish_message(
                testcase_message,
                topic_id=TopicId(type="testcase_generation", source=self.id.key),
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


@type_subscription(topic_type="testcase_generation")
class TestCaseGenerationAgent(RoutedAgent):

    def __init__(self) -> None:
        super().__init__(description="测试用例生成智能体")
        self._prompt = """
你是一位资深的软件测试专家，拥有超过15年的测试用例设计和测试执行经验。

你的任务是：
1. 基于需求分析结果，设计全面的测试用例
2. 确保测试用例覆盖正常流程、异常流程和边界条件
3. 每个测试用例都要包含：测试目标、前置条件、测试步骤、预期结果
4. 测试用例要具体、可执行、可验证

请生成结构化、专业的测试用例，确保测试覆盖率和质量。
        """

    def _create_assistant_agent(
        self, name: str = "testcase_generator"
    ) -> AssistantAgent:
        """使用工厂方法创建AssistantAgent"""
        from backend.ai_core.factory import create_assistant_agent

        return create_assistant_agent(name=name, system_message=self._prompt)

    @message_handler
    async def handle_testcase_generation(
        self, message: TestCaseGenerationMessage, ctx: MessageContext
    ) -> None:
        conversation_id = message.conversation_id
        logger.info(
            f"🧪 [测试用例生成智能体-团队模式] 收到测试用例生成任务 | 对话ID: {conversation_id} | 来源: {message.source}"
        )

        try:
            # 步骤1: 获取用户历史记忆
            logger.info(
                f"🧠 [测试用例生成智能体-团队模式] 步骤1: 获取用户历史记忆 | 对话ID: {conversation_id}"
            )
            user_memory = await get_user_memory_for_agent(conversation_id)
            buffered_context = create_buffered_context(buffer_size=4000)

            # 步骤2: 创建测试用例生成智能体
            logger.info(
                f"🤖 [测试用例生成智能体-团队模式] 步骤2: 创建测试用例生成智能体 | 对话ID: {conversation_id}"
            )
            if user_memory or buffered_context:
                from backend.ai_core.factory import create_assistant_agent

                generator_agent = create_assistant_agent(
                    name="testcase_generator",
                    system_message=self._prompt,
                    memory=[user_memory] if user_memory else None,
                    model_context=buffered_context if buffered_context else None,
                )
            else:
                generator_agent = self._create_assistant_agent("testcase_generator")

            logger.debug(f"   ✅ 测试用例生成智能体创建成功: {generator_agent.name}")

            # 步骤3: 创建用户反馈智能体 - 参考您提供的代码
            logger.info(
                f"👤 [测试用例生成智能体-团队模式] 步骤3: 创建用户反馈智能体 | 对话ID: {conversation_id}"
            )

            # 定义符合 UserProxyAgent 要求的 input_func（捕获当前消息的 conversation_id）
            async def user_feedback_input_func(
                prompt: str,  # 必须保留的 prompt 参数（尽管当前场景可能不需要使用）
                cancellation_token: Optional[
                    CancellationToken
                ] = None,  # 必须保留的取消令牌参数
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

            # 使用工厂方法创建UserProxyAgent
            from backend.ai_core.factory import create_user_proxy_agent

            user_feedback_agent = create_user_proxy_agent(
                name="user_approve",
                input_func=user_feedback_input_func,
            )
            logger.debug(f"   ✅ UserProxyAgent创建成功: {user_feedback_agent.name}")

            # 步骤4: 创建RoundRobinGroupChat团队 - 参考examples/topic1.py
            logger.info(
                f"🏢 [测试用例生成智能体-团队模式] 步骤4: 创建RoundRobinGroupChat团队 | 对话ID: {conversation_id}"
            )

            team = RoundRobinGroupChat(
                [generator_agent, user_feedback_agent],
                termination_condition=TextMentionTermination("同意"),
            )
            logger.debug(f"   ✅ RoundRobinGroupChat团队创建成功，成员数: 2")

            # 步骤5: 执行团队协作流式输出 - 参考examples/topic1.py
            logger.info(
                f"⚡ [测试用例生成智能体-团队模式] 步骤5: 开始执行团队协作流式输出 | 对话ID: {conversation_id}"
            )
            generation_task = f"请为以下需求生成测试用例：\n\n{message.content}"
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
                        await save_to_memory(conversation_id, task_result_data)

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

            logger.success(
                f"✅ [测试用例生成智能体-团队模式] 团队协作执行完成 | 对话ID: {conversation_id} | 生成结果长度: {len(testcases)} 字符"
            )

            # 步骤6: 保存生成结果到内存
            logger.info(
                f"💾 [测试用例生成智能体-团队模式] 步骤6: 保存生成结果到内存 | 对话ID: {conversation_id}"
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
            await save_to_memory(conversation_id, memory_data)

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


@type_subscription(topic_type="testcase_optimization")
class TestCaseOptimizationAgent(RoutedAgent):

    def __init__(self) -> None:
        super().__init__(description="测试用例优化智能体")
        self._prompt = """
你是一位资深的测试用例评审专家，拥有超过12年的测试用例优化和质量改进经验。

你的任务是：
1. 仔细分析用户的反馈意见
2. 识别现有测试用例中的不足之处
3. 根据用户反馈进行针对性的优化
4. 确保优化后的测试用例更加完善和实用

请根据用户反馈进行专业的测试用例优化，提高测试用例的质量和实用性。
        """

    def _create_assistant_agent(
        self, name: str = "testcase_optimizer"
    ) -> AssistantAgent:
        """使用工厂方法创建AssistantAgent"""
        from backend.ai_core.factory import create_assistant_agent

        return create_assistant_agent(name=name, system_message=self._prompt)

    @message_handler
    async def handle_optimization(
        self, message: OptimizationMessage, ctx: MessageContext
    ) -> None:
        conversation_id = message.conversation_id
        logger.info(f"🔧 [测试用例优化智能体] 收到优化任务 | 对话ID: {conversation_id}")

        try:
            # 简化实现，直接优化测试用例
            logger.info(
                f"⚡ [测试用例优化智能体] 开始优化测试用例 | 对话ID: {conversation_id}"
            )

            # 获取用户历史记忆
            user_memory = await get_user_memory_for_agent(conversation_id)
            buffered_context = create_buffered_context(buffer_size=4000)

            # 使用工厂方法创建AssistantAgent
            if user_memory or buffered_context:
                from backend.ai_core.factory import create_assistant_agent

                optimizer_agent = create_assistant_agent(
                    name="testcase_optimizer",
                    system_message=self._prompt,
                    memory=[user_memory] if user_memory else None,
                    model_context=buffered_context if buffered_context else None,
                )
            else:
                optimizer_agent = self._create_assistant_agent("testcase_optimizer")

            # 优化测试用例
            optimization_task = f"""
用户对之前生成的测试用例提出了以下反馈意见：

**用户反馈**：{message.feedback}

**之前的测试用例**：
{message.previous_testcases}

请根据用户的反馈意见，对测试用例进行优化和改进。
"""

            optimized_parts = []
            final_optimized = ""

            async for item in optimizer_agent.run_stream(task=optimization_task):
                if isinstance(item, ModelClientStreamingChunkEvent):
                    if item.content:
                        optimized_parts.append(item.content)
                        queue_message = {
                            "type": "streaming_chunk",
                            "source": "测试用例优化智能体",
                            "content": item.content,
                            "message_type": "streaming",
                            "timestamp": datetime.now().isoformat(),
                        }
                        await put_message_to_queue(
                            conversation_id,
                            json.dumps(queue_message, ensure_ascii=False),
                        )

                elif isinstance(item, TextMessage):
                    final_optimized = item.content

                elif isinstance(item, TaskResult):
                    if item.messages:
                        final_optimized = item.messages[-1].content
                        task_result_data = {
                            "type": "task_result",
                            "user_input": item.messages[0].content,
                            "final_output": final_optimized,
                            "agent": "测试用例优化智能体",
                            "timestamp": datetime.now().isoformat(),
                        }
                        await save_to_memory(conversation_id, task_result_data)

            optimized_testcases = final_optimized or "".join(optimized_parts)

            # 发送完整消息
            complete_message = {
                "type": "text_message",
                "source": "测试用例优化智能体",
                "content": optimized_testcases,
                "message_type": "测试用例优化",
                "is_complete": True,
                "timestamp": datetime.now().isoformat(),
            }
            await put_message_to_queue(
                conversation_id, json.dumps(complete_message, ensure_ascii=False)
            )

            logger.success(
                f"✅ [测试用例优化智能体] 测试用例优化完成 | 对话ID: {conversation_id}"
            )

        except Exception as e:
            logger.error(
                f"❌ [测试用例优化智能体] 处理失败 | 对话ID: {conversation_id} | 错误: {e}"
            )


@type_subscription(topic_type="testcase_finalization")
class TestCaseFinalizationAgent(RoutedAgent):

    def __init__(self) -> None:
        super().__init__(description="测试用例最终化智能体")
        self._prompt = """
你是一位测试用例结构化处理专家，负责将最终确认的测试用例转换为标准格式。

你的任务是：
1. 将测试用例转换为结构化的JSON格式
2. 确保数据格式的标准化和完整性
3. 添加必要的元数据信息
4. 生成可直接入库的数据结构

请输出标准的JSON格式测试用例数据。
        """

    @message_handler
    async def handle_finalization(
        self, message: FinalizationMessage, ctx: MessageContext
    ) -> None:
        conversation_id = message.conversation_id
        logger.info(
            f"📦 [测试用例最终化智能体] 收到最终化任务 | 对话ID: {conversation_id}"
        )

        try:
            # 简化实现，直接发送最终化完成消息
            complete_message = {
                "type": "text_message",
                "source": "测试用例最终化智能体",
                "content": "✅ 测试用例已确认完成，可以开始执行测试。",
                "message_type": "测试用例最终化",
                "is_complete": True,
                "timestamp": datetime.now().isoformat(),
            }
            await put_message_to_queue(
                conversation_id, json.dumps(complete_message, ensure_ascii=False)
            )

            logger.success(
                f"✅ [测试用例最终化智能体] 最终化完成 | 对话ID: {conversation_id}"
            )

        except Exception as e:
            logger.error(
                f"❌ [测试用例最终化智能体] 处理失败 | 对话ID: {conversation_id} | 错误: {e}"
            )


# 导出接口
__all__ = [
    "RequirementAnalysisAgent",
    "TestCaseGenerationAgent",
    "TestCaseOptimizationAgent",
    "TestCaseFinalizationAgent",
    "RequirementAnalysisMessage",
    "TestCaseGenerationMessage",
    "OptimizationMessage",
    "FinalizationMessage",
]
