# Chat 会话状态机加固与流式体验优化 - 任务拆分

## Phase 1: 权限刷新与排队消息容错 (P0)

### Task 1.1: 加固 `workspaceStore.refreshCurrentProjectAccess` 容错
- **改动内容：** 请求失败时区分错误类型，仅在明确 403 确认无权限时清空 `currentProjectAccess`，网络波动或 401 刷新中保留原有缓存，防止工作区误踢。
- **代码位置：** `apps/platform-web/src/stores/workspace.ts` → `refreshCurrentProjectAccess()`
- **预期结果：** 刷新失败时不踩空原有权限对象，页面不闪现“当前页面权限已失效”。
- **验证项：** `pnpm test:run src/stores/workspace.spec.ts` → ✅ 通过 (4/4 tests passed)
- **状态：** `[x]` 已完成 2026-10-04 → 见 implementation/01-session-state-and-stream-hardening.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新（会话加固）
  - [x] docs/FEATURES.md 已更新（跳过，纯会话交互防御性修复）
  - [x] docs/CHANGELOG.md 已更新（登记在 [Unreleased] fix 分组）

### Task 1.2: 修复 `QueuedMessagesBanner.vue` 显隐条件
- **改动内容：** 仅当 `totalCount > 0` 时展示排队 Banner；空队列下的 `receiptError` 转为后台静默处理，不展示 Banner。
- **代码位置：** `apps/platform-web/src/modules/chat/components/QueuedMessagesBanner.vue`
- **预期结果：** 空队列不再弹出“排队补充消息 0 存在未进入上下文的补充消息”黄色横条。
- **验证项：** `pnpm test:run src/modules/chat/components/QueuedMessagesBanner.spec.ts` → ✅ 通过 (6/6 tests passed)
- **状态：** `[x]` 已完成 2026-10-04 → 见 implementation/01-session-state-and-stream-hardening.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新（会话加固）
  - [x] docs/FEATURES.md 已更新（跳过，纯会话交互防御性修复）
  - [x] docs/CHANGELOG.md 已更新（登记在 [Unreleased] fix 分组）

## Phase 2: Live Step 状态指示与流式感知优化 (P1)

### Task 2.1: 修复 `ChatMessageList.vue` 的 `shouldShowLiveStep` 状态判定
- **改动内容：** 增加 `props.isInterrupted` 守卫，排除 `request_information` 等人工澄清工具对 `hasRunningTools` 的污染。
- **代码位置：** `apps/platform-web/src/modules/chat/components/ChatMessageList.vue` → `shouldShowLiveStep`
- **预期结果：** 当进入澄清中断等待输入时，不再显示“Agent 正在处理当前回合”。
- **验证项：** `pnpm test:run src/modules/chat/components/ChatMessageList.spec.ts` → ✅ 通过 (4/4 tests passed)
- **状态：** `[x]` 已完成 2026-10-04 → 见 implementation/01-session-state-and-stream-hardening.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新（会话加固）
  - [x] docs/FEATURES.md 已更新（跳过，纯会话交互防御性修复）
  - [x] docs/CHANGELOG.md 已更新（登记在 [Unreleased] fix 分组）

### Task 2.2: 优化思维链首轮流式加载反馈
- **改动内容：** 当流式过程中处于推理阶段（Reasoning 产出）时，通过 `liveReasonings` 实时捕获流式思维链增量，并投影到活跃 AIMessage，避免首轮静止假死和突兀弹出。
- **代码位置：** `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.ts`
- **预期结果：** 思维链生成阶段具有平滑动态感知与折叠思考卡片。
- **验证项：** `pnpm test:run src/modules/chat/composables/useTranscriptMessages.spec.ts` → ✅ 通过 (8/8 tests passed)
- **状态：** `[x]` 已完成 2026-10-04 → 见 implementation/01-session-state-and-stream-hardening.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新（会话加固）
  - [x] docs/FEATURES.md 已更新（跳过，纯流式渲染体验加固）
  - [x] docs/CHANGELOG.md 已更新（登记在 [Unreleased] fix 分组）

## Phase 3: 全量验证与收尾

### Task 3.1: Final 全量验证
- **改动内容：** 运行前端所有相关单元测试、TypeScript 类型检查与生产打包验证。
- **验证项：** `pnpm typecheck` + `pnpm test:run` + `pnpm build` → ✅ 全部通过 (22/22 tests passed, build in 16.18s)
- **状态：** `[x]` 已完成 2026-10-04 → 见 verification.md
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新
  - [x] docs/FEATURES.md 已更新（跳过）
  - [x] docs/CHANGELOG.md 已更新

## 进度追踪
- [x] Phase 1 完成
- [x] Phase 2 完成
- [x] Phase 3 全量验证通过
