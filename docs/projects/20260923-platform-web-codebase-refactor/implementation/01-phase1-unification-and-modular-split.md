# Phase 1 实现记录：双生模块去重、核心 Composable 解耦与错误解析统一

## 改动时间
2026-09-23

## 相关任务
- 子专题 04 Task 4.1 / 4.2：统一 HTTP 错误拆包与收敛遗留 `assistants.service.ts`
- 子专题 01 Task 1.1 / 1.2 / 1.3：消除 `modules/chat` 与 `modules/dear-agent` 双生复制粘贴（净减 ~11,915 行代码）
- 子专题 02 Task 2.1：从 `useChatSession.ts` 抽离 `useSessionInterrupts.ts` 与 `useSessionAttachmentUpload.ts`
- 子专题 03 Task 3.1：从 `DearAgentSkillsPage.vue` 抽离 `SkillDetailDrawer.vue`

## 具体改动与战果对比

### 1. 全仓代码体量对比（`apps/platform-web/src`）
- **重构前总行数**：`74,655` 行
- **重构后总行数**：`62,740` 行
- **净削减冗余代码**：**`-11,915` 行（减少 16.0%）**

### 2. `chat` 与 `dear-agent` 双生模块唯一事实源（SSOT）合并
- 在 `src/modules/chat/components/ChatSession.vue` 与 `ChatRunOptionsDialog.vue` 中原生集成 `enableExecutionMode` (`standard` | `flash` | `pro` | `ultra`) 能力与顶部模式胶囊。
- 将 `DearAgent` 侧 `ToolResult.vue` 的图表/PPT/证据源（`evidenceSources`）增强渲染能力与 `chat` 侧的 `fromOutput` 图像提取合并为唯一 `src/modules/chat/components/ToolResult.vue`。
- 将 `src/modules/dear-agent/` 下 28 个重复的 `.vue` 与 `.ts` 文件（含 1827 行的 `DearAgentSession.vue`、1191 行的 `useDearAgentSession.ts`、1084 行的 `ChatContextDrawer.vue`、593 行的 `transcript.ts`、504 行的 `human-input.ts`、481 行的 `trajectory-adapter.ts` 等）收敛为指向 `@/modules/chat/...` 的 1 行桶重导出（Barrel Re-export），既 100% 保持外部/单测 import 路径零破坏，又使 Dear Agent 自动继承 `useChatSession.ts` 的历史澄清防闪现与 409 抢跑自愈修复。

### 3. 核心会话与管理页模块化拆分
- 新增 `src/modules/chat/composables/useSessionInterrupts.ts`：独立封装 `reviews` 与 `clarifications` 解析、防闪现过滤及 `approve` / `answerClarification` 提交逻辑。
- 新增 `src/modules/chat/composables/useSessionAttachmentUpload.ts`：独立封装消息发送前图片与文档 SHA256 计算、上传与 Runtime Text Block 转换。
- 新增 `src/modules/dear-agent/components/SkillDetailDrawer.vue`：从 `DearAgentSkillsPage.vue` (1312 行 → 1037 行) 抽离文件树伸缩、拖拽分割条、Markdown 预览与代码复制逻辑。

### 4. HTTP 错误拆包统一与遗留 Service 收敛
- 在 `src/utils/http-error.ts` 中新增 `extractEnvelopeFields` 与 `unwrapPlatformHttpError`，统一支持 `platform-api` 的 `{ error: { code, message }, meta: { request_id } }` 嵌套结构与 Blob 错误流解析；重构 `src/services/threads/workspace.service.ts` 复用该函数。
- 将 0 引用的 `src/services/assistants/assistants.service.ts` (141 行) 收敛为对 `@/services/agents/agents.service` 的兼容重导出。

## 验证结果
- [x] `pnpm typecheck`：`TypeScript: No errors found`（0 报错）
- [x] `pnpm test:run src/modules/chat/composables/useChatSession.spec.ts`：16 passed
- [x] `pnpm test:run src/modules/chat/pages/ChatPage.spec.ts src/modules/dear-agent/pages/DearAgentPage.spec.ts`：5 passed
- [x] `pnpm test:run src/modules/dear-agent/pages/DearAgentSkillsPage.spec.ts`：6 passed
- [x] `pnpm test:run src/modules/dear-agent/human-input.spec.ts src/modules/dear-agent/transcript.spec.ts`：13 passed
