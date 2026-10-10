# 前端交接：通用后台非阻塞任务能力（v2 工业级设计方案）

> **状态：实现版 v2 交接（老王技术审查订正版）。** 修复了原 v1 方案中「Stop 报告 Schema 丢字段」、「新 Run 发现职责割裂与双重轮询」、「SFC 组件颗粒度超标」、「日志 ANSI 转义乱码」、「退出码为负数时校验崩溃」五大严重缺陷。F01-F11 已实施，[B01 引擎只读回查门禁](engine-handoff.md) 已解除；F12 仍需 T10 全栈联合验收，正式启用另需部署门禁。本页保留原设计与验收契约，表中的“拟新增”等不表示现在仍需从零开发。

**2026-10-10 增量接续：** 非 Docker 兼容 A/B 后端已完成，前端只接续 ABF01-ABF03；具体 Worktree、代码入口、能力语义、恢复提示与浏览器草稿见 [A/B 前端交接](local-compatibility-frontend-handoff.md)。

---

## 1. 工作范围与界面入口

在现有 Chat WorkspacePanel 中增加第四个选项卡：**「任务」**（与「工作区」「产物库」「终端」并列）。
展示当前 Thread 授权范围内的后台任务列表、真实运行状态、有界只读纯文本日志、单任务取消确认，以及展示服务端创建的完成通知 Run。

**硬性系统约束：**
1. **服务端绝对主导**：命令启动、监控、容器回收、通知与完成 Run 均由服务端全权负责。前端不新增 shell 启动表单、不自己派发完成 Run、不用 localStorage 模拟长任务队列、不通过 `send("任务完成继续")` 伪造用户发言、不自动 approve/resume。
2. **轻量与解耦**：任务不是普通 ToolResult 的持续运行态，不是独立子 Agent，不是定时任务，更不是 PTY 交互终端。
3. **视觉与设计规范依从**：严格遵守 `apps/platform-web/docs/` 下的 `frontend-development-playbook.md`、`control-plane-page-standard.md` 与 `frontend-visual-baseline-standard.md`。沿用现有的 Workspace/Inspector 范式、共享组件（BaseIcon、pw-panel 系列、BaseButton、Tooltip、ConfirmModal 等），不新增左侧全局大导航，不另起炉灶建立独立的后台任务中心。

---

## 2. 最小代码落点与单一职责拆分

为严格遵守 Playbook 中 **`<script setup>` ≤ 150 行、`<template>` 嵌套 ≤ 5 层、Props ≤ 6 个** 的代码颗粒度铁律，彻底杜绝单文件膨胀成数百行的面条代码，本次改动代码落点精细化拆分如下：

