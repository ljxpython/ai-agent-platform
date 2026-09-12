# Chat 流式输出标准化与 open-swe 架构对齐 - 任务拆分

## Phase 1: 消息管道疏通与协议对齐

### Task 1.1: 梳理与核验 Gateway / Runtime 流模式契约
- **文件：** `apps/platform-api/src/platform_api/modules/runtime_gateway/application/service.py`
- **内容：** 确保下发给上游的参数带全 `stream_mode: ["messages", "values"]`，核查 SSE 转发未引入缓冲。
- **状态：** 已完成 ✅ (2026-09-12)

### Task 1.2: 重构 `useTranscriptMessages.ts` 释放 Live 流
- **文件：** `apps/platform-web/src/modules/chat/composables/useTranscriptMessages.ts`
- **内容：** 剥除对 `values` 所有权锁死的限制，直接基于 `useMessages` 响应式投影透传 live 增量，保留基于 namespace 的作用域隔离。
- **状态：** 已完成 ✅ (2026-09-12)

---

## Phase 2: 视图转换与 Reasoning 呈现

### Task 2.1: 优化 `transcript.ts` 纯函数视图映射
- **文件：** `apps/platform-web/src/modules/chat/transcript.ts`
- **内容：** 引入类似 open-swe 的 reasoning 提取与流式块拼装，支持 `<thinking>` 及 `reasoning_content`。
- **状态：** 已完成 ✅ (2026-09-12)

### Task 2.2: 升级 `ChatSession.vue` 视口平滑跟随
- **文件：** `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- **内容：** 监听流式输出文本变化，结合 requestAnimationFrame 实现平滑滚底；流式状态与状态栏对齐。
- **状态：** 已完成 ✅ (2026-09-12)

### Task 2.3: `ChatMessageList.vue` 流式视觉优化
- **文件：** `apps/platform-web/src/modules/chat/components/ChatMessageList.vue`
- **内容：** 增加流式生成中的动态光标动画与思考块样式。
- **状态：** 已完成 ✅ (2026-09-12)

---

## Phase 3: 全链路验证与回归

### Task 3.1: Chat 模块单元测试与 Lint 回归
- **命令：** `pnpm exec vitest run src/modules/chat`、`pnpm lint`、`pnpm typecheck`
- **状态：** 已完成 ✅ (2026-09-12)

### Task 3.2: 真实模型流式对话与工作台 E2E 验收
- **内容：** 验证长文本真实打字机流式、思考过程展开、中途停止、分支导航和抽屉完整可用。
- **状态：** 已完成 ✅ (2026-09-12 用户真实环境联调验收通过)

## 进度追踪
- [x] Phase 1 完成
- [x] Phase 2 完成
- [x] Phase 3 完成
