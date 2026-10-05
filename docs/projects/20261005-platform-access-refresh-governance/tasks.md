# 平台权限状态与刷新治理 - 任务拆分

## Phase 1: 权限状态与会话错误分类

### Task 1.1: 修复项目权限快照状态
- **改动内容：** 后台刷新失败保留快照；明确拒绝才清除；统一路由与 Layout 的具体权限判断。
- **代码位置：** `apps/platform-web/src/stores/workspace.ts`、`WorkspaceLayout.vue`、`router/guards.ts`
- **预期结果：** 切屏/网络抖动不显示权限失效；真实无权仍阻断。
- **验证项：** workspace、router、layout 单测。
- **验证项：** `pnpm exec vitest run src/stores/workspace.spec.ts src/router/guards.spec.ts src/layouts/WorkspaceLayout.access.spec.ts` → ✅ 通过（17 项）
- **状态：** `[x]` 已完成 2026-10-05 → 见 implementation/01-permission-state.md

### Task 1.2: 区分 Token 刷新失败类型
- **改动内容：** 网络/5xx 不清理会话，明确 400/401 才过期。
- **代码位置：** `apps/platform-web/src/services/http/client.ts`、`langgraph/client.ts`
- **预期结果：** 临时认证服务故障可恢复，不跳登录。
- **验证项：** HTTP 和 LangGraph 客户端单测。
- **验证项：** `pnpm exec vitest run src/services/http/client.spec.ts src/services/langgraph/client.spec.ts` → ✅ 通过（17 项）
- **状态：** `[x]` 已完成 2026-10-05 → 见 implementation/02-token-refresh.md

## Phase 2: 作用域化刷新

### Task 2.1: 作用域化拒绝事件
- **改动内容：** 事件携带 project/thread/operation，区分项目授权和资源授权。
- **代码位置：** HTTP/Fetch 客户端、`useSessionConnection.ts`、`ThreadGovernancePage.vue`
- **预期结果：** 单个 Thread 403 不触发整页项目刷新。
- **验证项：** SessionConnection 单测、客户端事件单测。
- **验证项：** `pnpm exec vitest run src/services/auth/access-events.spec.ts src/modules/chat/composables/useSessionConnection.spec.ts` → ✅ 通过（8 项）
- **状态：** `[x]` 已完成 2026-10-05 → 见 implementation/03-scoped-refresh.md

### Task 2.2: 合并项目权限刷新
- **改动内容：** 同一项目共享 in-flight 刷新，聚焦/可见性/定时器复用统一入口。
- **代码位置：** `workspace.ts`、`WorkspaceLayout.vue`
- **预期结果：** 多会话场景刷新请求数量稳定且可控。
- **验证项：** 并发刷新与事件风暴测试。
- **验证项：** `pnpm exec vitest run src/stores/workspace.spec.ts` → ✅ 并发合并用例通过；Playwright 4 条故障注入通过
- **状态：** `[x]` 已完成 2026-10-05 → 见 implementation/03-scoped-refresh.md

## Phase 3: 后端校核与全面验证

### Task 3.1: 校核 ACL 回查链路
- **改动内容：** 核对超时配置、连接复用和日志字段，不降低授权边界。
- **代码位置：** `apps/runtime-service/src/runtime_service/auth/platform.py`、Runtime Gateway。
- **预期结果：** ACL 暂时不可用返回明确可诊断错误，真实拒绝仍为 403。
- **验证项：** Runtime 认证和 Gateway 测试。
- **验证项：** `uv run pytest tests/runtime/test_platform_auth.py tests/runtime/test_auth.py -q` → ✅ 定向 52 项通过；Runtime runtime 目录 114 项通过；最终连接池模块分离后 platform_auth + app_lifespan 定向 41 项通过；platform-api 13 项和 299 子测试通过
- **状态：** `[x]` 已完成 2026-10-05 → 见 implementation/04-runtime-acl.md

### Task 3.2: Final 全量验证
- **改动内容：** 执行单元、集成、端到端、安全和必要性能验证。
- **验证项：** 见 `verification.md`。
- **验证项：** 前端全量 473 passed/1 skipped；生产构建通过；治理 E2E 4 项通过；故障注入 E2E 4 项通过
- **状态：** `[x]` 已完成 2026-10-05 → 见 implementation/05-verification.md

## 进度追踪
- [x] Phase 1 完成
- [x] Phase 2 完成
- [x] Phase 3 全量验证通过

## 各 Task 合规检查（1.1/1.2/2.1/2.2/3.1/3.2）
- [x] 实现完成并完成对应验证项，结果见上述每个 Task。
- [x] tasks 状态更新；implementation 只记录细节。
- [x] CONTEXT、FEATURES、CHANGELOG 及服务规范统一收尾更新。
- [x] 用户在本会话批准方案；未提交或生产部署。