| 文件路径（相对 `apps/platform-web/`） | 类型 | 职责与设计边界 |
|---|---|---|
| `src/services/threads/background-tasks.service.ts` | **拟新增** | 纯底层 HTTP 请求层：`listBackgroundTasks`、`getBackgroundTask`、`getBackgroundTaskOutput`、`cancelBackgroundTask`。统一复用 `platformHttpClient`、带 `x-project-id`、透传 `AbortSignal`、执行 Zod DTO 校验、统一经 `extractPlatformHttpError` 解析异常。 |
| `src/modules/chat/background-tasks/types.ts` | **拟新增** | **工业级 Zod Schema 与 TypeScript 类型定义**：定义 TaskV1、TaskListV1、OutputV1、CancelResponseV1，严谨兼容负信号退出码、带时区 RFC3339 日期、safe count 上限、12 个白名单 reason_code。陌生字段 strip，核心字段缺失/非法直接拒绝。 |
| `src/modules/chat/stop/types.ts` | **必须修改** | **【严重缺陷修复】** 在现存 `stopReportSchema` 中显式扩展 `background_tasks: backgroundStopSummarySchema.nullable().optional()`，防止 `.strip()` 抹除后端返回的后台停止快照数据。 |
| `src/utils/ansi.ts` | **拟新增** | 极简纯函数 `stripAnsi(text: string): string`，正则过滤终端 ANSI 转义序列（如 `\u001b[32m`、`\r`），确保纯文本 `<pre>` 渲染无乱码。零外部依赖。 |
| `src/modules/chat/composables/useBackgroundTasks.ts` | **拟新增** | **单一数据源（Single Source of Truth）核心状态机**：挂载于 `ChatSession` 顶层生命周期，通过 `provide/inject` 共享给工作区。管理任务列表/分页、5 秒全局低频探针（当 `has_unresolved=true` 且页面可见）、新 Run 发现缓冲队列（LLM busy 避让）、导出会话级 `hasActiveBackgroundTasks` 供 Stop 按钮消费；提供单任务日志按需加载和取消单飞保护。 |
| `src/components/workspace/BackgroundTasksPanel.vue` | **拟新增** | 工作区「任务」Tab 主体面板容器：负责 Tab 头部操作栏、列表容器、分页栏、空/错/加载/不可用态。通过 `inject` 消费 `useBackgroundTasks`。代码行数 ≤ 150 行。 |
| `src/components/workspace/BackgroundTaskItem.vue` | **拟新增** | 单个任务卡片子组件：展示状态微胶囊、运行/超时倒计时、退出码、交付状态徽章、操作按钮区（查看日志、取消）。行数 ≤ 150 行。 |
| `src/components/workspace/BackgroundTaskLogViewer.vue` | **拟新增** | 单任务有界只读日志查看抽屉/区域：纯文本展示、ANSI 清洗、64KiB/保留字节截断警告条、复制按钮、加载与不可用状态。行数 ≤ 150 行。 |
| `src/components/workspace/WorkspacePanel.vue` | **修改** | 新增「任务」Tab 选项卡（当 `capabilities?.background_tasks` 时展示）；支持在 Tab 按钮上显示活跃运行中微胶囊红点；自适应移动端与宽屏拖拽。 |
| `src/modules/chat/components/ChatSession.vue` | **修改** | 顶层实例化 `useBackgroundTasks` 并 provide 给子树；在 LLM 空闲但后台有活跃任务时保持顶部 Stop 按钮可见可达；监听新 Run 发现事件并受控转交 SDK。 |
| `src/modules/chat/composables/useChatSession.ts` | **修改** | 补充受控接收点 `acceptDiscoveredRun(runId: string)`：若前台正忙或存在 HITL 中断则进入暂存区，待前台空闲后触发 `service.runs()` 核实并沿 SDK 订阅，绝不直接冲掉当前活动流。 |
| `src/modules/chat/composables/useThreadStopControl.ts` | **修改** | Stop 控制器接入后台活跃状态判断；Stop 成功且返回的 report 含 `background_tasks` 时，将其注入停止确认报告，区分 LLM 停止与后台容器清理。 |
| `src/types/workspace.ts`、`src/composables/useThreadWorkspace.ts` | **修改** | 扩展 `WorkspaceCapabilities` 接口加法字段：`background_tasks?: boolean` 与 `background_tasks_start_enabled?: boolean`，缺省默认 false。 |
| `src/modules/chat/components/ToolResult.vue` | **仅必要时** | 启动 ACK 工具调用回执链接到对应后台任务 Tab；历史工具卡片保持既有快照，不持续覆写旧 ToolMessage。 |

---

## 3. 实际接口与工业级 Zod Schema 契约

所有公开接口均通过 Platform API 网关，Header 必须带当前 `x-project-id`。
禁止直连 Runtime Service，禁止前端自行签发 Token。

### 3.1 HTTP 路由清单

| 方法 / 路径 | 请求参数 / Body | 成功响应 | 关键语义与约束 |
|---|---|---|---|
| `GET /api/langgraph/threads/{thread_id}/background-tasks` | `limit=20` (1-100), `before=<cursor>` | 200 `TaskListV1` | 当前 Thread 授权范围的任务列表，按 `created_at` 倒序。`has_unresolved` 全局计算，不受当前分页遮蔽。 |
| `GET /api/langgraph/threads/{thread_id}/background-tasks/{task_id}` | 无 | 200 `TaskV1` | 读取单个任务权威快照。HTTP 200 不等于命令成功。 |
| `GET /api/langgraph/threads/{thread_id}/background-tasks/{task_id}/output` | 无 | 200 `OutputV1` | 读取单次最多 64KiB 的有界文本日志快照。仅在用户展开详情时按需拉取。 |
| `POST /api/langgraph/threads/{thread_id}/background-tasks/{task_id}/cancel` | Body `{}`<br>Header `Idempotency-Key` (1-128字符) | 202 `TaskV1` | 接受取消意图。状态置为 `cancel_requested`，清理确认以服务端 `cleanup_state=confirmed` 为准。 |

