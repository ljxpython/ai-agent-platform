"""
Midscene 智能体服务
完全参照 examples/midscene_agents.py 的实现
整合 Midscene 四智能体系统到当前 AI 测试平台
"""

import asyncio
import json
import time
import traceback
from asyncio import Queue
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import uuid4

import aiofiles
import PIL.Image
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import (
    ModelClientStreamingChunkEvent,
    MultiModalMessage,
    TextMessage,
)
from autogen_core import (
    CancellationToken,
    ClosureAgent,
    ClosureContext,
    DefaultTopicId,
    Image,
    MessageContext,
    RoutedAgent,
    SingleThreadedAgentRuntime,
    TopicId,
    TypeSubscription,
    message_handler,
    type_subscription,
)
from loguru import logger
from pydantic import BaseModel, Field

from backend.ai_core.llm import get_default_client as get_model_client
from backend.conf.config import settings
from backend.models.midscene import (
    MidsceneAgentLog,
    MidsceneSession,
    MidsceneStatistics,
    MidsceneUploadedFile,
)

# ==================== Topic定义 ====================

UI_ANALYSIS_TOPIC = "ui_analysis"
INTERACTION_ANALYSIS_TOPIC = "interaction_analysis"
MIDSCENE_GENERATION_TOPIC = "midscene_generation"
SCRIPT_GENERATION_TOPIC = "script_generation"
COLLABORATIVE_ANALYSIS_TOPIC = "collaborative_analysis"
TASK_RESULTS_TOPIC = "task_results"

# ==================== 数据模型定义 ====================


class UIAnalysisRequest(BaseModel):
    user_id: str = Field(..., description="用户ID")
    image_path: str = Field(..., description="图片路径")
    user_requirement: str = Field(..., description="用户需求描述")


class InteractionAnalysisRequest(BaseModel):
    user_id: str = Field(..., description="用户ID")
    ui_elements: str = Field(..., description="UI元素分析结果")
    user_requirement: str = Field(..., description="用户需求描述")


class MidsceneGenerationRequest(BaseModel):
    user_id: str = Field(..., description="用户ID")
    ui_analysis: str = Field(..., description="UI分析结果")
    interaction_analysis: str = Field(..., description="交互分析结果")
    user_requirement: str = Field(..., description="用户需求描述")


class ScriptGenerationRequest(BaseModel):
    user_id: str = Field(..., description="用户ID")
    midscene_json: str = Field(..., description="Midscene JSON结果")
    user_requirement: str = Field(..., description="用户需求描述")


class CollaborativeAnalysisRequest(BaseModel):
    user_id: str = Field(..., description="用户ID")
    image_paths: List[str] = Field(..., description="图片路径列表")
    user_requirement: str = Field(..., description="用户需求描述")


class TaskResult(BaseModel):
    user_id: str = Field(..., description="用户ID")
    agent_name: str = Field(..., description="智能体名称")
    content: str = Field(..., description="处理结果")
    step: str = Field(..., description="处理步骤")


# ==================== 队列管理 ====================

message_queues: Dict[str, Queue] = {}  # 按用户ID隔离队列


def get_queue(user_id: str) -> Queue:
    """获取用户消息队列"""
    if user_id not in message_queues:
        message_queues[user_id] = Queue(maxsize=100)
    return message_queues[user_id]


async def message_generator(user_id: str):
    """消息生成器，用于SSE流式输出"""
    queue = get_queue(user_id)
    try:
        while True:
            message = await queue.get()

            # 处理不同类型的消息
            if isinstance(message, dict):
                message_type = message.get("type", "unknown")

                if message_type == "system_start":
                    # 系统开始工作
                    yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"

                elif message_type == "agent_start":
                    # 智能体开始工作
                    yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"

                elif message_type == "step_info":
                    # 步骤信息
                    yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"

                elif message_type == "stream_chunk":
                    # 流式内容块
                    yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"

                elif message_type == "agent_complete":
                    # 智能体完成工作
                    yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"

                elif message_type == "agent_error":
                    # 智能体错误
                    yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"

                elif message_type == "system_complete":
                    # 系统完成所有工作
                    yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
                    break

                elif message_type == "system_error":
                    # 系统错误
                    yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"
                    break

                else:
                    # 其他类型的字典消息
                    yield f"data: {json.dumps(message, ensure_ascii=False)}\n\n"

            elif message == "COMPLETE":
                # 兼容旧的完成标记
                yield f"data: {json.dumps({'type': 'system_complete', 'message': '所有分析完成'}, ensure_ascii=False)}\n\n"
                break

            else:
                # 其他类型的消息
                yield f"data: {json.dumps({'type': 'message', 'content': str(message)}, ensure_ascii=False)}\n\n"

            queue.task_done()
    finally:
        # 不在这里清理队列，由协作分析函数负责清理
        logger.debug(f"📋 消息生成器结束 - 用户: {user_id}")
        pass


# ==================== 图片处理工具 ====================


def load_image_from_file(file_path: Union[str, Path]) -> Image:
    """从本地文件加载图片"""
    try:
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"图片文件不存在: {file_path}")

        pil_image = PIL.Image.open(file_path)
        return Image(pil_image)
    except Exception as e:
        raise ValueError(f"无法从文件加载图片: {e}")


def create_multimodal_message(
    text: str, images: List[Union[str, Path, Image]], source: str = "user"
) -> MultiModalMessage:
    """创建多模态消息"""
    content = [text]

    for img in images:
        if isinstance(img, Image):
            content.append(img)
        elif isinstance(img, str):
            content.append(load_image_from_file(img))
        else:
            content.append(load_image_from_file(img))

    return MultiModalMessage(content=content, source=source)


