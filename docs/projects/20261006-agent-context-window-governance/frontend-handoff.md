# 上下文窗口管理 - 前端交接规范（修订版）

> 更新日期：2026-10-07。状态：已完成技术审查与方案修订。后端/Runtime 契约已在隔离环境与真实模型验证通过；前端按本规范开展 F01–F03 实施。严禁抄写 open-swe 的私有 payload 结构与顶层 configurable 路径。

---

## 1. 核心设计准则与交付范围

经过架构审查与评审讨论，前端实施明确以下三大设计基线：

1. **状态呈现轻量化（微胶囊交互）**：
   - 整理状态不占主视口大面板，不干扰消息流与流式打字机，采用轻量微胶囊 Tag / 横条悬浮于输入框上方（或会话视口顶部）；
   - **双重消失机制**：`completed`（已整理）和 `skipped`（无须整理）提示在 **4 秒后平滑淡出**；若用户在此期间**开始输入草稿或发起新动作，立即清除提示**，绝不常驻霸屏。
2. **模型容量配置符合 KISS 原则**：
   - 标准/自定义提供商的**批量创建模式保持原样**，默认不填（后端按未设置处理），避免在模型行列表中堆砌字段导致小屏挤压；
   - 仅在**单模型编辑模式（`edit`）**中提供正整数输入框、常用药丸预设（32K、64K、128K、200K、1M）及“清除”操作。
3. **严格遵守 Clean Architecture 五层解耦**：
   - 提取独立的纯函数模块 `offload-status.ts` 进行事件与状态解析，保障 100% 纯逻辑单测；
   - 底层连接 `useSessionConnection.ts` 保持纯洁，**严禁向其中塞入业务整理事件**；
   - 由 `useChatSession.ts` 通过官方推荐的 `useChannelEffect(stream, ["custom"], ...)` 订阅事件并编排响应式状态。

### 交付任务清单

| 任务 | 模块与文件 | 核心职责 | 状态 |
|---|---|---|---|
| **F01** | `RuntimeModelEditor.vue`<br>`RuntimeModelDetailDialog.vue`<br>`management.ts`<br>`runtime.service.ts` | 模型容量类型补全、单模型编辑正整数输入与 null 清除、详情卡片格式化展示与复制 | 待实施 |
| **F02** | `offload-status.ts` (新建)<br>`useChatSession.ts`<br>`ChatSession.vue` | 纯函数事件解析、`useChannelEffect` custom 订阅、4秒+输入双重消失定时器、轻量微胶囊展示 | 待实施 |
| **F03** | `run-actions.ts`<br>`ThreadActionsMenu.vue`<br>`useChatSession.ts`<br>`workspace.ts` | `capabilities.conversation_offloading` 解析、菜单前置条件与置灰、`kind="offload"` 幂等登记、严格 `platform_runtime` 路径 | 待实施 |

---

## 2. 现有入口与复用边界

所有路径均相对仓库根目录：