### 3.2 工业级 Zod Schema 实现规范（`types.ts`）

```typescript
import { z } from 'zod';

// 1. 安全数值与边界
export const safeCountSchema = z.number().int().nonnegative().max(Number.MAX_SAFE_INTEGER);

// exit_code 必须兼容进程被信号终止时的负值（-255 ~ 255）及 null
export const exitCodeSchema = z.number().int().min(-255).max(255).nullable();

// 2. Reason Code 白名单枚举（与后端 Pydantic 严格对齐）
export const BACKGROUND_TASK_REASONS = [
  'background_task_control_unavailable',
  'background_task_resource_missing',
  'background_task_start_unconfirmed',
  'background_task_deadline_exceeded',
  'background_task_oom',
  'background_task_command_failed',
  'background_task_disabled',
  'background_task_delivery_expired',
  'background_task_delivery_unavailable',
  'background_task_denied',
  'background_task_thread_busy',
  'background_task_approval_pending',
] as const;
export type BackgroundTaskReason = (typeof BACKGROUND_TASK_REASONS)[number];

// 3. 任务核心枚举
export const TASK_STATUSES = [
  'starting',
  'running',
  'succeeded',
  'failed',
  'timed_out',
  'cancel_requested',
  'cancelled',
  'unknown',
] as const;
export type TaskStatus = (typeof TASK_STATUSES)[number];

export const CLEANUP_STATES = ['not_required', 'pending', 'confirmed', 'unconfirmed'] as const;
export type CleanupState = (typeof CLEANUP_STATES)[number];

export const DELIVERY_STATES = [
  'not_ready',
  'pending',
  'dispatching',
  'accepted',
  'blocked',
  'suppressed',
  'expired',
  'unknown',
] as const;
export type DeliveryState = (typeof DELIVERY_STATES)[number];

export const ALLOWED_ACTIONS = ['read', 'logs', 'cancel'] as const;
export type AllowedAction = (typeof ALLOWED_ACTIONS)[number];

// 4. 子结构 Schema
export const taskOutputMetaSchema = z.object({
  available: z.boolean(),
  retained_bytes: z.number().int().nonnegative().max(1048576), // 最大 1MiB
  omitted_bytes: safeCountSchema,
  truncated: z.boolean(),
  updated_at: z.string().datetime({ offset: true }).nullable(),
}).strip();

export const taskDeliverySchema = z.object({
  state: z.enum(DELIVERY_STATES),
  event_id: z.string().uuid().nullable(),
  run_id: z.string().uuid().nullable(),
  reason_code: z.enum(BACKGROUND_TASK_REASONS).nullable(),
}).strip();

// 5. 单任务 TaskV1 Schema
export const taskV1Schema = z.object({
  version: z.literal(1),
  task_id: z.string().uuid(),
  thread_id: z.string().uuid(),
  graph_id: z.string().min(1).max(128),
  origin_run_id: z.string().uuid(),
  status: z.enum(TASK_STATUSES),
  reason_code: z.enum(BACKGROUND_TASK_REASONS).nullable(),
  exit_code: exitCodeSchema,
  created_at: z.string().datetime({ offset: true }),
  started_at: z.string().datetime({ offset: true }).nullable(),
  finished_at: z.string().datetime({ offset: true }).nullable(),
  deadline_at: z.string().datetime({ offset: true }),
  updated_at: z.string().datetime({ offset: true }),
  cleanup_state: z.enum(CLEANUP_STATES),
  output: taskOutputMetaSchema,
  delivery: taskDeliverySchema,
  allowed_actions: z.array(z.enum(ALLOWED_ACTIONS)).max(3),
}).strip();
export type TaskV1 = z.infer<typeof taskV1Schema>;

// 6. 任务列表 TaskListV1 Schema
export const taskListV1Schema = z.object({
  version: z.literal(1),
  thread_id: z.string().uuid(),
  items: z.array(taskV1Schema).max(100),
  next_cursor: z.string().max(256).nullable(),
  has_unresolved: z.boolean(),
  latest_delivery_run_id: z.string().uuid().nullable(),
}).strip();
export type TaskListV1 = z.infer<typeof taskListV1Schema>;

// 7. 有界日志 OutputV1 Schema
export const outputV1Schema = z.object({
  version: z.literal(1),
  task_id: z.string().uuid(),
  thread_id: z.string().uuid(),
  available: z.boolean(),
  text: z.string().max(65536), // 最多 64KiB 文本
  retained_bytes: z.number().int().nonnegative().max(1048576),
  omitted_bytes: safeCountSchema,
  truncated: z.boolean(),
  updated_at: z.string().datetime({ offset: true }).nullable(),
}).strip();
export type OutputV1 = z.infer<typeof outputV1Schema>;

// 8. Stop 报告后台清理摘要 Schema（必须合入 stop/types.ts）
export const backgroundStopSummarySchema = z.object({
  target_count: safeCountSchema,
  cleanup_confirmed_count: safeCountSchema,
  cleanup_unconfirmed_count: safeCountSchema,
  notifications_suppressed_count: safeCountSchema,
  truncated: z.boolean(),
}).strip();
export type BackgroundStopSummary = z.infer<typeof backgroundStopSummarySchema>;
```

