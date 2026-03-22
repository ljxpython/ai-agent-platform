# 本地开发与联调说明

本文是给人快速浏览的本地联调摘要。

默认本地部署的唯一事实源是 `docs/local-deployment-contract.yaml`；如果本文与 contract 有冲突，以 contract 为准。

本文只保留人类排查时最常看的摘要信息，不再承担独立规范源的职责。

## 1. 固定端口与链路

以下内容对应 contract 中的默认四服务 profile，不包含按需服务 `interaction-data-service`。

- `apps/runtime-service`: `8123`
- `apps/platform-api`: `2024`
- `apps/platform-web`: `3000`
- `apps/runtime-web`: `3001`

当前默认链路：

- `platform-web` -> `platform-api` -> `runtime-service`
- `runtime-web` -> `runtime-service`

## 2. 配置文件口径

根目录不维护统一 `.env`，本地调试时只使用各应用自己的配置文件：

- `apps/platform-api/.env`
- `apps/platform-web/.env`
- `apps/runtime-web/.env`
- `apps/runtime-service/graph_src_v2/.env`
- `apps/runtime-service/graph_src_v2/conf/settings.yaml`

本地联调时，`runtime-web` 应直连 `http://localhost:8123`，不要沿用旧模板里的 `http://localhost:2024`。

## 3. 推荐启动顺序

1. 启动 `runtime-service`
2. 启动 `platform-api`
3. 启动 `platform-web`
4. 启动 `runtime-web`

## 4. 各应用启动命令

### 4.1 `apps/runtime-service`

```bash
cd apps/runtime-service
uv run langgraph dev --config graph_src_v2/langgraph.json --port 8123 --no-browser
```

### 4.2 `apps/platform-api`

```bash
cd apps/platform-api
uv run uvicorn main:app --host 0.0.0.0 --port 2024 --reload
```

### 4.3 `apps/platform-web`

```bash
cd apps/platform-web
pnpm dev
```

### 4.4 `apps/runtime-web`

```bash
cd apps/runtime-web
PORT=3001 pnpm dev
```

## 5. 最小健康检查

### 5.1 `runtime-service`

```bash
curl http://127.0.0.1:8123/info
curl http://127.0.0.1:8123/internal/capabilities/models
curl http://127.0.0.1:8123/internal/capabilities/tools
```

### 5.2 `platform-api`

```bash
curl http://127.0.0.1:2024/_proxy/health
curl http://127.0.0.1:2024/api/langgraph/info
```

### 5.3 页面访问

- `platform-web`: `http://127.0.0.1:3000`
- `runtime-web`: `http://127.0.0.1:3001`

如果 `platform-api` 的 `/api/langgraph/info` 返回 `200`，说明平台到 runtime 的主联调链路已经打通。

## 6. 根级快捷脚本

仓库根目录提供：

```bash
scripts/dev-up.sh
scripts/check-health.sh
scripts/dev-down.sh
```

首次排错更推荐手工逐个启动；脚本适合在口径已经确认无误后做快速联调。

## 7. 当前约定

- 不共享 `.venv`
- 不共享 Node 依赖
- 不共享根级 `.env`
- 先保证默认四服务启动集可独立运行，再处理统一工具链或更深层重构
