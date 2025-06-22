# AI核心框架文档

[← 返回架构文档](./BACKEND_ARCHITECTURE.md) | [📖 文档中心](../) | [📋 导航索引](../DOCS_INDEX.md)

## 🎯 框架概述

AI核心框架（`backend/ai_core`）是专门为大模型应用开发设计的核心组件库，提供了统一的LLM客户端管理、提示词模板、工具函数等常用功能。

## 📁 目录结构

```
backend/ai_core/
├── __init__.py          # 统一导出接口
├── llm.py              # LLM客户端管理器
├── prompts.py          # 提示词模板（计划中）
├── tools.py            # 工具函数（计划中）
└── agents.py           # 智能体基础类（计划中）
```

## 🤖 LLM客户端管理器

### 支持的模型类型

1. **DeepSeek-Chat**: 通用对话模型，适用于文本生成和分析
2. **Qwen-VL-Max-Latest**: 多模态模型，支持视觉理解
3. **UI-TARS**: 专门的UI测试模型，支持界面分析

### 核心特性

#### 1. 统一的客户端管理
```python
from backend.ai_core.llm import LLMClientManager

manager = LLMClientManager()
```

#### 2. 多模型支持
```python
from backend.ai_core.llm import (
    get_deepseek_client,    # DeepSeek模型
    get_qwen_vl_client,     # Qwen-VL模型
    get_ui_tars_client,     # UI-TARS模型
    get_default_client      # 默认模型（自动选择）
)
```

#### 3. 配置验证
```python
from backend.ai_core.llm import validate_model_configs

configs = validate_model_configs()
# 返回: {'deepseek_configured': True, 'qwen_vl_configured': True, 'ui_tars_configured': True}
```

#### 4. 单例模式
每种模型类型的客户端都采用单例模式，避免重复创建：
```python
# 多次调用返回同一个实例
client1 = get_deepseek_client()
client2 = get_deepseek_client()
assert client1 is client2  # True
```

### 使用示例

#### 基础使用
```python
from backend.ai_core.llm import get_default_client

# 获取默认客户端（按优先级自动选择）
client = get_default_client()
if client:
    # 使用客户端进行对话
    response = await client.create(
        messages=[{"role": "user", "content": "Hello"}]
    )
```

#### 指定模型使用
```python
from backend.ai_core.llm import get_qwen_vl_client

# 使用Qwen-VL模型处理图像
vl_client = get_qwen_vl_client()
if vl_client:
    response = await vl_client.create(
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "描述这张图片"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}}
            ]
        }]
    )
```

#### 配置检查
```python
from backend.ai_core.llm import get_model_config_status

# 检查模型配置状态
status = get_model_config_status()
if status['deepseek_configured']:
    print("DeepSeek模型已配置")
if status['qwen_vl_configured']:
    print("Qwen-VL模型已配置")
```

### 模型选择策略

默认客户端按以下优先级自动选择：
1. **DeepSeek** - 通用性强，成本较低
2. **Qwen-VL** - 支持多模态，功能丰富
3. **UI-TARS** - 专业UI分析，特定场景

### 配置要求

在 `backend/conf/settings.yaml` 中配置模型信息：

```yaml
test:
  # DeepSeek配置
  aimodel:
    model: "deepseek-chat"
    base_url: "https://api.deepseek.com/v1"
    api_key: "sk-your-deepseek-key"

  # Qwen-VL配置
  qwen_model:
    model: "qwen-vl-max-latest"
    base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_key: "sk-your-qwen-key"

  # UI-TARS配置
  ui_tars_model:
    model: "doubao-1-5-ui-tars-250428"
    base_url: "https://ark.cn-beijing.volces.com/api/v3"
    api_key: "your-ui-tars-key"
```

## 🔄 API接口

### 统一接口设计
AI核心模块提供了统一的接口设计，支持多种使用方式：

```python
# 推荐方式：使用默认客户端（智能选择）
from backend.ai_core.llm import get_default_client
client = get_default_client()

# 指定模型类型
from backend.ai_core.llm import get_deepseek_client, get_qwen_vl_client
deepseek_client = get_deepseek_client()    # DeepSeek模型
qwen_client = get_qwen_vl_client()         # Qwen-VL模型

# 向后兼容接口（保留原有函数名）
from backend.ai_core.llm import get_openai_model_client
client = get_openai_model_client()  # 等同于 get_default_client()
```

### 使用指南

#### 1. 基础使用
```python
from backend.ai_core.llm import get_default_client

client = get_default_client()
if client:
    # 使用客户端进行对话
    response = await client.create(messages=messages)
```

#### 2. 指定模型使用
```python
from backend.ai_core.llm import get_deepseek_client, get_qwen_vl_client

# 文本处理使用DeepSeek
text_client = get_deepseek_client()

# 图像分析使用Qwen-VL
vision_client = get_qwen_vl_client()
```

## 🚀 扩展计划

### 即将添加的组件

#### 1. 提示词模板管理 (`prompts.py`)
```python
from backend.ai_core.prompts import PromptTemplate

template = PromptTemplate.get("test_case_generation")
prompt = template.format(requirement="用户登录功能")
```

#### 2. 工具函数库 (`tools.py`)
```python
from backend.ai_core.tools import TokenCounter, ResponseParser

counter = TokenCounter()
tokens = counter.count(text)
```

#### 3. 智能体基础类 (`agents.py`)
```python
from backend.ai_core.agents import BaseAgent

class CustomAgent(BaseAgent):
    def __init__(self):
        super().__init__(model_type=ModelType.DEEPSEEK)
```

## 📊 性能优化

### 1. 连接池管理
- 每种模型类型维护独立的连接池
- 自动重连和错误恢复机制

### 2. 缓存策略
- 客户端实例缓存（单例模式）
- 配置状态缓存，避免重复验证

### 3. 资源管理
- 自动清理无效连接
- 内存使用监控和优化

## 🔧 最佳实践

### 1. 模型选择
- **文本生成**: 使用 DeepSeek
- **图像分析**: 使用 Qwen-VL
- **UI测试**: 使用 UI-TARS
- **通用场景**: 使用 get_default_client()

### 2. 错误处理
```python
from backend.ai_core.llm import get_default_client

client = get_default_client()
if client is None:
    logger.error("没有可用的模型客户端")
    return

try:
    response = await client.create(messages=messages)
except Exception as e:
    logger.error(f"模型调用失败: {e}")
```

### 3. 配置管理
- 使用环境变量管理敏感信息
- 定期检查配置状态
- 实现配置热重载（计划中）

## 🔗 相关文档

- [后端架构文档](./BACKEND_ARCHITECTURE.md)
- [服务重构文档](./SERVICES_REFACTORING.md)
- [开发指南](../development/DEVELOPMENT_GUIDE.md)