---

## 4. 状态正交矩阵与前端展示策略

后台长任务涉及三个正交维度的状态：
1. **命令执行状态 (`status`)**
2. **容器资源清理状态 (`cleanup_state`)**
3. **完成通知交付状态 (`delivery.state`)**

前端界面严禁把三者混为一个单一 spinner，必须按以下正交矩阵组合展示：

| 维度 | 枚举值 | 推荐 Badge 样式 | 用户感知文案 | 交互行为与说明 |
|---|---|---|---|---|
| **命令状态 (`status`)** | `starting` | 黄色微胶囊 | 正在启动容器 | 允许已授权的取消；不标命令成功 |
| | `running` | 蓝色微胶囊 (微脉冲动效) | 任务执行中 | 显示已运行时间与期限；允许看日志/取消 |
| | `succeeded` | 绿色微胶囊 | 命令执行成功 | 显示 exit 0；完成 Run 可能仍待处理 |
| | `failed` | 红色微胶囊 | 命令执行失败 | 展示安全 reason_code 及 exit_code，不自动重试 |
| | `timed_out` | 橙色微胶囊 | 命令执行超时 | 单独命令 deadline 超时，与模型/会话超时区分 |
| | `cancel_requested` | 灰色微胶囊 (转圈) | 正在取消中... | 禁用重复取消，等待服务端 GET 对账 |
| | `cancelled` | 灰色微胶囊 | 任务已取消 | 服务端确认后展示；警告文件副作用不回滚 |
| | `unknown` | 紫灰色微胶囊 | 状态待确认 | 保留刷新入口，禁止当失败后自动重新启动 |
| **清理状态 (`cleanup_state`)** | `pending` | 文本小标签 | 资源回收中 | 命令已终态但 Docker 容器仍在回收 |
| | `confirmed` | 隐藏或微提示 | 容器已释放 | 正常终态 |
| | `unconfirmed` | 警告微标签 | 清理未确认 | 明确提示容器/进程可能残留，不宣称已释放 |
| **交付状态 (`delivery.state`)** | `not_ready` | 隐藏 | 运行中待交付 | 正常前置状态 |
| | `pending` | 浅蓝徽章 | 通知待生成 | 命令已完成，等待 Agent 线程空闲或 HITL 恢复 |
| | `accepted` | 蓝紫徽章 (带外链图标) | 通知已受理 (Run) | 关联新 Run ID；点击可在主对话中定位新 Run |
| | `suppressed` | 浅灰徽章 | 通知已抑制 | 用户停止或取消后抑制通知模型，不额外扣费 |
| | `blocked` / `expired` | 警告徽章 | 通知未发送 | 权限不足或超期；输出结果仍可查询 |

