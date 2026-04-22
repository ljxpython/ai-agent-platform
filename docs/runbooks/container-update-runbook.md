# Container Update Runbook

文档类型：`Current Runbook`

本文定义当前容器化交付面的标准更新路径。

## 1. 适用范围

适用于：

- `apps/runtime-service` 单应用部署
- 整仓 compose（无 Nginx）
- 整仓 compose（有 Nginx）

## 2. 更新动作分类

### 2.1 代码或 Dockerfile 变更

单应用 `runtime-service`：

```bash
docker compose -f apps/runtime-service/deploy/docker-compose.runtime-service.yml --env-file apps/runtime-service/deploy/.env.runtime-service build
docker compose -f apps/runtime-service/deploy/docker-compose.runtime-service.yml --env-file apps/runtime-service/deploy/.env.runtime-service up -d
```

如果你修改了 `TEST_CASE_V2_*` 或 `INTERACTION_DATA_SERVICE_*` 这类 runtime 私有 env，也按这条重建 / 重启 `runtime-service`。

整仓 `platform-api` / worker 共镜像：

```bash
docker compose -f deploy/docker-compose.stack.yml --env-file deploy/.env.stack build platform-api
docker compose -f deploy/docker-compose.stack.yml --env-file deploy/.env.stack up -d --force-recreate platform-api platform-api-worker
```

说明：

- `platform-api-worker` 会执行 `runtime.*.refresh`、`knowledge.documents.*`、`testcase.*.export`、`assistant.resync`
- 这些异步 operation 依赖的 upstream env 必须和 `platform-api` 主容器保持一致
- 如果你改了 `PLATFORM_API_LANGGRAPH_*`、`PLATFORM_API_INTERACTION_DATA_SERVICE_*`、`PLATFORM_API_KNOWLEDGE_*`，要同时重建 / 重启 worker

### 2.2 仅 env / 配置变更

```bash
docker compose -f apps/runtime-service/deploy/docker-compose.runtime-service.yml --env-file apps/runtime-service/deploy/.env.runtime-service up -d --force-recreate runtime-service
docker compose -f deploy/docker-compose.stack.yml --env-file deploy/.env.stack up -d --force-recreate <service>
docker compose -f deploy/docker-compose.stack.nginx.yml --env-file deploy/.env.stack up -d --force-recreate <service>
```

### 2.3 数据库相关变更

共享 Postgres 初始化入口：

- `deploy/postgres/init/01-init-shared-databases.sh`

标准动作：

1. 先处理数据库更新 / 初始化脚本
2. 必要时清卷重建
3. 再重启受影响服务
4. 再做 health / smoke 验证

### 2.4 Nginx 配置变更

```bash
docker compose -f deploy/docker-compose.stack.nginx.yml --env-file deploy/.env.stack up -d --force-recreate nginx
```

## 3. 推荐验证顺序

### 3.1 单应用 `runtime-service`

```bash
docker compose -f apps/runtime-service/deploy/docker-compose.runtime-service.yml --env-file apps/runtime-service/deploy/.env.runtime-service config
curl http://127.0.0.1:8123/info
curl http://127.0.0.1:8123/internal/capabilities/models
curl http://127.0.0.1:8123/internal/capabilities/tools
```

### 3.2 整仓 no-nginx stack

```bash
docker compose -f deploy/docker-compose.stack.yml --env-file deploy/.env.stack config
curl http://127.0.0.1:8081/_service/health
curl http://127.0.0.1:2142/_system/probes/ready
curl http://127.0.0.1:8123/info
curl -I http://localhost:3000
```

### 3.3 整仓 nginx stack

```bash
docker compose -f deploy/docker-compose.stack.nginx.yml --env-file deploy/.env.stack config
curl -I http://127.0.0.1:80
curl http://127.0.0.1:80/_system/probes/ready
```

## 4. 回滚原则

标准思路：

1. 先停掉新版本服务
2. 回退到上一个可用镜像或代码版本
3. 如涉及 DB 风险，先恢复备份或回退 migration/init
4. 再重新启动服务
5. 重跑 health / smoke

## 5. 注意事项

- `runtime-service` Lite 模式依赖当前有效的 `LANGSMITH_API_KEY`
- 可选外部知识依赖如果运行在宿主机，不应在容器 env 中写成 `127.0.0.1`
- 可选 MCP 地址不应写成 `0.0.0.0`
- 对容器来说，推荐使用：
  - `host.docker.internal:<port>`
  - 或同网络 service name
