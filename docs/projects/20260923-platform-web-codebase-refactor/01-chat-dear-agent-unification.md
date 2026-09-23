# 01 - Chat 与 Dear-Agent 双生模块去重收敛

## 目标
解决当前 `apps/platform-web` 最严重的代码冗余灾难：`src/modules/chat` 与 `src/modules/dear-agent` 之间存在 **22 个 100% 字节级一模一样的文件** 和 **12 个 90%+ 相似但已出现 Bug 修复漂移（Drift）的分叉文件**（合计重复超过 10,000 行）。
例如：近期在 `useChatSession.ts` 修复的「切回会话界面时历史需求澄清卡片闪现」与「消息队列 409 抢跑排空缺陷」，在 `useDearAgentSession.ts` 中就因复制粘贴分叉而漏同步。

## 现状盘点（基于源码实测）

### 1. 100% 完全相同的文件（共 22 个，直接删除 `dear-agent` 侧副本并复用）
- 组件层：
  - `ChatContextDrawer.vue` (1084 行 × 2)
  - `ChatModelSelector.vue` (458 行 × 2)
  - `ChatAgentStatusBar.vue`, `ChatAttachmentPreview.vue`, `ChatStickyTaskPill.vue`, `MessageContent.vue`, `SubtaskDetail.vue`
  - `components/trajectory/TrajectoryInspector.vue`, `TrajectoryLedger.vue`, `TrajectoryTimeline.vue`, `TrajectoryView.vue` 及对应 `.spec.ts`
- 逻辑与模型层：
  - `composables/useChatAttachments.ts`
  - `trajectory/trajectory-adapter.ts` (481 行 × 2) 及 `types.ts`, `trajectory-adapter.spec.ts`
  - `history-view-model.ts`, `live-follow-view-model.ts`, `run-actions.ts`, `scroll-state.ts`

### 2. 95% 相似但发生分叉的核心文件（需合并参数化后统一收敛至 `modules/chat`）
- `useChatSession.ts` (1204 行) vs `useDearAgentSession.ts` (1191 行)
  - 差异点仅在于 `useChatSession` 包含最新的 clarifying 闪现防御和 queue fallback 参数，两者本应是同一个 Composable。
- `ChatSession.vue` (1715 行) vs `DearAgentSession.vue` (1827 行)
  - 差异点仅在于 `DearAgentSession` 支持 `executionMode` (`flash` | `standard` | `pro` | `ultra`) 选择器及 `resumeClarification` 透传。
- `transcript.ts` (591 行 vs 593 行)、`human-input.ts` (513 行 vs 504 行)、`ToolResult.vue` (463 行 vs 684 行，DearAgent 侧多了部分特殊工具渲染展示，可无损合并入统一 `ToolResult.vue`)。

## 方案设计

1. **统一对话底座至 `src/modules/chat`**：
   - 为 `ChatSession.vue` / `useChatSession.ts` 增加可选特性配置 `sessionFeatures?: { enableExecutionMode?: boolean; defaultExecutionMode?: ExecutionMode }`。
   - 将 `DearAgent` 侧 `ToolResult.vue` 的增强渲染能力合并回 `src/modules/chat/components/ToolResult.vue`。
2. **精简 `src/modules/dear-agent` 职责边界**：
   - `src/modules/dear-agent` **只保留** Dear Agent 独有的业务模块：
     - `pages/DearAgentPage.vue`（薄包装层，固定挂载 `dear_agent` 目标并传入 `enableExecutionMode: true` 渲染 `<ChatSession>`）
     - `pages/DearAgentSkillsPage.vue`（Skills 技能管理）
     - `pages/DearAgentMemoryPage.vue`（长期记忆管理）
     - `pages/DearAgentArtifactsPage.vue`（任务成果归档）
     - `composables/useDearGovernanceContext.ts`（Dear Agent 专属治理上下文）
   - 删除 `src/modules/dear-agent` 下所有重复的 `components/`、`trajectory/`、`useDearAgentSession.ts`、`transcript.ts`、`human-input.ts` 等副本。

## 任务拆分
- [x] Task 1.1：收敛 `dear-agent` 下 22 个 100% 相同的组件与工具文件至 `@/modules/chat/...` - **状态：** `[x]` 已完成 2026-09-23 → 见 [implementation/01](implementation/01-phase1-unification-and-modular-split.md)
- [x] Task 1.2：合并 `transcript.ts`、`human-input.ts`、`useTranscriptMessages.ts` 与 `ToolResult.vue` 的分叉差异至 `modules/chat` - **状态：** `[x]` 已完成 2026-09-23
- [x] Task 1.3：在 `ChatSession.vue` 与 `ChatRunOptionsDialog.vue` 中原生支持 `enableExecutionMode` 切换，将 `useDearAgentSession` + `DearAgentSession` 统一指向 `useChatSession` + `ChatSession` - **状态：** `[x]` 已完成 2026-09-23

## 验证要求与记录
### 验证要求
- [x] `pnpm test:run` 核心单测通过（ChatPage、DearAgentPage、useChatSession、human-input、transcript 共 40 个用例全绿）
- [x] `pnpm typecheck` 零类型错误

### 验证记录
#### 2026-09-23 验证
- ✅ `pnpm typecheck`：0 errors
- ✅ `vitest run src/modules/dear-agent/pages/DearAgentPage.spec.ts src/modules/chat/pages/ChatPage.spec.ts src/modules/chat/composables/useChatSession.spec.ts`：全部通过，净删重复代码 11,915 行。

## 状态
done
