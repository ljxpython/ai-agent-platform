# platform-web-vue 切换到 Platform API V2 的策略

当前决定：

- 不新建新的前端 app
- 继续使用 `apps/platform-web-vue` 作为唯一正式前端宿主
- 后端改造的主战场是 `apps/platform-api-v2`

## 1. 为什么前端不复制一份

如果再建一份新的 `platform-web-vue`，会立刻出现：

- 两套页面
- 两套路由
- 两套组件封装
- 两套资源库
- 两套视觉与交互维护成本

这不符合当前目标。

当前目标是：

> 保持一个正式前端宿主，让前端服务层逐步切到新的控制面。

## 2. 前端切换原则

### 2.1 页面壳层不重做

现有 `platform-web-vue` 的：

- 布局
- 主题
- 资源库
- 导航
- 页面视觉体系

继续保留。

### 2.2 服务契约逐步切换

优先通过前端服务层完成切换，而不是页面里直接改 URL。

目标做法：

- 页面组件不关心是 `platform-api` 还是 `platform-api-v2`
- 页面只调用统一的 service client
- service client 决定最终命中哪个控制面

### 2.3 以模块为单位迁移

不按“整站一次切”做，而按模块逐步切：

1. identity
2. projects
3. users
4. members
5. announcements
6. assistants
7. runtime catalog / policies
8. testcase
9. runtime gateway

## 3. 推荐切换方式

### 第一阶段

- 前端继续默认连旧 `platform-api`
- 新功能与新契约先在 `platform-api-v2` 内开发
- 页面服务层开始预留模块化 client 结构
- 前端允许进入“双控制面过渡期”：
  - 旧控制面继续承接未迁模块
  - 新控制面模块通过独立 client / token / baseURL 接入
  - 禁止页面组件自己判断该打哪一套后端

### 第二阶段

- 某个模块在 `v2` 完整后，前端对应 service 切到 `v2`
- 页面层不变
- 一个模块切完就不回头继续走旧 API

当前已经明确的第一批前端切换对象：

- `runtime`
- `graphs`
- `chat`
- `threads`
- 与聊天目标直接相关的 `assistants` 读链路
- `assistant create` 所依赖的 runtime models / tools / graphs 目录

当前已经落地的前端过渡基座：

- `legacy` / `v2` 双 token 存储与刷新逻辑已经接通
- `legacy` / `v2` 双 http client 已接通
- `runtime_gateway` 已具备模块级 control plane 选择能力
- `workspaceStore` 已拆出独立的 runtime 项目上下文：
  - `runtimeProjectId`
  - `runtimeProjects`
  - `runtimeProject`
- 顶部项目切换器已经按路由切换项目上下文：
  - 普通页面继续使用 legacy 项目上下文
  - `chat / threads / sql-agent / assistants` 这些已迁页面优先使用 runtime 项目上下文
- `assistants` 服务已经支持显式 `mode: 'runtime'`
- `assistant create` 页的 graph 列表也已经支持显式 runtime 模式，避免 project 上下文串到 legacy 图目录
- `assistants` 模块级 control plane 选择现在正式挂到 `v2` runtime 开关下：
  - runtime 开关开启且 v2 token 存在时，`mode: 'runtime'` 的 assistants 请求会优先走 `platform-api-v2`
  - 这让列表 / 详情 / 创建 / 更新 / 重同步 / 删除保持同一套控制面
- `chat` 最近目标现在不再只缓存 `assistantId / graphId`：
  - 入口页会同时写入展示名
  - `chat` 页在展示名缺失时会受控调用 `assistants / runtime graph catalog` 做一次补齐
  - 旧 localStorage 数据保持兼容，不需要清缓存
- `threads` 页面现在和 `chat` 对齐目标展示：
  - 线程列表与详情优先显示 `assistant_name / graph_name`
  - 老线程如果只有 ID，会受控查询 `platform-api-v2` 的 assistants / runtime graph catalog 补名字
  - 新 thread 在创建时会写入 `target_display_name / assistant_name / graph_name`，避免后续继续制造裸 ID 元数据
- `identity` 模块现在支持显式 `runtime` 模式：
  - 登录仍保持 legacy 主登录链路，但会在登录成功后引导建立 `platform-api-v2` 会话
  - 当前用户读取优先走 `GET /api/identity/me`
  - 个人资料更新优先走 `PATCH /api/identity/me`
  - 改密优先走 `POST /api/identity/password/change`
  - 当前登录用户的资料链路已经与后台用户管理页彻底拆开，避免 `users` 模块未迁完时继续互相污染
- `announcements` 管理页现在支持显式 `runtime` 模式：
  - `/workspace/announcements` 在 `v2` 打开时会切到独立 runtime 项目上下文
  - 公告列表 / 创建 / 更新 / 删除优先走 `platform-api-v2`
  - 顶栏公告中心 feed 现已一并切到 `platform-api-v2`，与公告管理页保持同一套控制面
