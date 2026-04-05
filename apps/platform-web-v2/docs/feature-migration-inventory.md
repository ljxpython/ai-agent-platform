# Platform Web V2 功能迁移台账

更新时间：2026-04-01

## 1. 目的

这份文档用于完整盘点当前 `apps/platform-web` 已有能力，并作为后续迁移到 `apps/platform-web-v2` 的功能验收基线。

最终目标不是“迁几个好看的页面”，而是：

- 当前平台已有功能全部迁移成功
- 页面观感升级
- UI 代码工程化

## 2. 迁移验收总原则

后续任何页面只有同时满足以下条件，才算迁移完成：

1. 路由已在 `platform-web-v2` 中落地
2. 页面主要展示与核心交互可用
3. 依赖的 API / provider / query-state 已接通
4. 视觉风格符合新版工作台标准
5. 页面没有脱离统一母版体系独自野长

## 3. 当前平台能力全量盘点

## 3.1 根路由与认证

### `/`

职责：

- 根据登录态跳转
- 已登录 -> `/workspace/projects`
- 未登录 -> `/auth/login`

迁移要求：

- 保持相同行为

### `/auth/login`

职责：

- 用户名密码登录
- 写入本地 token
- 登录后跳转工作区

依赖：

- `/_management/auth/login`
- 本地 token 存储

### `/auth/callback`

职责：

- 认证回调承接页

迁移要求：

- 保持认证链路兼容

## 3.2 工作区壳子

### `/workspace/*`

当前能力：

- `WorkspaceAuthGuard`
- `WorkspaceProvider`
- `LogBootstrap`
- `WorkspaceShell`

主导航范围：

- Chat
- Testcase
- SQL Agent
- Threads
- Graphs
- Assistants
- Runtime
- Projects
- Users
- My Profile
- Security
- Audit

迁移要求：

- 改为新版工作台壳子
- 但所有导航能力必须保留

## 3.3 工作区共享状态

### `WorkspaceContext`

当前能力：

- 基于 URL query state 管理：
  - `projectId`
  - `assistantId`
  - `threadId`
- 项目切换时清理 thread / assistant 状态
- 若 URL 无 `projectId`，自动回退到第一条项目

迁移要求：

- 行为保持一致
- 可以优化展示方式，但不应破坏当前状态约定

### `ThreadProvider` / `StreamProvider`

当前能力：

- thread 查询与列表
- stream 运行时交互
- assistant / graph 选择
- chat 消息与 UI event 合并

迁移要求：

- 在 chat / threads / sql-agent / testcase generate 迁移时复用或平滑承接

## 3.4 标准管理页

### `/workspace/projects`

当前能力：

- 项目分页列表
- 搜索
- 删除项目
- 全局项目上下文切换
- 跳转项目创建页
- 跳转项目详情页

依赖：

- `projects.ts`
- `WorkspaceContext`

### `/workspace/projects/new`

当前能力：

- 新建项目

### `/workspace/projects/[projectId]`

当前能力：

- 项目详情入口
- 管理跳转

### `/workspace/projects/[projectId]/members`

当前能力：

- 项目成员列表
- 新增/更新成员角色
- 删除成员

依赖：

- `members.ts`

### `/workspace/users`

当前能力：

- 用户分页列表
- 系统级用户管理

### `/workspace/users/new`

当前能力：

- 新建系统用户

### `/workspace/users/[userId]`

当前能力：

- 用户详情
- 编辑资料
- 修改密码
- 角色/状态相关管理

依赖：

- `users.ts`

### `/workspace/assistants`

当前能力：

- assistant 分页列表
- 搜索
- 编辑
- 删除
- resync
- 运行时模型 / tools 配置承接

依赖：

- `assistants.ts`
- `runtime.ts`

### `/workspace/assistants/new`

当前能力：

- 新建 assistant
- 配置 graph / config / context / metadata

### `/workspace/assistants/[assistantId]`

当前能力：

- assistant 详情
- 编辑动态参数
- resync
- 跳转相关工作区

### `/workspace/graphs`

当前能力：

- graph 列表
- 搜索
- 从 runtime catalog 刷新

依赖：

- `graphs.ts`

### `/workspace/runtime`

当前能力：

- 跳转到 runtime 子页面

### `/workspace/runtime/models`

当前能力：

- 模型能力页

### `/workspace/runtime/tools`

