# showcase_demo 流式输出问题修复 - 最终方案

## 问题描述
showcase_demo 在前端无法看到AI的响应消息。虽然API调用返回200状态码，但前端UI不显示任何内容。

## 根本原因

经过深入对比 open-swe 项目的实现，发现了两个关键问题：

### 1. ❌ State Schema 未指定（已修复）
**问题：** `create_deep_agent()` 没有传入 `state_schema` 参数
**影响：** Graph的state可能没有正确的messages字段结构
**修复：** 添加 `state_schema=ShowcaseState`

### 2. ❌ Stream Modes 未配置（本次修复）
**问题：** 创建run时没有设置 `stream_mode` 参数
**影响：** LangGraph不发送流式的messages/tools/lifecycle事件，前端无法接收增量内容
**修复：** 在platform-api中设置默认的stream_mode

## 技术背景

根据 open-swe 文档 `10-langgraph-sdk-command-and-sse.md`：

> **误区二：只订阅 `messages-tuple` 就能驱动新版 UI**
> 
> 错。项目注释已经说明旧式 tuple 流对 `@langchain/react` 的 `messages/tools/lifecycle` 投影不够。缺少 `lifecycle` 时，UI 可能没有 `isLoading`；缺少 `tools` 时，工具卡片无法正确结束；**缺少 `messages` 时，文本只会在完整 `values` 快照时突然出现**。

### SSE 事件频道

| 频道 | UI/SDK 用途 | 典型数据 |
| --- | --- | --- |
| `values` | 完整状态快照 | `{ messages, ... }` |
| `updates` | 节点级增量 | `{ "node_name": { ... } }` |
| `messages` | **内容块级消息流** | `message-start`、`content-block-delta`、`message-finish` |
| `messages-tuple` | 旧式兼容流 | token chunk + metadata |
| `tools` | 工具生命周期 | started、output delta、finished、error |
| `lifecycle` | run/namespace 生命周期 | running、completed、failed、interrupted |
| `checkpoints` | 可恢复快照 | values、next、checkpoint、interrupts |
| `events` | LangChain 回调事件 | `on_chat_model_*`、`on_tool_*` 等 |

**关键：** 前端 `@langchain/react` 需要 `messages` 频道来接收**流式的增量内容**，而不仅仅是完整快照。

## 修复方案

### 修改 1: showcase_demo agent.py（已完成）

**文件：** `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py`

```python
# 1. 导入ShowcaseState
from runtime_service.services.demo.showcase_demo.schemas import ShowcaseState

# 2. 在create_deep_agent中指定state_schema
agent = create_deep_agent(
    model=model,
    backend=backend,
    tools=[...],
    state_schema=ShowcaseState,  # ← 指定state schema
    context_schema=RuntimeContext,
    ...
)
```

### 修改 2: platform-api service.py（本次修复）

**文件：** `apps/platform-api/app/modules/runtime_gateway/application/service.py`

#### 2.1 添加默认 stream_mode 常量

```python
# 在文件开头的常量定义区域添加
_DEFAULT_STREAM_MODES: tuple[str, ...] = (
    "values",
    "updates",
    "messages",        # ← 关键：流式消息事件
    "messages-tuple",  # 兼容旧版
    "tools",           # 工具生命周期
    "checkpoints",     # 状态快照
    "events",          # LangChain 回调
)
```

#### 2.2 在 create_thread_run 中设置默认值

```python
async def create_thread_run(...):
    # ... 前面的代码 ...
    
    await self._assert_runtime_target_allowed(
        project_id=project_id,
        assistant_id=assistant_id or "",
        thread=thread,
    )
    
    # ← 新增：设置默认 stream_mode
    next_payload.setdefault("stream_mode", list(_DEFAULT_STREAM_MODES))
    next_payload.setdefault("stream_resumable", True)
    
    command = {"id": "standard-run", "method": "run.start", "params": next_payload}
    # ...
```