| 文件 | 职责与改动点 | 避坑与边界 |
|---|---|---|
| `apps/platform-web/src/types/management.ts` | `RuntimeModelItem` 补齐 `context_window_tokens?: number | null` | 只读与展示 DTO |
| `apps/platform-web/src/services/runtime/runtime.service.ts` | `RuntimeModelInput` 补齐 `context_window_tokens?: number | null` | PATCH payload 必须支持 `null` 传递 |
| `apps/platform-web/src/modules/runtime/components/RuntimeModelEditor.vue` | 仅在 `activeMode === 'edit'` 增加容量输入区、快捷预设药丸和清除操作 | 批量创建模式保持省略；输入必须做客户端 `> 0` 整数校验 |
| `apps/platform-web/src/modules/runtime/components/RuntimeModelDetailDialog.vue` | 详情指标网格增加“上下文窗口”卡片 | 有值格式化为如 `128,000 (128K)` 并支持复制，无值显示“未设置” |
| `apps/platform-web/src/types/workspace.ts` | `WorkspaceCapabilities` 补齐 `conversation_offloading?: boolean` | 来自 `/api/langgraph/threads/{thread_id}/capabilities` |
| `apps/platform-web/src/services/threads/session.service.ts` | `ChatState` 补齐 `conversation_offloading?: ConversationOffloadPersistedState` | 仅用于快照只读水合，不触发动态假 loading |
| `apps/platform-web/src/modules/chat/offload-status.ts` **(新建)** | 纯函数模块：定义状态类型、解析 `custom` 帧、过滤 root namespace、映射文案与图标 | 纯逻辑，无 UI 与响应式依赖，Vitest 单测 100% 覆盖 |
| `apps/platform-web/src/modules/chat/run-actions.ts` | `RunAction.kind` 增加 `"offload"`；复用 `begin/dispatch/retry` | 幂等 Key 沿用 `run:<uuid>`；`platformCommand` 保持原样拦截 |
| `apps/platform-web/src/modules/chat/composables/useChatSession.ts` | 消费 `offload-status.ts`，挂载 `useChannelEffect(stream, ["custom"], ...)`，暴露 `offloadState` 与 `offloadConversation()` | 维护双重消失定时器；维护 Run 结束后禁止触发 prompt drain 与推荐问题 |
| `apps/platform-web/src/modules/chat/components/ThreadActionsMenu.vue` | 增加“整理上下文”项，由 `conversation_offloading` 能力控制可见性，状态冲突时置灰 | 依赖 `canComment`、`!busy`、`!hasPendingInterrupts`、`hasConversationStarted` |
| `apps/platform-web/src/modules/chat/components/ChatSession.vue` | 在输入框上方（`ChatComposer` 区域）引入轻量微胶囊展示组件 | 绝不能依赖 `ChatAgentStatusBar.vue`（其仅在中断或报错时渲染） |
| `apps/platform-web/src/modules/dear-agent/components/DearAgentSession.vue` | 复用主 `ChatSession`，无须二次开发 | 自动继承整理状态与菜单操作 |

---

## 3. 模型容量配置契约 (F01)

### 3.1 字段规范与校验

- **字段名**：`context_window_tokens`
- **类型**：`number | null`
- **语义**：端点模型支持的最大总上下文 Token 上限（严格区别于生成输出参数 `max_tokens`）。
- **后端校验硬规则**：
  - 后端为 Pydantic `Field(default=None, gt=0, strict=True)`；
  - 必须是严格大于 0 的整数；输入 `0`、负数、浮点数或字符串会导致后端 422 校验失败；
  - **更新逻辑**：若前端传 `undefined`，后端 `exclude_unset` 视为未修改；若前端传 `null`，后端将其从数据库清除（设为 NULL）。

### 3.2 交互设计（`RuntimeModelEditor.vue`）

1. **批量创建模式（Standard / Custom）**：
   - 保持现有极简表单，不增加容量列，默认不提交该字段。
2. **单模型编辑模式（Edit）**：
   - 在 Base URL 下方增加独立表单项：`上下文窗口容量 (Tokens)`；
   - **预设药丸按钮**：`[32K (32768)]`、`[64K (65536)]`、`[128K (131072)]`、`[200K (200000)]`、`[1M (1048576)]`，点击自动填入对应数值；
   - **输入框**：支持手动键入，限制仅允许正整数（失焦或输入时过滤非法字符）；
   - **清除操作**：输入框后方提供“设为未设置”或“清除”快捷按钮，点击后清空输入框，提交时 payload 设为 `context_window_tokens: null`；
   - **保存前校验**：若输入了非正整数，阻止提交并给出明确红色提示 `“上下文窗口必须为大于 0 的整数”`。

### 3.3 详情展示（`RuntimeModelDetailDialog.vue`）

- 在指标网格中新增卡片：
  - 标题：`上下文窗口 (Context Window)`；
  - 内容：若有值，展示格式化文本如 `128,000 Tokens (128K)`；若未设置，展示浅灰字体 `未设置`；
  - 提供快捷复制数值按钮。

---

## 4. 手动整理动作与请求 (F03)

### 4.1 协议与参数构建

手动整理是一次无副作用的维护 Run。发起必须通过 SDK 的 `stream.submit` 并在 `run-actions` 中注册：

```http
POST /api/langgraph/threads/{thread_id}/commands
x-project-id: <当前项目 ID>
Idempotency-Key: run:<唯一 UUID>
Content-Type: application/json
```

```json
{
  "id": 1,
  "method": "run.start",
  "params": {
    "assistant_id": "dearflow_agent",
    "input": {},
    "config": {
      "configurable": {
        "platform_runtime": {
          "offload_conversation": true
        }
      }
    },
    "durability": "sync",
    "stream_resumable": true,
    "version": "v3",
    "on_disconnect": "continue"
  }
}
```