---

## 5. 架构拓扑：单例状态机与新 Run 发现机制

### 5.1 单一数据源（Single Source of Truth）拓扑

为了彻底避免组件销毁导致轮询中断，以及多个组件实例化引发的双重轮询问题，状态实例在树中的挂载必须遵循以下拓扑：

```
                    ChatSession.vue
                           │
       ┌───────────────────┴───────────────────┐
       ▼                                       ▼
useChatSession.ts                      useBackgroundTasks.ts (单例实例化)
(流式对话/SDK Controller)                       │
       │                                ├── 负责 5s 低频探针 (has_unresolved)
       │                                ├── 负责新 Run 发现与缓冲队列
       │                                ├── 导出 hasActiveBackgroundTasks
       │                                │
       │◄───(转交新 Run: acceptDiscoveredRun)─┤
       │                                │
       │                        provide('backgroundTasks')
       │                                │
WorkspacePanel.vue                      │
       │                                │
       ▼                                ▼
BackgroundTasksPanel.vue ◄──── inject('backgroundTasks')
(仅作为视图层渲染)
```

### 5.2 新 Run 发现与 LLM Busy 避让机制

1. **5 秒低频探针**：
   - 仅当当前 Thread 的 `has_unresolved === true` 时保留 5 秒轮询定时器。
   - 页面隐藏 (`document.hidden`) 或网络离线时暂停定时器；页面重新可见或网络恢复立即拉取一次。
   - `has_unresolved === false` 且所有任务进入终态后，立即清除探针定时器。
2. **发现新 Run 时的平滑转交（避让逻辑）**：
   - 当检测到新的 `latest_delivery_run_id` 或任务中的 `delivery.run_id`（按 `threadId + run_id` 集合去重）时：
   - **若前台 LLM 正在生成（`stream.isLoading` 或 `active(run.value)`）或存在待处理的 HITL 人工审批**：
     - **绝对禁止冲刷或覆盖当前 `run.value`！**
     - 将新 Run ID 暂存至 `pendingDeliveryRunIds` 缓冲队列。
   - **若前台 LLM 处于空闲状态（Idle）**：
     - 将暂存的或新发现的 Run ID 提交给 `useChatSession::acceptDiscoveredRun(runId)`。
     - 复用现有的 `service.runs(threadId)` 和 SDK 订阅机制挂接新 Run，消息沿 Transcript 原序追加，显示平台标准的系统完成通知胶囊。

### 5.3 后台任务完成通知的系统微胶囊规范（消灭假用户气泡）

1. **背景根因与问题**：
   - 服务端后台任务完成后，为唤醒 Agent 总结输出，发起 completion run，注入首条触发消息：
     `Workspace background task <task_id> finished: status=<status>, exit_code=<code-or-null>...`
   - 后端为遵循 LangGraph 状态机 trigger 契约，将该输入标记为 `role: "user"`（ID 以 `background:` 开头）。
   - 前端若仅根据 `type === 'human'` 渲染，会将其误画为右侧深蓝色用户消息气泡并挂载「编辑重发」按钮，破坏用户认知。

2. **识别与拦截契约（双重断言）**：
   - **断言 1（ID 命名空间）**：`message.id` 包含 `background:` 前缀（或 raw message id 命中）。
   - **断言 2（内容模式匹配）**：消息文本匹配正则 `/^Workspace background task\s+([a-f0-9-]+)\s+finished:\s+status=([a-z]+),\s+exit_code=(-?\d+|None|null)/i`。
   - 命中任一断言时，前端必须将该项判定为 `system` 消息，打标 `systemType: "background_completion"`，严禁判定为 `author: "user"`。

