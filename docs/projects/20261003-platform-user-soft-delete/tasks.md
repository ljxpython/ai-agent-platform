# 平台用户软删除与生命周期治理 - 任务拆分

## Phase 1: 后端数据模型、枚举与安全删除逻辑

### Task 1.1: 扩展 UserStatus 枚举与仓储层操作
- **改动内容：** 在 `UserStatus` 中增加 `DELETED = "deleted"`；在 `SqlAlchemyUsersRepository` 中增加软删除方法 `soft_delete_user`（重命名 username/external_subject、设置状态为 deleted、清理 refresh tokens），并在 `list_users` 中默认过滤 `deleted` 用户。
- **代码位置：**
  - `apps/platform-api/src/platform_api/modules/identity/schemas.py` → `UserStatus`
  - `apps/platform-api/src/platform_api/modules/users/repository.py` → `SqlAlchemyUsersRepository`
- **预期结果：** 支持将用户状态设置为 deleted，默认 `list_users` 排除已删除用户。
- **验证项：** `pytest apps/platform-api/tests/test_user_soft_delete_api.py` → ✅ 通过 (4 passed)
- **状态：** `[x]` 已完成 2026-10-03
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新

### Task 1.2: 服务层安全护栏与软删除业务实现
- **改动内容：** 在 `UsersService` 实现 `delete_user`，包含四大防线：
  1. 权限拦截 `PLATFORM_USER_STATUS_WRITE`；
  2. 防自杀检查（当前操作者 `actor.user_id == target_user_id` 时拦截报错 `cannot_delete_self`）；
  3. 最后超管保护（`last_super_admin_protected`）；
  4. 唯一项目管理员检查（若用户是任何一个项目的唯一 admin，拦截报错 `user_is_sole_project_admin`）；
  5. 自动从该用户参与的所有项目中移除成员记录，完成软删除与 token 吊销。
- **代码位置：** `apps/platform-api/src/platform_api/modules/users/service.py` → `UsersService.delete_user`
- **预期结果：** 防护机制生效，安全完成用户软删除与项目退出。
- **验证项：** `pytest apps/platform-api/tests/test_user_soft_delete_api.py` → ✅ 通过 (4 passed)
- **状态：** `[x]` 已完成 2026-10-03
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新

### Task 1.3: HTTP 路由与审计日志挂载
- **改动内容：** 暴露 `DELETE /api/users/{user_id}` 路由，响应 `AckResponse`，审计标记为 `user.deleted`。
- **代码位置：**
  - `apps/platform-api/src/platform_api/modules/users/router.py` → `delete_user`
  - `apps/platform-api/src/platform_api/modules/audit/http_resolution.py` → `user.item.deleted`
- **预期结果：** HTTP 请求能正确路由并返回统一响应。
- **验证项：** `test_soft_delete_success_and_list_filter` 验证 HTTP 契约与 `user.item.deleted` 审计 → ✅ 通过
- **状态：** `[x]` 已完成 2026-10-03
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新

## Phase 2: 前端用户管理页面与交互集成

### Task 2.1: 前端 Service 与数据契约扩展
- **改动内容：** 在 `users.service.ts` 中封装 `deleteUser(userId: string)` API 调用；在 `types/management.ts` 中补充 `status` 类型支持。
- **代码位置：**
  - `apps/platform-web/src/services/users/users.service.ts`
  - `apps/platform-web/src/types/management.ts`
- **预期结果：** 前端具备调用删除接口的类型与客户端能力。
- **验证项：** `pnpm --dir apps/platform-web build` 类型检查 → ✅ 通过
- **状态：** `[x]` 已完成 2026-10-03
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新

### Task 2.2: 用户管理列表与详情页交互实装
- **改动内容：**
  1. `UsersPage.vue`: 操作菜单新增“删除用户”动作，当前登录账号自杀保护置灰提示，点击弹出二次确认对话框，删除成功后 Toast 提示并刷新列表，状态下拉增加 deleted 选项；
  2. `UserDetailPage.vue`: 头部危险操作区提供“删除用户”按钮与确认弹窗，删除后自动跳转回 `/workspace/users`。
- **代码位置：**
  - `apps/platform-web/src/modules/users/pages/UsersPage.vue`
  - `apps/platform-web/src/modules/users/pages/UserDetailPage.vue`
- **预期结果：** 页面交互流畅，危险操作有防误触二次确认，拦截报错友好呈现。
- **验证项：** `pnpm --dir apps/platform-web test run src/modules/users` → ✅ 通过 (2 套件 / 7 项测试)
- **状态：** `[x]` 已完成 2026-10-03
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新

## Phase 3: 全链路验证与文档收敛

### Task 3.1: Final 全量验证
- **改动内容：** 执行后端 Python 测试全量、前端 Vitest 单测与生产打包，记录验证结果。
- **验证项：**
  - 后端 Python 测试通过（10 项全通）；
  - 前端 Vitest 测试通过（7 项全通）；
  - 前端 `pnpm build` 生产构建全绿通过。
- **状态：** `[x]` 已完成 2026-10-03
- **合规检查：**
  - [x] 代码实现完成
  - [x] 验证项已执行
  - [x] tasks.md 状态已更新

## 进度追踪
- [x] Phase 1 完成（后端）
- [x] Phase 2 完成（前端）
- [x] Phase 3 完成（全量验证）
