# 框架优化第三步：服务抽象与智能体框架

[← 返回架构文档](./BACKEND_ARCHITECTURE.md) | [📖 文档中心](../) | [📋 导航索引](../DOCS_INDEX.md)

## 🎯 优化目标

第三步优化专注于对服务进行抽象，建立完整的智能体开发框架，包括智能体工厂、基础类、运行时管理和内存管理，为大模型应用开发提供标准化的架构支持。

## 📁 新增架构组件

### AI核心框架扩展
```
backend/ai_core/
├── __init__.py              # 统一导出接口
├── llm.py                  # LLM客户端管理器
├── agents.py               # 智能体基础类（新增）
├── factory.py              # 智能体工厂（新增）
├── runtime.py              # 运行时基类（新增）
├── memory.py               # 内存管理器（新增）
└── testcase_runtime.py     # 测试用例专用运行时（新增）
```

## 🏗️ 核心组件设计

### 1. 智能体基础类 (`agents.py`)

#### BaseAgent 抽象基类
```python
class BaseAgent(RoutedAgent, ABC):
    """智能体基础类，提供通用功能"""

    def __init__(self, agent_id: str, agent_name: str, model_client: OpenAIChatCompletionClient, **kwargs):
        # 统一的初始化逻辑

    async def send_message(self, content: str, message_type: str = "info", **kwargs):
        # 统一的消息发送接口

    async def send_progress(self, content: str, progress_percent: Optional[float] = None):
        # 进度消息发送

    async def handle_exception(self, func_name: str, exception: Exception):
        # 统一的异常处理

    @abstractmethod
    async def process_message(self, message: Any, ctx: MessageContext):
        # 抽象方法，子类必须实现
```

#### StreamingAgent 流式智能体
```python
class StreamingAgent(BaseAgent):
    """支持流式输出的智能体基类"""

    async def send_streaming_chunk(self, content: str, **kwargs):
        # 流式内容块发送

    async def send_streaming_complete(self, final_content: str, **kwargs):
        # 流式输出完成
```

### 2. 智能体工厂 (`factory.py`)

#### AgentFactory 工厂类
```python
class AgentFactory:
    """智能体工厂类，统一管理智能体的创建和注册"""

    def register_agent_class(self, agent_type: AgentType, agent_class: Type[BaseAgent]):
        # 注册智能体类

    def create_assistant_agent(self, name: str, system_message: str, model_type: ModelType):
        # 创建AssistantAgent

    def create_agent(self, agent_type: AgentType, **kwargs):
        # 创建自定义智能体

    async def register_agent_to_runtime(self, runtime, agent_type, topic_type, **kwargs):
        # 注册智能体到运行时
```

#### 支持的智能体类型
```python
class AgentType(Enum):
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
```

### 3. 运行时基类 (`runtime.py`)

#### BaseRuntime 抽象基类
```python
class BaseRuntime(ABC):
    """智能体运行时基类"""

    async def initialize_runtime(self, conversation_id: str):
        # 初始化运行时环境

    @abstractmethod
    async def register_agents(self, runtime: SingleThreadedAgentRuntime, conversation_id: str):
        # 注册智能体（抽象方法）

    async def cleanup_runtime(self, conversation_id: str):
        # 清理运行时资源

    async def update_state(self, conversation_id: str, stage: str, status: str):
        # 更新运行时状态
```

#### RuntimeState 状态管理
```python
class RuntimeState:
    """运行时状态管理"""

    def update_stage(self, stage: str, status: str = "processing"):
        # 更新运行时阶段

    def update_round(self, round_number: int):
        # 更新轮次

    def get_state_dict(self) -> Dict[str, Any]:
        # 获取状态字典
```

#### MessageQueue 消息队列
```python
class MessageQueue:
    """消息队列管理器"""

    async def put_message(self, message: str):
        # 放入消息到队列

    async def get_message(self) -> str:
        # 从队列获取消息

    async def put_feedback(self, feedback: str):
        # 放入用户反馈
```

### 4. 内存管理器 (`memory.py`)

#### ConversationMemory 对话内存
```python
class ConversationMemory:
    """对话内存管理器"""

    async def add_message(self, message_type: str, content: Any, metadata: Optional[Dict]):
        # 添加消息到内存

    async def get_history(self, limit: Optional[int] = None) -> List[Dict]:
        # 获取对话历史

    async def get_agent_memory(self) -> Optional[ListMemory]:
        # 获取用于智能体的内存副本
```

#### MemoryManager 内存管理器
```python
class MemoryManager:
    """内存管理器，管理多个对话的内存"""

    async def initialize_memory(self, conversation_id: str) -> ConversationMemory:
        # 初始化对话内存

    async def save_to_memory(self, conversation_id: str, data: Dict):
        # 保存数据到对话内存

    async def get_conversation_history(self, conversation_id: str) -> List[Dict]:
        # 获取对话历史
```

### 5. 测试用例专用运行时 (`testcase_runtime.py`)

#### TestCaseRuntime 实现
```python
class TestCaseRuntime(BaseRuntime):
    """测试用例生成专用运行时"""

    async def register_agents(self, runtime: SingleThreadedAgentRuntime, conversation_id: str):
        # 注册测试用例相关智能体

    async def start_requirement_analysis(self, conversation_id: str, requirement_data: Dict):
        # 启动需求分析流程

    async def process_user_feedback(self, conversation_id: str, feedback_data: Dict):
        # 处理用户反馈
```

