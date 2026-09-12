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

---

## Phase 4: 子智能体卡片对齐 Open SWE 与视口通知体验优化

### Task 4.1: 新增 `SubagentCard.vue` 专用组件与单测
- **文件：** `apps/platform-web/src/modules/chat/components/SubagentCard.vue`、`SubagentCard.spec.ts`
- **内容：** 提取角色名、子智能体标签、描述与状态，反序列化清洗 Python Command 输出，并编写完整单测。
- **状态：** 已完成 ✅ (2026-09-12)

### Task 4.2: `ToolResult.vue` 拦截分发 `task` 工具
- **文件：** `apps/platform-web/src/modules/chat/components/ToolResult.vue`
- **内容：** 当工具名称为 `task` 时委派给 `SubagentCard`。
- **状态：** 已完成 ✅ (2026-09-12)

### Task 4.3: `ChatSession.vue` 消除底部残留与未读胶囊化
- **文件：** `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- **内容：** 移除消息列表外部硬编码的重复全局 `subtasks`；重构未读通知为底部居中微型胶囊，触底即重置未读数。
- **状态：** 已完成 ✅ (2026-09-12)

## Phase 5: TodoList 结构化渲染与系统提示词精准触发

### Task 5.1: 后端 `prompts.py` 强化多步工程与 TodoList 触发规则
- **文件：** `apps/runtime-service/src/runtime_service/services/demo/showcase_demo/prompts.py`
- **内容：** 明确任务规划与多步工程必须调用 `write_todos` 登记结构化列表（首项 in_progress，其余 pending），禁止仅以 Markdown 纯文本敷衍输出。
- **状态：** 已完成 ✅ (2026-09-12)

### Task 5.2: 前端 `ToolResult.vue` 增加 `write_todos` 专属结构化展示与抽屉联动
- **文件：** `apps/platform-web/src/modules/chat/components/ToolResult.vue`、`ToolResult.spec.ts`、`ChatSession.vue`
- **内容：** 标题转译为“更新任务清单 · 共 N 项”；展开渲染迷你待办条目与状态圆点；增加“在详情面板查看任务看板 →”一键唤起抽屉并切到 ToDo 标签页。
- **状态：** 已完成 ✅ (2026-09-12)

## 进度追踪
- [x] Phase 1 完成
- [x] Phase 2 完成
- [x] Phase 3 完成
- [x] Phase 4 完成
- [x] Phase 5 完成