# ==================== UI分析智能体 ====================


@type_subscription(topic_type=UI_ANALYSIS_TOPIC)
class UIAnalysisAgent(RoutedAgent):

    def __init__(self, description: str):
        super().__init__(description=description)
        logger.info(f"🔍 UI分析智能体初始化: {description}")

        self.system_prompt = """你是UI元素识别专家，专门分析界面截图中的UI组件，为自动化测试提供精确的元素信息。

## 核心职责

### 1. 元素识别与分类
- **交互元素**: 按钮、链接、输入框、下拉菜单、复选框、单选按钮、开关
- **显示元素**: 文本、图片、图标、标签、提示信息
- **容器元素**: 表单、卡片、模态框、侧边栏、导航栏
- **列表元素**: 表格、列表项、菜单项、选项卡

### 2. 视觉特征描述标准
- **颜色**: 主色调、背景色、边框色（如"蓝色按钮"、"红色警告文字"）
- **尺寸**: 相对大小（大、中、小）和具体描述
- **形状**: 圆角、方形、圆形等
- **图标**: 具体图标类型（如"搜索图标"、"用户头像图标"）
- **文字**: 完整的文字内容和字体样式

### 3. 位置定位规范
- **绝对位置**: "页面左上角"、"右下角"、"中央区域"
- **相对位置**: "搜索框右侧"、"表单底部"、"导航栏下方"
- **层级关系**: "主容器内"、"弹窗中"、"侧边栏里"

### 4. 功能用途分析
- **操作类型**: 提交、取消、搜索、筛选、导航等
- **交互状态**: 可点击、禁用、选中、悬停等
- **业务功能**: 登录、注册、购买、编辑等

## 输出格式要求

请严格按照以下JSON格式输出，每个元素包含完整信息：

```json
[
  {
    "id": "element_001",
    "name": "登录按钮",
    "element_type": "button",
    "description": "页面右上角的蓝色圆角按钮，白色文字'登录'，位于搜索框右侧",
    "text_content": "登录",
    "position": {
      "area": "页面右上角",
      "relative_to": "搜索框右侧"
    },
    "visual_features": {
      "color": "蓝色背景，白色文字",
      "size": "中等尺寸",
      "shape": "圆角矩形"
    },
    "functionality": "用户登录入口",
    "interaction_state": "可点击",
    "confidence_score": 0.95
  }
]
```

## 质量标准

- **完整性**: 识别所有可见的交互元素（目标≥90%覆盖率）
- **准确性**: 元素类型和描述准确无误
- **详细性**: 每个元素包含足够的视觉特征用于自动化定位
- **结构化**: 严格遵循JSON格式，便于后续处理"""

    @message_handler
    async def analyze_ui(self, message: UIAnalysisRequest, ctx: MessageContext) -> None:
        start_time = time.time()
        logger.info(f"🔍 开始UI元素分析 - 用户ID: {message.user_id}")
        logger.info(f"📷 分析图片: {message.image_path}")
        logger.info(f"📝 用户需求: {message.user_requirement[:100]}...")
        logger.debug(f"🔧 消息上下文: {ctx}")

        try:
            # 验证图片文件是否存在
            image_path = Path(message.image_path)
            if not image_path.exists():
                logger.error(f"❌ 图片文件不存在: {message.image_path}")
                raise FileNotFoundError(f"图片文件不存在: {message.image_path}")

            logger.info(
                f"✅ 图片文件验证通过: {image_path.name} (大小: {image_path.stat().st_size} bytes)"
            )

            # 发送开始分析的消息
            if message.user_id in message_queues:
                logger.debug(f"📤 发送开始分析消息到队列: {message.user_id}")
                await message_queues[message.user_id].put(
                    {
                        "type": "agent_start",
                        "agent": "UI分析智能体",
                        "step": "开始分析UI元素",
                        "content": "正在分析界面截图中的UI元素...",
                    }
                )
                logger.debug("✅ 开始分析消息已发送")
            else:
                logger.warning(f"⚠️ 用户队列不存在: {message.user_id}")

            # 构建分析问题
            question = f"""请分析这张界面截图中的UI元素。用户需求：{message.user_requirement}

{self.system_prompt}

请严格按照上述要求分析图片中的所有UI元素，并以JSON格式输出结果。"""

            logger.debug(f"📝 构建分析问题完成，长度: {len(question)} 字符")

            # 创建多模态消息
            logger.info("🔧 创建多模态消息...")
            multimodal_message = create_multimodal_message(
                question, [message.image_path]
            )
            logger.success("✅ 多模态消息创建完成")

            # 获取模型客户端并创建智能体
            model_client = get_model_client()
            ui_agent = AssistantAgent(
                "ui_analyst",
                model_client=model_client,
                system_message=self.system_prompt,
                model_client_stream=True,
            )

            # 使用流式输出进行分析
            logger.info("🚀 开始流式分析处理...")
            ui_analysis_result = ""
            chunk_count = 0
            total_content_length = 0

            async for item in ui_agent.run_stream(task=multimodal_message):
                if isinstance(item, ModelClientStreamingChunkEvent):
                    # 流式输出内容
                    chunk_content = item.content
                    ui_analysis_result += chunk_content
                    chunk_count += 1
                    total_content_length += len(chunk_content)

                    logger.debug(
                        f"📦 接收流式块 #{chunk_count}: {len(chunk_content)} 字符"
                    )

                    # 发送流式内容到队列
                    if message.user_id in message_queues:
                        await message_queues[message.user_id].put(
                            {
                                "type": "stream_chunk",
                                "agent": "UI分析智能体",
                                "content": chunk_content,
                            }
                        )
                        logger.trace(f"📤 流式块已发送到队列: {message.user_id}")
                    else:
                        logger.warning(
                            f"⚠️ 用户队列不存在，无法发送流式块: {message.user_id}"
                        )

                elif isinstance(item, TextMessage):
                    # 完整输出
                    ui_analysis_result = item.content
                    logger.info(f"📄 接收完整文本消息: {len(ui_analysis_result)} 字符")

                    # 发送完整结果
                    if message.user_id in message_queues:
                        await message_queues[message.user_id].put(
                            {
                                "type": "agent_complete",
                                "agent": "UI分析智能体",
                                "step": "UI元素分析完成",
                                "content": ui_analysis_result,
                            }
                        )
                        logger.debug("✅ 完整结果已发送到队列")

                elif isinstance(item, TaskResult):
                    # 任务结果
                    if item.messages:
                        ui_analysis_result = item.messages[-1].content
                        logger.info(f"📋 接收任务结果: {len(ui_analysis_result)} 字符")
                    else:
                        logger.warning("⚠️ 任务结果中没有消息内容")

            logger.success(
                f"✅ 流式分析完成 - 总块数: {chunk_count}, 总长度: {total_content_length} 字符"
            )

            # 发送结果到消息收集器
            logger.info("📤 发送分析结果到消息收集器...")
            task_result = TaskResult(
                user_id=message.user_id,
                agent_name="UI分析智能体",
                content=ui_analysis_result,
                step="UI元素分析完成",
            )

            await self.publish_message(
                message=task_result,
                topic_id=TopicId(type=TASK_RESULTS_TOPIC, source=self.id.key),
            )
            logger.debug(f"✅ 任务结果已发布到Topic: {TASK_RESULTS_TOPIC}")

            # 发送给交互分析智能体
            logger.info("🔄 发送结果给交互分析智能体...")
            interaction_request = InteractionAnalysisRequest(
                user_id=message.user_id,
                ui_elements=ui_analysis_result,
                user_requirement=message.user_requirement,
            )

            await self.publish_message(
                message=interaction_request,
                topic_id=TopicId(type=INTERACTION_ANALYSIS_TOPIC, source=self.id.key),
            )
            logger.debug(f"✅ 交互分析请求已发布到Topic: {INTERACTION_ANALYSIS_TOPIC}")

            # 计算处理时间
            processing_time = time.time() - start_time
            logger.success(
                f"🎉 UI分析完成 - 用户: {message.user_id}, 耗时: {processing_time:.2f}秒"
            )

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                f"❌ UI分析失败 - 用户: {message.user_id}, 耗时: {processing_time:.2f}秒"
            )
            logger.error(f"🔥 错误详情: {str(e)}")
            logger.error(f"📍 错误堆栈: {traceback.format_exc()}")

            # 发送错误消息到队列
            if message.user_id in message_queues:
                logger.debug("📤 发送错误消息到用户队列...")
                await message_queues[message.user_id].put(
                    {
                        "type": "agent_error",
                        "agent": "UI分析智能体",
                        "step": "UI元素分析失败",
                        "content": f"分析失败: {str(e)}",
                    }
                )
                logger.debug("✅ 错误消息已发送到队列")

            # 发送错误结果到消息收集器
            logger.debug("📤 发送错误结果到消息收集器...")
            error_result = TaskResult(
                user_id=message.user_id,
                agent_name="UI分析智能体",
                content=f"分析失败: {str(e)}",
                step="UI元素分析失败",
            )

            await self.publish_message(
                message=error_result,
                topic_id=TopicId(type=TASK_RESULTS_TOPIC, source=self.id.key),
            )
            logger.debug("✅ 错误结果已发布到消息收集器")


