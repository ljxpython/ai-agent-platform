# 前端执行预算预警与停机展示实施记录

- **项目：** 20261007-agent-execution-budget
- **阶段：** Phase 5 & Phase 6 (F01-F04, T08B)
- **实现人：** 老王（技术流）
- **完成日期：** 2026-10-07
- **工作树：** `/Users/lijiaxin/.codex/worktrees/ce00/ai-agent-platform`

---

## 1. 概述与范围

本项目前端实施落地了执行预算通知解析、Amber 警报与终态停机原因提示、子图/子任务隔离展示、会话输入与动作合法分流（F01-F04）。
所有实现严格遵循 Karpathy Guidelines（Surgical Changes, Simplicity First），复用现有 SDK 连接与状态流，不引入额外轮询或冗余状态层。

---

## 2. 核心架构与模块实现

### 2.1 纯函数与数据契约 (`src/modules/chat/budget/`)

1. **类型与 Zod 校验 (`types.ts`)**
   - 严格遵循后端与 Runtime 输出契约：
     - `budget_notice_payload_schema`：区分 `metric` 为 `seconds`（浮点数，`remaining` 为 `null`）与 `model_calls`/`graph_supersteps`（整型数值，含 `remaining`）。
     - `phase`：支持 `approaching`、`wrapup_started`、`reached`。
     - `budget_safety_error_schema`：结构化匹配 `model_call_limit_exceeded`、`superstep_limit_exceeded`、`tool_call_limit_exceeded`、`run_timeout` 四类安全码。
2. **安全提取与视图投影 (`view-model.ts`)**
   - `safeExtractBudgetNotice(item)`：多层弹性解包，支持 Direct payload、Protocol custom payload、`data.custom` 以及历史人工消息中的 `custom_event` 结构化标记。对非法版本或字段缺损安全忽略。
   - `safeExtractBudgetSafetyError(error)`：从 HTTP / LangGraph error 中解构 `status_code === 400` 或 `code === "budget_limit_exceeded"` 的结构化 details。
   - `deriveBudgetViewModel(notices, error, runStatus, currentRunId, isThreadExhausted)`：
     - 严格过滤 `notice.run_id === currentRunId`，防止历史 Run 污染当前 Run。
     - 状态级别分级：`stop`（reached 或 400 预算错误）、`wrapup`（wrapup_started）、`approaching`（接近阈值预警）。
     - 区分 Run 级预算（可调整请求）与 Thread 级预算（禁用当前会话发送，引导新建会话或 Fork 分支）。

### 2.2 响应式 Composable (`src/modules/chat/composables/useRunBudget.ts`)

- 官方 SDK 连接复用与响应式解耦：
  - 通过 `@langchain/vue` 提供的 `useChannel(stream, ["custom"])` 进行非侵入式顶层订阅，不创建额外的 SDK 实例或物理连接。
  - 针对 `useChannel` 的 `target` 参数不支持响应式 Ref 的静态陷阱，在顶层订阅全量 custom 通道，内部通过响应式 `isNamespaceMatch` 与 `currentRunId` 进行安全路由。
- 有界去重与增量消费：
  - 实现 `BoundedNoticeCache`（容量上限 200，LRU 淘汰），对重复推送的 `notice_id` 静默去重。
  - 维护 `lastEventsRef` + `processedCount` 增量消费指针，根治在 SDK buffer（最大 4096 条事件）下 computed hot path 反复全量跑 Zod 的性能问题。
  - 针对新 Run 启动但尚未产生新事件的瞬态，增加 `currentRunId !== lastRunId` 校验，杜绝旧 Run 的 `endMarkerNotice` 发生界面闪烁。

### 2.3 视图组件集成 (`src/modules/chat/components/`)

1. **`ChatAgentStatusBar.vue`**
   - 放宽显隐门槛：由原来的仅阻断/错误展示，扩展为 `v-if="isInterrupted || error || budget"`。
   - 样式与状态分流：
     - `approaching` / `wrapup`：渲染为 Amber 预警横条，不伪造 `failed` 状态，Agent 仍保持 running/thinking。
     - **预警态保留取消操作**：在 running + warning 态下明确保留“取消”按钮，支持用户即时停止任务。
     - **文案解耦**：消除主副标题复读机问题，格式采用 `${title}（${description}）`。
     - **可访问性**：添加 `aria-live="polite"` 与 `role="status"`，支持屏幕阅读器平滑播报。
     - `stop`：当 Run 虽为原生 `success` 但因预算耗尽停止时，渲染精确的红色/橙色停机原因说明与操作引导。
     - 派发 `action` 事件（`adjust_request`、`new_session`、`fork_branch`），供父组件接入。
2. **`SubtaskDetail.vue` 与 `SubagentCard.vue`**
   - `SubtaskDetail.vue`：引入 `useRunBudget({ stream, runId, namespace: [taskId] })`，在抽屉顶部展示子任务专属预算微横条，具备文案解耦与 `aria-live` 支持。
   - `SubagentCard.vue`：无条件在组件顶层安全调用 Composable，杜绝 Vue Reactivity 崩溃；在子 Agent 卡片头部增加状态胶囊（Amber 预警、Orange 收尾中、Red 超额），子图预算告警不冒泡污染父 Run 状态条。
3. **`ChatSession.vue`**
   - 接入主 Run `useRunBudget` 并透传至 `ChatAgentStatusBar`。
   - 实现 `handleBudgetAction`：
     - `adjust_request`：安全抽取多模态与纯文本输入，移除粗暴的 `window.confirm`，保留输入框既有内容并引导精简任务。
     - `new_session`：调用现有的会话新建流。
     - `fork_branch`：调用已有的 Fork/分支流。
   - Thread 耗尽硬约束：当 Thread 额度耗尽（`isThreadExhausted === true`）时，禁用输入框 `canSubmit` 与队列提交，彻底杜绝无效重试。

---

## 3. 测试与门禁验证证据

### 3.1 单元测试（Vitest）
- `src/modules/chat/budget/view-model.spec.ts`：**14 passed**（涵盖 Zod 白名单、浮点秒数无 remaining、Direct/Protocol/History/payload 解包、非法数据安全丢弃、Thread 耗尽动作分流、文案解耦与未知错误降级）。
- `src/modules/chat/composables/useRunBudget.spec.ts`：**6 passed**（涵盖 200 条有界 LRU 淘汰、Run 隔离、namespace 隔离、无通知默认态、running 态防历史闪烁）。
- `src/modules/chat/components/ChatAgentStatusBar.spec.ts`：**6 passed**（涵盖 Amber 预警不伪造 failed、预警态保留取消按钮、原生 success 停机展示、动作按钮点击派发、A11y 属性）。
- `src/modules/chat/components/SubtaskDetail.spec.ts`：**3 passed**（涵盖子任务专属 namespace 预算条过滤、文案解耦与展示）。
- `src/modules/chat/components/SubagentCard.spec.ts`：**2 passed**（涵盖头部微胶囊状态展示与响应式更新）。
- 全仓全量回归：**116 passed (1 skipped), 571 passed, 0 failed**。

### 3.2 静态类型与规范门禁
- `pnpm check`（`vue-tsc --noEmit` + `vite build`）：**0 errors**，构建输出耗时 10.96s 正常。
- `pnpm lint`（`oxlint` + `eslint`）：**0 errors**，新增与修改的 budget 相关代码 **0 warnings**。

---

## 4. 结论与交付确认

前端任务 F01、F02、F03、F04 均已高质量交付并验证完毕。代码完全契约对齐，无类型报错，无多余冗余设计。
