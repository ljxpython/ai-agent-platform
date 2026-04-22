# Containerized Deployment Guide

文档类型：`Current Delivery Guide`

本文描述当前已经落地并完成基础运行验证的容器化交付面。

当前仓库已验证的交付面：

1. `apps/runtime-service` 单应用 Docker 部署
2. 整仓 Docker Compose，不带 Nginx
3. 整仓 Docker Compose，带 Nginx 单入口

当前正式本地默认 bring-up 事实仍以：

- [`docs/local-deployment-contract.yaml`](/Users/bytedance/PycharmProjects/my_best/AITestLab/docs/local-deployment-contract.yaml)
- [`docs/deployment-guide.md`](/Users/bytedance/PycharmProjects/my_best/AITestLab/docs/deployment-guide.md)

为准。

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
- `platform-api-v2`
- `platform-api-v2-worker`
- `interaction-data-service`
- `platform-web-vue`
- `redis`
- `postgres`

当前约束：

- `runtime-service`、`platform-api-v2`、`interaction-data-service` 共用一个 Postgres 实例
- 默认数据库名：
  - `runtime_service`
  - `platform_api_v2`
  - `interaction_data_service`
- `platform-api-v2` 使用 `redis_list`
- `interaction-data-service` 启用 DB
- 共享 Postgres 默认只在容器网络内可达，不默认绑定宿主机 `5432`

当前已补齐：

- `deploy/docker-compose.stack.yml`
- `deploy/postgres/init/01-init-shared-databases.sh`
- `apps/interaction-data-service/Dockerfile`
- `apps/platform-web-vue/Dockerfile`
- 各 app `.dockerignore`

当前已验证：

- `interaction-data-service` healthy
- `platform-api-v2` ready
- `platform-api-v2-worker` running
- `platform-web-vue` 可访问
- `runtime-service` `/info`、models、tools 可访问

no-nginx 前端约束：

- 浏览器不会经过同源 Nginx 代理访问 `platform-api-v2`
- 因此前端构建参数必须指向：
  - `http://localhost:2142`
- 当前已把 no-nginx stack 的前端构建参数固定到：
  - `VITE_PLATFORM_API_URL_DIRECT`
  - `VITE_PLATFORM_API_V2_URL_DIRECT`

### 1.3 整仓 Compose（带 Nginx）

在无 Nginx 栈之上增加：

- `nginx`

默认路由方向：

- `/` -> `platform-web-vue`
- `/api/` -> `platform-api-v2`
- `/_system/` -> `platform-api-v2`

`runtime-service` 默认保持内部可达，不作为默认公网入口。

当前已补齐：

- `deploy/docker-compose.stack.nginx.yml`
- `deploy/nginx/default.conf`

当前已验证：

- `http://127.0.0.1/`
- `http://127.0.0.1/_system/probes/ready`
- `http://127.0.0.1/api/*` 已通过 Nginx 路由到 `platform-api-v2`

nginx 前端约束：

- 浏览器通过同源入口访问
- 前端构建参数保持：
  - `VITE_PLATFORM_API_URL_INGRESS=/`
  - `VITE_PLATFORM_API_V2_URL_INGRESS=/`

## 2. 外部依赖

### 2.1 LightRAG / RAG

LightRAG / RAG 在首版容器化中是外部依赖，不编排进 compose。

支持两条可选地址：

- 平台侧 RAG HTTP URL
  - 归 `platform-api-v2`
- runtime 私有 knowledge MCP SSE URL
  - 归 `runtime-service`

它们都是可选输入：

- 未提供时，不阻塞基础容器栈启动
- 但会影响 knowledge 相关能力是否可用

当前验证结果：

- `PLATFORM_API_V2_KNOWLEDGE_UPSTREAM_URL=http://host.docker.internal:9621`
  - 已验证容器内可达
- `TEST_CASE_V2_KNOWLEDGE_MCP_URL=http://host.docker.internal:8621/sse`
  - 已被 runtime 配置正确读取
  - 已验证容器内可达，返回 `text/event-stream`

如需在容器内启用这两条链路，建议改成：

- 宿主机服务：
  - `http://host.docker.internal:<port>`
- 同一容器网络内服务：
  - `http://<service-name>:<port>`

## 3. 配置归属

### 3.1 `runtime-service`

长期配置归属：

- 运行时轻量开关：
  - `apps/runtime-service/runtime_service/.env`
- 模型组配置：
  - `apps/runtime-service/runtime_service/conf/settings.local.yaml`

容器化交付配置：

- `apps/runtime-service/deploy/.env.runtime-service.example`
- `deploy/.env.stack.example`

多模态附件解析模型默认值：

- `MULTIMODAL_PARSER_MODEL_ID`
- 当前容器化基线默认值：`gpt_5.4-ccr`
- 作用范围：所有未显式覆盖 `parser_model_id` 的 `MultimodalMiddleware`

runtime 私有 knowledge MCP env：

- `TEST_CASE_V2_KNOWLEDGE_MCP_ENABLED`
- `TEST_CASE_V2_KNOWLEDGE_MCP_URL`
- `TEST_CASE_V2_KNOWLEDGE_TIMEOUT_SECONDS`
- `TEST_CASE_V2_KNOWLEDGE_SSE_READ_TIMEOUT_SECONDS`

runtime 持久化到 `interaction-data-service` 的 env：

- `INTERACTION_DATA_SERVICE_URL`
- `INTERACTION_DATA_SERVICE_TOKEN`
- `INTERACTION_DATA_SERVICE_TIMEOUT_SECONDS`

这些 env 只属于 service-private config，不进入公共 MCP registry。

### 3.2 `platform-api-v2`

配置归属：

- `apps/platform-api-v2/.env`
- `deploy/.env.stack.example`

平台侧 RAG HTTP 配置归 `platform-api-v2`：

- `PLATFORM_API_V2_KNOWLEDGE_UPSTREAM_URL`
- `PLATFORM_API_V2_KNOWLEDGE_UPSTREAM_API_KEY`
- `PLATFORM_API_V2_KNOWLEDGE_UPSTREAM_TIMEOUT_SECONDS`

注意：

- `platform-api-v2` 主容器和 `platform-api-v2-worker` 必须共享同一组 upstream 配置
- 只改主容器 env、不重建 worker，会导致页面主链路正常，但异步 operation 失败

### 3.3 `interaction-data-service`

配置归属：

- `apps/interaction-data-service/.env`
- `deploy/.env.stack.example`

容器化 stack 默认：

- `INTERACTION_DB_ENABLED=true`

## 4. 更新与重建

更新流程统一收敛到：

- [`docs/runbooks/container-update-runbook.md`](/Users/bytedance/PycharmProjects/my_best/AITestLab/docs/runbooks/container-update-runbook.md)

## 5. 跟踪方式

当前跟踪面：

- [PRD](/Users/bytedance/PycharmProjects/my_best/AITestLab/.omx/plans/prd-containerized-deployment-20260421.md)
- [Test Spec](/Users/bytedance/PycharmProjects/my_best/AITestLab/.omx/plans/test-spec-containerized-deployment-20260421.md)
- [TODO Checklist](/Users/bytedance/PycharmProjects/my_best/AITestLab/.omx/plans/todo-containerized-deployment-20260421.md)
