# 04 - Services 收敛、错误解析统一与死代码清理

## 目标
清理前端仓库中积存的 0 引用死代码（Dead Code），解决 `src/services/` 下多达 19 个子目录职责碎片化、同一套后端 API 存在新旧两套 Service（如 `assistants` vs `agents`）、以及 HTTP 错误解析存在 3 套独立实现的问题；同时消除 `src/views/` 与 `src/modules/*/pages/` 的双轨目录分裂。

## 现状问题清单（基于源码全量扫描）

### 1. 确认 0 引用的死代码（Dead Code，可直接安全清除）
经 AST / 引用扫描确认，以下文件在业务代码中 **0 引用**：
1. `src/services/assistants/assistants.service.ts`（141 行）：旧版 Assistant 命名时期的 API 封装，与现行 `src/services/agents/agents.service.ts` 调用完全相同的 `/api/projects/{id}/agents` 接口，属于遗留重复代码。
2. `src/services/platform/workspace-context.ts`（29 行）：已被 `src/composables/useWorkspaceProjectContext.ts` 取代。
3. `src/modules/chat/components/ChatArtifactPanel.vue` & `src/modules/dear-agent/components/ChatArtifactPanel.vue`：已被 `WorkspacePanel.vue` 取代。
4. `src/components/platform/FilterSettingsMenu.vue` (125 行) & `src/composables/useVisibleFilterSettings.ts` (58 行)：未使用的表格列筛选组件。
5. `src/components/base/ThemeToggle.vue` & `src/components/platform/ButtonWithTooltip.vue`。

### 2. 三套重复的 HTTP 错误解析逻辑
目前前端在三个地方各自手写了 Axios / Blob 错误响应拆包逻辑：
- `src/utils/http-error.ts` (`resolvePlatformHttpErrorMessage`)
- `src/services/threads/workspace.service.ts` (`unwrapWorkspaceError`，第 25-66 行，含 Blob JSON 解析)
- `src/services/runtime-gateway/workspace.service.ts` (`toRuntimeGatewayErrorMeta`，含状态码分类)
**改造方案**：在 `src/utils/http-error.ts` 中统一提供支持 JSON 与 Blob 响应体的结构化错误解析器 `unwrapPlatformHttpError(err)`，供 `threads`、`runtime-gateway` 及全量页面统一调用。

### 3. `src/views/` 与 `src/modules/*/pages/` 双轨制收敛
- 现况：90% 的页面位于 `src/modules/{domain}/pages/*.vue`，但唯有登录页（`src/views/auth/LoginView.vue`、`AuthCallbackView.vue`）和无权限页（`src/views/workspace/AccessUnavailableView.vue`）还散落在顶层 `src/views/` 下。
- **改造方案**：将 `src/views/auth/*` 移入 `src/modules/account/pages/`（或 `src/modules/auth/pages/`），将 `AccessUnavailableView.vue` 移入 `src/modules/overview/pages/`（或共享反馈页），彻底废弃顶层 `src/views/` 目录。

## 任务拆分
- [x] Task 4.1：删除 8 个确认 0 引用的死代码文件及空目录（`services/assistants`、`services/platform` 等） - **状态：** 待开始
- [x] Task 4.2：统一 `src/utils/http-error.ts` 错误拆包逻辑，重构 `threads/workspace.service.ts` 与 `runtime-gateway/workspace.service.ts` 中的重复错误解析代码 - **状态：** 待开始
- [x] Task 4.3：迁移 `src/views/` 下的 3 个遗留视图至 `src/modules/` 对应模块并更新 `src/router/routes.ts` - **状态：** 待开始

## 验证要求与记录
### 验证要求
- [x] `pnpm typecheck` 零报错
- [x] `pnpm test:unit` 全量单测通过
- [x] `src/views/`、`src/services/assistants/`、`src/services/platform/` 目录彻底清空移除

## 状态
规划中