- `audit` 页面现在支持显式 `runtime` 模式：
  - `/workspace/audit` 在 `v2` 打开时会切到独立 runtime 项目上下文
  - 审计列表优先走 `GET /api/audit`
  - `v2` 的 `actor_user_id` 会在前端 service 层归一化成旧页面仍在使用的 `user_id`
- `projects` 页面族现在支持显式 `runtime` 模式：
  - `projects` 模块已纳入 control plane 选择器，`runtime` 开关开启且 `v2` token 存在时，`/workspace/projects*` 会使用独立 runtime 项目上下文
  - 项目列表读取 `GET /api/projects`
  - 项目创建读取 `POST /api/projects`
  - 项目详情中的成员预览读取 `GET /api/projects/{project_id}/members`
  - 成员页的成员列表 / 新增更新 / 删除分别读取 `GET /api/projects/{project_id}/members`、`PUT /api/projects/{project_id}/members/{user_id}`、`DELETE /api/projects/{project_id}/members/{user_id}`
  - 顶部项目切换器在 `projects` 页不再误用 legacy 项目上下文
- `overview` 页面现在开始复用 runtime 项目上下文：
  - `/workspace/overview` 已纳入 `projects` 模块的项目上下文规则
  - 项目摘要读取 `GET /api/projects`
  - 用户摘要读取 `GET /api/users`
  - 审计摘要读取 `GET /api/audit`
  - 助手摘要继续读取 `GET /api/projects/{project_id}/assistants`
- 顶栏 `AnnouncementCenter` feed 现在支持显式 `runtime` 模式：
  - 公告 feed 读取 `GET /api/announcements/feed`
  - 单条已读读取 `POST /api/announcements/{announcement_id}/read`
  - 全部已读读取 `POST /api/announcements/read-all`
  - 当 `v2` 不可用时仍保留本地 fallback 公告与已读状态，不让顶部交互直接挂死
- `runtime_catalog` 已在 `platform-api-v2` 落地：
  - `GET /api/runtime/models`
  - `POST /api/runtime/models/refresh`
  - `GET /api/runtime/tools`
  - `POST /api/runtime/tools/refresh`
  - `GET /api/runtime/graphs`
  - `POST /api/runtime/graphs/refresh`
- `runtime.service` 已具备模块级 control plane 选择能力：
  - runtime 开关开启且 v2 token 存在时，models / tools 自动走 `platform-api-v2`
  - 否则自动回退 legacy 的 `/_management/runtime/*`
- `runtime` 页面族现在也纳入 runtime 项目上下文：
  - `/workspace/runtime`
  - `/workspace/runtime/models`
  - `/workspace/runtime/tools`
- `graphs` 页面与 `assistant create` 的 graph 目录现在优先读取 `platform-api-v2` 的 runtime graph catalog
- `assistants` 列表页与详情页已经完成 `platform-api-v2` 联调：
  - 列表读取 `GET /api/projects/{project_id}/assistants`
  - 详情读取 `GET /api/assistants/{assistant_id}`
  - 删除通过 `DELETE /api/assistants/{assistant_id}` 受控执行
- `overview` 页面中的助手摘要也已经切到 runtime assistants 上下文：
  - 项目摘要与审计摘要也已经切到对应模块的 `v2` 控制面
- `users` 模块现在支持显式 `runtime` 模式：
  - `users` 模块已纳入 control plane 选择器，`runtime` 开关开启且 `v2` token 存在时，`/workspace/users*` 会优先使用 `platform-api-v2`
  - 用户列表读取 `GET /api/users`
  - 用户创建读取 `POST /api/users`
  - 用户详情读取 `GET /api/users/{user_id}`
  - 用户项目访问读取 `GET /api/users/{user_id}/projects`
  - 用户资料更新读取 `PATCH /api/users/{user_id}`
  - `ProjectMembersPage` 中的候选用户搜索也会复用这套 `users` 目录，避免 runtime 项目成员管理串回 legacy 用户接口
  - `UserDetailPage` 中最近审计记录继续复用独立的 `audit` 模块 scope，而不是把审计逻辑混回 `users` service
