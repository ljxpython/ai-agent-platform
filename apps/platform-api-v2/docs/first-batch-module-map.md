# Platform API V2 首批模块迁移地图

这份文档解决一个很实际的问题：

> 旧 `platform-api` 里第一批最该迁的控制面能力，到 `platform-api-v2` 里分别落到哪里，顺序怎么排。

## 1. 当前优先级

推荐顺序：

1. `identity`
2. `projects`
3. `announcements`
4. `audit`
5. `assistants`
6. `runtime_gateway`

理由很简单：

- `identity` 决定认证上下文和前端接入稳定性
- `projects` 决定项目边界和后续几乎所有项目级资源
- `announcements` 业务独立，适合作为第一批完整样板模块
- `audit` 要尽早把真分页和事件标准立起来
- `assistants` 会直接影响前端 workspace、chat target 和 runtime 映射
- `runtime_gateway` 最复杂，必须等权限和项目边界先站稳

## 2. 旧接口到新模块的映射

### 2.1 `identity`

旧入口：

- `app/api/management/auth.py`

新落点：

- `app/modules/identity/domain/`
- `app/modules/identity/application/`
- `app/modules/identity/infra/`
- `app/modules/identity/presentation/`

当前已冻结的契约：

- `LoginCommand`
- `RefreshSessionCommand`
- `LogoutCommand`
- `ChangePasswordCommand`
- `AuthenticatedSession`

当前状态：

- 已完成第一版实现
- 已完成登录 / 刷新 / 退出 / 当前用户 / 改密烟测

### 2.2 `projects`

旧入口：

- `app/api/management/projects.py`
- `app/api/management/members.py`

新落点：

- `app/modules/projects/domain/`
- `app/modules/projects/application/`
- `app/modules/projects/infra/`
- `app/modules/projects/presentation/`

当前已冻结的契约：

- `ListProjectsQuery`
- `CreateProjectCommand`
- `UpsertProjectMemberCommand`
- `ProjectSummary`
- `ProjectMember`

当前状态：

- 已完成第一版实现
- 已完成项目创建 / 项目列表 / 成员列表 / 成员增删 / 项目级权限烟测

### 2.3 `announcements`

旧入口：

- `app/api/management/announcements.py`

新落点：

- `app/modules/announcements/domain/`
- `app/modules/announcements/application/`
- `app/modules/announcements/infra/`
- `app/modules/announcements/presentation/`

当前已冻结的契约：

- `ListAnnouncementsQuery`
- `CreateAnnouncementCommand`
- `UpdateAnnouncementCommand`
- `AnnouncementItem`

当前状态：

- 已完成第一版实现
- 已完成公告管理 / feed / 单条已读 / 全部已读 / global-project scope 权限烟测

### 2.4 `audit`

旧入口：

- `app/api/management/audit.py`
- `app/middleware/audit_log.py`

新落点：

- `app/modules/audit/domain/`
- `app/modules/audit/application/`
- `app/modules/audit/infra/`
- `app/modules/audit/presentation/`

当前已冻结的契约：

- `ListAuditEventsQuery`
- `AuditEvent`
- `AuditEventPage`

当前状态：

- 已完成第一版实现
- 已完成审计中间件、真分页查询、action/plane/target 标准落地
- 已完成临时 SQLite 烟测：
  - 平台审计查询权限校验
  - 项目审计查询权限校验
  - `project_id` 归档与 action 前缀筛选

### 2.5 `assistants`

旧入口：

- `app/api/management/assistants.py`
- `app/services/langgraph_sdk/assistants_service.py`
- `app/services/graph_parameter_schema.py`

新落点：

- `app/modules/assistants/domain/`
- `app/modules/assistants/application/`
- `app/modules/assistants/infra/`
- `app/modules/assistants/presentation/`
- `app/adapters/langgraph/`

当前已冻结的契约：

- `ListAssistantsQuery`
- `CreateAssistantCommand`
- `UpdateAssistantCommand`
- `AssistantItem`
- `AssistantPage`

当前状态：

- 已完成第一版实现
- 已完成项目级 assistant 列表、创建、详情、更新、删除、resync
- 已完成 assistant parameter schema provider 与 LangGraph upstream adapter
- 已完成临时 SQLite + stub upstream 烟测：
  - create / list / detail / update / resync / delete
  - schema fallback
  - assistant action 审计事件

### 2.6 `runtime_gateway`

旧入口：

- `app/api/langgraph/info.py`
- `app/api/langgraph/graphs.py`
- `app/api/langgraph/threads.py`
- `app/api/langgraph/runs.py`
- `app/services/langgraph_sdk/`

新落点：

- `app/modules/runtime_gateway/application/`
- `app/modules/runtime_gateway/presentation/`
- `app/adapters/langgraph/runtime_client.py`

当前已冻结的职责：

- 项目级运行时权限校验
- `thread` 项目边界校验
- assistant / graph 目标合法性校验
- LangGraph JSON / SSE 受控代理
- runtime plane 审计动作归类

当前状态：

- 已完成第一版实现
- 已完成 `/api/langgraph` 入口收口：
  - `info`
  - `graphs search/count`
  - `threads create/search/count/get/update/delete/copy/state/history`
  - `runs create/stream/wait/batch/cancel`
  - `thread runs stream/wait/list/update-state/delete`
- 已完成临时 SQLite + 本地 LangGraph dev 烟测：
  - admin 登录
  - 项目创建
  - runtime info 读取
  - thread 创建 / 搜索 / state 读取 / state 更新 / 删除
  - thread run SSE 流式返回
- 当前已确认一条边界结论：
  - `runs/wait` 若返回 `__error__`，是上游 graph / model 响应格式问题，不是控制面网关链路故障

## 3. 每个模块迁移时都要做什么

固定动作：

1. 先补 domain model
2. 再补 command / query DTO
3. 再补 repository / adapter interface
4. 再补 use case
5. 最后接 presentation router

禁止一上来直接从旧 router 复制业务逻辑。

## 4. 前端协同

前端 `apps/platform-web-vue` 后续切到 `v2` 时，也按这个模块顺序切：

- 先切登录与当前用户
- 再切项目与项目成员
- 再切公告
- 再切审计
- 再切 assistant 管理
- 最后切 runtime gateway / chat / threads

这样前端不会同时面对多套未稳定的契约。
