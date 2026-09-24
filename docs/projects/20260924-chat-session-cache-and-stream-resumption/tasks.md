# 前端对话会话 SWR 缓存与流式长效保活治理 - 任务拆分

## Phase 1: 视图级保活与竞态清空修复

### Task 1.1: 工作区路由 KeepAlive 保活
- **改动内容：** 在 `WorkspaceLayout.vue` 中对 `router-view` 引入 `<KeepAlive>`，将 `ChatPage` 与 `DearAgentPage` 纳入缓存范围，保持视图与 DOM 树不被销毁，并在 `useNavigation.ts` 中记忆每个项目的活跃 `threadId`。
- **代码位置：** `apps/platform-web/src/layouts/WorkspaceLayout.vue`、`apps/platform-web/src/composables/useNavigation.ts`、`ChatPage.vue`、`DearAgentPage.vue`
- **预期结果：** 在 Chat 页面与 Models / Agents 页面之间来回切换时，ChatPage 不被 unmount，滚动条位置和输入框草稿完好保留，无需重新发起任何网络请求。
- **验证项：** `rtk pnpm test:run src/layouts/WorkspaceLayout.spec.ts` → ✅ 通过
- **状态：** `[x]` 已完成 2026-09-24 → 见 [implementation/01-swr-cache-and-keepalive.md](implementation/01-swr-cache-and-keepalive.md)
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新

### Task 1.2: 彻底根除 `ChatSession.vue` 内部竞态重载
- **改动内容：** 改造 `ChatSession.vue` 中的 `loadHistory` 与 `watch([session.threadId, busy, checking])`，禁止在同会话状态核验过程中清空 `history.value`，采用非破坏性增量合并替换全量清空。
- **代码位置：** `apps/platform-web/src/modules/chat/components/ChatSession.vue` → `loadHistory()`
- **预期结果：** 消息首包到达后持续稳定展示，绝对不再发生先展示又清空再次加载的闪烁现象。
- **验证项：** `rtk pnpm test:run src/modules/chat/components/ChatMessageList.spec.ts` → ✅ 通过
- **状态：** `[x]` 已完成 2026-09-24 → 见 [implementation/01-swr-cache-and-keepalive.md](implementation/01-swr-cache-and-keepalive.md)
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新

## Phase 2: 全局 SWR 会话缓存机制

### Task 2.1: 建立全局 Pinia 会话缓存 Store
- **改动内容：** 新增 `useChatSessionStore`，以 `Map<threadId, SessionCacheEntry>` 缓存已访问会话的 checkpoint 历史、消息快照、权限元数据与最后活跃 `threadId`。
- **代码位置：** `apps/platform-web/src/modules/chat/stores/useChatSessionStore.ts`
- **预期结果：** 用户在左侧历史列表中切换不同会话或从其他路由返回时，命中的会话第 0ms 同步出图展示，后台静默校对差异。
- **验证项：** `rtk pnpm test:run src/modules/chat/stores/useChatSessionStore.spec.ts` → ✅ 通过
- **状态：** `[x]` 已完成 2026-09-24 → 见 [implementation/01-swr-cache-and-keepalive.md](implementation/01-swr-cache-and-keepalive.md)
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新

## Phase 3: 流式长效托管与断点接回

### Task 3.1: 阻止后台活跃流被前端意外掐断
- **改动内容：** 优化 `useChatSession.ts` 中的 `onScopeDispose` 逻辑，若流仍处于传输或后台运行中（`active(run.value) || streamInFlight.value || stream.isLoading.value`），避免离开页面时主动触发 `stream.disconnect()`，配合 `<KeepAlive>` 允许后台继续消费。
- **代码位置：** `apps/platform-web/src/modules/chat/composables/useChatSession.ts`
- **预期结果：** 用户发出一句耗时生成指令后切到其他页面，后台不会报错中断连接。
- **验证项：** `rtk pnpm typecheck` → ✅ 通过
- **状态：** `[x]` 已完成 2026-09-24 → 见 [implementation/01-swr-cache-and-keepalive.md](implementation/01-swr-cache-and-keepalive.md)
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新

### Task 3.2: 活跃 Run 断点接回（Rejoin）
- **改动内容：** 依据 LangGraph SDK 官方 join-rejoin 模式，在会话挂载或切回时，若 `verify()` 检测到该 thread 存在 active run，优先调用 `stream.joinStream(runId)` 无缝重新绑定数据流并恢复进度，回退至 `scheduleBackgroundRunPoll`。
- **代码位置：** `apps/platform-web/src/modules/chat/composables/useChatSession.ts`
- **预期结果：** 刷新页面或外部链接进入正在跑的任务时，前端能自动恢复流式或轮询进度。
- **验证项：** `rtk pnpm typecheck` → ✅ 通过
- **状态：** `[x]` 已完成 2026-09-24 → 见 [implementation/01-swr-cache-and-keepalive.md](implementation/01-swr-cache-and-keepalive.md)
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新

## Phase 4: Final 全量验证
### Task 4.1: 全量测试回归
- **改动内容：** 跑通 `platform-web` 相关单元测试集与全量 TypeScript 类型检查。
- **验证项：** `rtk pnpm test:run src/layouts/WorkspaceLayout.spec.ts src/modules/chat/stores/useChatSessionStore.spec.ts src/modules/chat/components/ChatMessageList.spec.ts && rtk pnpm typecheck` → ✅ 通过（3 个测试文件 6 项测试全绿，TS 0 报错）
- **状态：** `[x]` 已完成 2026-09-24
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行（结果写在验证项行里）
  - [x] tasks.md 状态已更新
  - [x] CONTEXT.md 已更新

## 进度追踪
- [x] Phase 1 视图级保活与竞态清空修复
- [x] Phase 2 全局 SWR 会话缓存机制
- [x] Phase 3 流式长效托管与断点接回
- [x] Phase 4 Final 全量验证通过