# ==================== 交互分析智能体 ====================


@type_subscription(topic_type=INTERACTION_ANALYSIS_TOPIC)
class InteractionAnalysisAgent(RoutedAgent):

    def __init__(self, description: str):
        super().__init__(description=description)
        logger.info(f"🔄 交互分析智能体初始化: {description}")

        self.system_prompt = """你是用户交互流程分析师，专门分析用户在界面上的操作流程，为自动化测试设计提供用户行为路径。

## 核心职责

### 1. 用户行为路径分析
- **主要流程**: 用户完成核心任务的标准路径
- **替代流程**: 用户可能采用的其他操作方式
- **异常流程**: 错误操作、网络异常等情况的处理
- **回退流程**: 用户撤销、返回等逆向操作

### 2. 交互节点识别
- **入口点**: 用户开始操作的位置
- **决策点**: 用户需要选择的关键节点
- **验证点**: 系统反馈和状态确认
- **出口点**: 流程完成或退出的位置

### 3. 操作序列设计
- **前置条件**: 执行操作前的必要状态
- **操作步骤**: 具体的用户动作序列
- **后置验证**: 操作完成后的状态检查
- **错误处理**: 异常情况的应对措施

### 4. 用户体验考量
- **操作便利性**: 符合用户习惯的操作方式
- **认知负荷**: 避免复杂的操作序列
- **反馈及时性**: 操作结果的即时反馈
- **容错性**: 允许用户纠错的机制

## 输出格式要求

请按照以下结构化格式输出交互流程：

```json
{
  "primary_flows": [
    {
      "flow_name": "用户登录流程",
      "description": "用户通过用户名密码登录系统",
      "steps": [
        {
          "step_id": 1,
          "action": "点击登录按钮",
          "target_element": "页面右上角蓝色登录按钮",
          "expected_result": "显示登录表单",
          "precondition": "用户未登录状态"
        }
      ],
      "success_criteria": "成功登录并跳转到主页",
      "error_scenarios": ["用户名密码错误", "网络连接失败"]
    }
  ],
  "alternative_flows": [],
  "interaction_patterns": {
    "navigation_style": "顶部导航栏",
    "input_validation": "实时验证",
    "feedback_mechanism": "弹窗提示",
    "error_handling": "内联错误信息"
  }
}
```"""

    @message_handler
    async def analyze_interaction(
        self, message: InteractionAnalysisRequest, ctx: MessageContext
    ) -> None:
        start_time = time.time()
        logger.info(f"🔄 开始交互流程分析 - 用户ID: {message.user_id}")
        logger.info(f"📝 用户需求: {message.user_requirement[:100]}...")
        logger.debug(f"🔧 消息上下文: {ctx}")

        try:
            # 发送开始分析的消息
            if message.user_id in message_queues:
                logger.debug(f"📤 发送开始分析消息到队列: {message.user_id}")
                await message_queues[message.user_id].put(
                    {
                        "type": "agent_start",
                        "agent": "交互分析智能体",
                        "step": "开始分析用户交互流程",
                        "content": "正在基于UI元素设计用户交互流程...",
                    }
                )
                logger.debug("✅ 开始分析消息已发送")

            # 获取模型客户端并创建智能体
            model_client = get_model_client()
            interaction_agent = AssistantAgent(
                "interaction_analyst",
                model_client=model_client,
                system_message=self.system_prompt,
                model_client_stream=True,
            )

            question = f"""基于以下UI元素分析结果，请分析用户交互流程。

UI元素分析结果：
{message.ui_elements}

用户需求：{message.user_requirement}

请根据UI元素，设计完整的用户交互流程，并严格按照JSON格式输出。"""

            logger.debug(f"📝 构建分析问题完成，长度: {len(question)} 字符")

            # 使用流式输出
            logger.info("🚀 开始流式分析处理...")
            interaction_result = ""
            chunk_count = 0

            async for item in interaction_agent.run_stream(task=question):
                if isinstance(item, ModelClientStreamingChunkEvent):
                    chunk_content = item.content
                    interaction_result += chunk_content
                    chunk_count += 1

                    logger.debug(
                        f"📦 接收流式块 #{chunk_count}: {len(chunk_content)} 字符"
                    )

                    # 发送流式内容到队列
                    if message.user_id in message_queues:
                        await message_queues[message.user_id].put(
                            {
                                "type": "stream_chunk",
                                "agent": "交互分析智能体",
                                "content": chunk_content,
                            }
                        )

                elif isinstance(item, TextMessage):
                    interaction_result = item.content
                    logger.info(f"📄 接收完整文本消息: {len(interaction_result)} 字符")

                elif isinstance(item, TaskResult):
                    if item.messages:
                        interaction_result = item.messages[-1].content
                        logger.info(f"📋 接收任务结果: {len(interaction_result)} 字符")

            logger.success(
                f"✅ 交互分析完成 - 总块数: {chunk_count}, 总长度: {len(interaction_result)} 字符"
            )

            # 发送完成消息
            if message.user_id in message_queues:
                await message_queues[message.user_id].put(
                    {
                        "type": "agent_complete",
                        "agent": "交互分析智能体",
                        "step": "交互流程分析完成",
                        "content": interaction_result,
                    }
                )

            # 发送结果到消息收集器
            task_result = TaskResult(
                user_id=message.user_id,
                agent_name="交互分析智能体",
                content=interaction_result,
                step="交互流程分析完成",
            )

            await self.publish_message(
                message=task_result,
                topic_id=TopicId(type=TASK_RESULTS_TOPIC, source=self.id.key),
            )

            # 发送给Midscene生成智能体
            midscene_request = MidsceneGenerationRequest(
                user_id=message.user_id,
                ui_analysis=message.ui_elements,
                interaction_analysis=interaction_result,
                user_requirement=message.user_requirement,
            )

            await self.publish_message(
                message=midscene_request,
                topic_id=TopicId(type=MIDSCENE_GENERATION_TOPIC, source=self.id.key),
            )

            processing_time = time.time() - start_time
            logger.success(
                f"🎉 交互分析完成 - 用户: {message.user_id}, 耗时: {processing_time:.2f}秒"
            )

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                f"❌ 交互分析失败 - 用户: {message.user_id}, 耗时: {processing_time:.2f}秒"
            )
            logger.error(f"🔥 错误详情: {str(e)}")
            logger.error(f"📍 错误堆栈: {traceback.format_exc()}")

            # 发送错误消息
            if message.user_id in message_queues:
                await message_queues[message.user_id].put(
                    {
                        "type": "agent_error",
                        "agent": "交互分析智能体",
                        "step": "交互流程分析失败",
                        "content": f"分析失败: {str(e)}",
                    }
                )

            # 发送错误结果到消息收集器
            error_result = TaskResult(
                user_id=message.user_id,
                agent_name="交互分析智能体",
                content=f"分析失败: {str(e)}",
                step="交互流程分析失败",
            )

            await self.publish_message(
                message=error_result,
                topic_id=TopicId(type=TASK_RESULTS_TOPIC, source=self.id.key),
            )


