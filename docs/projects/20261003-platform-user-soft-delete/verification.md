# 平台用户软删除与生命周期治理 - 验证计划和记录

## 验证计划

### 单元测试
- [x] `test_soft_delete_user_success` - 正常软删除用户，用户名加后缀释放，状态更新为 deleted，tokens 被吊销，退出关联项目
- [x] `test_soft_delete_user_cannot_delete_self` - 拦截自杀操作，返回 409 cannot_delete_self
- [x] `test_soft_delete_user_last_super_admin_protected` - 拦截删除最后一个激活的超级管理员，返回 409
- [x] `test_soft_delete_user_sole_project_admin_protected` - 拦截删除作为项目唯一管理员的用户，返回 409 user_is_sole_project_admin 并提示冲突项目
- [x] `test_list_users_filters_out_deleted_by_default` - 默认查询排除已删除用户，显式传 status=deleted 可查出
- [x] `test_frontend_users_page_delete_action` - 前端 UsersPage 操作菜单、防自杀禁用与弹窗交互单测

### 端到端与打包测试
- [x] 后端 `pytest apps/platform-api/tests/test_user_soft_delete_api.py` 全绿
- [x] 前端 `pnpm test run src/modules/users` 全绿
- [x] 前端 `pnpm build` 生产构建全绿

## 验证记录

### 2026-10-03 验证
**执行人：** @laowang

#### 1. 后端定向与回归测试
- **命令：** `env PYTHONPATH="apps/platform-api:apps/platform-api/src" apps/platform-api/.venv/bin/pytest apps/platform-api/tests/test_user_soft_delete_api.py apps/platform-api/tests/test_user_platform_roles_api.py`
- **结果：** ✅ 10 passed in 16.16s
  - `UserSoftDeleteApiTest.test_soft_delete_cannot_delete_self`: ✅ passed
  - `UserSoftDeleteApiTest.test_soft_delete_last_super_admin_protected`: ✅ passed
  - `UserSoftDeleteApiTest.test_soft_delete_user_sole_project_admin_protected`: ✅ passed
  - `UserSoftDeleteApiTest.test_soft_delete_success_and_list_filter`: ✅ passed
  - 存量 6 项用户平台角色与凭据测试全部通过。

#### 2. 前端单元测试
- **命令：** `pnpm --dir apps/platform-web test run src/modules/users`
- **结果：** ✅ 2 test files passed, 7 tests passed in 4.16s
  - `UserCreatePage.spec.ts`: 6 passed
  - `UsersPage.spec.ts`: 1 passed（覆盖列表渲染、操作菜单、自杀置灰保护、确认弹窗与 deleteUser API 调用）

#### 3. 前端生产打包验证
- **命令：** `pnpm --dir apps/platform-web build`
- **结果：** ✅ built in 21.48s（TypeScript 零错误、Vite 打包 100% 成功）

#### 最终结论
- **项目状态：** `done`
- **四态判定：** 达成全部预期设计，后端安全栅栏坚固，前端交互完整，无任何回归问题。
