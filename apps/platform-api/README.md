# Platform API

`apps/platform-api` 是当前平台控制面后端。

它不再是“所有路径透明透传”的代理服务，而是一个同时承担以下职责的 FastAPI 应用：

- 管理面 API：`/_management/*`
- LangGraph SDK 风格运行时网关：`/api/langgraph/*`
- 平台数据库与自建认证/RBAC
- 运行时对象目录同步、项目边界治理、审计中间件

## 开发范式入口

跨应用统一开发方式先看根文档：

- `docs/development-paradigm.md`

对 `platform-api` 来说，最重要的执行原则是：

1. 只做平台治理、协议整形、权限和聚合，不承接智能体核心业务
2. 新接口上线前，先把上下游链路和边界写清楚
3. 当前层改动优先用真实登录、真实 token、真实下游服务验证
4. 能在本层闭环验证的问题，不要一上来依赖前端页面

如果你想理解“为什么现在要重构、后面应该收敛成什么样”，直接看：

- `docs/refactor-blueprint.md`

## 当前职责边界

### 负责

- 用户、项目、成员、审计等平台管理能力
- Assistant 管理与 LangGraph assistant 映射
- Runtime catalog 同步（graph / model / tool）
- LangGraph 线程、run、assistant、graph 查询的受控代理
- `x-project-id` 驱动的项目边界治理

### 不负责

- 浏览器 UI 渲染（由 `apps/platform-web` 负责）
- Graph 真正执行（由 `apps/runtime-service` 负责）
- 已退休的 catch-all transparent passthrough 路由

## 本应用的开发与验证要求

如果本轮只改 `platform-api`，推荐顺序是：

1. 先明确：
   - 这是管理面接口还是运行时代理接口
   - 它调用哪个下游
   - 哪一层负责权限
   - 返回口径由谁兜底
2. 先用真实登录拿 token
3. 再直接调用真实接口验证：
   - 路由是否正确
   - 权限是否正确
   - 下游错误是否正确透出
   - 下载或聚合结果是否正确
4. 最后再交给 `platform-web` 对接页面

关键约束：

- `platform-api` 不直接替代 `runtime-service` 做智能体开发
- `platform-api` 不直接替代 `interaction-data-service` 做结果域存储
- 只要涉及文件下载、导出、聚合列表，优先走真实接口联调，不要只看静态类型通过

## 当前公开路由面

- `/_management/*`：平台管理面
- `/api/langgraph/*`：LangGraph SDK 风格代理
- `/_proxy/health`：健康检查

其中 testcase 相关管理接口当前挂在：

- `/_management/projects/{project_id}/testcase/*`

当前应用装配以 `app/factory.py` 为准；历史 passthrough 路由已经 retired，不再作为当前接口基线。

## 5 分钟本地启动

1. 准备环境文件

```bash
cp .env.example .env
```

2. 准备 PostgreSQL，并把 `.env` 中的 `DATABASE_URL` 改成你的真实密码

3. 启动服务

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 2024 --reload
```

4. 检查健康状态

```bash
curl http://127.0.0.1:2024/_proxy/health
```

5. 如启用了数据库与 bootstrap admin，可使用 `.env` 中的管理员账号登录管理面

## 最重要的环境变量

- `LANGGRAPH_UPSTREAM_URL`
- `PLATFORM_DB_ENABLED`
- `PLATFORM_DB_AUTO_CREATE`
- `DATABASE_URL`
- `AUTH_REQUIRED`
- `LANGGRAPH_AUTH_REQUIRED`
- `LANGGRAPH_SCOPE_GUARD_ENABLED`
- `JWT_ACCESS_SECRET`
- `JWT_REFRESH_SECRET`
- `BOOTSTRAP_ADMIN_USERNAME`
- `BOOTSTRAP_ADMIN_PASSWORD`
- `API_DOCS_ENABLED`

完整说明以 `app/config.py` 和 `docs/local-dev.md` 为准。

## 推荐阅读顺序

1. `README.md`
2. `docs/README.md`
3. `docs/onboarding.md`
4. `docs/current-architecture.md`
5. `docs/local-dev.md`
6. `docs/testing.md`
7. `docs/refactor-blueprint.md`

如果你要改具体专题，再读：

- `docs/postgres-operations.md`
- `docs/error-playbook.md`
- `docs/assistant-management-design.md`
- `docs/runtime-object-catalog-design.md`
- `docs/testcase-management-api.md`
- `docs/refactor-blueprint.md`

## 当前代码入口

- `main.py`：启动壳层，只负责 `app = create_app()`
- `app/factory.py`：应用装配入口
- `app/bootstrap/lifespan.py`：启动/关闭、DB、bootstrap admin、共享 HTTP client
- `app/api/management/`：管理面路由
- `app/api/langgraph/`：LangGraph 网关路由
- `app/services/`：runtime catalog、LangGraph service、schema 生成等服务逻辑
- `app/db/`：模型、访问层、session、初始化

## 与其他应用的关系

```text
apps/platform-web
  -> /_management/*
  -> /api/langgraph/*
       apps/platform-api
         -> platform postgres
         -> apps/runtime-service (LangGraph upstream)
```

## 文档目录

- `docs/README.md`：文档导航
- `docs/onboarding.md`：开发者上手路径
- `docs/current-architecture.md`：当前真实架构与路由面
- `docs/local-dev.md`：本地开发与环境配置
- `docs/testing.md`：测试策略与命令