> ⚠️ **高危避坑：**
> 1. 严禁仿照 open-swe 写成顶层 `configurable.offload_conversation: true`！必须严格放在 `configurable.platform_runtime` 命名空间下！
> 2. `input` 必须固定为 `{}`（空对象），严禁携带消息、附件或旧 checkpoint。
> 3. `assistant_id` 必须是图 ID（如 `dearflow_agent` 或 `showcase_demo`），不是平台 Agent 管理 UUID。

### 4.2 前置检查与菜单入口（`ThreadActionsMenu.vue`）

1. **可见性门禁**：
   - 依赖 Thread capabilities 中的 `conversation_offloading === true`；
   - 若接口返回 `false`、未配置或获取失败，**隐藏“整理上下文”菜单项**，不占用视觉空间。
2. **可用性与置灰门禁**：
   - 以下任意条件满足时，菜单项处于 `disabled`（置灰）态，并通过 Tooltip 说明原因：
     - 当前会话无消息（`!hasConversationStarted`）：提示 *“空会话无需整理”*；
     - 会话正在执行（`busy` / `isSessionRunning`）：提示 *“会话正在执行，无法整理”*；
     - 当前存在待处理审批或澄清（`hasPendingInterrupts`）：提示 *“请先处理当前审批”*；
     - 当前无评论权限（`!canComment`）：提示 *“没有此会话的发言权限”*；
     - 存在待确认 unknown 动作：提示 *“上一动作结果确认中”*。
3. **动作执行与互斥**：
   - 用户点击后调用 `useChatSession` 暴露的 `offloadConversation()`；
   - 登记 `actions.begin(threadId, "offload", {})`；
   - 触发维护 Run 期间，会话进入 `busy` 状态，输入框处于禁用态；
   - 用户可在执行中点击 `Stop` 取消整理 Run，取消后整理状态安全重置。

---

## 5. 事件消费与状态生命周期 (F02)

### 5.1 事件层级与解析（严禁照搬 open-swe）

后端通过官方 `custom` 通道广播整理进度。真实 v3 Protocol 的 SDK 帧如下：

```json
{
  "method": "custom",
  "params": {
    "namespace": [],
    "timestamp": 1791319429958,
    "data": {
      "type": "conversation_offloading",
      "status": "started",
      "trigger": "manual",
      "operation_id": "step-uuid-1",
      "run_id": "run-uuid-1"
    }
  },
  "seq": 28
}
```

> ⚠️ **关键契约差异：**
> - **SDK 暴露位置**：数据直接挂载在 `event.params.data`，**绝对没有额外的 `.payload` 属性**！如果按 open-swe 访问 `event.params.data.payload` 将导致读取为 `undefined`！
> - **命名空间过滤**：必须严格判断 `event.params.namespace.length === 0`，非空 namespace 属于子 Agent 内部操作，根会话一律忽略。

### 5.2 状态流转与文案映射

| 事件 status | 触发阶段 | 界面文案 | 表现形式 | 生命周期与消失逻辑 |
|---|---|---|---|---|
| `started` | 整理开始 | “正在整理上下文...” | 微型 Spinner + 蓝色微胶囊 | 持续至步骤结束，保持 Run busy 语义 |
| `completed` | 整理成功 | “上下文已整理” | Check 图标 + 绿色微胶囊 | **启动 4 秒自动淡出定时器**；若用户在此期间**输入草稿或发送消息，立即清除** |
| `skipped` | 无需整理 | “暂无需要整理的历史” | Info 图标 + 灰色微胶囊 | **启动 4 秒自动淡出定时器**；用户发起新动作时立即清除 |
| `failed` | 整理失败 | “上下文整理失败” | Alert 图标 + 红色微胶囊 | 展示安全错误，提供关闭按钮，不自动盲重试 |

### 5.3 历史恢复与水合隔离

- `values.conversation_offloading` 仅保存最近一次成功/跳过的持久终态：
  ```json
  {
    "type": "conversation_offloading",
    "status": "completed",
    "operation_id": "step-uuid-1",
    "run_id": "run-uuid-1",
    "history_saved": true
  }
  ```
- **水合隔离规则**：
  - 切换 Thread 或从缓存水合时，读到的 `values.conversation_offloading` 仅作为静态会话元数据；
  - **切回会话严禁重新弹出“正在整理”Spinner 或已完成 Toast**；
  - 只有当前活跃 Run 产生的实时事件才驱动动态微胶囊状态机。