# ==================== Midscene生成智能体 ====================


@type_subscription(topic_type=MIDSCENE_GENERATION_TOPIC)
class MidsceneGenerationAgent(RoutedAgent):

    def __init__(self, description: str):
        super().__init__(description=description)
        logger.info(f"🎯 Midscene生成智能体初始化: {description}")

        self.system_prompt = """你是MidScene.js自动化测试专家，专门基于UI专家和交互分析师的分析结果，设计符合MidScene.js脚本风格的测试用例。

## MidScene.js 核心知识（基于官方文档）

### 支持的动作类型

#### 1. 复合操作
- **ai**: 自然语言描述的复合操作，如 "type 'computer' in search box, hit Enter"
- **aiAction**: ai的完整形式，功能相同

#### 2. 即时操作（精确控制时使用）
- **aiTap**: 点击操作，用于按钮、链接、菜单项
- **aiInput**: 文本输入，格式为 aiInput: "输入内容", locate: "元素描述"
- **aiHover**: 鼠标悬停，用于下拉菜单触发
- **aiScroll**: 滚动操作，支持方向和距离
- **aiKeyboardPress**: 键盘操作，如Enter、Tab等

#### 3. 数据提取操作
- **aiQuery**: 通用查询，支持复杂数据结构，使用多行格式
- **aiBoolean**: 布尔值查询
- **aiNumber**: 数值查询
- **aiString**: 字符串查询

#### 4. 验证和等待
- **aiAssert**: 断言验证
- **aiWaitFor**: 等待条件满足
- **sleep**: 固定等待（毫秒）

### MidScene.js 提示词最佳实践（基于官方指南）

#### 1. 提供详细描述和示例
- ✅ 优秀描述: "找到搜索框（搜索框的上方应该有区域切换按钮，如'国内'，'国际'），输入'耳机'，敲回车"
- ❌ 简单描述: "搜'耳机'"
- ✅ 详细断言: "界面上有个'外卖服务'的板块，并且标识着'正常'"
- ❌ 模糊断言: "外卖服务正在正常运行"

#### 2. 精确的视觉定位描述
- ✅ 详细位置: "页面右上角的'Add'按钮，它是一个带有'+'图标的按钮，位于'range'下拉菜单的右侧"
- ❌ 模糊位置: "Add按钮"
- 包含视觉特征: 颜色、形状、图标、相对位置
- 提供上下文参考: 周围元素作为定位锚点

#### 3. 单一职责原则（一个指令只做一件事）
- ✅ 分解操作:
  - "点击登录按钮"
  - "在表单中[邮箱]输入'test@test.com'"
  - "在表单中[密码]输入'test'"
  - "点击注册按钮"
- ❌ 复合操作: "点击登录按钮，然后点击注册按钮，在表单中输入邮箱和密码，然后点击注册按钮"

#### 4. API选择策略
- **确定交互类型时优先使用即时操作**: aiTap('登录按钮') > ai('点击登录按钮')
- **复杂流程使用ai**: 适合多步骤操作规划
- **数据提取使用aiQuery**: 避免使用aiAssert进行数据提取

#### 5. 基于视觉而非DOM属性
- ✅ 视觉描述: "标题是蓝色的"
- ❌ DOM属性: "标题有个`test-id-size`属性"
- ✅ 界面状态: "页面显示登录成功消息"
- ❌ 浏览器状态: "异步请求已经结束了"

#### 6. 提供选项而非精确数值
- ✅ 颜色选项: "文本的颜色，返回：蓝色/红色/黄色/绿色/白色/黑色/其他"
- ❌ 精确数值: "文本颜色的十六进制值"

#### 7. 交叉验证和断言策略
- 操作后检查结果: 每个关键操作后添加验证步骤
- 使用aiAssert验证状态: 确认操作是否成功
- 避免依赖不可见状态: 所有验证基于界面可见内容

## 重点任务

你将接收UI专家和交互分析师的分析结果，需要：

1. **整合分析结果**: 结合UI元素识别和交互流程分析
2. **设计测试场景**: 基于用户行为路径设计完整测试用例
3. **应用提示词最佳实践**:
   - 提供详细的视觉描述和上下文信息
   - 遵循单一职责原则，每个步骤只做一件事
   - 优先使用即时操作API（aiTap、aiInput等）
   - 基于视觉特征而非DOM属性进行描述
4. **详细视觉描述**: 利用UI专家提供的元素特征进行精确定位
5. **完整验证流程**: 包含操作前置条件、执行步骤和结果验证
6. **交叉验证策略**: 为每个关键操作添加验证步骤

## 输出格式要求

请输出结构化的测试场景，格式如下：

```json
{
  "test_scenarios": [
    {
      "scenario_name": "用户登录测试",
      "description": "验证用户通过用户名密码登录系统的完整流程",
      "priority": "high",
      "estimated_duration": "30秒",
      "preconditions": ["用户未登录", "页面已加载完成"],
      "test_steps": [
        {
          "step_id": 1,
          "action_type": "aiTap",
          "action_description": "页面右上角的蓝色'登录'按钮，它是一个圆角矩形按钮，白色文字，位于搜索框右侧约20像素处",
          "visual_target": "蓝色背景的登录按钮，具有圆角设计，按钮上显示白色'登录'文字，位于页面顶部导航区域的右侧",
          "expected_result": "显示登录表单弹窗或跳转到登录页面",
          "validation_step": "检查是否出现用户名和密码输入框"
        }
      ],
      "validation_points": [
        "登录按钮可点击",
        "表单正确显示",
        "输入验证正常",
        "登录成功跳转"
      ]
    }
  ]
}
```

## 设计原则

1. **基于真实分析**: 严格基于UI专家和交互分析师的输出设计测试
2. **MidScene.js风格**: 使用自然语言描述，符合MidScene.js的AI驱动特性
3. **视觉定位优先**: 充分利用UI专家提供的详细视觉特征
4. **流程完整性**: 确保测试场景覆盖完整的用户操作路径
5. **可执行性**: 每个步骤都能直接转换为MidScene.js YAML脚本
6. **提示词工程最佳实践**:
   - 详细描述胜过简单描述
   - 提供视觉上下文和参考点
   - 单一职责，每个步骤只做一件事
   - 基于界面可见内容而非技术实现
   - 为关键操作添加验证步骤
7. **稳定性优先**: 设计能够在多次运行中获得稳定响应的测试步骤
8. **错误处理**: 考虑异常情况和用户可能的错误操作
9. **多语言支持**: 支持中英文混合的界面描述"""

    @message_handler
    async def generate_midscene_test(
        self, message: MidsceneGenerationRequest, ctx: MessageContext
    ) -> None:
        start_time = time.time()
        logger.info(f"🎯 开始生成Midscene测试脚本 - 用户ID: {message.user_id}")
        logger.info(f"📝 用户需求: {message.user_requirement[:100]}...")
        logger.debug(f"🔧 消息上下文: {ctx}")

        try:
            # 发送开始分析的消息
            if message.user_id in message_queues:
                await message_queues[message.user_id].put(
                    {
                        "type": "agent_start",
                        "agent": "Midscene用例生成智能体",
                        "step": "开始生成Midscene测试脚本",
                        "content": "正在整合分析结果，生成Midscene.js测试脚本...",
                    }
                )

            # 获取模型客户端并创建智能体
            model_client = get_model_client()
            midscene_agent = AssistantAgent(
                "midscene_generator",
                model_client=model_client,
                system_message=self.system_prompt,
                model_client_stream=True,
            )

            question = f"""基于以下分析结果，生成符合MidScene.js规范的测试脚本。

UI分析结果：
{message.ui_analysis}

交互流程分析结果：
{message.interaction_analysis}

用户需求：{message.user_requirement}

请整合上述分析结果，设计完整的MidScene.js测试场景，严格按照JSON格式输出。"""

            # 使用流式输出
            logger.info("🚀 开始流式生成处理...")
            midscene_result = ""
            chunk_count = 0

            async for item in midscene_agent.run_stream(task=question):
                if isinstance(item, ModelClientStreamingChunkEvent):
                    chunk_content = item.content
                    midscene_result += chunk_content
                    chunk_count += 1

                    # 发送流式内容到队列
                    if message.user_id in message_queues:
                        await message_queues[message.user_id].put(
                            {
                                "type": "stream_chunk",
                                "agent": "Midscene用例生成智能体",
                                "content": chunk_content,
                            }
                        )

                elif isinstance(item, TextMessage):
                    midscene_result = item.content

                elif isinstance(item, TaskResult):
                    if item.messages:
                        midscene_result = item.messages[-1].content

            logger.success(
                f"✅ Midscene生成完成 - 总块数: {chunk_count}, 总长度: {len(midscene_result)} 字符"
            )

            # 发送完成消息
            if message.user_id in message_queues:
                await message_queues[message.user_id].put(
                    {
                        "type": "agent_complete",
                        "agent": "Midscene用例生成智能体",
                        "step": "Midscene测试脚本生成完成",
                        "content": midscene_result,
                    }
                )

            # 发送结果到消息收集器
            task_result = TaskResult(
                user_id=message.user_id,
                agent_name="Midscene用例生成智能体",
                content=midscene_result,
                step="Midscene测试脚本生成完成",
            )

            await self.publish_message(
                message=task_result,
                topic_id=TopicId(type=TASK_RESULTS_TOPIC, source=self.id.key),
            )

            # 发送给脚本生成智能体
            script_request = ScriptGenerationRequest(
                user_id=message.user_id,
                midscene_json=midscene_result,
                user_requirement=message.user_requirement,
            )

            await self.publish_message(
                message=script_request,
                topic_id=TopicId(type=SCRIPT_GENERATION_TOPIC, source=self.id.key),
            )

            processing_time = time.time() - start_time
            logger.success(
                f"🎉 Midscene生成完成 - 用户: {message.user_id}, 耗时: {processing_time:.2f}秒"
            )

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                f"❌ Midscene生成失败 - 用户: {message.user_id}, 耗时: {processing_time:.2f}秒"
            )
            logger.error(f"🔥 错误详情: {str(e)}")
            logger.error(f"📍 错误堆栈: {traceback.format_exc()}")

            # 发送错误消息
            if message.user_id in message_queues:
                await message_queues[message.user_id].put(
                    {
                        "type": "agent_error",
                        "agent": "Midscene用例生成智能体",
                        "step": "Midscene测试脚本生成失败",
                        "content": f"生成失败: {str(e)}",
                    }
                )

            # 发送错误结果到消息收集器
            error_result = TaskResult(
                user_id=message.user_id,
                agent_name="Midscene用例生成智能体",
                content=f"生成失败: {str(e)}",
                step="Midscene测试脚本生成失败",
            )

            await self.publish_message(
                message=error_result,
                topic_id=TopicId(type=TASK_RESULTS_TOPIC, source=self.id.key),
            )