3. **视觉与交互呈现规范**：
   - **布局**：居中微胶囊呈现，对齐平台 `.pw-chat-system-message` 样式标准，浅色/深色主题适配。
   - **语义化状态与文案**：
     - `succeeded`：绿勾图标，展示“后台任务已完成: #<short_id> · 退出码: 0”
     - `failed`：红叉/警告图标，展示“后台任务执行失败: #<short_id> · 退出码: <code-or-null>”
     - `timeout`：黄色时钟图标，展示“后台任务超时终止: #<short_id>”
     - `cancelled`：灰色禁止图标，展示“后台任务已取消: #<short_id>”
   - **操作剥离与联动**：
     - **严禁渲染**：编辑、重试、新建分支等用户级写操作按钮。
     - **快捷入口**：提供可点击的“在任务面板查看详情”操作，可联动触发打开 Workspace 右侧任务 Tab。
     - **折叠原始提示**：提供轻量可折叠展开面板查看原始 trigger prompt，默认收起。
   - **回合连续性**：通知胶囊紧随前序会话出现，其下方紧接着渲染 Agent 对该任务的总结性回答（`turn.answer`）。

---

## 6. 取消、只读日志、Stop 按钮与安全策略

### 6.1 单任务取消状态机（F04）
- 用户点击取消触发通用 `ConfirmModal` 确认弹窗。
- 弹窗必须明确包含副作用警告：`“取消命令将向正在运行的容器发送停止信号。已经创建的文件或修改的环境状态不会自动回滚。”`
- 取消请求发送时必须生成唯一的 `Idempotency-Key`，并将该任务的 `cancelInFlight` 置为 true（禁用二次点击）。
- 接口返回 202 后，状态更新为 `cancel_requested`。若发生网络超时或 502/504，前端禁止将任务标记为失败或已取消，而是通过单任务 GET 接口重查对账。

### 6.2 有界只读日志查看与 ANSI 过滤（F05）
- **按需拉取**：只有用户主动点击展开或打开某个任务的日志抽屉时，才调用 `GET .../output`。
- **纯文本与 ANSI 清洗**：
  - 日志渲染统一使用 `<pre class="font-mono text-xs overflow-x-auto whitespace-pre-wrap select-text">`。
  - 严禁使用 `v-html`，严禁执行 Markdown 脚本，禁止终端自动链接。
  - 使用 `src/utils/ansi.ts::stripAnsi` 清洗控制字符（如 `\u001b[32m`、`\r`），杜绝乱码。
- **截断与容量警示**：
  - 若 `output.truncated === true` 或 `output.omitted_bytes > 0`，在日志顶部呈现明显的警告栏：`“日志已截断，服务器保留 ${formatBytes(retained_bytes)}，已忽略 ${formatBytes(omitted_bytes)}。单次最多显示 64 KiB 最新日志。”`
  - 若 `output.available === false`，展示灰色不可用状态提示：`“日志源已释放或暂不可用”`，不将其视作 HTTP 请求失败。
- **活动任务有限轮询**：若当前打开详情的任务处于 `running` 状态，以 3 秒间隔拉取日志；抽屉关闭或任务终态时，立即销毁日志轮询 timer。

### 6.3 LLM 空闲时的会话级 Stop 控制器（F10）
- **Stop 按钮显示条件**：
  ```typescript
  const canShowStopButton = computed(() => {
    return isLlmActive.value || backgroundTasks.hasActiveBackgroundTasks.value;
  });
  ```
- **文案与提示**：
  - 当 LLM 活跃时，展示常规「停止生成」；
  - 当 LLM 空闲但后台任务运行时，展示「停止后台任务 (N)」，Tooltip 提示「停止当前会话正在执行的所有后台长命令」。
- **Stop 报告双区呈现**：
  - Stop 成功后，`useThreadStopControl` 读取 `report.value?.background_tasks`。
  - 展示独立的「后台任务清理摘要」面板：
    - 目标任务数 (`target_count`)
    - 已确认清理 (`cleanup_confirmed_count`)
    - 未确认清理 (`cleanup_unconfirmed_count`) —— 若 `> 0`，以黄色警告标识呈现，禁止宣称“所有后台资源已全部释放”！
    - 通知已抑制 (`notifications_suppressed_count`)

---

## 7. F01-F12 验收清单与验证基线

