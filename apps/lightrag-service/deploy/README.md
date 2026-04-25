# LightRAG Service Optional Deployment

文档类型：`Current Delivery Guide`

这里描述的是 `apps/lightrag-service` 的**可选**部署面，不是仓库默认 stack 成员。

## 1. 主机直跑（推荐）

优先使用：

- `scripts/lightrag-service-up.sh`
- `scripts/lightrag-service-health.sh`
- `scripts/lightrag-service-down.sh`

这条 lane 更贴近当前 AITestLab 的默认集成方式：

- `platform-api` / `runtime-service` 如需容器访问该可选服务，可继续通过 `host.docker.internal`

## 2. app-local compose（可选）

准备：

```bash
cp apps/lightrag-service/deploy/.env.lightrag-service.example apps/lightrag-service/deploy/.env.lightrag-service
```

然后把 `apps/lightrag-service/.env.example` 中你实际需要的 LLM / embedding / auth 配置补到
`apps/lightrag-service/deploy/.env.lightrag-service` 里。

启动：

```bash
docker compose -f apps/lightrag-service/deploy/docker-compose.lightrag-service.yml \
  --env-file apps/lightrag-service/deploy/.env.lightrag-service \
  up -d
```

验证：

```bash
docker compose -f apps/lightrag-service/deploy/docker-compose.lightrag-service.yml \
  --env-file apps/lightrag-service/deploy/.env.lightrag-service \
  ps

curl http://127.0.0.1:9621/health
curl -I http://127.0.0.1:8621/sse
```

停止：

```bash
docker compose -f apps/lightrag-service/deploy/docker-compose.lightrag-service.yml \
  --env-file apps/lightrag-service/deploy/.env.lightrag-service \
  down
```

## 3. 与 root stack 的关系

- `deploy/docker-compose.stack.yml`
- `deploy/docker-compose.stack.nginx.yml`

默认都**不会**自动拉起 `lightrag-service`。

如果 root stack 需要接入它，应继续通过：

- `PLATFORM_API_KNOWLEDGE_UPSTREAM_URL`
- `TEST_CASE_V2_KNOWLEDGE_MCP_URL`

把地址指向：

- 宿主机直跑时：`host.docker.internal`
- 或你显式提供的其他可达地址
