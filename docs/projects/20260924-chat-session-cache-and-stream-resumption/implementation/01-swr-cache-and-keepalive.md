# 前端对话会话 SWR 缓存与流式长效保活实现记录

## 改动时间
2026-09-24

## 相关任务
- Task 1.1: 工作区路由 KeepAlive 保活
- Task 1.2: 彻底根除 `ChatSession.vue` 内部竞态重载
- Task 2.1: 建立全局 Pinia 会话缓存 Store
- Task 3.1: 阻止后台活跃流被前端意外掐断
- Task 3.2: 活跃 Run 断点接回（Rejoin）

## 改动文件
- `apps/platform-web/src/modules/chat/stores/useChatSessionStore.ts`
- `apps/platform-web/src/modules/chat/stores/useChatSessionStore.spec.ts`
- `apps/platform-web/src/layouts/WorkspaceLayout.vue`
- `apps/platform-web/src/composables/useNavigation.ts`
- `apps/platform-web/src/modules/chat/pages/ChatPage.vue`
- `apps/platform-web/src/modules/dear-agent/pages/DearAgentPage.vue`
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- `apps/platform-web/src/modules/chat/composables/useChatSession.ts`

## 具体改动

### 1. 工作区路由 `<KeepAlive>` 与活跃会话导航记忆
**位置：** `WorkspaceLayout.vue:79-93`、`useNavigation.ts:34-43`、`ChatPage.vue`、`DearAgentPage.vue`
- 在 `WorkspaceLayout.vue` 中将 `<router-view>` 升级为 `<KeepAlive :include="['ChatPage', 'DearAgentPage']">` 包裹，使在同项目内切换到模型管理、智能体列表等页面再返回时，对话页 DOM 树、滚动位置、输入框草稿与活跃流实例 100% 保持原样不卸载。
- 在 `ChatPage.vue` 与 `DearAgentPage.vue` 的路由监听器头部增加 `if (route.name && route.name !== 'workspace-chat') return;` 守卫，防止后台 KeepAlive 实例响应其他页面的路由参数导致误销毁会话。
- 在 `useNavigation.ts` 中接入 `useChatSessionStore.getLastActiveThread()`，点击左侧导航栏“对话 / Dear Agent”时自动回到上次活跃的 `threadId`，而非丢失参数回退到空白新会话。

### 2. 全局 Pinia SWR 会话缓存层 (`useChatSessionStore`)
**位置：** `src/modules/chat/stores/useChatSessionStore.ts`
- 按 `${projectId}:${threadId}` 缓存 `messages`、`history`（Checkpoint 列表）与 `thread`（含 `allowed_actions` 权限元数据），最多 LRU 缓存 40 个活跃会话。
- 在 `ChatSession.vue` 与 `useChatSession.ts` 初始化时同步从 `useChatSessionStore` 水合历史消息与权限，使已访问会话在切换时实现 **0ms 同步上屏**，且 `accessLoading` 直接为 `false`，杜绝全屏“正在核验会话访问权限...”闪烁。

### 3. 消除 `loadHistory` 竞态清空与流式保活 / Rejoin
**位置：** `ChatSession.vue:1125-1155, 1398-1415`、`useChatSession.ts:396-470, 1088-1091`
- 重构 `ChatSession.vue` 中的 `watch([session.threadId, busy, checking])`：仅在 `threadId` 切换、运行从 `busy=true` 转为完成态（`prevRunning && !running`）或历史为空时才拉取历史，彻底禁止因 `checking` 状态切换引发的重复 `loadHistory(true)`。
- 将 `loadHistory(true)` 改造为非破坏性 SWR 更新：在服务端返回新 `rows` 前绝不将 `history.value` 置空，根治“消息先显示出来又突然清空重新加载”的幽灵闪烁。
- 在 `useChatSession.ts` 的 `onScopeDispose` 中增加活跃运行守卫（`!active(run.value) && !streamInFlight.value && !stream.isLoading.value`），并在 `verify()` 发现活跃 Run 时优先调用 `stream.joinStream(runId)` 接回实时流。

## 验证
- [x] 单元测试通过（`WorkspaceLayout.spec.ts`、`useChatSessionStore.spec.ts`、`ChatMessageList.spec.ts`）
- [x] TypeScript 类型检查通过（`rtk pnpm typecheck`）