| ID | 需求项 | 前端验收标准 | 验证手段 |
|---|---|---|---|
| **F01** | Tab 入口与降级 | 当 `capabilities?.background_tasks` 为 true 时展示任务 Tab；字段缺省或为 false 时平滑隐藏；工作区原有文件/产物/终端功能 0 退化。 | Vitest 单元测试 + 组件挂载快照 |
| **F02** | 任务列表与分页 | 完整覆盖 loading/empty/error/forbidden 状态；支持分页查询；`has_unresolved` 与 `latest_delivery_run_id` 不受分页遮蔽； scope 校验拒绝不符数据。 | 组件测试 + Mock HTTP 验证 |
| **F03** | 异步运行状态呈现 | 任务在后台运行、原 Run 已经 success 时，任务状态依然可独立定时/手动刷新；杜绝伪造百分比进度条。 | 状态机测试 + 模拟原 Run 终态 |
| **F04** | 单任务取消与对账 | 取消二次确认、副作用警示文案齐全；`Idempotency-Key` 单飞防重；202 pending 正确展示；网络超时通过 GET 对账。 | 模拟并发点击 + 模拟 504 重试 |
| **F05** | 有界只读纯文本日志 | 按需拉取；64KiB 纯文本展示；ANSI 控制字符清洗干净；截断与 omitted_bytes 警告栏齐全；关闭抽屉立即销毁轮询。 | ANSI 样本测试 + 截断 Mock 验证 |
| **F06** | 服务端新 Run 发现 | 后台任务完成后服务端创建新 Run，前端 5s 探针发现并接入；当前台 LLM busy 或 HITL 时安全暂存，待空闲平滑更新。 | 模拟新 Run 注入 + 前台 busy 阻断验证 |
| **F07** | 作用域与生命周期隔离 | 页面隐藏/再可见暂停与恢复；切换会话/项目/退出登录时，立即 Abort 请求并清理所有 timer；迟到响应不污染新会话。 | 页面可见性事件触发 + Scope 切换测试 |
| **F08** | 细粒度权限控制 | 严格根据 `allowed_actions` 呈现 logs 与 cancel 按钮；遇到 403 触发局部复核，不误登出用户；404 路由缺失不当撤权。 | 模拟仅 read 权限 + 错误处理断言 |
| **F09** | 三态独立正交展示 | 命令状态 (status)、容器清理 (cleanup)、通知交付 (delivery) 独立 Badge 呈现，严禁揉成单个 spinner。 | 多状态组合快照测试 |
| **F10** | 空闲时会话 Stop | LLM 空闲但后台任务活跃时，会话 Stop 按钮依然可达；Stop 报告正确消费并展示 `background_tasks` 摘要；未确认清理有告警。 | Stop 状态机单测 + 模拟 StopReport |
| **F11** | 响应式与视觉无障碍 | 390×844 (移动)、768×1024 (平板)、1440×900 (宽屏) 下面板无溢出、无文本重叠；浅色/深色主题适配；键盘 Esc 与 aria 属性完备。 | 浏览器全分辨率截图 + 无障碍键盘验证 |
| **F12** | 全链路真实环境联合验收 | B01已解除；真实 Platform API + Runtime Service + LLM/浏览器的全范围联合验收由T10执行，尚未完成。 | E2E 联合测试 |

---

## 8. 接续实施指导与质量门禁

1. **当前实施范围**：
   - 本轮实施聚焦于 **F01-F11** 的全部前端代码、单文件拆分、Composable 与 Vitest / Vue Test Utils 单元测试。
   - B01已解除；F12全链路端到端验收由T10收口，生产部署开关另验，不据引擎交付自动启用。
2. **前端本地质量门禁（必须全绿）**：
   - `pnpm vitest run src/modules/chat/background-tasks src/components/workspace`（新增单测全绿）
   - `pnpm vitest run`（全仓回归单测 0 失败）
   - `pnpm vue-tsc --noEmit`（TypeScript 静态检查 0 错误）
   - `pnpm eslint .`（代码规范检查 0 警告 0 报错）
   - `pnpm build`（生产构建打包全绿通过）
3. **交付产出**：
   - 完整的新增及修改源码；
   - 包含 390×844、768×1024、1440×900 三档分辨率的实际页面呈现验证证据；
   - 更新 tasks.md 中 T09 的逐项进度标记。