## 对比：open-swe 的实现

**open-swe:** `agent/dashboard/thread_api.py`

```python
_DASHBOARD_STREAM_MODES: tuple[str, ...] = (
    "values",
    "updates",
    "messages",
    "messages-tuple",
    "tools",
    "checkpoints",
    "events",
)

# 在enrichment中设置
params.setdefault("stream_mode", list(_DASHBOARD_STREAM_MODES))
params.setdefault("stream_resumable", True)
```

**我们的实现：** 完全一致的设计模式

## 工作流程

### 修复前
```
前端发送消息
  ↓
platform-api 创建 run（没有 stream_mode）
  ↓
LangGraph 只发送 values 快照
  ↓
前端只在完整快照时突然显示（不流式）
  ↓
❌ 用户看不到增量内容
```

### 修复后
```
前端发送消息
  ↓
platform-api 创建 run（包含完整 stream_mode）
  ↓
LangGraph 发送流式事件：
  - messages (增量文本)
  - tools (工具调用)
  - lifecycle (运行状态)
  ↓
前端 @langchain/react 接收并聚合事件
  ↓
✅ 用户看到流式输出
```

## 验证步骤

1. **重启服务**
   ```bash
   bash scripts/local-stack.sh restart
   ```

2. **访问测试**
   - URL: http://127.0.0.1:3000
   - 登录: admin / admin123456
   - 进入 showcase_demo
   - 发送消息："你好"

3. **预期结果**
   - ✅ 应该能看到AI的回复**逐字**流式显示
   - ✅ 而不是突然整段出现
   - ✅ 应该能看到工具调用卡片
   - ✅ 应该能看到运行状态指示器

## 技术要点

### 1. Protocol v2 SSE 架构

```
Browser StreamProvider
  ↓ POST /threads/{id}/stream/events
platform-api (鉴权 + 透传)
  ↓ POST {RUNTIME_URL}/threads/{id}/stream/events
runtime-service LangGraph Server
  ↓ 产生 SSE 事件流
  - event: messages → content-block-delta
  - event: tools → tool-started, tool-finished
  - event: lifecycle → running, completed
  ↓
@langchain/react 解析并聚合
  ↓
React UI 渲染流式内容
```

### 2. stream_mode 的作用

- **LangGraph Server** 根据 `stream_mode` 决定产生哪些事件
- **SSE 订阅** 的 `channels` 决定客户端接收哪些事件
- 两者必须匹配，前端才能正确接收流式内容

### 3. 为什么需要多个 mode

- `messages`: 流式文本（逐token显示）
- `tools`: 工具调用状态（加载中、完成、失败）
- `lifecycle`: 运行状态（isLoading、完成指示）
- `values`: 完整快照（页面刷新后恢复状态）

缺少任何一个，UI 的某部分功能就会失效。

## 相关文件

### 修改的文件
1. `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py`
   - 添加 `state_schema=ShowcaseState`

2. `apps/platform-api/app/modules/runtime_gateway/application/service.py`
   - 添加 `_DEFAULT_STREAM_MODES` 常量
   - 在 `create_thread_run` 中设置默认值

### 参考文档
- `/Users/lijiaxin/PyCharmMiscProject/research/open-swe/docs/open-swe-learning/10-langgraph-sdk-command-and-sse.md`
- open-swe 源码：`agent/dashboard/thread_api.py`

## 总结

**问题本质：** 创建run时缺少 `stream_mode` 配置，导致LangGraph不发送流式消息事件，前端只能等待完整快照，无法实现流式输出。

**解决方案：** 参考 open-swe 的实现，在 platform-api 中设置默认的 stream_mode，包含所有必需的事件频道。

**验证方法：** 手动测试前端是否能看到**逐字**流式显示的AI回复。

---

**修复工程师：** Claude (老王)  
**修复时间：** 2026-09-09 17:15  
**状态：** 等待用户验证流式输出 🌊
