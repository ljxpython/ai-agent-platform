# 02. 裁剪与保留方案

## 裁剪原则

本轮迁移必须遵守一个硬规则：

- 先把 `sub2api` 裁成“平台前端基座”
- 再把我们自己的业务迁进去

不能反过来。

如果不先裁剪，后面一定会出现：

- 旧业务残留
- 路由名称混乱
- API 模块命名污染
- 文案、权限、导航混杂

## 保留项

下面这些建议保留，作为未来新 app 的基础资产。

### 1. 样式与视觉系统

建议保留：

- `frontend/src/style.css`
- `frontend/tailwind.config.js`
- 整体色板、阴影、玻璃卡片、导航与表格样式

原因：

- 这是老板真正看中的部分
- 也是这套方案里最值钱的资产

### 2. 布局层

建议保留并改造：

- `frontend/src/components/layout/AppLayout.vue`
- `frontend/src/components/layout/AppSidebar.vue`
- `frontend/src/components/layout/AppHeader.vue`
- `frontend/src/components/layout/AuthLayout.vue`
- `frontend/src/components/layout/TablePageLayout.vue`

处理方式：

- 不直接照搬
- 迁移到我们自己的布局目录后再拆分和重命名

### 3. 基础设施层

建议保留思路或局部实现：

- `frontend/src/api/client.ts`
- `frontend/src/stores/app.ts`
- `frontend/src/stores/auth.ts`
- `frontend/src/router/*`
- `frontend/src/components/common/*`
- `frontend/src/components/icons/*`
- `frontend/src/composables/*`

处理方式：

- 保留模式
- 不保留上游业务含义

### 4. 工程能力

建议保留：

- `Vite`
- `Vue 3`
- `TypeScript strict`
- `Vue Router`
- `Pinia`
- `Vitest`
- `ESLint`

## 删除项

下面这些在正式迁移时应该被直接裁掉，不进入新 app。

### 1. 上游仓库非前端部分

建议不纳入新平台前端：

- `backend/`
- `deploy/`
- `tools/`
- `assets/partners/`
- 上游产品 README / 发布配置 / Docker 相关文件

### 2. 与我们业务无关的用户侧页面

优先裁掉：

- `HomeView`
- `RegisterView`
- `EmailVerifyView`
- `OAuthCallbackView`
- `LinuxDoCallbackView`
- `ForgotPasswordView`
- `ResetPasswordView`
- `KeyUsageView`
- `KeysView`
- `UsageView`
- `RedeemView`
- `SubscriptionsView`
- `PurchaseSubscriptionView`
- `SoraView`
- `CustomPageView`

### 3. 与我们业务无关的管理页

优先裁掉：

- `AccountsView`
- `GroupsView`
- `PromoCodesView`
- `ProxiesView`
- `SubscriptionsView`
- `BackupView`
- `DataManagementView`
- `SettingsView`
- `AnnouncementsView`
- `OpsDashboard`

这些页面不是“可选功能”，而是会污染未来平台前端认知的噪音。

## 必须重建项

下面这些即便保留技术基座，也必须按我们的业务重新做。

### 1. 路由体系

未来应该围绕这些路由建立：

- `/workspace/overview`
- `/workspace/projects`
- `/workspace/projects/:projectId`
- `/workspace/users`
- `/workspace/users/:userId`
- `/workspace/assistants`
- `/workspace/assistants/new`
- `/workspace/assistants/:assistantId`
- `/workspace/graphs`
- `/workspace/runtime`
- `/workspace/runtime/models`
- `/workspace/runtime/tools`
- `/workspace/sql-agent`
- `/workspace/threads`
- `/workspace/chat`
- `/workspace/testcase/generate`
- `/workspace/testcase/cases`
- `/workspace/testcase/documents`
- `/workspace/me`
- `/workspace/security`
- `/workspace/audit`

### 2. 认证链路

必须重建：

- 用户名密码登录
- token 持久化
- refresh token
- 当前用户信息
- 权限守卫

不能继续沿用上游的：

- 邮箱注册
- 2FA 模态
- LinuxDo OAuth
- setup wizard

### 3. API 模块

必须按我们业务重建：

- `auth`
- `projects`
- `members`
- `users`
- `assistants`
- `graphs`
- `runtime`
- `audit`
- `threads`
- `testcase`
- `artifacts`

### 4. 状态层

必须重建：

- 会话状态
- workspace 上下文
- 当前项目切换
- 当前 chat target 偏好
- 页面级筛选状态

## 当前建议的处理方式

### 当前阶段

- `apps/platform-web-sub2api-base` 只做参考和裁剪评估

### 正式迁移阶段

建议新建正式 app，名称已确认：

- `apps/platform-web-vue`

然后：

1. 从 `sub2api/frontend` 提取真正有价值的壳子和基础设施
2. 不保留上游无关业务目录
3. 不保留上游页面命名与业务语义
4. 重新组织为当前平台自己的前端结构
