# Containerized Deployment Guide

文档类型：`Current Delivery Guide`

本文描述当前已经落地并完成基础运行验证的容器化交付面。

当前仓库已验证的交付面：

1. `apps/runtime-service` 单应用 Docker 部署
2. 整仓 Docker Compose，不带 Nginx
3. 整仓 Docker Compose，带 Nginx 单入口

当前正式本地默认 bring-up 事实仍以：

- [`docs/local-deployment-contract.yaml`](../docs/local-deployment-contract.yaml)
- [`docs/deployment-guide.md`](../docs/quickstart/deployment-guide.md)

为准。

首次建库脚本、空卷/已有卷差异、Alembic 初始化和后续迁移，统一遵循[数据库运维规范](../docs/guides/database-operations.md)。控制面关闭自动建表，Compose 在 API 启动前执行 Alembic。

## 1. 目标拓扑

### 1.1 单应用 `runtime-service`

目标拓扑：

- `runtime-service`
- `redis`
- `postgres`

当前约束：

- 镜像构建通过仓库内受管 Dockerfile 完成
- runtime 镜像 Python 基线固定为 `3.13`
- 官方基座镜像：`langchain/langgraph-api:3.13`
- 运行模式：Lite
  - 提供当前有效的 `LANGSMITH_API_KEY`
  - `LANGGRAPH_CLOUD_LICENSE_KEY` 留空
- 用户可直接运行 `docker compose build` / `docker compose up -d`
- 不要求本地安装 LangGraph CLI

当前已补齐：

- `apps/runtime-service/deploy/Dockerfile`
- `apps/runtime-service/deploy/docker-compose.runtime-service.yml`
- `apps/runtime-service/deploy/.env.runtime-service.example`
- `apps/runtime-service/.dockerignore`

当前已验证：

- `docker compose build`
- `docker compose up -d`
- `GET /info`
- `GET /internal/capabilities/models`
- `GET /internal/capabilities/tools`

### 1.2 整仓 Compose（无 Nginx）

目标服务：

- `runtime-service`
- `platform-api`
- `platform-web`
- `redis`
- `postgres`

当前约束：

- `runtime-service`、`platform-api` 共用一个 Postgres 实例
- 默认数据库名：
  - `runtime_service`
  - `platform_api`
- `platform-api` 使用 `redis_list`
- 共享 Postgres 默认只在容器网络内可达，不默认绑定宿主机 `5432`

当前已补齐：

- `deploy/docker-compose.stack.yml`
- `deploy/postgres/init/01-init-shared-databases.sh`
- `apps/platform-web/Dockerfile`
- 各 app `.dockerignore`

当前已验证：

- `platform-api` ready
- `platform-web` 可访问
- `runtime-service` `/info`、models、tools 可访问

no-nginx 前端约束：

- 浏览器不会经过同源 Nginx 代理访问 `platform-api`
- 因此前端构建参数必须指向：
  - `http://localhost:2142`
- 当前已把 no-nginx stack 的前端构建参数固定到：
  - `VITE_PLATFORM_API_URL_DIRECT`
  - `VITE_PLATFORM_API_RUNTIME_ENABLED`

### 1.3 整仓 Compose（带 Nginx）

在无 Nginx 栈之上增加：

- `nginx`

默认路由方向：

- `/` -> `platform-web`
- `/api/` -> `platform-api`
- `/_system/` -> `platform-api`

`runtime-service` 默认保持内部可达，不作为默认公网入口。

当前已补齐：

- `deploy/docker-compose.stack.nginx.yml`
- `deploy/nginx/default.conf`

当前已验证：

- `http://127.0.0.1/`
- `http://127.0.0.1/_system/probes/ready`
- `http://127.0.0.1/api/*` 已通过 Nginx 路由到 `platform-api`

nginx 前端约束：

- 浏览器通过同源入口访问
- 前端构建参数保持：
  - `VITE_PLATFORM_API_URL_INGRESS=/`
  - `VITE_PLATFORM_API_RUNTIME_ENABLED=true`

## 2. 外部依赖

当前 Compose 栈不部署 LightRAG，主服务也没有对应的部署配置入口。

## 3. 配置归属

### 3.1 `runtime-service`

长期配置归属：

- 运行时轻量开关：
  - `apps/runtime-service/.env`
- 模型组配置：
  - `apps/runtime-service/conf/settings.local.yaml`

容器化交付配置：

- `apps/runtime-service/deploy/.env.runtime-service.example`
- `deploy/.env.stack.example`

多模态附件解析模型默认值：

- `MULTIMODAL_PARSER_MODEL_ID`
- 当前容器化基线默认值：`gpt_5.4-ccr`
- 作用范围：所有未显式覆盖 `parser_model_id` 的 `MultimodalMiddleware`

runtime 认证 env：

- `PLATFORM_RUNTIME_DELEGATION_SECRET`：校验 platform-api 签发的短期运行 JWT
- `PLATFORM_RUNTIME_MANAGEMENT_API_KEY`：仅用于 catalog、assistant 等平台管理调用
- 两者都必须使用独立的至少 32 bytes 随机 secret，不能复用用户 access/refresh JWT secret

这些 env 只属于 service-private config，不进入公共 MCP registry。

### 3.2 `platform-api`

配置归属：

- `apps/platform-api/.env`
- `deploy/.env.stack.example`

runtime 上游认证配置：

- `PLATFORM_API_RUNTIME_DELEGATION_SECRET` 必须与 runtime-service 的 delegation secret 相同
- `PLATFORM_API_LANGGRAPH_UPSTREAM_API_KEY` 必须与 runtime-service 的 management API key 相同
- 正式 run/thread 请求使用短期 delegation JWT；平台管理调用使用 service API key

注意：


## 4. 更新与重建

更新流程统一收敛到：

- [`docs/runbooks/container-update-runbook.md`](../docs/runbooks/container-update-runbook.md)
