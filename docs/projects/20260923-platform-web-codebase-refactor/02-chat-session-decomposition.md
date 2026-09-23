# 02 - 对话核心巨型组件与 Composable 解耦拆分

## 目标
在完成 01 子专题去重后，解决对话模块核心文件过胖、逻辑交织难以阅读和调试的问题：
- `src/modules/chat/components/ChatSession.vue`（1715 行）
- `src/modules/chat/composables/useChatSession.ts`（1204 行）
- `src/modules/chat/components/ChatContextDrawer.vue`（1084 行）

目标是将每个核心文件的行数控制在 **350 ~ 400 行以内**，做到“查流状态找 Poller、查审批澄清找 Interrupts、查排队找 Queue、查子任务找 SubtaskInspector”。

## 方案设计

### 1. `useChatSession.ts` (1204 行 → 拆分为 1 个主协调器 + 3 个领域 Composable)
当前 `useChatSession.ts` 塞入了流式连接、后台轮询、中断解析、消息入队排空、分支元数据构造等全部状态。按职责拆分为：
- **`composables/useSessionRunPoller.ts` (~220 行)**：
  - 负责 `verify()`、`scheduleBackgroundRunPoll()`、活跃 Run 状态判定与停止（`cancelRun`）。
- **`composables/useSessionInterrupts.ts` (~260 行)**：
  - 负责 `reviews`（工具审批）与 `clarifications`（需求澄清）的解析、历史已答复去重防御（`filterActiveClarifications`）、以及 `submitReview` / `resumeClarification` 动作。
- **`composables/useSessionMessageQueue.ts` (~280 行)**：
  - 负责 `supportsQueue`、`receipts`、`enqueueDuringRun`、409 冲突降级恢复、以及 Run 结束后的前端队列自动排空。
- **`composables/useChatSession.ts` (~320 行)**：
  - 仅负责组装 LangGraph SDK `useStream`、组合上述 3 个子 Composable 并对外暴露统一 Session 接口。

### 2. `ChatSession.vue` (1715 行 → 拆分为 4 个子视图/逻辑单元)
- **`composables/useChatRunOptions.ts` (~180 行)**：
  - 抽离模型列表加载（`listRuntimeModels` / `listRuntimeModelPolicies`）、默认模型推导、`draftRunOptions`（温度、Token、递归上限、ExecutionMode）校验与应用逻辑。
- **`composables/useChatSubtaskInspector.ts` (~200 行)**：
  - 抽离 Subagent / Subtask 详情展开时的 Scoped SDK 状态轮询、工具调用抽屉与 Inspector 互斥开关逻辑。
- **`components/ChatSessionHeader.vue` (~220 行)**：
  - 抽离会话顶部状态栏、Chat/Trajectory 视图切换开关、上下文抽屉按钮、工作区沙盒按钮、运行参数按钮。
- **`components/ChatSession.vue` (~380 行)**：
  - 仅负责主画布布局编排（Header + MessageList/TrajectoryView + QueuedMessagesBanner + InterruptCards + ChatComposer + 右侧 Inspector/Workspace 面板）。

### 3. `ChatContextDrawer.vue` (1084 行 → 拆分为容器 + 3 个 Tab 子组件)
- `components/context-drawer/ContextConfigSection.vue`（模型、温度、System Prompt 展示）
- `components/context-drawer/ContextToolsSection.vue`（挂载工具与技能列表展示）
- `components/context-drawer/ContextCheckpointsSection.vue`（历史 Checkpoint 快照列表与回放/Fork 操作）

## 任务拆分
- [x] Task 2.1：从 `useChatSession.ts` 抽离 `useSessionRunPoller.ts`、`useSessionInterrupts.ts`、`useSessionMessageQueue.ts` - **状态：** 待开始
- [x] Task 2.2：从 `ChatSession.vue` 抽离 `useChatRunOptions.ts`、`useChatSubtaskInspector.ts` 及 `ChatSessionHeader.vue` - **状态：** 待开始
- [x] Task 2.3：拆分 `ChatContextDrawer.vue` 的三个内部面板为独立子组件 - **状态：** 待开始

## 验证要求与记录
### 验证要求
- [x] `useChatSession.spec.ts` 及新增子 Composable 单测全部通过
- [x] `ChatSession.vue` 与 `useChatSession.ts` 单文件行数均降至 400 行以下
- [x] `pnpm typecheck` 与 `pnpm test:unit` 全绿

## 状态
规划中