当前能力：

- tools 能力页

依赖：

- `runtime.ts`

### `/workspace/audit`

当前能力：

- 审计日志列表
- 项目级审计查询

依赖：

- `audit.ts`

### `/workspace/me`

当前能力：

- 个人资料
- 头像 / 签名 / 资料维护
- 本地扩展资料缓存
- 修改密码入口

### `/workspace/security`

当前能力：

- 修改当前登录用户密码

## 3.5 Chat / Thread / Agent 工作区

### `/workspace/chat`

当前能力：

- 默认 chat 页面
- provider 组合
- thread / stream 运行时体验

### `/workspace/threads`

当前能力：

- thread 列表与 thread 视图

### `/workspace/sql-agent`

当前能力：

- 基于 Base Chat Template 的 agent 专属页面

### Chat 模板层

当前能力：

- `BaseChatTemplate`
- 默认 chat 包装
- SQL Agent 示例
- Testcase 生成页复用

迁移要求：

- 不能丢
- 应视为复杂工作区能力，不宜最先迁

## 3.6 Testcase 工作区

### `/workspace/testcase`

当前行为：

- 默认跳转到 `/workspace/testcase/generate`

### `/workspace/testcase/generate`

当前能力：

- 基于 `BaseChatTemplate`
- 固定 `test_case_agent`
- 支持真实文件上传
- 显示 testcase 专属上下文头

### `/workspace/testcase/cases`

当前能力：

- overview / batches / cases 查询
- 按 `batch_id / status / query` 查询
- testcase 新增 / 编辑 / 删除
- 来源文档选择
- 导出 `.xlsx`
- 列白名单导出
- 基于角色控制写权限
- 左侧列表 + 右侧详情编辑

### `/workspace/testcase/documents`

当前能力：

- 文档列表
- overview / batches / documents 查询
- 导出当前筛选结果
- 文档详情
- relations / batch detail
- PDF 预览
- PDF 下载
- 相关用例查看

依赖：

- `testcase.ts`

迁移要求：

- 这是复杂业务区，后置迁移，但不能丢

## 4. 当前 API 与前端边界

当前主要依赖的 management API 模块：

- `auth.ts`
- `projects.ts`
- `members.ts`
- `users.ts`
- `assistants.ts`
- `graphs.ts`
- `runtime.ts`
- `audit.ts`
- `testcase.ts`
- `threads.ts`
- `artifacts.ts`

迁移原则：

- 第一阶段尽量复用现有 client 思路
- 不先发明新协议
- 不让页面越过 `platform-api` 直连其他服务

## 5. 迁移优先级矩阵

### P0：最先迁移

这些页面最适合作为新版 UI 基座打样页：

- `/auth/login`
- `/workspace/projects`
- `/workspace/users`
- `/workspace/assistants`

原因：

- 最像标准企业后台
- 最能验证页面母版
- 最能直接体现审美升级

### P1：标准管理页扩展

- `/workspace/projects/new`
- `/workspace/projects/[projectId]`
- `/workspace/projects/[projectId]/members`
- `/workspace/users/new`
- `/workspace/users/[userId]`
- `/workspace/assistants/new`
- `/workspace/assistants/[assistantId]`
- `/workspace/graphs`
- `/workspace/runtime/models`
- `/workspace/runtime/tools`
- `/workspace/audit`
- `/workspace/me`
- `/workspace/security`

### P2：复杂工作区

- `/workspace/chat`
- `/workspace/threads`
- `/workspace/sql-agent`
- `/workspace/testcase/generate`
- `/workspace/testcase/cases`
- `/workspace/testcase/documents`

## 6. 当前最小迁移闭环

如果要尽快形成第一个“可展示、可继续开发”的新版工作台闭环，建议优先完成：

1. 新版登录页
2. 新版工作区壳子
3. Projects
4. Users
5. Assistants

做到这一步后，已经能够证明：

- 新版布局成立
- 默认主题成立
- 平台组件库成立
- 标准管理页迁移路线成立

## 7. 最终验收口径

最终迁移完成时，需要满足：

- 当前 `platform-web` 已有页面全部在 `platform-web-v2` 中承接
- 每个页面的关键交互仍可用
- 默认主题符合企业后台审美
- B/C 主题仍可切换
- 页面不再各写各的壳子
- 基础组件与平台组件边界清晰