# ==================== 脚本生成智能体 ====================


@type_subscription(topic_type=SCRIPT_GENERATION_TOPIC)
class ScriptGenerationAgent(RoutedAgent):

    def __init__(self, description: str):
        super().__init__(description=description)
        logger.info(f"📜 脚本生成智能体初始化: {description}")

        self.system_prompt = """你是专业的测试脚本生成专家，专门将Midscene JSON测试用例转换为可执行的YAML脚本和Playwright脚本。

## 核心职责

### 1. JSON解析和提取
- 解析Midscene JSON格式的测试用例
- 提取测试场景、步骤和验证点
- 识别操作类型和目标元素

### 2. YAML脚本生成
- 转换为标准的Midscene YAML格式
- 保持操作的语义和逻辑
- 确保脚本的可读性和可维护性

### 3. Playwright脚本生成
- 基于提供的示例模板生成Playwright测试脚本
- 使用Midscene的AI操作API
- 遵循TypeScript语法规范

## 输出格式要求

请严格按照以下JSON格式输出两种脚本：

```json
{
  "yaml_script": "完整的YAML格式脚本内容",
  "playwright_script": "完整的TypeScript格式Playwright脚本内容",
  "script_info": {
    "test_name": "测试名称",
    "description": "测试描述",
    "estimated_duration": "预估执行时间",
    "steps_count": 步骤数量
  }
}
```

## 生成规则

### YAML脚本规则
1. 使用标准的Midscene YAML语法
2. 每个操作独立成行
3. 保持缩进和格式规范
4. 包含必要的等待和验证步骤

### Playwright脚本规则
1. **固定头部导入**: 所有Playwright脚本必须以以下导入语句开头：
   import { expect } from "@playwright/test";
   import { test } from "./fixture";
2. 导入必要的fixture和类型定义
3. 使用beforeEach设置初始状态
4. 每个测试步骤使用对应的AI操作API
5. 包含适当的断言和验证
6. 遵循TypeScript语法规范
7. 使用提供的示例作为模板参考

## 质量标准
- **准确性**: 忠实转换原始JSON中的操作逻辑
- **可执行性**: 生成的脚本可以直接运行
- **可读性**: 代码结构清晰，注释适当
- **完整性**: 包含所有必要的步骤和验证"""

    @message_handler
    async def generate_scripts(
        self, message: ScriptGenerationRequest, ctx: MessageContext
    ) -> None:
        start_time = time.time()
        logger.info(f"📜 开始生成脚本 - 用户ID: {message.user_id}")
        logger.debug(f"🔧 消息上下文: {ctx}")

        try:
            # 发送开始消息
            if message.user_id in message_queues:
                await message_queues[message.user_id].put(
                    {
                        "type": "agent_start",
                        "agent": "脚本生成智能体",
                        "step": "开始生成YAML和Playwright脚本",
                        "content": "正在解析Midscene JSON并生成可执行脚本...",
                    }
                )

            # 获取模型客户端并创建智能体
            model_client = get_model_client()
            script_agent = AssistantAgent(
                "script_generator",
                model_client=model_client,
                system_message=self.system_prompt,
                model_client_stream=True,
            )

            question = f"""请将以下Midscene JSON测试用例转换为YAML脚本和Playwright脚本。

Midscene JSON测试用例：
{message.midscene_json}

用户需求：{message.user_requirement}

{self.system_prompt}

请严格按照JSON格式输出两种脚本。"""

            # 使用流式输出
            logger.info("🚀 开始流式生成处理...")
            script_result = ""
            chunk_count = 0

            async for item in script_agent.run_stream(task=question):
                if isinstance(item, ModelClientStreamingChunkEvent):
                    chunk_content = item.content
                    script_result += chunk_content
                    chunk_count += 1

                    # 发送流式内容到队列
                    if message.user_id in message_queues:
                        await message_queues[message.user_id].put(
                            {
                                "type": "stream_chunk",
                                "agent": "脚本生成智能体",
                                "content": chunk_content,
                            }
                        )

                elif isinstance(item, TextMessage):
                    script_result = item.content

                elif isinstance(item, TaskResult):
                    if item.messages:
                        script_result = item.messages[-1].content

            logger.success(
                f"✅ 脚本生成完成 - 总块数: {chunk_count}, 总长度: {len(script_result)} 字符"
            )

            # 发送完成消息
            if message.user_id in message_queues:
                await message_queues[message.user_id].put(
                    {
                        "type": "agent_complete",
                        "agent": "脚本生成智能体",
                        "step": "YAML和Playwright脚本生成完成",
                        "content": script_result,
                    }
                )

            # 尝试解析脚本结果并发送到前端
            try:
                # 提取JSON部分
                import re

                json_match = re.search(r"\{.*\}", script_result, re.DOTALL)
                if json_match:
                    script_data = json.loads(json_match.group())

                    # 发送脚本生成结果
                    if message.user_id in message_queues:
                        await message_queues[message.user_id].put(
                            {
                                "type": "script_generated",
                                "content": json.dumps(script_data, ensure_ascii=False),
                            }
                        )
                        logger.info("📜 脚本数据已发送到前端")
                else:
                    logger.warning("⚠️ 无法从结果中提取JSON格式的脚本数据")
            except Exception as parse_error:
                logger.error(f"❌ 解析脚本结果失败: {parse_error}")

            # 发送系统完成消息
            if message.user_id in message_queues:
                await message_queues[message.user_id].put(
                    {
                        "type": "system_complete",
                        "message": "所有智能体分析完成",
                        "content": "Midscene测试脚本已生成完成",
                    }
                )

            # 发送结果到消息收集器
            task_result = TaskResult(
                user_id=message.user_id,
                agent_name="脚本生成智能体",
                content=script_result,
                step="YAML和Playwright脚本生成完成",
            )

            await self.publish_message(
                message=task_result,
                topic_id=TopicId(type=TASK_RESULTS_TOPIC, source=self.id.key),
            )

            processing_time = time.time() - start_time
            logger.success(
                f"🎉 脚本生成完成 - 用户: {message.user_id}, 耗时: {processing_time:.2f}秒"
            )

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(
                f"❌ 脚本生成失败 - 用户: {message.user_id}, 耗时: {processing_time:.2f}秒"
            )
            logger.error(f"🔥 错误详情: {str(e)}")
            logger.error(f"📍 错误堆栈: {traceback.format_exc()}")

            # 发送错误消息
            if message.user_id in message_queues:
                await message_queues[message.user_id].put(
                    {
                        "type": "agent_error",
                        "agent": "脚本生成智能体",
                        "step": "脚本生成失败",
                        "content": f"生成失败: {str(e)}",
                    }
                )

                # 发送系统错误消息
                await message_queues[message.user_id].put(
                    {
                        "type": "system_error",
                        "message": "系统处理失败",
                        "content": f"脚本生成失败: {str(e)}",
                    }
                )

            # 发送错误结果到消息收集器
            error_result = TaskResult(
                user_id=message.user_id,
                agent_name="脚本生成智能体",
                content=f"生成失败: {str(e)}",
                step="脚本生成失败",
            )

            await self.publish_message(
                message=error_result,
                topic_id=TopicId(type=TASK_RESULTS_TOPIC, source=self.id.key),
            )


