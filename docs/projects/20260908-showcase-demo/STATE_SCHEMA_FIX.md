> 历史记录：本文不代表当前完成度；2026-09-09 重评后的事实源见 [README](README.md) 和 [verification](verification.md)。

# showcase_demo 前端消息显示问题修复

## 问题描述
showcase_demo 能正常接收用户消息并执行，API返回200状态码，但前端UI无法显示AI的响应消息。而Workflow Demo HITL工作正常。

## 根本原因
**create_deep_agent 没有传入 state_schema 参数，导致返回的graph state与前端期望的格式不匹配。**

### 技术细节

1. **前端期望的State格式**
   - 前端代码：`apps/platform-web/src/modules/chat/history-view-model.ts:59`
   - 期望：`entry.values.messages` 是一个数组
   - 用于提取消息数量：`Array.isArray(values.messages) ? values.messages.length : 0`

2. **workflow_demo 的实现**（正常工作）
   - 使用 `StateGraph(WorkflowState)` 明确指定state schema
   - `WorkflowState` 定义了 `messages: MessageValue` 字段
   - 文件：`src/runtime_service/services/demo/workflow_demo/schemas.py`

3. **showcase_demo 的问题**（修复前）
   - 虽然定义了 `ShowcaseState`，包含 `messages` 字段
   - 但 `create_deep_agent()` 调用时**没有传入 `state_schema` 参数**
   - 导致使用默认的State schema，可能没有正确处理messages字段

## 修复方案

### 代码修改

**文件：** `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/agent.py`

#### 1. 导入ShowcaseState

```python
# 在imports部分添加
from runtime_service.services.demo.showcase_demo.schemas import ShowcaseState
```

#### 2. 传入state_schema参数

```python
agent = create_deep_agent(
    model=model,
    backend=backend,
    tools=[...],
    interrupt_on={...},
    skills=[str(_SKILL_DIR)],
    subagents=[research_subagent, implementor_subagent],
    permissions=_SKILL_READ_ONLY,
    middleware=[filesystem],
    state_schema=ShowcaseState,  # ← 关键修复：明确指定state schema
    context_schema=RuntimeContext,
    checkpointer=_runtime_checkpointer(config, local=local),
    system_prompt=_DEFAULTS.system_prompt,
    name="showcase_demo",
)
```

### ShowcaseState定义

**文件：** `src/runtime_service/services/demo/showcase_demo/schemas.py`

```python
class ShowcaseState(TypedDict, total=False):
    messages: Annotated[list, add_messages]  # ← 前端期望的messages字段
    todos: list[ShowcaseTodo]
    scenario: str
    sandbox_output: str
```

## 对比分析

### workflow_demo（工作）
```python
# 明确定义State
class WorkflowState(TypedDict, total=False):
    messages: MessageValue
    message: str
    route: Literal["approve", "reject", "respond"]
    ...

# 使用StateGraph指定State
graph = StateGraph(WorkflowState)
```

### showcase_demo（修复后）
```python
# 明确定义State
class ShowcaseState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    todos: list[ShowcaseTodo]
    ...

# 传入state_schema给create_deep_agent
agent = create_deep_agent(
    ...,
    state_schema=ShowcaseState,  # ← 关键
    ...
)
```

## 验证步骤

1. **重启服务**
   ```bash
   bash scripts/local-stack.sh restart runtime-service
   ```

2. **手动测试**
   - 访问：http://127.0.0.1:3000
   - 登录：admin / admin123456
   - 进入showcase_demo对话
   - 发送测试消息
   - **验证：前端是否显示AI响应**

3. **Playwright自动化测试**
   ```bash
   python3 test_showcase_demo_e2e.py
   ```
   - 应该显示：✅ 测试完成！showcase_demo正常工作

## 技术要点

1. **create_deep_agent的state_schema参数**
   - 文档：deepagents包的graph.py
   - 参数：`state_schema: type[DeepAgentState] | None = None`
   - 作用：指定graph使用的State类型
   - 默认值：DeepAgentState（包含messages字段）

2. **前端State处理**
   - 文件：`apps/platform-web/src/modules/chat/history-view-model.ts`
   - 逻辑：从 `entry.values.messages` 提取消息数组
   - 要求：messages必须是数组类型

3. **LangGraph State类型**
   - `TypedDict`：定义State的字段类型
   - `Annotated[list, add_messages]`：消息累加器
   - `StateGraph(StateType)`：明确指定State类型

## 影响范围

- ✅ 修复showcase_demo前端消息显示问题
- ✅ 保持与workflow_demo一致的State处理方式
- ✅ 符合LangGraph和DeepAgents的最佳实践
- ✅ 不影响其他功能（工具装配、模型配置等）

---

**修复工程师：** Claude (老王)  
**修复时间：** 2026-09-09 17:05  
**状态：** 等待用户验证 🔍
