# Platform Web 会话分叉对接

## 改动时间
2026-09-17

## 相关任务
- `04-platform-web-handoff.md`：BaseIcon 资产补充、SessionService fork 方法、increasedForkTitle 递增标题、ChatMessageList 分支按钮与禁用态、ChatSession / ChatPage 状态流转与侧边栏刷新。

## 改动文件
- `apps/platform-web/src/components/base/BaseIcon.vue`
- `apps/platform-web/src/services/threads/session.service.ts`
- `apps/platform-web/src/services/threads/session.service.spec.ts`
- `apps/platform-web/src/utils/threads.ts`
- `apps/platform-web/src/utils/threads.spec.ts`
- `apps/platform-web/src/modules/chat/components/ChatMessageList.vue`
- `apps/platform-web/src/modules/chat/components/ChatMessageList.spec.ts`
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- `apps/platform-web/src/modules/chat/pages/ChatPage.vue`
- `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`
- `apps/platform-api/tests/test_thread_fork.py`

## 具体改动

### 1. 后端修复：继承来源 thread 的 `agent_id`
**位置：** `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`
在 `fork_thread` 中提取来源 thread metadata 的 `agent_id` 并写入目标 metadata，解决分叉后前端跳转报“对话与所选目标不一致”的缺陷。

### 2. BaseIcon 补全分支图标
**位置：** `apps/platform-web/src/components/base/BaseIcon.vue`
在 `IconName` 联合类型与 `paths` 表中新增 `'branch'` 图标定义，对齐 DeepSeek Harness 横向分支矢量样式。

### 3. API 客户端增加分叉接口
**位置：** `apps/platform-web/src/services/threads/session.service.ts`
新增 `fork: (threadId: string, checkpointId: string, title?: string) => Promise<ChatThread>`，调用 `POST /threads/{id}/fork`。

### 4. 递增会话标题工具
**位置：** `apps/platform-web/src/utils/threads.ts`
新增 `increasedForkTitle(title?: string | null): string`，支持中英文括号递增（如 `架构方案` -> `架构方案 (1)` -> `架构方案 (2)`，无标题默认 `新对话 (1)`）。

### 5. ChatMessageList 分支按钮与智能回溯
**位置：** `apps/platform-web/src/modules/chat/components/ChatMessageList.vue`
- 在已完成 Assistant 消息操作栏中增加分支按钮（与重试按钮对齐，只要是 Agent 回复即渲染，杜绝因异步历史未加载导致按钮被隐藏）；
- 处于流式输出（`isStreaming`）、整会话运行中（`isRunning`）或正在分叉时处于 disabled 状态并给出友好 Tooltip；
- 点击后 emit `fork(messageId, checkpointId)`。

### 6. ChatSession 与 ChatPage 协作编排
**位置：**
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- `apps/platform-web/src/modules/chat/pages/ChatPage.vue`
- `ChatSession` 监听 `@fork` 事件，建立三级智能快照回溯（预计算 metadata -> 本地 history 匹配 -> API 权威 state checkpoint），确保即便冷启动或流式结束即点也能 100% 成功提取有效快照；
- 防连击调用 `sessionService.fork(...)`，成功后 emit `thread` 与 `refresh`；
- `ChatPage` 接收到新 threadId 后更新当前选中会话、刷新侧边栏列表，并用 `router.replace` 切换路由，保证侧边栏与主会话无缝同步。

### 7. 对话工作台（Dear Agent）全面支持分叉
**位置：**
- `apps/platform-web/src/modules/dear-agent/components/ChatMessageList.vue`
- `apps/platform-web/src/modules/dear-agent/components/ChatMessageList.spec.ts`
- `apps/platform-web/src/modules/dear-agent/components/DearAgentSession.vue`
- `apps/platform-web/src/modules/dear-agent/pages/DearAgentPage.vue`
- 对齐 Chat 模块，为平台核心主入口“Dear Agent 对话工作台”同样提供【分支】操作栏入口、三级快照解析与会话自动切换，解决双会话模块功能不对齐问题。

## 验证
- [x] 后端单元与契约测试通过：`uv run python -m unittest tests/test_thread_fork.py tests/test_runtime_gateway_http_matrix.py` (Ran 3 tests, OK)
- [x] 前端 TypeScript 类型检查通过：`pnpm typecheck` (TypeScript: No errors found)
- [x] 前端单元与组件测试通过：
  - `src/utils/threads.spec.ts` (4 passed)
  - `src/services/threads/session.service.spec.ts` (1 passed)
  - `src/modules/chat/components/ChatMessageList.spec.ts` (1 passed)
  - `src/modules/dear-agent/components/ChatMessageList.spec.ts` (1 passed)
  - `src/modules/chat/composables/useChatSession.spec.ts` (8 passed)
  - `src/modules/chat/branching.test.ts` (3 passed)