# ==================== 协作分析函数 ====================


async def collaborative_analysis(
    user_id: str, image_paths: List[str], user_requirement: str
) -> str:
    """
    启动四智能体协作分析
    完全参照 examples/midscene_agents.py 的实现
    """
    logger.info(f"🚀 启动四智能体协作分析 - 用户ID: {user_id}")
    logger.info(f"📷 图片数量: {len(image_paths)}")
    logger.info(f"📝 用户需求: {user_requirement[:100]}...")

    try:
        # 创建运行时
        runtime = SingleThreadedAgentRuntime()
        runtime.start()
        logger.info("✅ 运行时启动成功")

        # 注册所有智能体
        logger.info("🔧 注册智能体...")

        await UIAnalysisAgent.register(
            runtime,
            UI_ANALYSIS_TOPIC,
            lambda: UIAnalysisAgent(description="UI元素分析智能体"),
        )
        logger.debug("✅ UI分析智能体注册完成")

        await InteractionAnalysisAgent.register(
            runtime,
            INTERACTION_ANALYSIS_TOPIC,
            lambda: InteractionAnalysisAgent(description="交互分析智能体"),
        )
        logger.debug("✅ 交互分析智能体注册完成")

        await MidsceneGenerationAgent.register(
            runtime,
            MIDSCENE_GENERATION_TOPIC,
            lambda: MidsceneGenerationAgent(description="Midscene用例生成智能体"),
        )
        logger.debug("✅ Midscene生成智能体注册完成")

        await ScriptGenerationAgent.register(
            runtime,
            SCRIPT_GENERATION_TOPIC,
            lambda: ScriptGenerationAgent(description="脚本生成智能体"),
        )
        logger.debug("✅ 脚本生成智能体注册完成")

        logger.success("🎉 所有智能体注册完成")

        # 发送系统开始消息
        if user_id in message_queues:
            await message_queues[user_id].put(
                {
                    "type": "system_start",
                    "message": "四智能体协作分析开始",
                    "content": "正在启动UI分析、交互分析、Midscene生成和脚本生成智能体...",
                }
            )

        # 为每张图片启动UI分析
        logger.info("🔍 开始UI分析阶段...")
        for i, image_path in enumerate(image_paths):
            logger.info(
                f"📷 处理图片 {i+1}/{len(image_paths)}: {Path(image_path).name}"
            )

            ui_request = UIAnalysisRequest(
                user_id=user_id,
                image_path=image_path,
                user_requirement=user_requirement,
            )

            await runtime.publish_message(
                ui_request, topic_id=DefaultTopicId(type=UI_ANALYSIS_TOPIC)
            )
            logger.debug(f"✅ UI分析请求已发布 - 图片: {Path(image_path).name}")

        logger.info("⏳ 等待所有智能体完成处理...")

        # 等待一段时间让所有智能体完成处理
        # 这里可以根据实际需要调整等待时间
        await asyncio.sleep(2)

        logger.success(f"🎉 四智能体协作分析启动完成 - 用户: {user_id}")
        return user_id

    except Exception as e:
        logger.error(f"❌ 协作分析启动失败 - 用户: {user_id}")
        logger.error(f"🔥 错误详情: {str(e)}")
        logger.error(f"📍 错误堆栈: {traceback.format_exc()}")

        # 发送系统错误消息
        if user_id in message_queues:
            await message_queues[user_id].put(
                {
                    "type": "system_error",
                    "message": "系统启动失败",
                    "content": f"协作分析启动失败: {str(e)}",
                }
            )

        raise


# ==================== 服务类 ====================


class MidsceneService:
    """Midscene 智能体服务"""

    def __init__(self):
        self.results_dir = Path("uploads/midscene_results")
        self.results_dir.mkdir(parents=True, exist_ok=True)

    async def start_analysis(
        self, user_id: str, image_paths: List[str], user_requirement: str
    ) -> str:
        """启动 Midscene 分析流程"""
        logger.info(f"🚀 启动 Midscene 分析流程 - 用户ID: {user_id}")

        try:
            # 创建用户队列
            get_queue(user_id)

            # 启动协作分析（在后台运行）
            asyncio.create_task(
                collaborative_analysis(user_id, image_paths, user_requirement)
            )

            return user_id

        except Exception as e:
            logger.error(f"❌ 启动分析失败: {e}")
            raise

    def get_stream_response(self, user_id: str):
        """获取流式响应"""
        return message_generator(user_id)

    def cleanup_session(self, user_id: str):
        """清理会话"""
        if user_id in message_queues:
            del message_queues[user_id]
        logger.info(f"🧹 会话资源已清理: {user_id}")


# 创建服务实例
midscene_service = MidsceneService()
