# 前端功能实施与闭环验证

日期：2026-10-10。范围：P4.1、P4.2、P4.3；进度以 tasks.md 为准。

## 架构决策与实现

### 1. 全局通知状态单例（Pinia Store）
- 文件：`apps/platform-web/src/stores/run-notifications.ts`
- 架构考量：
  - 避免组件级重复轮询与竞态，采用 Pinia Store 单例管理所有运行失败通知与未读角标。
  - 轮询机制：采用递归 `setTimeout`（基线 15s），单飞互斥锁（`isFetching` 守卫），页面后台（`document.visibilityState === "hidden"`）立即暂停轮询，切回前台立即触发补偿轮询。
  - 错误退避：针对 503 异常实施有界指数退避（15s -> 30s -> 60s），连续失败上限保护，保留当前项目已有私有通知。
  - 乐观已读更新：点击“标为已读”时立刻更新内存未读数与项状态，并在接口返回异常时自动回滚，对账真实数据。

### 2. 细粒度优先文案与白名单投影
- 文件：
  - `apps/platform-web/src/modules/chat/completion/types.ts`
  - `apps/platform-web/src/modules/chat/completion/presentation.ts`
  - `apps/platform-web/src/services/threads/completion.service.ts`
  - `apps/platform-web/src/services/run-notifications/run-notifications.service.ts`
- 架构考量：
  - 严格 Zod DTO 校验，拦截后端多余敏感字段或非法枚举。针对 `version` 做防御性补齐（默认 1）。
  - 文案降级策略遵循“细粒度优先”原则：`model_error_code` -> `reason_code` -> `notification_code` -> `status`。
  - 安全投影：非白名单的错误原因一律降级为安全文案（如“执行遇到内部错误”），严禁直接将原始服务端异常暴露给用户。

### 3. 会话保护与跳转防护（Navigation Guard）
- 文件：
  - `apps/platform-web/src/components/layout/RunNotificationCenter.vue`
  - `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- 架构考量：
  - 会话在 `isChatExecuting === true` 时，用户点击通知卡片的“查看会话”不会直接执行路由跳转，而是弹出二次确认模态框（“留在当前会话” / “确认离开并查看”），有效防止正在进行的任务流被意外打断。

### 4. 历史 Run 终态诊断卡片集成
- 文件：
  - `apps/platform-web/src/modules/chat/composables/useRunCompletion.ts`
  - `apps/platform-web/src/modules/chat/components/trajectory/RunDiagnostics.vue`
- 架构考量：
  - `useRunCompletion` 使用代数编号（generation counter）防止迟到响应覆盖当前活跃 Run。
  - 在会话处于 running 时惰性跳过 completion 查询，避免打扰实时流式输出；仅在终态判定后主动拉取一次失败原因投影。
  - `RunDiagnostics` 增加专属失败安全摘要卡片，展示白名单错误码、排查详情与建议重试动作。

### 5. 全局顶栏与沉浸式会话头部挂载
- 文件：
  - `apps/platform-web/src/components/layout/TopContextBar.vue`
  - `apps/platform-web/src/modules/chat/pages/ChatPage.vue`
- 架构考量：
  - 在全局工作区顶栏挂载 `<RunNotificationCenter />`（Overview, Projects, Control Plane, Governance 等全页面覆盖）。
  - 在沉浸式 Chat 页面右上角（无论是未选智能体欢迎状态还是活跃对话状态）均常驻挂载 `<RunNotificationCenter />`，保证用户在任何视图下都能感知未读失败并快捷跳转。

## 验证结论

- **静态类型与 Lint**：`vue-tsc --noEmit` 0 报错；ESLint 0 报错。
- **单元测试**：Vitest 134 文件，722 用例全通过（含本专项新增与修改的 8 个 Spec 文件，全部 passed）。
- **生产构建**：`pnpm build` 打包成功，各 chunk 正常生成。
- **Playwright 端到端自动化测试**：
  - 启动 Worktree 隔离全栈三服务。
  - `e2e/run-completion.spec.ts` 4/4 用例全部通过（24.8s）。
  - 真实调用大模型（`deepseek-v4.1-flash`），成功终态绝不误报错误。
  - 1440/768/390 三视口自适应截图留存于 `docs/projects/20261009-agent-production-capability-extension/evidence/screenshots/`。
