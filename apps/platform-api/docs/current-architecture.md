# 当前架构说明

这份文档只描述 `apps/platform-api` 当前真实实现，不描述已退休的 proxy/passthrough 历史方案。

## 1. 服务定位

当前 `platform-api` 是一个 FastAPI 平台后端，承担三类职责：

- 管理面 API（用户、项目、成员、审计、assistants、catalog、runtime policies/capabilities）
- LangGraph SDK 风格运行时网关
- 平台数据库、自建认证、项目边界治理

## 2. 应用入口与启动链路

### 2.1 入口

- `main.py`：仅负责 `app = create_app()`
- `app/factory.py`：真实应用装配入口

### 2.2 启动时发生的事

`app/factory.py` 当前会：

1. `load_dotenv()` 读取 `apps/platform-api` 目录下的 `.env`
2. `load_settings()` 构造 `Settings`
3. `setup_backend_logging(settings)` 初始化后端日志
4. 创建 FastAPI app
5. 挂载 `management_router`
6. 挂载 `langgraph_router`
7. 注册中间件：auth / audit / request_context
8. 注册 `/_proxy/health`

### 2.3 lifespan 行为

`app/bootstrap/lifespan.py` 当前负责：

- 创建共享 `httpx.AsyncClient`
- 按 `PLATFORM_DB_ENABLED` 决定是否初始化数据库
- 按 `PLATFORM_DB_AUTO_CREATE` 决定是否执行 `create_core_tables()`
- 确保 bootstrap admin 存在且具备 super admin 能力
- 在 shutdown 时关闭 `httpx` client 并释放 DB engine

## 3. 当前活跃路由面

### 3.1 管理面

前缀：`/_management`

当前挂载模块：

- `auth`
- `users`
- `projects`
- `members`
- `audit`
- `assistants`
- `catalog`
- `runtime_policies`
- `runtime_capabilities`
- `testcase`

### 3.2 LangGraph 网关

前缀：`/api/langgraph`

当前挂载模块：

- `info`
- `assistants`
- `graphs`
- `threads`
- `runs`

### 3.3 健康检查

- `/_proxy/health`

## 4. 已退休的旧路径

以下路径与模块不再作为当前架构的一部分：

- `/_runtime/{full_path:path}`
- `/{full_path:path}` catch-all passthrough
- `app/api/frontend_passthrough.py`
- `app/api/proxy/runtime_passthrough.py`

这些旧能力曾经存在，但现在已经 retired，不再作为新开发基线。

## 5. 当前请求链路

### 5.1 管理面请求

```text
caller
  -> auth_context middleware
  -> audit_log middleware
  -> request_context middleware
  -> /_management/* route
  -> db/session/access/service
  -> response
```

典型场景：

- 用户登录
- 项目/成员管理
- Assistant CRUD
- catalog refresh
- runtime policy 更新
- testcase 工作区读取/管理

### 5.2 LangGraph 网关请求

```text
caller
  -> auth_context middleware
  -> audit_log middleware
  -> request_context middleware
  -> /api/langgraph/* route
  -> langgraph_sdk client/service
  -> runtime upstream
  -> response
```

这里不是原始 HTTP 透明透传，而是：

- 路由显式定义
- 参数做必要白名单处理
- 按需做项目边界校验
- 按需做 metadata 注入

## 6. 数据与治理边界

### 6.1 平台数据库

核心模型位于 `app/db/models.py`，当前不止基础 RBAC 表，还包括：

- `Tenant`
- `User`
- `Project`
- `ProjectMember`
- `RefreshToken`
- `Agent`
- `AssistantProfile`
- `AuditLog`
- `RuntimeCatalogGraph`
- `RuntimeCatalogModel`
- `RuntimeCatalogTool`
- 项目级 graph/model/tool policy 表

### 6.2 项目边界

当前项目边界主要依赖：

- `x-project-id` 请求头
- `app/api/management/common.py` 的项目角色校验
- `app/services/langgraph_sdk/scope_guard.py` 的 assistant/thread project 归属校验

### 6.3 runtime catalog

`app/services/runtime_catalog_sync.py` 负责从 runtime 获取 graph/model/tool 等能力信息，并同步到平台库。

## 7. 当前最重要的 extension points

### 新增管理面能力

- 路由：`app/api/management/`
- 模型：`app/db/models.py`
- 数据访问：`app/db/access.py`
- 业务逻辑：`app/services/`

## 8. Testcase 管理面

当前新增了 `/_management/projects/{project_id}/testcase/*` 路由组。

职责：

- 为 `platform-web` 的 Testcase 工作区提供统一管理接口
- 承担项目级权限校验
- 通过本地共享 JSON HTTP client 调用 `interaction-data-service`

当前不承担：

- testcase 业务数据落库
- testcase 聚合统计自算

### 新增 LangGraph 代理能力

- 路由：`app/api/langgraph/`
- 上游交互：`app/services/langgraph_sdk/`

### 新增项目治理与 schema 能力

- `app/services/graph_parameter_schema.py`
- `app/services/runtime_catalog_sync.py`