- `testcase` 模块现在支持显式 `runtime` 模式：
  - `testcase` 模块已纳入 control plane 选择器，`runtime` 开关开启且 `v2` token 存在时，`/workspace/testcase*` 会优先使用 `platform-api-v2`
  - testcase 总览读取 `GET /api/projects/{project_id}/testcase/overview`
  - 当前用户 testcase 角色读取 `GET /api/projects/{project_id}/testcase/role`
  - testcase 批次列表读取 `GET /api/projects/{project_id}/testcase/batches`
  - testcase 批次详情读取 `GET /api/projects/{project_id}/testcase/batches/{batch_id}`
  - testcase 用例列表读取 `GET /api/projects/{project_id}/testcase/cases`
  - testcase 用例详情读取 `GET /api/projects/{project_id}/testcase/cases/{case_id}`
  - testcase 用例创建 / 更新 / 删除分别读取 `POST /api/projects/{project_id}/testcase/cases`、`PATCH /api/projects/{project_id}/testcase/cases/{case_id}`、`DELETE /api/projects/{project_id}/testcase/cases/{case_id}`
  - testcase 用例导出读取 `GET /api/projects/{project_id}/testcase/cases/export`
  - testcase 文档列表读取 `GET /api/projects/{project_id}/testcase/documents`
  - testcase 文档详情读取 `GET /api/projects/{project_id}/testcase/documents/{document_id}`
  - testcase 文档导出读取 `GET /api/projects/{project_id}/testcase/documents/export`
  - testcase 文档关联读取 `GET /api/projects/{project_id}/testcase/documents/{document_id}/relations`
  - testcase 文档预览 / 下载分别读取 `GET /api/projects/{project_id}/testcase/documents/{document_id}/preview` 与 `GET /api/projects/{project_id}/testcase/documents/{document_id}/download`
  - `TestcaseCasesPage` 已在现有 Vue 壳层下补齐详情弹窗、人工补录 / 修订、来源文档选择和当前筛选结果导出
  - `TestcaseDocumentsPage` 已在现有 Vue 壳层下补齐当前筛选结果导出、runtime_meta / parsed_text / provenance 展示，以及同批次文档 / 用例上下文
  - `TestcaseGeneratePage` 的概览条和项目上下文改走 `testcase` scope，实际聊天执行仍继续复用 `runtime_gateway` 的 thread / run 链路
- `assistant create` 与 chat 运行参数已经不再读取 legacy runtime 目录，而是直接消费 `platform-api-v2` 的 runtime catalog
- 当前 graph 目录不再依赖 `runtime info -> graphs/search/count` 的能力探测链路
- 只有当 `platform-api-v2` 不可用或 graph catalog 请求失败时，前端才受控回退 legacy 的 `/_management/catalog/graphs`
- phase-2 当前新增的治理向前端 service 也已经有正式落点：
  - `src/services/runtime-gateway/workspace.service.ts`
  - `src/services/operations/operations.service.ts`
  - `src/services/system/platform-config.service.ts`

这意味着前端已经不再依赖“全站共用一个 projectId”的做法。

当前保护规则：

- 在 `projects / assistants / workspace context` 还没切到 `v2` 之前，`runtime_gateway` 的前端开关默认保持关闭
- 禁止直接把 chat 运行时请求切到 `v2`，却继续复用旧控制面的项目上下文

当前更新后的保护规则：

- `runtime` 页面族允许先完成“页面层与项目上下文解耦”
- 只有当 runtime 项目上下文可独立工作后，才允许打开 `VITE_PLATFORM_API_V2_RUNTIME_ENABLED=true`
- 如果 runtime 开关关闭，已迁页面会自动回退到 legacy 项目上下文，不允许因为过渡基座存在而把现有演示环境搞挂

原因：

- 这几块直接依赖 `runtime_gateway`
- 它们最能验证项目边界、SSE、thread 历史和 assistant 目标映射
- 对旧控制面的 testcase / announcement / admin 页面影响最小

### 第三阶段

- 大部分控制面模块都切到 `v2`
- 旧 `platform-api` 仅保留参考和回退用途

## 4. 前端服务层后续结构目标

推荐收敛成：

```text
src/services/platform/
  identity/
  projects/
  users/
  announcements/
  assistants/
  audit/
  testcase/
  runtime/
```

要求：

- service 按模块分包
- DTO 明确
- 页面不直接拼 URL
- 不把控制面切换逻辑泄漏到页面层
- client 层必须支持模块级 scope 选择：
  - `legacy`
  - `v2`
- 过渡期允许双 token 并存，但 token 管理必须集中在服务层

## 5. 切换验收标准

某个前端模块切到 `platform-api-v2` 时，至少满足：

- 页面功能可用
- 权限行为正确
- 审计行为正确
- 错误提示不退化
- 旧页面样式与交互不受影响
- 顶部项目切换不串到错误控制面
- 最近聊天目标、thread 打开、assistant 跳转等项目级行为不串项目

## 6. 当前结论

这次重构的前端策略不是“再做一个前端”，而是：

> 保持 `platform-web-vue` 为唯一正式宿主，通过服务层和模块契约逐步切换到新的控制面。

## 7. 下一批推荐切换

当前下一批最值得继续切到 `platform-api-v2` 的前端模块：

1. `testcase` 的导出 / 详情 / 写入链路
2. 需要补齐更多 runtime 管理能力的页面

原因：

- `identity / projects / users / announcements / audit / assistants` 这些管理面主链路已经能复用统一的 `v2` 控制面能力
- `overview` 摘要卡片与 `AnnouncementCenter` feed 现在已经和对应模块 scope 保持一致
- `testcase` 的页面读取链路已经切到 `v2`，剩余缺口主要集中在导出、详情和写入侧
- 下一轮可以把注意力从“控制面切换”继续转向“业务能力补齐”
