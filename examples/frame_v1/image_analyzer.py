"""
图片专门分析智能体
基于AutoGen团队协作机制，专门用于深度分析UI界面图片
支持MultiModalMessage和团队协作分析
"""

import base64
import json
import uuid
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional

import requests
from app.core.agents.base import BaseAgent
from app.core.messages.web import (
    AnalysisType,
    PageAnalysis,
    UIElement,
    WebMultimodalAnalysisRequest,
    WebMultimodalAnalysisResponse,
)
from app.core.types import AGENT_NAMES, AgentTypes, MessageRegion, TopicTypes
from autogen_agentchat.agents import (
    AssistantAgent,
    MessageFilterAgent,
    MessageFilterConfig,
    PerSourceFilter,
    UserProxyAgent,
)
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import (
    ModelClientStreamingChunkEvent,
    MultiModalMessage,
    TextMessage,
)
from autogen_agentchat.teams import DiGraphBuilder, GraphFlow, RoundRobinGroupChat
from autogen_core import Image as AGImage
from autogen_core import MessageContext, TopicId, message_handler, type_subscription
from loguru import logger
from PIL import Image


@type_subscription(topic_type=TopicTypes.IMAGE_ANALYZER.value)
class ImageAnalyzerAgent(BaseAgent):
    """图片专门分析智能体，基于AutoGen团队协作"""

    def __init__(
        self,
        model_client_instance=None,
        enable_user_feedback: bool = False,
        collector=None,
        **kwargs,
    ):
        """初始化图片分析智能体"""
        super().__init__(
            agent_id=AgentTypes.IMAGE_ANALYZER.value,
            agent_name=AGENT_NAMES[AgentTypes.IMAGE_ANALYZER.value],
            model_client_instance=model_client_instance,
            **kwargs,
        )

        self.metrics = None
        self.enable_user_feedback = enable_user_feedback
        self._analysis_team = None
        self.collector = collector

        logger.info(f"图片专门分析智能体初始化完成，用户反馈: {enable_user_feedback}")

    @classmethod
    def create_ui_expert_agent(cls, **kwargs) -> AssistantAgent:
        """创建UI专家智能体"""
        from app.agents.factory import agent_factory

        return agent_factory.create_assistant_agent(
            name=AgentTypes.UI_EXPERT.value,
            system_message=cls._build_ui_expert_prompt(),
            model_client_type="uitars",
            **kwargs,
        )

    @classmethod
    def create_interaction_analyst_agent(cls, **kwargs) -> AssistantAgent:
        """创建交互分析师智能体"""
        from app.agents.factory import agent_factory

        return agent_factory.create_assistant_agent(
            name=AgentTypes.INTERACTION_ANALYST.value,
            system_message=cls._build_interaction_analyst_prompt(),
            model_client_type="uitars",
            **kwargs,
        )

    @classmethod
    def create_quality_reviewer_agent(cls, **kwargs) -> AssistantAgent:
        """创建质量审查员智能体"""
        from app.agents.factory import agent_factory

        return agent_factory.create_assistant_agent(
            name=AgentTypes.QUALITY_REVIEWER.value,
            system_message=cls._build_quality_reviewer_prompt(),
            model_client_type="deepseek",
            **kwargs,
        )

    @classmethod
    def create_midscene_expert_agent(cls, **kwargs) -> AssistantAgent:
        """创建MidScene.js专家智能体"""
        from app.agents.factory import agent_factory

        return agent_factory.create_assistant_agent(
            name=AgentTypes.MIDSCENE_EXPERT.value,
            system_message=cls._build_midscene_expert_prompt(),
            model_client_type="deepseek",
            **kwargs,
        )

    @message_handler
    async def handle_message(
        self, message: WebMultimodalAnalysisRequest, ctx: MessageContext
    ) -> None:
        """处理图片分析请求"""
        try:
            monitor_id = self.start_performance_monitoring()
            analysis_id = str(uuid.uuid4())

            # 创建分析团队
            team = await self._create_image_analysis_team()

            # 准备多模态消息
            multimodal_message = await self._prepare_multimodal_message(message)

            # 运行团队分析
            team_results = await self._run_team_analysis(team, multimodal_message)
            self.metrics = self.end_performance_monitoring(monitor_id)
            # 整合分析结果
            analysis_result = await self._integrate_analysis_results(
                team_results, analysis_id, message
            )

            await self.send_response(
                "✅ 图片分析完成",
                is_final=True,
                result={
                    "analysis_result": analysis_result.model_dump(),
                    "team_collaboration": True,
                    "user_feedback_enabled": self.enable_user_feedback,
                    "metrics": self.metrics,
                },
            )

            # 根据用户选择的格式发送到相应的智能体
            await self._route_to_script_generators(
                analysis_result, message.generate_formats
            )

        except Exception as e:
            await self.handle_exception("handle_message", e)

    async def _route_to_script_generators(
        self,
        analysis_result: WebMultimodalAnalysisResponse,
        generate_formats: List[str],
    ) -> None:
        """根据用户选择的格式路由到相应的脚本生成智能体"""
        try:
            await self.send_response("🔀 根据选择的格式路由到脚本生成智能体...\n\n")

            # 支持的格式映射
            format_topic_mapping = {
                "yaml": TopicTypes.YAML_GENERATOR.value,
                "playwright": TopicTypes.PLAYWRIGHT_GENERATOR.value,
            }

            # 为每种选择的格式发送消息
            for format_type in generate_formats:
                if format_type in format_topic_mapping:
                    topic_type = format_topic_mapping[format_type]

                    try:
                        await self.publish_message(
                            analysis_result,
                            topic_id=TopicId(type=topic_type, source=self.id.key),
                        )
                        await self.send_response(
                            f"✅ 已发送到 {format_type.upper()} 生成智能体\n\n"
                        )
                        logger.info(f"成功发送分析结果到 {format_type} 生成智能体")

                    except Exception as e:
                        await self.send_response(
                            f"❌ 发送到 {format_type.upper()} 生成智能体失败: {str(e)}\n\n"
                        )
                        logger.error(f"发送到 {format_type} 生成智能体失败: {str(e)}")
                else:
                    await self.send_response(f"⚠️ 不支持的格式: {format_type}\n")
                    logger.warning(f"不支持的脚本格式: {format_type}")

            await self.send_response("🎯 脚本生成路由完成\n\n")

        except Exception as e:
            await self.send_response(f"❌ 脚本生成路由失败: {str(e)}\n\n")
            logger.error(f"脚本生成路由失败: {str(e)}")

    async def _create_image_analysis_team(self) -> GraphFlow:
        """创建基于GraphFlow的图片分析团队，支持并行分析和条件分支"""
        try:
            if self._analysis_team:
                return self._analysis_team

            # 使用工厂创建专业智能体
            ui_expert = self.create_ui_expert_agent()
            interaction_analyst = self.create_interaction_analyst_agent()
            midscene_expert_core = self.create_midscene_expert_agent()

            # 用户反馈代理（如果启用）
            participants = [ui_expert, interaction_analyst, midscene_expert_core]
            user_proxy = None
            if self.enable_user_feedback and self.collector.user_input:
                user_proxy = UserProxyAgent(
                    name="user_proxy", input_func=self.collector.user_input
                )
                participants.append(user_proxy)

            # 构建GraphFlow工作流
            builder = DiGraphBuilder()

            # 添加所有节点
            for participant in participants:
                builder.add_node(participant)

            # 构建执行图：
            # 1. UI分析和交互分析并行执行
            builder.add_edge(ui_expert, midscene_expert_core)
            builder.add_edge(interaction_analyst, midscene_expert_core)

            # # 2. 质量审查的条件分支
            # # 如果需要修订，回到并行分析阶段
            # builder.add_edge(quality_reviewer, ui_expert, condition="REVISE")
            # builder.add_edge(quality_reviewer, interaction_analyst, condition="REVISE")
            #
            # # 如果批准，进入测试设计阶段
            # builder.add_edge(quality_reviewer, filtered_midscene_expert, condition="APPROVE")

            # 3. 用户反馈（如果启用）
            if user_proxy:
                builder.add_edge(midscene_expert_core, user_proxy)

            # 设置入口点（并行开始）
            # builder.set_entry_point(ui_expert)
            # builder.set_entry_point(interaction_analyst)

            # 构建图
            graph = builder.build()

            # 创建GraphFlow团队
            team = GraphFlow(participants=builder.get_participants(), graph=graph)

            self._analysis_team = team
            return team

        except Exception as e:
            logger.error(f"创建图片分析团队失败: {str(e)}")
            raise

    async def _run_team_analysis(
        self, team: GraphFlow, multimodal_message: MultiModalMessage
    ) -> Dict[str, Any]:
        """运行团队协作分析"""
        try:
            # 运行团队分析
            stream = team.run_stream(task=multimodal_message)
            messages = []
            async for event in stream:  # type: ignore
                # 流式消息
                if isinstance(event, ModelClientStreamingChunkEvent):
                    await self.send_response(
                        content=event.content,
                        region=MessageRegion.ANALYSIS,
                        source=AGENT_NAMES[event.source],
                    )
                    continue

                # 最终的完整结果
                if isinstance(event, TaskResult):
                    messages = event.messages
                    continue
            # 收集分析结果
            analysis_results = {
                "ui_analysis": [],
                "interaction_analysis": [],
                "test_scenarios": [],
                "user_feedback": [],
                "chat_history": [],
            }

            # 解析团队对话历史
            for message in messages:
                if isinstance(message, TextMessage):
                    source = message.source
                    content = message.content
                else:
                    continue

                analysis_results["chat_history"].append(
                    {
                        "source": source,
                        "content": content,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

                # 根据来源分类结果
                if source == AgentTypes.UI_EXPERT.value:
                    analysis_results["ui_analysis"].append(content)
                elif source == AgentTypes.INTERACTION_ANALYST.value:
                    analysis_results["interaction_analysis"].append(content)
                elif source == AgentTypes.MIDSCENE_EXPERT.value:
                    analysis_results["test_scenarios"].append(content)
                elif source == AgentTypes.QUALITY_REVIEWER.value:
                    # 质量审查结果也记录到聊天历史中，但不单独分类
                    pass
                elif source == "user_proxy":
                    analysis_results["user_feedback"].append(content)

            return analysis_results

        except Exception as e:
            logger.error(f"团队分析执行失败: {str(e)}")
            # 返回默认结果
            return {
                "ui_analysis": ["团队分析失败"],
                "interaction_analysis": ["团队分析失败"],
                "test_scenarios": ["团队分析失败"],
                "user_feedback": [],
                "chat_history": [],
            }

    @staticmethod
    def _build_midscene_expert_prompt() -> str:
        """构建MidScene.js专家的详细提示词（静态版本）"""
        return """你是MidScene.js自动化测试专家，专门基于UI专家和交互分析师的分析结果，设计符合MidScene.js脚本风格的测试用例。

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
        },
        {
          "step_id": 2,
          "action_type": "aiInput",
          "action_description": "test@example.com",
          "visual_target": "用户名输入框，标签显示'用户名'或'邮箱'，位于登录表单的顶部，是一个白色背景的矩形输入框",
          "expected_result": "输入框显示邮箱地址，光标位于输入内容后",
          "validation_step": "检查输入框内容是否正确显示"
        },
        {
          "step_id": 3,
          "action_type": "aiInput",
          "action_description": "password123",
          "visual_target": "密码输入框，标签显示'密码'，位于用户名输入框下方，输入时显示为圆点或星号",
          "expected_result": "密码框显示遮蔽字符",
          "validation_step": "确认密码已输入且被正确遮蔽"
        },
        {
          "step_id": 4,
          "action_type": "aiTap",
          "action_description": "登录表单底部的'登录'或'提交'按钮，通常为蓝色或绿色背景",
          "visual_target": "表单提交按钮，位于密码输入框下方，可能显示'登录'、'提交'或'Sign In'文字",
          "expected_result": "开始登录验证过程",
          "validation_step": "检查是否显示加载状态或跳转"
        },
        {
          "step_id": 5,
          "action_type": "aiAssert",
          "action_description": "界面显示登录成功的标识，如用户头像、欢迎信息，或者跳转到主页面显示用户相关内容",
          "expected_result": "登录成功，用户进入已登录状态",
          "validation_step": "确认页面显示用户已登录的视觉标识"
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
9. **多语言支持**: 支持中英文混合的界面描述
"""

    @staticmethod
    def _build_ui_expert_prompt() -> str:
        """职责 (Responsibilities):
        接收用户提供的界面截图或实时界面信息。
        利用多模态大模型的能力，识别界面中的关键元素，例如按钮、输入框、文本标签、图片、列表项等。
        输出结构化的界面元素信息，包括元素类型、位置、文本内容、可能的交互方式以及推荐的定位符（如ID、类名、文本内容等，MidScene.js可能用到的）。"""
        return """你是UI元素识别专家，专门分析界面截图中的UI组件，为自动化测试提供精确的元素信息。
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
- **结构化**: 严格遵循JSON格式，便于后续处理
"""

    @staticmethod
    def _build_interaction_analyst_prompt() -> str:
        """构建交互分析师的详细提示词（静态版本）"""
        return """你是用户交互流程分析师，专门分析用户在界面上的操作流程，为自动化测试设计提供用户行为路径。

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
        },
        {
          "step_id": 2,
          "action": "输入用户名",
          "target_element": "用户名输入框",
          "expected_result": "输入框显示用户名",
          "validation": "检查输入格式"
        }
      ],
      "success_criteria": "成功登录并跳转到主页",
      "error_scenarios": ["用户名密码错误", "网络连接失败"]
    }
  ],
  "alternative_flows": [
    {
      "flow_name": "第三方登录流程",
      "trigger_condition": "用户选择第三方登录",
      "steps": []
    }
  ],
  "interaction_patterns": {
    "navigation_style": "顶部导航栏",
    "input_validation": "实时验证",
    "feedback_mechanism": "弹窗提示",
    "error_handling": "内联错误信息"
  }
}
```

## 分析维度

### 1. 流程完整性
- 覆盖所有主要用户场景
- 包含异常情况处理
- 考虑不同用户角色的需求

### 2. 操作可行性
- 每个步骤都有明确的触发元素
- 操作序列逻辑合理
- 符合界面实际布局

### 3. 测试友好性
- 每个步骤都可以自动化执行
- 包含明确的验证点
- 提供详细的元素定位信息
"""

    @staticmethod
    def _build_quality_reviewer_prompt() -> str:
        """构建质量审查员的详细提示词（静态版本）"""
        return """你是分析质量审查员，负责评估UI和交互分析的质量，确保分析结果符合自动化测试的要求。

## 核心职责

### 1. UI分析质量评估
- **元素覆盖率**: 检查是否识别了所有主要交互元素（目标≥90%）
- **描述准确性**: 验证元素描述是否详细且准确
- **定位信息**: 确认位置描述足够精确，便于自动化定位
- **格式规范**: 检查JSON格式是否正确完整

### 2. 交互流程质量评估
- **流程完整性**: 验证是否覆盖了主要用户场景
- **逻辑合理性**: 检查操作序列是否符合用户习惯
- **可执行性**: 确认每个步骤都可以自动化执行
- **异常处理**: 评估错误场景的覆盖程度

### 3. 协作质量标准
- **信息一致性**: UI分析和交互分析的信息是否一致
- **关联性**: 交互流程是否正确引用了UI元素
- **完整性**: 两个分析是否相互补充，形成完整图景

## 评估维度与标准

### 1. 完整性评估 (权重: 30%)
- **优秀 (9-10分)**: 识别≥95%关键元素，覆盖所有主要流程
- **良好 (7-8分)**: 识别≥85%关键元素，覆盖主要流程
- **一般 (5-6分)**: 识别≥70%关键元素，基本流程完整
- **不足 (<5分)**: 遗漏重要元素或流程

### 2. 准确性评估 (权重: 25%)
- **优秀 (9-10分)**: 元素类型、描述、位置信息完全准确
- **良好 (7-8分)**: 主要信息准确，细节有轻微偏差
- **一般 (5-6分)**: 基本信息正确，部分描述不够精确
- **不足 (<5分)**: 存在明显错误或误判

### 3. 详细性评估 (权重: 20%)
- **优秀 (9-10分)**: 包含丰富的视觉特征和上下文信息
- **良好 (7-8分)**: 描述较为详细，基本满足定位需求
- **一般 (5-6分)**: 描述简单但可用
- **不足 (<5分)**: 描述过于简单，难以定位

### 4. 结构化程度 (权重: 15%)
- **优秀 (9-10分)**: 严格遵循JSON格式，结构清晰
- **良好 (7-8分)**: 格式基本正确，结构合理
- **一般 (5-6分)**: 格式有小问题但可解析
- **不足 (<5分)**: 格式错误或结构混乱

### 5. 可执行性评估 (权重: 10%)
- **优秀 (9-10分)**: 所有操作都可以直接自动化执行
- **良好 (7-8分)**: 大部分操作可执行，少量需要调整
- **一般 (5-6分)**: 基本可执行，需要一定程度的解释
- **不足 (<5分)**: 难以直接执行，需要大量补充信息

## 决策标准

### APPROVE 条件 (综合评分≥7.0)
- 完整性评分≥7分
- 准确性评分≥7分
- 其他维度评分≥6分
- 无严重格式错误
- 信息足够支持后续测试设计

### REVISE 条件 (综合评分<7.0)
- 任一核心维度评分<6分
- 存在明显的信息缺失
- 格式错误影响解析
- 信息不足以支持测试设计

## 输出格式

### 批准输出
```
APPROVE

质量评估报告:
- 完整性: 8.5/10 (识别了95%的关键元素)
- 准确性: 9.0/10 (元素描述准确详细)
- 详细性: 8.0/10 (包含丰富的视觉特征)
- 结构化: 9.5/10 (严格遵循JSON格式)
- 可执行性: 8.5/10 (操作步骤清晰可执行)

综合评分: 8.7/10

优势:
- UI元素识别全面，描述详细准确
- 交互流程逻辑清晰，步骤完整
- 格式规范，便于后续处理

建议:
- 可进一步优化部分元素的视觉描述
- 建议增加更多异常场景的处理
```

### 修订输出
```
REVISE

质量评估报告:
- 完整性: 6.0/10 (遗漏了部分重要元素)
- 准确性: 5.5/10 (部分描述不够准确)
- 详细性: 4.0/10 (描述过于简单)
- 结构化: 7.0/10 (格式基本正确)
- 可执行性: 5.0/10 (部分操作难以执行)

综合评分: 5.5/10

主要问题:
- 遗漏了导航栏和侧边栏的重要元素
- 部分按钮的位置描述不够精确
- 交互流程缺少异常处理步骤

改进建议:
- 重新扫描页面，识别遗漏的交互元素
- 增加更详细的视觉特征描述
- 补充完整的用户操作流程
- 添加错误场景和异常处理
```
"""

    async def _prepare_multimodal_message(
        self, request: WebMultimodalAnalysisRequest
    ) -> MultiModalMessage:
        """准备多模态消息，基于AutoGen的MultiModalMessage格式"""
        try:
            # 构建文本内容
            text_content = f"""
请分析以下UI界面截图：

**分析需求**: {request.test_description}
**附加说明**: {request.additional_context or '无'}

工作流程说明：
1. UI_Expert和Interaction_Analyst将并行分析界面
2. Quality_Reviewer将评估分析质量，决定是否需要重新分析
3. 通过质量审查后，MidScene_Expert将设计测试用例

请开始分析工作。
"""

            # 转换图片为AGImage对象
            ag_image = await self._convert_image_to_agimage(request)

            # 创建MultiModalMessage，参考官方示例格式
            multimodal_message = MultiModalMessage(
                content=[text_content, ag_image], source="user"
            )

            return multimodal_message

        except Exception as e:
            logger.error(f"准备多模态消息失败: {str(e)}")
            raise

    async def _convert_image_to_agimage(
        self, request: WebMultimodalAnalysisRequest
    ) -> AGImage:
        """将图片内容转换为AGImage对象，参考官方示例代码"""
        try:
            pil_image = None

            if request.image_url:
                # 从URL获取图片，参考官方示例：requests.get(url).content
                response = requests.get(request.image_url)
                response.raise_for_status()
                pil_image = Image.open(BytesIO(response.content))
            elif request.image_data:
                # 处理base64数据
                if request.image_data.startswith("data:image"):
                    # 移除data URI前缀
                    base64_data = request.image_data.split(",")[1]
                else:
                    base64_data = request.image_data

                # 解码base64数据并创建PIL图片
                image_bytes = base64.b64decode(base64_data)
                pil_image = Image.open(BytesIO(image_bytes))
            else:
                raise ValueError("缺少图片数据或URL")

            # 转换为AGImage，完全按照官方示例：AGImage(pil_image)
            ag_image = AGImage(pil_image)
            logger.info(f"成功转换图片为AGImage，尺寸: {pil_image.size}")

            return ag_image

        except Exception as e:
            logger.error(f"转换图片为AGImage失败: {str(e)}")
            raise

    async def _integrate_analysis_results(
        self,
        team_results: Dict[str, Any],
        analysis_id: str,
        request: WebMultimodalAnalysisRequest,
    ) -> WebMultimodalAnalysisResponse:
        """整合团队分析结果"""
        try:
            await self.send_response("🔧 整合团队分析结果...\n\n")

            # 解析UI元素
            # ui_elements = await self._parse_ui_elements_from_team_results(team_results.get("ui_analysis", []))
            #
            # # 解析交互流程
            # user_flows = await self._parse_interaction_flows_from_team_results(team_results.get("interaction_analysis", []))
            #
            # # 解析测试场景
            # test_scenarios = await self._parse_test_scenarios_from_team_results(team_results.get("test_scenarios", []))

            # 构建页面分析结果
            page_analysis = PageAnalysis(
                page_title=self._extract_page_title_from_results(team_results),
                page_type=self._extract_page_type_from_results(team_results),
                main_content=self._extract_main_content_from_results(team_results),
                ui_elements=team_results.get("ui_analysis", []),
                user_flows=team_results.get("interaction_analysis", []),
                test_scenarios=team_results.get("test_scenarios", []),
                analysis_summary="基于团队协作的图片界面分析",
                confidence_score=self._calculate_confidence_score(team_results),
            )

            # 计算置信度
            confidence_score = self._calculate_confidence_score(team_results)

            return WebMultimodalAnalysisResponse(
                session_id=request.session_id,
                analysis_id=analysis_id,
                analysis_type=AnalysisType.IMAGE,
                page_analysis=page_analysis,
                confidence_score=confidence_score,
                status="completed",
                message="图片分析完成",
                processing_time=self.metrics.get("duration_seconds", 0.0),
            )

        except Exception as e:
            logger.error(f"整合团队分析结果失败: {str(e)}")
            raise

    # ==================== 解析方法 ====================

    async def _parse_ui_elements_from_team_results(
        self, ui_analysis_results: List[str]
    ) -> List[UIElement]:
        """从团队结果中解析UI元素"""
        try:
            ui_elements = []
            element_id = 1

            for analysis_text in ui_analysis_results:
                try:
                    import re

                    # 查找JSON格式的元素描述
                    json_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
                    json_matches = re.findall(json_pattern, analysis_text, re.DOTALL)

                    for json_str in json_matches:
                        try:
                            element_data = json.loads(json_str)
                            if self._is_valid_ui_element(element_data):
                                ui_element = UIElement(
                                    element_type=element_data.get(
                                        "element_type", "unknown"
                                    ),
                                    description=element_data.get("description", ""),
                                    location=str(element_data.get("position", {})),
                                    attributes=element_data.get("attributes", {}),
                                    confidence_score=float(
                                        element_data.get("confidence_score", 0.8)
                                    ),
                                )
                                ui_elements.append(ui_element)
                                element_id += 1
                        except (json.JSONDecodeError, ValueError):
                            continue

                except Exception as e:
                    logger.debug(f"解析UI元素时出错: {str(e)}")
                    continue

            # 如果没有解析到元素，创建默认元素
            if not ui_elements:
                ui_elements.append(
                    UIElement(
                        element_type="unknown",
                        description="从团队分析中识别的界面元素",
                        location="页面中央",
                        attributes={},
                        confidence_score=0.6,
                    )
                )

            return ui_elements

        except Exception as e:
            logger.error(f"解析UI元素失败: {str(e)}")
            return []

    def _is_valid_ui_element(self, element_data: Dict[str, Any]) -> bool:
        """验证是否为有效的UI元素数据"""
        required_fields = ["name", "element_type"]
        return any(field in element_data for field in required_fields)

    async def _parse_interaction_flows_from_team_results(
        self, interaction_analysis_results: List[str]
    ) -> List[str]:
        """解析交互流程"""
        try:
            interaction_flows = []

            for analysis_text in interaction_analysis_results:
                lines = analysis_text.split("\n")
                for line in lines:
                    line = line.strip()
                    if line and (
                        line.startswith("-")
                        or line.startswith("*")
                        or line.startswith("1.")
                        or "步骤" in line
                        or "流程" in line
                    ):
                        import re

                        clean_line = re.sub(r"^[-*\d\.]\s*", "", line)
                        clean_line = re.sub(r"步骤\d+[：:]\s*", "", clean_line)
                        if clean_line and len(clean_line) > 3:
                            interaction_flows.append(clean_line)

            if not interaction_flows:
                interaction_flows = [
                    "用户访问页面",
                    "用户查看页面内容",
                    "用户进行交互操作",
                    "系统响应用户操作",
                ]

            return interaction_flows

        except Exception as e:
            logger.error(f"解析交互流程失败: {str(e)}")
            return ["默认交互流程"]

    async def _parse_test_scenarios_from_team_results(
        self, test_analysis_results: List[str]
    ) -> List[Dict[str, Any]]:
        """解析测试场景"""
        try:
            test_scenarios = []
            scenario_id = 1

            for analysis_text in test_analysis_results:
                try:
                    import re

                    scenario_patterns = [
                        r"测试场景[：:]\s*([^\n]+)",
                        r"场景[：:]\s*([^\n]+)",
                        r"test\s*scenario[：:]\s*([^\n]+)",
                    ]

                    scenario_name = None
                    for pattern in scenario_patterns:
                        matches = re.findall(pattern, analysis_text, re.IGNORECASE)
                        if matches:
                            scenario_name = matches[0].strip()
                            break

                    if not scenario_name:
                        scenario_name = f"测试场景{scenario_id}"

                    # 提取测试步骤
                    steps = []
                    lines = analysis_text.split("\n")
                    for line in lines:
                        line = line.strip()
                        if line and (
                            "ai" in line.lower()
                            or "点击" in line
                            or "输入" in line
                            or "验证" in line
                        ):
                            steps.append(line)

                    if not steps:
                        steps = ["分析界面元素", "执行用户操作", "验证操作结果"]

                    test_scenarios.append(
                        {
                            "name": scenario_name,
                            "steps": steps[:10],
                            "priority": "medium",
                            "estimated_duration": f"{len(steps) * 5}秒",
                        }
                    )
                    scenario_id += 1

                except Exception as e:
                    logger.debug(f"解析测试场景时出错: {str(e)}")
                    continue

            if not test_scenarios:
                test_scenarios = [
                    {
                        "name": "基本界面测试",
                        "steps": [
                            "验证页面加载完成",
                            "识别主要交互元素",
                            "执行基本操作",
                            "验证操作结果",
                        ],
                        "priority": "high",
                        "estimated_duration": "30秒",
                    }
                ]

            return test_scenarios

        except Exception as e:
            logger.error(f"解析测试场景失败: {str(e)}")
            return []

    # ==================== 提取方法 ====================

    def _extract_page_title_from_results(self, team_results: Dict[str, Any]) -> str:
        """从团队结果中提取页面标题"""
        try:
            all_content = " ".join(
                [
                    " ".join(team_results.get("ui_analysis", [])),
                    " ".join(team_results.get("interaction_analysis", [])),
                    " ".join(team_results.get("test_scenarios", [])),
                ]
            )

            import re

            title_patterns = [
                r"页面标题[：:]\s*([^\n]+)",
                r"标题[：:]\s*([^\n]+)",
                r"title[：:]\s*([^\n]+)",
                r"界面标题[：:]\s*([^\n]+)",
            ]

            for pattern in title_patterns:
                matches = re.findall(pattern, all_content, re.IGNORECASE)
                if matches:
                    return matches[0].strip()

            # 尝试从UI元素中推断标题
            if "login" in all_content.lower() or "登录" in all_content:
                return "登录页面"
            elif "dashboard" in all_content.lower() or "仪表板" in all_content:
                return "仪表板页面"
            elif "form" in all_content.lower() or "表单" in all_content:
                return "表单页面"

            return "图片分析页面"

        except Exception as e:
            logger.debug(f"提取页面标题失败: {str(e)}")
            return "未知界面"

    def _extract_page_type_from_results(self, team_results: Dict[str, Any]) -> str:
        """从团队结果中提取页面类型"""
        try:
            all_content = " ".join(
                [
                    " ".join(team_results.get("ui_analysis", [])),
                    " ".join(team_results.get("interaction_analysis", [])),
                ]
            ).lower()

            # 页面类型关键词映射
            type_keywords = {
                "login": ["登录", "login", "sign in", "账号", "密码", "用户名"],
                "dashboard": ["仪表板", "dashboard", "控制台", "主页", "首页", "概览"],
                "form": ["表单", "form", "填写", "提交", "输入框", "表格"],
                "list": ["列表", "list", "表格", "table", "数据", "清单"],
                "detail": ["详情", "detail", "详细", "查看", "信息"],
                "homepage": ["首页", "homepage", "主页", "欢迎", "导航"],
                "settings": ["设置", "settings", "配置", "选项"],
                "profile": ["个人", "profile", "用户", "账户"],
            }

            for page_type, keywords in type_keywords.items():
                if any(keyword in all_content for keyword in keywords):
                    return page_type

            return "unknown"

        except Exception as e:
            logger.debug(f"提取页面类型失败: {str(e)}")
            return "unknown"

    def _extract_main_content_from_results(self, team_results: Dict[str, Any]) -> str:
        """从团队结果中提取主要内容描述"""
        try:
            # 优先使用UI分析结果
            ui_analysis = team_results.get("ui_analysis", [])
            if ui_analysis:
                main_content = ui_analysis[0][:300]
                if len(ui_analysis[0]) > 300:
                    main_content += "..."
                return main_content

            # 其次使用交互分析
            interaction_analysis = team_results.get("interaction_analysis", [])
            if interaction_analysis:
                main_content = interaction_analysis[0][:300]
                if len(interaction_analysis[0]) > 300:
                    main_content += "..."
                return main_content

            # 最后使用测试场景
            test_analysis = team_results.get("test_scenarios", [])
            if test_analysis:
                main_content = test_analysis[0][:300]
                if len(test_analysis[0]) > 300:
                    main_content += "..."
                return main_content

            return (
                "基于团队协作的图片界面分析，包含UI元素识别、交互流程分析和测试场景设计"
            )

        except Exception as e:
            logger.debug(f"提取主要内容失败: {str(e)}")
            return "界面内容分析"

    def _calculate_confidence_score(self, team_results: Dict[str, Any]) -> float:
        """计算分析结果的置信度"""
        try:
            # 基础置信度
            base_confidence = 0.75  # 团队协作分析置信度更高

            # 根据分析结果的丰富程度调整置信度
            ui_analysis_count = len(team_results.get("ui_analysis", []))
            interaction_analysis_count = len(
                team_results.get("interaction_analysis", [])
            )
            test_scenarios_count = len(team_results.get("test_scenarios", []))
            user_feedback_count = len(team_results.get("user_feedback", []))

            # 计算内容质量分数
            content_quality = 0
            for content_list in [
                team_results.get("ui_analysis", []),
                team_results.get("interaction_analysis", []),
                team_results.get("test_scenarios", []),
            ]:
                for content in content_list:
                    if len(content) > 50:  # 内容足够详细
                        content_quality += 0.05
                    if any(
                        keyword in content.lower()
                        for keyword in ["json", "element", "button", "input"]
                    ):
                        content_quality += 0.03  # 包含技术关键词

            # 计算加权置信度
            confidence_boost = (
                ui_analysis_count * 0.06
                + interaction_analysis_count * 0.05
                + test_scenarios_count * 0.04
                + user_feedback_count * 0.08
                + min(content_quality, 0.15)  # 内容质量最多贡献0.15
            )

            final_confidence = min(base_confidence + confidence_boost, 0.95)
            return round(final_confidence, 2)

        except Exception as e:
            logger.debug(f"计算置信度失败: {str(e)}")
            return 0.8