### 5.4 后处理副作用隔离

维护 Run 无论成功还是失败，均受以下隔离保护：
1. **不触发推荐问题**：[useFollowUpSuggestions.ts](file:///Users/lijiaxin/PyCharmMiscProject/ai-agent-platform/apps/platform-web/src/modules/chat/composables/useFollowUpSuggestions.ts) 不会因为维护 Run 完成而请求新建议；
2. **不触发排队消息消费**：不会触发持久消息队列出队（`drainNextQueuedItem`）；
3. **保留草稿与附件**：输入框中已有的文本草稿、选中的附件或待上传图片**原封不动保留**，不被清空或作为消息误发。

---

## 6. 错误反馈标准 (符合 error-envelope)

前端根据标准错误码转换为友好中文提示，严禁将原始服务端堆栈直接抛给用户：

| 错误码 / 场景 | HTTP 状态 | 前端反馈方式 | 提示文案 |
|---|---|---|---|
| `context_offload_not_supported` | 409 | Toast (warning) | 当前智能体不支持上下文手动整理 |
| `context_offload_empty_thread` | 409 | 菜单禁用 Tooltip / Toast | 当前会话尚无历史消息，无需整理 |
| `context_offload_input_invalid` | 400 | Toast (error) | 整理请求参数非法，请重试 |
| `context_offload_pending_input` | 409 | Toast (warning) | 当前存在排队或待发送消息，请完成后再试 |
| `context_offload_interrupt_pending` | 409 | Toast (warning) | 当前会话存在等待审批的动作，请先处理 |
| `thread_active_run_conflict` | 409 | Toast (warning) | 当前会话正在执行中，请等待其结束 |
| `runtime.context.capacity_unknown` | 400 | Toast (error) | 当前模型未配置上下文容量，请联系管理员配置 |
| 5xx / 408 / 网络异常 | 5xx | 状态机转为 unknown | 整理请求已发出但结果待确认，正在核实会话状态 |

---

## 7. UI 与验收清单 (对标 Playbook & V02B)

### 7.1 功能验收矩阵

- [ ] **F01 模型容量**：
  - [ ] `RuntimeModelEditor.vue` 批量创建模式保持原样，无冗余字段挤压；
  - [ ] 编辑模式下支持配置正整数容量，药丸预设（32K/64K/128K/200K/1M）点击准确填充；
  - [ ] 点击“清除”可置空，向后端提交 `context_window_tokens: null`；未修改时传 `undefined`；
  - [ ] 客户端硬门禁拦截 0、负数、浮点数与字符输入；
  - [ ] `RuntimeModelDetailDialog.vue` 正确显示格式化容量或“未设置”，支持复制。
- [ ] **F02 整理状态微胶囊**：
  - [ ] 纯函数模块 `offload-status.ts` Vitest 单测 100% 通过（涵盖 v3 帧提取、namespace 过滤、文案映射）；
  - [ ] 整理开始时出现“正在整理上下文...”微胶囊；
  - [ ] 整理完成/跳过显示对应文案，**4 秒后平滑淡出**；
  - [ ] 在淡出等待期间，用户键入新输入或发起发送，**微胶囊立即消失**；
  - [ ] 切换会话、页面重连或 410 水合时，不出现虚假 Spinner。
- [ ] **F03 手动维护动作**：
  - [ ] `WorkspaceCapabilities` 正确反序列化 `conversation_offloading` 字段；
  - [ ] 当智能体具备能力时，`ThreadActionsMenu` 渲染“整理上下文”；缺失能力时自动隐藏；
  - [ ] 空会话、执行中、待审批、无权限时，菜单项正确置灰并附带原因 Tooltip；
  - [ ] 手动整理使用空 input，成功发起维护 Run，不生成用户/AI 消息气泡，不冲刷草稿和推荐问题；
  - [ ] 整理过程中支持点击 Stop 正常取消。

### 7.2 视觉与多端基线

- [ ] **多视口测试**：390×844 (Mobile)、1024×768 (Tablet)、1440×900 (Desktop) 菜单与微胶囊无布局溢出；
- [ ] **多主题测试**：浅色模式与暗黑模式（`dark`）对比度符合 WCAG AA 基线；
- [ ] **自动化门禁**：`pnpm test` 全量单测通过，`pnpm vue-tsc --noEmit` 0 错误，`pnpm build` 生产打包通过。
