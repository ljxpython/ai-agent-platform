# 前端交互与验证

## 目标

让用户在发起或继续对话前看见当前访问档位并切换，同时清楚告知免审批边界，不把高风险开关伪装成普通样式选项。

## 方案设计

借鉴 `research/deepseek-harness`（`packages/client/ui-permission-presets` 与 `ui-conversation`）的最佳工程实践：

### 1. 组件位置与视觉表现（方案 A）
- **集成位置：** 直接集成在 `apps/platform-web/src/modules/chat/components/ChatComposer.vue`（及 `dear-agent` 对话输入组件）底部的工具栏中，与 `ChatModelSelector` 并列。作为核心输入操作流的前置安全选择器 `ThreadAccessPolicySelect`。
- **视觉语言：** 借鉴 deepseek-harness 的 Shield 护盾状态图标体系：
  - `review`（审阅每项操作，默认档位）：带勾/把关护盾（蓝色/中性色），表示严格审批，写文件、编辑文件和执行命令均逐项确认。
  - `workspace_write`（允许工作区操作）：带编辑铅笔护盾（琥珀色/强调色），明确标示工作区免审放行。
- **状态互斥与锁定：**
  - 当无项目写权限（`!canWrite`）、Agent 运行中（`busy` / `stream.isLoading`）或存在未决审批中断（`reviews.length > 0`）时，选择器进入锁定状态（`disabled`），防止并发切档触发后端的 409 冲突。

### 2. 风险确认弹窗（Risk Gate）
- 切换到 `workspace_write` 时弹出专用的 `ThreadAccessRiskDialog`（基于 `BaseDialog` 封装）。
- 列出明确免审工具列表：`write_file`、`edit_file`、`execute`。
- 列出不可突破的红线工具列表：`deploy_preview`、技能发布/撤销、外部写入及凭据操作。
- **强制知晓复选框（Acknowledge Checkbox）：** 用户必须手动勾选“我已了解工作区自动执行风险”，确认按钮方可解除禁用并高亮允许提交。

### 3. 草稿态与生命周期同步（方案 1）
- **新会话（Draft 态，无 `thread_id`）：** 允许用户在发送第一条消息前预选 `workspace_write`（同样触发风险确认弹窗）；前端在草稿状态中暂存该选择。在发送首条消息触发 `service.create` 成功生成 `thread_id` 后、调用 `stream.submit` 启动 run **之前**，自动执行 `PATCH /api/langgraph/threads/{thread_id}/access-policy` 同步服务端策略，确保首轮执行即可直接免审，不产生意外打断。
- **既有会话：** 切换时立即调用 Platform API；网络请求期间显示微型 Loading，成功后更新状态，失败时保留服务端原值并提示错误，严禁乐观更新。
- **状态还原：** 页面刷新、切换线程和流重连均从线程 `metadata.access_policy` 还原，缺省视为 `review`。策略仅影响后续 `run.start`，不回溯既有中断。

### 前端对接契约

1. 线程详情 `GET /api/langgraph/threads/{thread_id}` 的 `metadata.access_policy` 是唯一显示值；缺失时显示 `review`。
2. 切换调用 `PATCH /api/langgraph/threads/{thread_id}/access-policy`，body 固定为 `{ "access_policy": "review" }` 或 `{ "access_policy": "workspace_write" }`。成功响应为 `{ "thread_id": "...", "access_policy": "..." }`。
3. 仅在用户确认后发送 `workspace_write`；请求失败时保留服务端原值并显示网关错误。不要把档位塞进 run payload、`configurable.platform_runtime` 或 resume payload。
4. 收到新的 thread 数据、切换线程、重连 SSE 和刷新页面时，以 metadata 重建状态。策略只影响下一次 `run.start`，不自动恢复或批准既有 interrupt。
5. `ChatComposer.vue`（通用输入框）接入共享的 `ThreadAccessPolicySelect`；service 放在 `src/services/threads/access-policy.service.ts`，类型扩展现有 thread 类型定义。选择器在无项目写权限、当前处于运行/审批中或后端返回不支持时禁用。

## 任务拆分

- [x] 新增 `src/services/threads/access-policy.service.ts` 及单元测试，扩展 `session.service.ts` 类型定义。
- [x] 开发 `ThreadAccessRiskDialog.vue`（带强制勾选知晓与免审/红线清单）与 `ThreadAccessPolicySelect.vue`（含 Shield 图标与下拉菜单）。
- [x] 改造 `useChatSession.ts` 与 `useDearAgentSession.ts`：支持 `accessPolicy` 响应式状态、草稿态暂存与新建线程时前置补发 PATCH。
- [x] 在 `ChatComposer.vue` 与 `DearAgent` 输入区域接入 `ThreadAccessPolicySelect`，并在 `ChatSession.vue` 与 `DearAgentSession.vue` 完成数据与事件传递。
- [x] 补齐前端单元测试与组件测试，验证档位切换、草稿态补发、弹窗确认与禁用逻辑。
- [ ] 执行全栈浏览器端到端 E2E 验证。

## 验证要求与记录

### 验证要求
- [x] 初始线程及新会话默认显示 `review`。
- [x] 草稿态预选 `workspace_write` 或 `full_access` 并在弹窗确认后发送首条消息，新建线程成功后自动应用该策略，首轮免审。
- [x] 既有线程切换到 `workspace_write` 或 `full_access` 需强制勾选对应弹窗复选框确认；确认后刷新页面仍正确显示。
- [x] 输入框工具栏布局优化：左侧放置权限与附件，右侧放置模型选择器与发送按钮。
- [x] 运行中（busy）、审批中断（interrupted）或无写权限（!canWrite）时，选择器禁用。
- [x] 请求失败时不乐观伪造状态，正确回滚并展示错误提示。
- [ ] E2E 覆盖 `platform-web -> platform-api -> runtime-service`：写入免审、全权负责免全部审批，高风险操作按策略放行。
- [ ] 回归现有审批面板和恢复 run 流程。

### 验证记录

#### 2026-09-17 前端实施与验证
- **执行人：** @lijiaxin
- **验证范围：** `platform-web` 访问策略组件、服务层、会话 Composable 与构建链路。
- **单元测试：**
  - ✅ `src/services/threads/access-policy.service.spec.ts` (1 项通过)
  - ✅ `src/modules/chat/components/ThreadAccessRiskDialog.spec.ts` (3 项通过，含 Full access 专用警告与文案测试)
  - ✅ `src/modules/chat/components/ThreadAccessPolicySelect.spec.ts` (4 项通过，含 Full access 弹窗与确认流程测试)
  - ✅ `src/modules/chat/components/ChatComposer.spec.ts` (3 项通过，含工具栏新布局验证)
  - ✅ `src/modules/chat/composables/useChatSession.spec.ts` (7 项通过)
  - **总计：** 5 个测试文件，18 个单元用例全部通过。
- **质量检查：**
  - ✅ `vue-tsc --noEmit`：0 错误，严格类型检查通过。
  - ✅ `eslint`：0 错误通过。
  - ✅ `vite build`：生产环境打包成功。
- **四态判定：** `partial`
  - 前端组件、状态流转与单元契约已全部实现并通过验证；
  - 跨容器真实浏览器 E2E 联动（`local-stack.sh` + Playwright）需待本地完整服务栈启动后执行。

## 状态

部分完成：全权负责 (Full access) 端到端与前端新排版已落地，待全栈联调与 E2E 验收。

