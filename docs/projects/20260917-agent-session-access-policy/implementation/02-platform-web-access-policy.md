# Platform Web 访问策略实施

## 改动时间
2026-09-17

## 相关任务
- 04 前端交互与验证

## 改动文件
- `apps/platform-web/src/services/threads/session.service.ts`
- `apps/platform-web/src/services/threads/access-policy.service.ts`
- `apps/platform-web/src/services/threads/access-policy.service.spec.ts`
- `apps/platform-web/src/modules/chat/components/ThreadAccessRiskDialog.vue`
- `apps/platform-web/src/modules/chat/components/ThreadAccessRiskDialog.spec.ts`
- `apps/platform-web/src/modules/chat/components/ThreadAccessPolicySelect.vue`
- `apps/platform-web/src/modules/chat/components/ThreadAccessPolicySelect.spec.ts`
- `apps/platform-web/src/modules/chat/components/ChatComposer.vue`
- `apps/platform-web/src/modules/chat/components/ChatComposer.spec.ts`
- `apps/platform-web/src/modules/chat/components/ChatSession.vue`
- `apps/platform-web/src/modules/chat/composables/useChatSession.ts`
- `apps/platform-web/src/modules/chat/composables/useChatSession.spec.ts`
- `apps/platform-web/src/modules/dear-agent/components/ChatComposer.vue`
- `apps/platform-web/src/modules/dear-agent/components/DearAgentSession.vue`
- `apps/platform-web/src/modules/dear-agent/composables/useDearAgentSession.ts`

## 具体改动

### 1. 服务层与类型定义
- `session.service.ts` 导出 `AccessPolicy = 'review' | 'workspace_write'`。
- 新增 `access-policy.service.ts`，封装 `updateThreadAccessPolicy(projectId, threadId, policy)`，通过 `platformHttpClient` 向 `PATCH /api/langgraph/threads/{thread_id}/access-policy` 发送请求并自动携带 `x-project-id` 与认证凭据。

### 2. 交互与安全风控组件（借鉴 deepseek-harness 实践）
- `ThreadAccessRiskDialog.vue`：基于 `BaseDialog` 构建，展示白名单免审范围（文件读写、受限命令）与不可突破的审批底线（部署、技能发布、外部凭据），配置强制知晓 Checkbox（`acknowledged`），未勾选时确认按钮锁定。
- `ThreadAccessPolicySelect.vue`：集成在输入框底部工具栏中（方案 A），呈现语义化 Shield 盾牌状态图标（带勾把关盾牌 vs 带铅笔工作区写盾牌），支持浮层选择与安全互斥（运行中、待审批或无写权限时禁用）；选择 `workspace_write` 触发风险确认弹窗。

### 3. 会话状态机与草稿态生命周期（方案 1）
- `useChatSession.ts` 与 `useDearAgentSession.ts`：
  - 增加 `accessPolicy` 响应式变量与 `setAccessPolicy`、`refreshAccessPolicy` 方法。
  - 草稿态暂存：未创建线程时预选并确认的值暂存在前端；用户首发消息在 `service.create` 获取到 `thread_id` 后、`stream.submit` 启动 run 之前，自动前置补发 `PATCH /access-policy`，保障首轮对话即按预选策略执行。
  - 现有会话切换严格以服务端响应为准，失败保留原值并不乐观伪造。
  - 页面刷新、线程切换与状态校验时，从线程 `metadata.access_policy` 强一致恢复状态。

### 4. 页面集成
- `ChatComposer.vue` 与 `dear-agent` 的 `ChatComposer.vue` 分别在工具栏挂载 `ThreadAccessPolicySelect`（与 `ChatModelSelector` 并列）。
- `ChatSession.vue` 与 `DearAgentSession.vue` 透传策略状态与更新回调，并在头部 Thread ID 旁展示免审状态徽章。

## 验证
- 单元测试：
  - `access-policy.service.spec.ts`：1/1 通过。
  - `ThreadAccessPolicySelect.spec.ts`：3/3 通过。
  - `ThreadAccessRiskDialog.spec.ts`：2/2 通过。
  - `ChatComposer.spec.ts`：3/3 通过。
  - `useChatSession.spec.ts`：7/7 通过（包含草稿态暂存与首发补发、已有线程更新与失败回退）。
- 代码质量：
  - `vue-tsc --noEmit`：0 错误通过。
  - `eslint`：0 错误通过。
  - `vite build`：生产打包通过。