## 🔧 核心特性

### 1. 统一的智能体接口
- **标准化创建**：通过工厂模式统一创建智能体
- **通用功能**：消息发送、进度报告、异常处理
- **性能监控**：内置性能指标收集
- **流式支持**：专门的流式输出基类

### 2. 灵活的运行时管理
- **生命周期管理**：自动化的初始化和清理
- **状态跟踪**：完整的运行时状态管理
- **消息队列**：内置的消息和反馈队列
- **资源隔离**：按对话ID隔离运行时环境

### 3. 智能的内存管理
- **对话记忆**：自动保存和检索对话历史
- **智能体内存**：为智能体提供上下文记忆
- **安全序列化**：处理复杂对象的JSON序列化
- **内存优化**：按需创建和清理内存实例

### 4. 可扩展的架构设计
- **抽象基类**：便于扩展新的智能体类型
- **工厂模式**：统一的创建和注册机制
- **插件化**：支持动态注册智能体类
- **配置驱动**：通过配置管理智能体行为

## 📊 架构优势

### 重构前问题
- ❌ 智能体创建逻辑分散，难以维护
- ❌ 运行时管理复杂，资源泄漏风险
- ❌ 内存管理手动实现，容易出错
- ❌ 缺乏统一的抽象层，代码重复

### 重构后改进
- ✅ 统一的智能体工厂和基类
- ✅ 自动化的运行时生命周期管理
- ✅ 智能的内存管理和对话记忆
- ✅ 清晰的抽象层次和接口设计

## 🚀 使用示例

### 创建智能体
```python
from backend.ai_core import get_agent_factory, AgentType, ModelType

# 获取工厂实例
factory = get_agent_factory()

# 创建AssistantAgent
assistant = factory.create_assistant_agent(
    name="需求分析师",
    system_message="你是专业的需求分析师...",
    model_type=ModelType.DEEPSEEK
)

# 创建自定义智能体
custom_agent = factory.create_agent(
    agent_type=AgentType.REQUIREMENT_ANALYSIS,
    agent_name="需求分析智能体",
    model_type=ModelType.DEEPSEEK
)
```

### 使用运行时
```python
from backend.ai_core.testcase_runtime import get_testcase_runtime

# 获取测试用例运行时
runtime = get_testcase_runtime()

# 初始化运行时
await runtime.initialize_runtime("conversation_123")

# 启动需求分析
await runtime.start_requirement_analysis("conversation_123", {
    "text_content": "用户登录功能需求",
    "files": []
})

# 处理用户反馈
await runtime.process_user_feedback("conversation_123", {
    "feedback": "请增加密码强度验证",
    "previous_testcases": "..."
})
```

### 内存管理
```python
from backend.ai_core import get_memory_manager

# 获取内存管理器
memory_manager = get_memory_manager()

# 初始化对话内存
memory = await memory_manager.initialize_memory("conversation_123")

# 保存数据到内存
await memory_manager.save_to_memory("conversation_123", {
    "type": "user_input",
    "content": "用户需求描述",
    "timestamp": "2025-06-22T17:00:00"
})

# 获取对话历史
history = await memory_manager.get_conversation_history("conversation_123")
```

## 🧪 测试验证

### 功能测试结果
```bash
✅ 所有AI核心组件导入成功
✅ 智能体工厂创建成功: AgentFactory
✅ 内存管理器创建成功: MemoryManager
✅ 测试用例运行时创建成功: TestCaseRuntime
🎉 AI核心框架第三步优化测试完成！
```

## 📈 性能优化

### 1. 单例模式
- 工厂、内存管理器、运行时使用单例模式
- 避免重复创建和资源浪费
- 提供全局统一的访问接口

### 2. 资源管理
- 自动化的资源创建和清理
- 按对话ID隔离资源，避免冲突
- 内存泄漏检测和预防

### 3. 异步优化
- 全面使用异步编程模式
- 非阻塞的消息处理和队列操作
- 并发安全的状态管理

## 🎉 总结

第三步优化成功建立了完整的智能体开发框架，实现了：

- **🏭 智能体工厂**：统一创建和管理智能体
- **🤖 智能体基类**：提供通用功能和抽象接口
- **⚙️ 运行时管理**：自动化的生命周期管理
- **🧠 内存管理**：智能的对话记忆和上下文管理
- **🧪 专用运行时**：针对特定业务的运行时实现

这次优化体现了"**分层抽象**"的设计原则：
- 🏗️ **基础设施层**：LLM客户端、内存管理、消息队列
- 🤖 **智能体层**：基础类、工厂、运行时管理
- 🚀 **业务层**：专用运行时、具体智能体实现
- 📡 **接口层**：统一的API和服务接口

## 🔗 相关文档

- [AI核心框架文档](./AI_CORE_FRAMEWORK.md)
- [框架优化第二步](./FRAMEWORK_OPTIMIZATION_STEP2.md)
- [后端架构文档](./BACKEND_ARCHITECTURE.md)
