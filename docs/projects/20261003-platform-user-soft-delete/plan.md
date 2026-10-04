# 平台用户软删除与生命周期治理 - 整体方案

## 背景
当前平台用户管理页面（`/workspace/users`）仅支持将用户置为 `disabled`（停用），缺失删除能力。直接在数据库物理硬删除会引发外键级联灾难（导致审计日志断裂、会话 Owner 幽灵化、项目唯一管理员被抹除导致项目沦为无主孤儿）。因此需引入合规、安全的“状态软删除（Soft Delete）”机制，释放被占用的用户名与邮箱，吊销凭证，并保护项目与系统管理连续性。

## 目标
1. `platform-api` 实现 `DELETE /api/users/{user_id}` 接口与服务层安全逻辑。
2. 扩展用户状态枚举 `UserStatus.DELETED = "deleted"`，并在默认用户列表查询中自动排除已删除用户。
3. 建立三重硬核安全防护栅栏：
   - 禁止删除当前登录账号自己（防自杀）；
   - 禁止删除系统最后一个激活的超级管理员（防系统锁死）；
   - 禁止删除作为任意项目唯一管理员（Sole Admin）的用户，拦截并提示需先移交权限或删除项目。
4. 软删除成功后自动脱敏/释放用户名 `username` 与 `external_subject`，撤销该用户所在的所有项目普通成员身份，并吊销全部有效 Refresh Token。
5. `platform-web` 用户管理页面接入删除操作、二次确认弹窗、错误提示及用户体验优化。

## 方案设计

### 1. 契约与枚举扩展
- `UserStatus`:
  ```python
  class UserStatus(StrEnum):
      ACTIVE = "active"
      DISABLED = "disabled"
      DELETED = "deleted"
  ```
- API 端点：
  `DELETE /api/users/{user_id}` -> 返回 `AckResponse(ok=True)`。
  权限要求：`PermissionCode.PLATFORM_SUPER_ADMIN_MANAGE` 或 `PLATFORM_USER_STATUS_WRITE`（超管或具有用户状态写权限的平台管理员）。
  审计动作：`user.deleted`。

### 2. 核心服务层设计 (`UsersService.delete_user`)
```text
[发起 DELETE /api/users/{user_id}]
       │
       ▼
 权限校验 (PLATFORM_USER_STATUS_WRITE)
       │
       ▼
 目标存在性校验 (404 user_not_found) & 检查是否已是 deleted
       │
       ▼
 栅栏 1: 是不是自己？ (actor.user_id == user_id -> 409 cannot_delete_self)
       │
       ▼
 栅栏 2: 是不是最后一个活跃超管？ (is_super_admin and count_active_super_admins <= 1 -> 409 last_super_admin_protected)
       │
       ▼
 栅栏 3: 是不是某些项目的唯一管理员？
 查询用户的项目列表及每个项目的管理员数量：
 若存在任何一个项目该用户是 admin 且项目 admin 总数 <= 1
 -> 409 user_is_sole_project_admin (附带受阻项目名称)
       │
       ▼
 业务执行：
 1. 清理项目成员关系：从其所属的所有项目中移除 (DELETE FROM project_members WHERE user_id = :id)
 2. 释放唯一字段：
    new_username = f"{user.username}#deleted#{uuid_short}"
    new_subject = f"{user.external_subject}#deleted#{uuid_short}"
 3. 更新用户状态：status = "deleted", username = new_username, external_subject = new_subject
 4. 吊销所有 Refresh Tokens
 5. 写入审计日志 (action="user.deleted")
```

### 3. 用户列表查询默认过滤
在 `SqlAlchemyUsersRepository.list_users` 中：
- 若显式指定 `status`，按指定状态查；
- 若未指定 `status`，默认添加条件 `UserRecord.status != "deleted"`，确保已删除用户不会出现在正常列表内。

### 4. 前端集成设计 (`platform-web`)
- `services/users/users.service.ts`: 新增 `deleteUser(userId: string): Promise<AckResponse>`；
- `types/management.ts`: 扩展 `ManagementUser.status` 支持 `'deleted'`；
- `UsersPage.vue`:
  - 操作菜单增加“删除用户”项（标记为危险项 `danger: true`）；
  - 绑定二次确认弹窗 `ConfirmDialog`；
  - 若为当前登录用户，操作项置灰并提示“不可删除当前登录账号”。
- `UserDetailPage.vue`:
  - 增加“删除用户”按钮与确认弹窗，删除后自动跳转回 `/workspace/users`。

## 链路影响
- `platform-web` → `platform-api`（用户管理模块）
- 数据库 `users` 表与 `project_members` 表、`refresh_tokens` 表

## 风险和依赖
- **风险 1：** 用户名被释放后，若用户再次注册同名账号，历史审计日志中的旧记录仍指向旧 user_id，如何识别？
  - **应对：** 审计日志记录的是当时不可变的 `actor_user_id`（UUID）与当时的快照字段，新用户的 `id` 是全新 UUID，数据完全隔离。
- **风险 2：** 并发删除或超管竞争。
  - **应对：** 事务控制与锁检查，严格校验管理员计数。

## 实施计划
- Phase 1: 后端数据契约、安全栅栏与 `DELETE /api/users/{user_id}` 接口实现。
- Phase 2: 后端列表查询过滤与项目成员级联清理。
- Phase 3: 前端 API Client、`UsersPage.vue` 与 `UserDetailPage.vue` 删除交互集成。
- Phase 4: 全量单测与端到端链路验证。
